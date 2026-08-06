"""AI/ML platform V2 facades — MLflow experiments, model registry, RAG pipeline."""

from __future__ import annotations

import hashlib
import math
import random
import re
from datetime import datetime, timezone
from typing import Any

_HEX = "0123456789abcdef"


def _hex(n: int = 8) -> str:
    return "".join(random.choice(_HEX) for _ in range(n))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# RAG engine
#
# The retrieval below is real: a fixed corpus is chunked, embedded into a
# deterministic hashed bag-of-words vector, and ranked by cosine similarity
# against the embedded query. It is deliberately NOT a learned embedding —
# labs must replay identically for grading, and pulling a real model in would
# add a multi-hundred-MB dependency for a training simulator. Hashing gives us
# the property that actually matters pedagogically: similarity responds to the
# query, so a bad chunk size / missing overlap / wrong top-k visibly degrades
# recall the way it does in a production pipeline.
# --------------------------------------------------------------------------

_EMBED_DIM = 128

# Hash collisions in a 128-bucket space give unrelated text a small positive
# cosine (measured ~0.07-0.10 on out-of-corpus queries against this corpus).
# Anything under this is noise, not recall.
_MIN_SIMILARITY = 0.15

# 40 words with 10 overlap splits the longer runbooks across a boundary, which
# is the point: it makes "no overlap → answer split across chunks" reproducible.
_DEFAULT_CHUNK_SIZE = 40
_DEFAULT_OVERLAP = 10

# Deliberately tiny: enough documents that top-k selection is non-trivial and
# several near-miss chunks compete, small enough to keep state payloads light.
_CORPUS: tuple[tuple[str, str], ...] = (
    (
        "policies/refund-policy.pdf",
        "Digital products are eligible for a refund within 14 days of purchase provided the "
        "product has not been downloaded. Downloaded digital goods are final sale except where "
        "local consumer law requires otherwise. Physical merchandise may be returned within 30 "
        "days in unopened condition. Refund requests are submitted through the billing portal "
        "and reviewed by the billing team before funds are released to the original payment "
        "method.",
    ),
    (
        "faq/purchase-questions.md",
        "How long does a refund take? For digital goods refunds are processed within 3 to 5 "
        "business days after approval. Card networks may add a further 2 to 3 days before the "
        "credit appears on a statement. Can I change the payment method for a refund? No, the "
        "refund always returns to the original payment method used at checkout.",
    ),
    (
        "terms-of-service.pdf",
        "Section 7.2 Licensing. Software licenses and downloadable digital content are subject "
        "to the digital refund policy and are non transferable between accounts. Section 7.3 "
        "Termination. Accounts terminated for abuse forfeit any remaining license term without "
        "refund.",
    ),
    (
        "runbooks/RB-112-service-restarts.md",
        "Symptom: the inference service crashes and restarts under high load, and clients see "
        "connection reset errors. Cause: the worker pool exhausts host memory when concurrent "
        "batch size exceeds the configured limit, and the OOM killer terminates the process. "
        "Mitigation: reduce max batch size, raise the memory limit, then restart the deployment "
        "and watch the error rate return to baseline.",
    ),
    (
        "runbooks/RB-204-gpu-throughput.md",
        "GPU utilization sits near 100 percent while tokens per second falls. Check for "
        "thermal throttling with nvidia-smi, confirm the KV cache is not spilling to host "
        "memory, and verify that requests are being batched rather than served one at a time. "
        "Lowering the maximum sequence length restores throughput when the cache is the "
        "bottleneck.",
    ),
    (
        "handbook/onboarding.md",
        "New engineers request platform access on day one, complete the security training in "
        "the first week, and are paired with an onboarding buddy for thirty days. Laptop and "
        "hardware requests go through the IT portal.",
    ),
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Words that appear in almost every chunk carry no retrieval signal; keeping
# them lets long generic chunks win on raw overlap alone.
_STOPWORDS = frozenset(
    """a an and are as at be been but by can do does for from has have how i if in into is it
    its may must no not of on or our that the their then there these they this to was were what
    when where which who will with within without you your""".split()
)


def _stem(token: str) -> str:
    """Crude suffix stripping so "restarting"/"restarts"/"restart" collide.

    Without this, hashed bag-of-words treats inflections as unrelated terms and
    a natural-language question ("why does the service keep restarting") misses
    a chunk that says "restarts" — an obviously wrong result for a lab. Not a
    real Porter stemmer; the corpus is small enough that the common English
    suffixes below cover it, and a full stemmer is not worth the dependency.
    """
    for suffix in ("ing", "ers", "er", "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _tokenize(text: str) -> list[str]:
    return [
        _stem(t)
        for t in _TOKEN_RE.findall(text.lower())
        if t not in _STOPWORDS and len(t) > 1
    ]


def _embed(tokens: list[str]) -> list[float]:
    """Deterministic hashed bag-of-words embedding, L2-normalised.

    blake2b rather than ``hash()`` — Python salts ``hash()`` per process, which
    would make two runs of the same lab retrieve different chunks.
    """
    vec = [0.0] * _EMBED_DIM
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "big") % _EMBED_DIM
        # Sign bit spreads collisions in both directions instead of always
        # inflating the bucket, which keeps unrelated terms from stacking.
        sign = 1.0 if digest[4] & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _chunk(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split into ``chunk_size``-word windows advancing by ``chunk_size - overlap``."""
    words = text.split()
    if not words:
        return []
    stride = max(1, chunk_size - overlap)
    chunks = []
    for start in range(0, len(words), stride):
        window = words[start:start + chunk_size]
        if not window:
            break
        chunks.append(" ".join(window))
        if start + chunk_size >= len(words):
            break
    return chunks


def build_index(chunk_size: int = _DEFAULT_CHUNK_SIZE, overlap: int = _DEFAULT_OVERLAP) -> list[dict[str, Any]]:
    """Chunk + embed the corpus. Cheap enough (~20 chunks) to rebuild per query,
    which is what lets a lab retune chunk_size/overlap and see recall move."""
    index: list[dict[str, Any]] = []
    for source, body in _CORPUS:
        for pos, chunk_text in enumerate(_chunk(body, chunk_size, overlap)):
            tokens = _tokenize(chunk_text)
            index.append({
                "source": f"{source} — chunk {pos + 1}",
                "text": chunk_text,
                "tokens": tokens,
                "vector": _embed(tokens),
            })
    return index


def rag_search(
    query: str,
    top_k: int = 3,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap: int = _DEFAULT_OVERLAP,
    rerank: bool = True,
) -> list[dict[str, Any]]:
    """Cosine top-k over the hashed index, optionally reranked by term overlap.

    The reranker is a lexical pass over the shortlist — the same
    cheap-retrieve/expensive-rerank shape as a production cross-encoder stage,
    so turning it off is a lab-visible quality regression rather than a no-op.
    """
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []
    query_vec = _embed(query_tokens)
    query_set = set(query_tokens)

    scored = []
    for entry in build_index(chunk_size, overlap):
        score = _cosine(query_vec, entry["vector"])
        # Floor, not just >0: a 128-bucket hash collides, so an unrelated query
        # still lands a small positive cosine. Without this an out-of-corpus
        # question would "retrieve" a confident-looking irrelevant chunk.
        if score < _MIN_SIMILARITY:
            continue
        scored.append((score, entry))
    if not scored:
        return []

    scored.sort(key=lambda pair: (-pair[0], pair[1]["source"]))
    shortlist = scored[: max(top_k * 3, top_k)]

    if rerank:
        def rerank_score(pair: tuple[float, dict[str, Any]]) -> float:
            score, entry = pair
            entry_set = set(entry["tokens"])
            if not entry_set:
                return score
            overlap_ratio = len(query_set & entry_set) / len(query_set)
            return 0.5 * score + 0.5 * overlap_ratio

        shortlist.sort(key=lambda pair: (-rerank_score(pair), pair[1]["source"]))
        # Re-apply the floor after blending: a chunk can clear the cosine floor
        # on hash collisions alone and then score ~0 on real term overlap. That
        # is a false positive the reranker just caught — drop it, don't cite it.
        final = [
            {"score": round(rerank_score(pair), 3), "source": pair[1]["source"], "text": pair[1]["text"]}
            for pair in shortlist[:top_k]
            if rerank_score(pair) >= _MIN_SIMILARITY
        ]
    else:
        final = [
            {"score": round(pair[0], 3), "source": pair[1]["source"], "text": pair[1]["text"]}
            for pair in shortlist[:top_k]
        ]
    return final


# Rough BPE proxy. Real tokenizers average ~0.75 tokens per whitespace word for
# English prose; punctuation and digits each cost extra. len//4 was wrong in the
# other direction on short prompts (it charges by character, so "hi" cost 1 and
# a 400-char prompt cost 100 regardless of content).
def count_tokens(text: str) -> int:
    if not text.strip():
        return 0
    total = 0
    for word in text.split():
        core = re.sub(r"[^\w]", "", word)
        punct = len(word) - len(core)
        if not core:
            total += max(1, punct)
            continue
        # Subword split: ~4 characters per piece, digits tokenise more finely.
        pieces = max(1, math.ceil(len(core) / 4)) if not core.isdigit() else max(1, math.ceil(len(core) / 2))
        total += pieces + punct
    return max(1, total)


def seed_v2() -> dict[str, Any]:
    return {
        "experiments": [
            {
                "id": "exp1", "name": "bert-text-classification",
                "created": "2024-06-20T10:00:00Z", "runs": 48, "tags": ["NLP", "BERT"],
            },
            {
                "id": "exp2", "name": "xgboost-churn-prediction",
                "created": "2024-06-18T10:00:00Z", "runs": 127, "tags": ["Tabular", "XGB"],
            },
        ],
        "ml_runs": [
            {
                "id": "run_abc123", "experiment_id": "exp1", "name": "run_abc123",
                "status": "FINISHED", "duration_s": 5027,
                "metrics": {"acc": 0.942, "f1": 0.938, "loss": 0.123},
                "params": {"lr": "2e-5", "bs": 32, "epochs": 5},
                "user": "labuser", "created": _now(),
            },
            {
                "id": "run_bcd456", "experiment_id": "exp1", "name": "run_bcd456",
                "status": "FINISHED", "duration_s": 2700,
                "metrics": {"acc": 0.931, "f1": 0.927, "loss": 0.142},
                "params": {"lr": "5e-5", "bs": 32, "epochs": 3},
                "user": "labuser", "created": _now(),
            },
        ],
        "model_registry": [
            {
                "name": "bert-text-classifier", "latest_version": 8, "stage": "Production",
                "run_id": "run_abc123", "updated": _now(),
            },
            {
                "name": "xgboost-churn", "latest_version": 15, "stage": "Staging",
                "run_id": "run_bcd456", "updated": _now(),
            },
        ],
        "knowledge_bases": [
            {
                "id": "kb-policies", "name": "policies-kb",
                "vector_store": "pgvector",
                # Counts describe the corpus that rag_search actually queries,
                # so the panel and the retrieval results can't disagree.
                "documents": len(_CORPUS),
                "chunks": len(build_index()),
                "embedding_model": f"hashed-bow-{_EMBED_DIM}d", "status": "ready",
                "last_indexed": _now(),
            },
        ],
        "rag_results": [],
        "rag_last_query": "",
        "rag_params": {
            "chunk_size": _DEFAULT_CHUNK_SIZE, "overlap": _DEFAULT_OVERLAP,
            "top_k": 3, "rerank": True,
        },
        "llm_playground": {
            "models": [
                "GPT-4o", "Claude 3.5 Sonnet", "Gemini 1.5 Pro",
                "Llama 3.1 70B", "Mistral Large", "Mixtral 8x22B",
            ],
            "last_prompt": "",
            "last_response": "",
            "token_usage": {"input": 0, "output": 0},
        },
    }


def ensure_v2(state: dict) -> None:
    for key, value in seed_v2().items():
        if key not in state or state.get(key) is None:
            state[key] = value if not isinstance(value, dict) else dict(value)


def _retrieval_params(payload: dict) -> dict[str, Any]:
    """Clamp caller-supplied retrieval knobs. Overlap must stay below chunk_size
    or the sliding window never advances."""
    chunk_size = max(10, min(400, int(payload.get("chunk_size") or _DEFAULT_CHUNK_SIZE)))
    overlap = max(0, min(chunk_size - 1, int(payload.get("overlap") or 0) if payload.get("overlap") is not None else _DEFAULT_OVERLAP))
    top_k = max(1, min(10, int(payload.get("top_k") or 3)))
    rerank = payload.get("rerank")
    return {
        "chunk_size": chunk_size,
        "overlap": overlap,
        "top_k": top_k,
        "rerank": True if rerank is None else bool(rerank),
    }


def apply_v2_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(state)

    if action == "create_experiment":
        name = (payload.get("name") or f"exp-{_hex(4)}").strip()
        if any(e.get("name") == name for e in state.get("experiments") or []):
            return {"ok": False, "error": f"Experiment '{name}' already exists"}
        row = {
            "id": f"exp-{_hex(4)}", "name": name, "created": _now(),
            "runs": 0, "tags": payload.get("tags") or [],
        }
        state.setdefault("experiments", []).append(row)
        return {"ok": True, "message": f"Created experiment {name}", "experiment": row}

    if action == "log_run":
        exp_id = payload.get("experiment_id") or ((state.get("experiments") or [{}])[0].get("id"))
        row = {
            "id": f"run_{_hex(6)}",
            "experiment_id": exp_id,
            "name": payload.get("name") or f"run_{_hex(4)}",
            "status": payload.get("status") or "FINISHED",
            "duration_s": int(payload.get("duration_s") or random.randint(600, 5000)),
            "metrics": payload.get("metrics") or {"acc": round(random.uniform(0.85, 0.96), 3), "loss": round(random.uniform(0.1, 0.3), 3)},
            "params": payload.get("params") or {"lr": "2e-5", "epochs": 3},
            "user": payload.get("user") or "labuser",
            "created": _now(),
        }
        state.setdefault("ml_runs", []).insert(0, row)
        for e in state.get("experiments") or []:
            if e.get("id") == exp_id:
                e["runs"] = int(e.get("runs") or 0) + 1
        return {"ok": True, "message": f"Logged run {row['id']}", "run": row}

    if action == "register_model":
        name = (payload.get("name") or f"model-{_hex(4)}").strip()
        existing = next((m for m in state.get("model_registry") or [] if m.get("name") == name), None)
        if existing:
            existing["latest_version"] = int(existing.get("latest_version") or 1) + 1
            existing["run_id"] = payload.get("run_id") or existing.get("run_id")
            existing["updated"] = _now()
            return {"ok": True, "message": f"Registered {name} v{existing['latest_version']}", "model": existing}
        row = {
            "name": name, "latest_version": 1,
            "stage": payload.get("stage") or "None",
            "run_id": payload.get("run_id") or "",
            "updated": _now(),
        }
        state.setdefault("model_registry", []).append(row)
        return {"ok": True, "message": f"Registered model {name}", "model": row}

    if action == "transition_model_stage":
        name = payload.get("name") or ""
        model = next((m for m in state.get("model_registry") or [] if m.get("name") == name), None)
        if not model:
            return {"ok": False, "error": "Model not found"}
        stage = payload.get("stage") or "Staging"
        if stage not in ("None", "Staging", "Production", "Archived"):
            return {"ok": False, "error": "Invalid stage"}
        model["stage"] = stage
        model["updated"] = _now()
        return {"ok": True, "message": f"{name} → {stage}", "model": model}

    if action == "create_knowledge_base":
        name = (payload.get("name") or f"kb-{_hex(4)}").strip()
        row = {
            "id": f"kb-{_hex(4)}", "name": name,
            "vector_store": payload.get("vector_store") or "pgvector",
            "documents": int(payload.get("documents") or 0),
            "chunks": int(payload.get("chunks") or 0),
            "embedding_model": payload.get("embedding_model") or "text-embedding-3-small",
            "status": "ready", "last_indexed": _now(),
        }
        state.setdefault("knowledge_bases", []).append(row)
        return {"ok": True, "message": f"Created knowledge base {name}", "knowledge_base": row}

    if action == "rag_retrieve":
        query = (payload.get("query") or "").strip()
        if not query:
            return {"ok": False, "error": "query required"}
        params = _retrieval_params(payload)
        results = rag_search(query, **params)
        state["rag_results"] = results
        state["rag_last_query"] = query
        state["rag_params"] = params
        if not results:
            # A real miss, not a fabricated fallback: every corpus term the
            # query hashed to scored zero. Labs need to see empty recall.
            return {
                "ok": True, "message": "No chunks above the similarity floor",
                "results": [], "query": query, "params": params,
            }
        return {
            "ok": True, "message": f"Retrieved {len(results)} chunks",
            "results": results, "query": query, "params": params,
        }

    if action == "llm_chat":
        prompt = (payload.get("prompt") or "").strip()
        model = payload.get("model") or "GPT-4o"
        if not prompt:
            return {"ok": False, "error": "prompt required"}
        # Ground on retrieval instead of echoing the prompt: the answer is
        # assembled from chunks the query actually matched, so an unanswerable
        # question produces a refusal rather than confident-sounding filler.
        params = _retrieval_params(payload)
        context = rag_search(prompt, **params)
        if context:
            cited = ", ".join(c["source"] for c in context)
            body = " ".join(c["text"] for c in context)
            # Keep the grounded excerpt bounded — the panel renders it inline.
            excerpt = body if len(body) <= 700 else body[:700].rsplit(" ", 1)[0] + "…"
            response = (
                f"[{model}] {excerpt}\n\nSources: {cited}"
            )
            grounded = True
        else:
            response = (
                f"[{model}] The knowledge base has no chunk matching that question, "
                "so there is nothing to ground an answer on. Index a relevant document "
                "or rephrase the query."
            )
            grounded = False
        usage = {
            "input": count_tokens(prompt) + sum(count_tokens(c["text"]) for c in context),
            "output": count_tokens(response),
        }
        playground = state.setdefault("llm_playground", {})
        playground["last_prompt"] = prompt
        playground["last_response"] = response
        playground["last_model"] = model
        playground["last_sources"] = [c["source"] for c in context]
        playground["last_grounded"] = grounded
        playground["token_usage"] = usage
        return {
            "ok": True, "message": "Response generated", "response": response,
            "usage": usage, "sources": playground["last_sources"], "grounded": grounded,
        }

    return None

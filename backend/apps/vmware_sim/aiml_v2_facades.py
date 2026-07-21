"""AI/ML platform V2 facades — MLflow experiments, model registry, RAG pipeline."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

_HEX = "0123456789abcdef"


def _hex(n: int = 8) -> str:
    return "".join(random.choice(_HEX) for _ in range(n))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
                "vector_store": "pgvector", "documents": 42, "chunks": 1280,
                "embedding_model": "text-embedding-3-small", "status": "ready",
                "last_indexed": _now(),
            },
        ],
        "rag_results": [],
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
        results = [
            {
                "score": round(0.93 - i * 0.04, 3),
                "source": src,
                "text": text,
            }
            for i, (src, text) in enumerate([
                ("policies/refund-policy.pdf — Page 3", "Digital products are eligible for refund within 14 days of purchase if not downloaded."),
                ("faq/purchase-questions.md", "For digital goods, refunds are processed within 3-5 business days."),
                ("terms-of-service.pdf — §7.2", "Software licenses and digital content are subject to the digital refund policy."),
            ])
        ]
        if "crash" in query.lower() or "error" in query.lower():
            results[0]["text"] = "Known issue: high load can cause process restarts — see runbook RB-112."
        state["rag_results"] = results
        return {"ok": True, "message": f"Retrieved {len(results)} chunks", "results": results, "query": query}

    if action == "llm_chat":
        prompt = (payload.get("prompt") or "").strip()
        model = payload.get("model") or "GPT-4o"
        if not prompt:
            return {"ok": False, "error": "prompt required"}
        response = (
            f"[{model}] Based on the lab knowledge base: "
            f"{prompt[:120]}{'…' if len(prompt) > 120 else ''} "
            "— here is a concise, grounded answer for training purposes."
        )
        playground = state.setdefault("llm_playground", {})
        playground["last_prompt"] = prompt
        playground["last_response"] = response
        playground["last_model"] = model
        playground["token_usage"] = {
            "input": max(1, len(prompt) // 4),
            "output": max(1, len(response) // 4),
        }
        return {"ok": True, "message": "Response generated", "response": response, "usage": playground["token_usage"]}

    return None

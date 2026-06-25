"""Typed answer understanding — spaCy + rules, 100% offline."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from apps.interviews.services.conversation.normalize import normalize_transcript

_HEDGING = re.compile(
    r"\b(i think|maybe|probably|sort of|kind of|i guess|not sure|i'm not sure|"
    r"i don't know|idk|no idea)\b",
    re.I,
)
_NUMBERS = re.compile(
    r"\b(\d+(?:\.\d+)?\s*(?:%|ms|s|sec|seconds|minutes|hours|gb|tb|mb|rps|qps|pods?|nodes?|users?))\b",
    re.I,
)
_COMMANDS = re.compile(
    r"\b(kubectl|docker|systemctl|journalctl|grep|curl|terraform|ansible|helm|"
    r"nginx|prometheus|grafana)\b[^\n]{0,40}",
    re.I,
)
_IDK = re.compile(r"\b(i don'?t know|not sure|no idea|can'?t recall|don'?t remember|idk)\b", re.I)
_CANDIDATE_Q = re.compile(
    r"^(what|why|how|when|where|which|who|can you|could you|would you|do you|is there|are there)\b",
    re.I,
)

_STAR_MARKERS = {
    "situation": re.compile(r"\b(when|during|at\s+\w+|incident|outage|problem|issue)\b", re.I),
    "task": re.compile(r"\b(responsible|task|goal|needed to|had to|assigned)\b", re.I),
    "action": re.compile(r"\b(i\s+(did|ran|fixed|deployed|rolled|changed|wrote|built)|we\s+(did|ran))\b", re.I),
    "result": re.compile(r"\b(result|outcome|reduced|improved|fixed|zero downtime|as a result|cut)\b", re.I),
}

_NLP = None


def _get_nlp():
    global _NLP
    if _NLP is False:
        return None
    if _NLP is not None:
        return _NLP
    try:
        import spacy  # noqa: PLC0415

        _NLP = spacy.load("en_core_web_sm")
    except Exception:  # noqa: BLE001
        _NLP = False
    return _NLP if _NLP is not False else None


def _tfidf_relevance(answer: str, question: str, reference: str = "") -> float:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415
        from sklearn.metrics.pairwise import cosine_similarity  # noqa: PLC0415

        docs = [question or "interview", answer or "answer"]
        if reference:
            docs.append(reference)
        vec = TfidfVectorizer(stop_words="english", max_features=500)
        mat = vec.fit_transform(docs)
        sim = cosine_similarity(mat[0:1], mat[1:2])[0][0]
        return float(max(0.0, min(1.0, sim)))
    except Exception:  # noqa: BLE001
        q_tokens = set((question or "").lower().split())
        a_tokens = set((answer or "").lower().split())
        if not q_tokens:
            return 0.5
        return len(q_tokens & a_tokens) / max(len(q_tokens), 1)


@dataclass
class AnswerAnalysis:
    raw_text: str
    normalized_text: str
    entities: list[str] = field(default_factory=list)
    noun_phrases: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    numbers: list[str] = field(default_factory=list)
    star: dict[str, bool] = field(default_factory=dict)
    relevance: float = 0.0
    depth: float = 0.0
    vagueness: float = 0.0
    confidence: float = 0.0
    sentiment_stress: float = 0.0
    answered_question: bool = True
    is_idk: bool = False
    is_candidate_question: bool = False
    hedging_count: int = 0
    word_count: int = 0


def analyze_answer(
    *,
    answer_text: str,
    question_text: str = "",
    reference_text: str = "",
) -> AnswerAnalysis:
    raw = (answer_text or "").strip()
    normalized = normalize_transcript(raw)
    low = normalized.lower()
    words = normalized.split()
    wc = len(words)

    entities: list[str] = []
    noun_phrases: list[str] = []
    actions: list[str] = []

    nlp = _get_nlp()
    if nlp and normalized:
        doc = nlp(normalized[:4000])
        for ent in doc.ents:
            if ent.label_ in ("ORG", "PRODUCT", "GPE", "PERSON", "WORK_OF_ART"):
                entities.append(ent.text.strip())
        for chunk in doc.noun_chunks:
            phrase = chunk.text.strip()
            if 3 <= len(phrase) <= 60:
                noun_phrases.append(phrase)
        for tok in doc:
            if tok.pos_ == "VERB" and tok.lemma_ not in ("be", "have", "do"):
                actions.append(tok.text)

    numbers = _NUMBERS.findall(normalized)
    evidence = _COMMANDS.findall(normalized)
    star = {k: bool(pat.search(normalized)) for k, pat in _STAR_MARKERS.items()}

    relevance = _tfidf_relevance(normalized, question_text, reference_text)
    hedges = len(_HEDGING.findall(low))
    vagueness = min(1.0, hedges / max(wc / 8, 1))
    depth = min(1.0, (len(evidence) * 0.15) + (len(numbers) * 0.12) + min(wc / 80, 0.5))
    confidence = max(0.0, 1.0 - vagueness - (0.1 if wc < 12 else 0))
    stress = min(1.0, hedges * 0.2 + (0.3 if wc < 8 else 0))

    is_idk = bool(_IDK.search(low)) and wc < 30
    is_cq = bool(_CANDIDATE_Q.search(low.strip())) and low.strip().endswith("?")
    answered = relevance >= 0.12 or wc >= 15 or bool(evidence)

    return AnswerAnalysis(
        raw_text=raw,
        normalized_text=normalized,
        entities=list(dict.fromkeys(entities))[:12],
        noun_phrases=list(dict.fromkeys(noun_phrases))[:10],
        actions=actions[:8],
        evidence=evidence[:8],
        numbers=numbers[:8],
        star=star,
        relevance=round(relevance, 3),
        depth=round(depth, 3),
        vagueness=round(vagueness, 3),
        confidence=round(confidence, 3),
        sentiment_stress=round(stress, 3),
        answered_question=answered,
        is_idk=is_idk,
        is_candidate_question=is_cq,
        hedging_count=hedges,
        word_count=wc,
    )

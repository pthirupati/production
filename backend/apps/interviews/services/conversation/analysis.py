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

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.\-/]*")

_STOPWORDS = frozenset("""
a an the and or but if then than that this these those there here of in on at to for from by with
without about into over under again further is are was were be been being have has had having do
does did doing i you he she it we they me him her them my your his its our their what which who whom
whose when where why how all any both each few more most other some such no nor not only own same so
too very can will just should now would could may might must shall as up down out off
""".split())

# Domain vocabulary an on-topic technical answer uses even when it paraphrases
# the question rather than echoing it. Presence here is what separates "developed
# a real answer" from "repeated the prompt back".
_DOMAIN_TERMS = frozenset("""
kubectl kubernetes k8s pod pods container containers docker image registry namespace deployment
replica replicaset node nodes cluster ingress service configmap secret secrets volume mount probe
liveness readiness oomkilled crashloopbackoff exit restart rollout helm yaml manifest
log logs stdout stderr journalctl systemd systemctl process pid kernel cgroup memory cpu disk
limit limits request requests quota throttle throttling latency timeout retry backoff
nginx proxy upstream tls ssl certificate port socket dns resolve route firewall iptables
prometheus grafana alert alerting metric metrics dashboard slo sli trace tracing span
terraform ansible playbook pipeline jenkins argocd rollback deploy canary
postgresql mysql redis mongodb query index schema migration transaction lock replication
aws ec2 s3 iam vpc lambda eks rds cloudwatch region zone
debug reproduce root cause diagnose inspect verify check validate isolate bisect
error exception failure crash stack trace exitcode code status event events
""".split())

# Vague prose that survives stopword filtering but carries no information. Without
# this, a wall of "stakeholder synergy paradigm" reads as novel content.
_EMPTY_TERMS = frozenset("""
really honestly basically literally actually thing things stuff lot lots good bad great nice
important fundamental whole picture overall generally usually kind sort maybe probably think
believe feel guess opinion communication communicate listener listening people person everyone
team teamwork together collaborate collaboration stakeholder stakeholders synergy paradigm
leverage leveraging scalable resilient robust seamless holistic strategic innovative disrupt
best practices practice approach mindset culture ownership drive driving impact
""".split())

# Concrete grounding: quantities and first-person actions. These let a strong
# behavioral answer earn substance without any infrastructure vocabulary.
_SPECIFIC_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|ms|s|sec|seconds?|minutes?|hours?|days?|gb|tb|mb|k|x)?\b", re.I
)
_ACTION_RE = re.compile(
    r"\b(i|we)\s+(ran|set|fixed|rolled|called|asked|wrote|built|changed|escalated|paged|"
    r"agreed|decided|proposed|scheduled|reviewed|deployed|reverted|added|removed|migrated)\b",
    re.I,
)


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


def _content_tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS and len(t) > 1]


def _relevance(answer: str, question: str, reference: str = "") -> float:
    """How much the answer actually ADDRESSES the question, on 0..1.

    This replaced a TfidfVectorizer cosine fit over a 2-document corpus
    ([question, answer]). With n=2 the IDF term is degenerate — every token
    appears in 1 or 2 documents, so the weights collapse to a near-constant and
    the "cosine similarity" reduced to raw shared-token overlap. Measured on the
    CrashLoopBackOff question, that scored a 100-word genuine paraphrase at 3 and
    a bare 8-word keyword dump ("kubernetes pod stuck crashloopbackoff debug ...")
    at 100 — exactly backwards, while carrying 25-30% of the composite score.

    The replacement scores echo (repeating the question back) at only 0.35 weight
    and requires SUBSTANCE for the rest: novel domain vocabulary, overlap with a
    reference answer, or concrete grounding (numbers, "I/we <did>" actions) so
    behavioral answers that use no infra terms are not zeroed out. Generic filler
    is excluded explicitly, so a wall of buzzwords cannot buy relevance.
    """
    q_tokens = _content_tokens(question)
    a_tokens = _content_tokens(answer)
    if not a_tokens:
        return 0.0
    q_set, a_set = set(q_tokens), set(a_tokens)
    if not q_set:
        return 0.5

    echo = len(q_set & a_set) / len(q_set)
    novel = a_set - q_set
    ref_set = set(_content_tokens(reference))

    novel_domain = {t for t in novel if t in _DOMAIN_TERMS} | (novel & ref_set)
    novel_other = {t for t in novel if t not in _DOMAIN_TERMS and t not in _EMPTY_TERMS and t not in ref_set}
    grounded = len(_SPECIFIC_RE.findall(answer)) + len(_ACTION_RE.findall(answer))

    substance = min(1.0, (len(novel_domain) + grounded) / 8 + min(len(novel_other), 12) / 40)
    score = 0.35 * echo + 0.65 * substance
    if ref_set:
        score = 0.65 * score + 0.35 * (len(ref_set & a_set) / len(ref_set))
    return max(0.0, min(1.0, score))


# Kept as an alias: callers/tests referenced this name when the implementation
# was TF-IDF based. The scoring contract (0..1 relevance) is unchanged.
_tfidf_relevance = _relevance


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

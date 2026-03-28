import re
from collections import Counter


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "between",
    "by",
    "can",
    "could",
    "does",
    "for",
    "from",
    "has",
    "have",
    "how",
    "in",
    "into",
    "is",
    "it",
    "its",
    "like",
    "may",
    "might",
    "more",
    "most",
    "of",
    "on",
    "or",
    "our",
    "over",
    "should",
    "show",
    "than",
    "that",
    "the",
    "their",
    "this",
    "to",
    "under",
    "use",
    "uses",
    "using",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "why",
    "with",
    "you",
    "your",
}


_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)?")


_CONCEPT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?:structure|anatomy|parts|components|architecture)\s+of\s+(.{3,90})", re.I), "diagram"),
    (re.compile(r"(?:process|steps|procedure|workflow|algorithm)\s+of\s+(.{3,90})", re.I), "flowchart"),
    (re.compile(r"(?:life\s+cycle|cycle)\s+of\s+(.{3,90})", re.I), "cycle_diagram"),
    (re.compile(r"(?:types|classification|taxonomy|levels|hierarchy)\s+of\s+(.{3,90})", re.I), "hierarchy_tree"),
    (re.compile(r"(?:compare|difference)\s+between\s+(.{2,60})\s+(?:and|vs\.?|versus)\s+(.{2,60})", re.I), "comparison_table"),
    (re.compile(r"(.{2,60})\s+(?:vs\.?|versus)\s+(.{2,60})", re.I), "comparison_table"),
]


def _tokens(text: str) -> list[str]:
    src = (text or "").lower()
    out: list[str] = []
    for m in _TOKEN_RE.finditer(src):
        t = m.group(0)
        if len(t) <= 2:
            continue
        if t in _STOPWORDS:
            continue
        if t.isdigit():
            continue
        out.append(t)
    return out


def _limit_words(words: list[str], min_words: int = 2, max_words: int = 5) -> list[str]:
    w = [x for x in (words or []) if x]
    if len(w) > max_words:
        w = w[:max_words]
    if len(w) < min_words:
        w = (w + ["concept", "overview"])[:min_words]
    return w


def _extract_concept_words(raw_text: str) -> tuple[list[str], str | None]:
    head = " ".join((raw_text or "").strip().split())[:400]
    for pat, suggested_visual in _CONCEPT_PATTERNS:
        m = pat.search(head)
        if not m:
            continue
        if suggested_visual == "comparison_table" and m.lastindex and m.lastindex >= 2:
            left = _tokens(m.group(1))[:3]
            right = _tokens(m.group(2))[:3]
            words = _limit_words((left[:2] or left) + ["vs"] + (right[:2] or right), min_words=2, max_words=5)
            return words, suggested_visual
        phrase = m.group(1)
        phrase = re.split(r"[.;\n\r]", phrase, maxsplit=1)[0]
        words = _limit_words(_tokens(phrase), min_words=2, max_words=5)
        return words, suggested_visual

    toks = _tokens(head)
    if not toks:
        return ["key", "concept"], None

    counts = Counter(toks)
    first_idx: dict[str, int] = {}
    for idx, t in enumerate(toks):
        if t not in first_idx:
            first_idx[t] = idx

    ranked = sorted(counts.keys(), key=lambda t: (-counts[t], first_idx.get(t, 10**9)))
    chosen = set(ranked[:8])
    ordered = [t for t in toks if t in chosen]

    uniq: list[str] = []
    for t in ordered:
        if t not in uniq:
            uniq.append(t)
        if len(uniq) >= 5:
            break
    return _limit_words(uniq, min_words=2, max_words=5), None


def _infer_visual_type(raw_text: str, suggested: str | None, concept_words: list[str]) -> str:
    if suggested:
        return suggested

    src = (raw_text or "").lower()

    if any(k in src for k in [" vs ", " versus ", "difference", "compare", "comparison"]):
        return "comparison_table"
    if any(k in src for k in ["cycle", "life cycle", "loop", "feedback loop"]):
        return "cycle_diagram"
    if any(k in src for k in ["steps", "procedure", "workflow", "pipeline", "algorithm", "process"]):
        return "flowchart"
    if any(k in src for k in ["types of", "classification", "taxonomy", "hierarchy", "levels", "categories"]):
        return "hierarchy_tree"

    has_numbers = bool(re.search(r"\b\d+(?:\.\d+)?%?\b", src))
    if has_numbers or any(k in src for k in ["trend", "increase", "decrease", "distribution", "correlation", "graph", "chart"]):
        return "graph/chart"

    # Prioritize diagram for anatomical/structural content to get real images
    if any(k in src for k in ["structure", "anatomy", "parts", "components", "architecture", "labeled", "system", "body", "organ", "blood", "heart", "cells", "tissue", "bone"]):
        return "diagram"

    if any(k in src for k in ["relationship", "relations", "network"]):
        return "diagram"  # Use diagram instead of concept_map for better images

    # Default to diagram for real images instead of abstract concept maps
    return "diagram"


def generate_visual_search_payload(raw_text: str) -> dict[str, str]:
    """
    Enhancement layer for image retrieval query generation.

    Input: raw extracted text.
    Output: strict JSON-compatible dict:
      {"search_query": "...", "visual_type": "...", "concept": "..."}

    Rules:
    - concept: 2–5 words
    - visual_type: one of the supported types
    - search_query: "<visual_type> of <concept> simple labeled" (<= 10 words)
    """
    concept_words, suggested = _extract_concept_words(raw_text or "")
    visual_type = _infer_visual_type(raw_text or "", suggested, concept_words)
    concept = " ".join(concept_words).strip()

    # Build query with a strict 10-word cap.
    words = [visual_type, "of"] + concept.split() + ["simple", "labeled"]
    if len(words) > 10:
        # Keep the template shape; trim concept words.
        keep_concept = max(1, 10 - 4)  # visual_type + of + simple + labeled
        concept_trimmed = concept.split()[:keep_concept]
        concept = " ".join(concept_trimmed).strip()
        words = [visual_type, "of"] + concept.split() + ["simple", "labeled"]
    search_query = " ".join(words).strip()

    return {"search_query": search_query, "visual_type": visual_type, "concept": concept}


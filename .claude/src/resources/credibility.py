"""Deterministic credibility scoring for a web resource.

The user's hard requirement is that learning material be **factual, verifiable,
and widely-used**. This module assigns each candidate URL a credibility score in
``[0, 1]`` from a *registry tier prior* (see ``registries.py``) nudged by a few
cheap, observable signals. It is intentionally a deterministic **prior** — the
`/web` skill escalates borderline scores (near the keep threshold) to a cheap LLM
judgment for the final keep/drop decision, recording the rationale in frontmatter.

Backend is swappable in the same spirit as the retrieval index's
``BM25Index``/``MilvusIndex``: ``score()`` is the heuristic backend; a future
``llm_score()`` could replace it without changing callers.
"""

from __future__ import annotations

from urllib.parse import urlparse

from .registries import tier_for

# Base prior per registry tier.
TIER_BASE = {
    "canonical": 0.90,
    "reputable": 0.72,
    "unknown": 0.45,
    "blocked": 0.0,
}

# Candidates at/above this score are kept by default; below it the /web skill
# either drops them or escalates to an LLM judgment.
KEEP_THRESHOLD = 0.60


def _host(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def _is_https(url: str) -> bool:
    try:
        return urlparse(url).scheme == "https"
    except ValueError:
        return False


def score(
    url: str,
    *,
    has_references: bool | None = None,
    author: bool | str | None = None,
    year: int | None = None,
    now_year: int | None = None,
) -> dict:
    """Score a URL's credibility.

    Returns ``{"url", "score", "tier", "rationale"}`` where ``score`` is clamped
    to ``[0, 1]``. The optional signals (gathered by the skill after fetching the
    page) refine the registry prior:

    - ``has_references`` — the page cites sources / has a references section.
    - ``author`` — a named, identifiable author/byline is present.
    - ``year`` / ``now_year`` — publication recency (stale content decays a little).
    """
    host = _host(url)
    tier = tier_for(host)
    base = TIER_BASE.get(tier, TIER_BASE["unknown"])
    reasons: list[str] = [f"{tier} domain ({host or 'unknown host'})"]

    if tier == "blocked":
        return {"url": url, "score": 0.0, "tier": tier,
                "rationale": "blocked domain — never ingested"}

    adj = 0.0
    if not _is_https(url):
        adj -= 0.10
        reasons.append("not https (-0.10)")
    if has_references:
        adj += 0.10
        reasons.append("cites references (+0.10)")
    if author:
        adj += 0.05
        reasons.append("identifiable author (+0.05)")
    if year is not None and now_year is not None:
        age = now_year - year
        if age <= 6:
            adj += 0.05
            reasons.append(f"recent ({year}, +0.05)")
        elif age >= 12:
            adj -= 0.05
            reasons.append(f"dated ({year}, -0.05)")

    final = max(0.0, min(1.0, base + adj))
    return {
        "url": url,
        "score": round(final, 3),
        "tier": tier,
        "rationale": "; ".join(reasons),
    }

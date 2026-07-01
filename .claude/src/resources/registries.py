"""Curated registry of canonical / reputable learning-resource domains.

The credibility scorer's deterministic prior is a *tier* per domain. We keep the
map small and obvious — it's meant to be extended by hand as you discover sources
you trust. Tiers:

- ``"canonical"`` — encyclopedic or first-party authoritative docs (Wikipedia,
  official language/framework docs, standards bodies, peer-reviewed venues).
- ``"reputable"`` — widely-recommended expert blogs, course sites, and org blogs.
- ``"blocked"`` — known low-trust / content-farm domains we never ingest.
- anything else falls through to ``"unknown"`` (a cautious middle prior).

Also holds ``AWESOME_HUBS`` — a few canonical "awesome-list"/landing hubs used by
the `/web` skill as *discovery seeds* (not for scoring).
"""

from __future__ import annotations

# --- Tier 1: canonical (encyclopedic / first-party authoritative) -------------
CANONICAL_EXACT = {
    "distill.pub",
    "plato.stanford.edu",          # Stanford Encyclopedia of Philosophy
    "arxiv.org",
    "openreview.net",
    "jmlr.org",
    "dl.acm.org",
    "www.nature.com",
    "www.science.org",
    "python.org",
    "docs.python.org",
    "pytorch.org",
    "www.tensorflow.org",
    "numpy.org",
    "scikit-learn.org",
    "developer.mozilla.org",       # MDN
    "en.wikibooks.org",
}
# Domain *suffixes* that confer the canonical tier (host endswith one of these).
CANONICAL_SUFFIXES = (
    ".wikipedia.org",
)

# --- Tier 2: reputable (recommended expert blogs / courses / org blogs) -------
REPUTABLE_EXACT = {
    "lilianweng.github.io",
    "colah.github.io",
    "karpathy.github.io",
    "jalammar.github.io",
    "huggingface.co",
    "www.fast.ai",
    "fast.ai",
    "course.fast.ai",
    "d2l.ai",                       # Dive into Deep Learning
    "paperswithcode.com",
    "ai.googleblog.com",
    "research.google",
    "deepmind.google",
    "openai.com",
    "www.deeplearning.ai",
    "sebastianraschka.com",
    "ruder.io",
    "machinelearningmastery.com",
    "stats.stackexchange.com",
}
# Suffixes that confer the reputable tier (e.g. university course pages).
REPUTABLE_SUFFIXES = (
    ".edu",        # university pages — course notes, lecture slides
    ".ac.uk",
)

# --- Blocked: never ingest ----------------------------------------------------
BLOCKED_EXACT: set[str] = set()
BLOCKED_SUFFIXES: tuple[str, ...] = ()

# --- Discovery seeds (not used for scoring) -----------------------------------
# Canonical "awesome-list"/hub landing pages the /web skill can crawl for
# widely-recommended resources in a broad area. Keyed by coarse area keyword.
AWESOME_HUBS: dict[str, list[str]] = {
    "machine-learning": [
        "https://github.com/josephmisiti/awesome-machine-learning",
        "https://github.com/ChristosChristofidis/awesome-deep-learning",
    ],
    "nlp": [
        "https://github.com/keon/awesome-nlp",
    ],
    "computer-vision": [
        "https://github.com/jbhuang0604/awesome-computer-vision",
    ],
}


def _normalize_host(host: str) -> str:
    """Lowercase the host and strip a leading ``www.``."""
    host = (host or "").lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host


def tier_for(host: str) -> str:
    """Return the registry tier for a hostname.

    One of ``"canonical"``, ``"reputable"``, ``"blocked"``, or ``"unknown"``.
    Exact matches win over suffix matches; blocked always wins.
    """
    h = _normalize_host(host)
    if not h:
        return "unknown"
    if h in BLOCKED_EXACT or h.endswith(BLOCKED_SUFFIXES):
        return "blocked"
    # Check against both the normalized host and the original (www-stripped is
    # fine since our tables store bare domains).
    if h in CANONICAL_EXACT or ("www." + h) in CANONICAL_EXACT or h.endswith(CANONICAL_SUFFIXES):
        return "canonical"
    if h in REPUTABLE_EXACT or h.endswith(REPUTABLE_SUFFIXES):
        return "reputable"
    return "unknown"

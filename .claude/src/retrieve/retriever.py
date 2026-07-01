"""Pure retrieval over the knowledge-base index — no LLM, no API access.

``retrieve(query)`` returns the BM25 seed notes for a query; ``resolve(link)``
maps a wikilink/slug to the note file it points at (or ``None`` if dangling).

The agentic part — reading each note and deciding which of its wikilinks to
follow for a given query — lives in the **/retrieve skill**, not here. This
module only does lexical retrieval and graph resolution over the index, so it
needs no Claude API access.
"""

from .config import RetrievalConfig
from .index import get_index


def retrieve(query: str, config: RetrievalConfig | None = None) -> list[dict]:
    """Return the BM25 seed notes for ``query``.

    Each result is ``{"file", "slug", "title", "score"}``. The index is loaded
    (and auto-rebuilt if the corpus changed) on each call.
    """
    config = config or RetrievalConfig()
    index = get_index(config)
    index.load()
    return [
        {
            "file": str(ref.path),
            "slug": ref.slug,
            "title": ref.title,
            "score": round(float(score), 3),
        }
        for ref, score in index.search(query, config.top_k)
    ]


def resolve(link: str, config: RetrievalConfig | None = None) -> str | None:
    """Map a wikilink target / slug to its note file path, or ``None``.

    Lets the /retrieve skill turn a ``[[wikilink]]`` it has chosen to follow
    into a concrete file to read next, using the index's slug + alias table.
    """
    config = config or RetrievalConfig()
    index = get_index(config)
    index.load()
    ref = index.resolve(link)
    return str(ref.path) if ref else None

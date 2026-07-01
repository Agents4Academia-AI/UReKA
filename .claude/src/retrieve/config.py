"""Configuration for the knowledge-base retrieval index.

Retrieval is pure (no LLM): ``retrieve()`` returns BM25 seed notes, and the
agentic wikilink-following expansion lives in the /retrieve skill. These knobs
cover only the index/seed step, and let the backend be swapped (BM25 -> vector)
without touching callers.
"""

from dataclasses import dataclass


@dataclass
class RetrievalConfig:
    retriever: str = "bm25"   # "bm25" | "vector" (future: Milvus)
    top_k: int = 5            # number of seed notes retrieve() returns
    corpus: str = "base"      # "base" (personal vault) | "explore" (explore_library/)

    # Future knobs (unused until the vector backend lands):
    # embedder: str = "voyage-3"
    # store_uri: str = "./milvus.db"
    # similarity_threshold: float = 0.0
    # rerank: bool = False

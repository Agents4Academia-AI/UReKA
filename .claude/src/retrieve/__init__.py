"""Pure retrieval over the knowledge base — BM25 seed search + graph resolution.

Public entry points: ``src.retrieve.retriever.retrieve(query, config)`` (seed
notes) and ``...resolve(link, config)`` (wikilink -> file). No LLM access; the
agentic wikilink-following expansion lives in the /retrieve skill.
"""

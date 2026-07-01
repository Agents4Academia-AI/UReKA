"""Pluggable search index for the retriever.

The ``Index`` abstraction is built once over the corpus and persisted, then
loaded cheaply at query time. ``search()`` returns lightweight ``NoteRef``s
(never bodies); the orchestrator lazily loads only the few notes it actually
needs. This is the same shape a vector backend needs, so swapping BM25 for
Milvus changes only this module.
"""

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

# BM25Plus uses a strictly-positive IDF (log((N+1)/n)) that rewards distinctive
# terms; plain BM25Okapi's IDF collapses to 0 / goes negative on a tiny corpus,
# which inverts the ranking.
from rank_bm25 import BM25Plus

from .config import RetrievalConfig
from .notes import NoteRef, ref_from_path, slugify

SOURCES_DIR = Path("sources")
NOTES_DIR = Path("notes")
PAPERS_DIR = Path("papers")
CONCEPTS_DIR = Path("concepts")
COURSE_DIR = Path("course")
EXPLORE_DIR = Path("explore_library")
INDEX_DIR = Path(".index")


@dataclass(frozen=True)
class Corpus:
    """A named, separately-persisted search corpus.

    ``dirs`` are flat ``glob("*.md")`` directories (kind, path); ``include_course``
    additionally walks the nested ``course/`` docs (excluding per-course
    ``library/``). Each corpus persists to its own ``index_file`` so the personal
    base and the standalone ``explore_library/`` are independent indexes.
    """
    name: str
    dirs: tuple[tuple[str, Path], ...]
    include_course: bool
    index_file: Path


# The personal knowledge base (indexed today): sources/notes/papers/concepts + course docs.
BASE = Corpus(
    name="base",
    dirs=(("source", SOURCES_DIR), ("note", NOTES_DIR),
          ("paper", PAPERS_DIR), ("concept", CONCEPTS_DIR)),
    include_course=True,
    index_file=INDEX_DIR / "bm25.pkl",
)
# The standalone autoexplore corpus — one accumulating mini-vault, separately indexed
# so it can scale without polluting the personal base. Type subfolders mirror the vault
# (stem == slug, so wikilink resolution works). Per-course `library/` dirs are NOT a
# corpus here — they stay unindexed and are resolved via `--resolve-dir`.
EXPLORE = Corpus(
    name="explore",
    dirs=(("source", EXPLORE_DIR / "sources"), ("paper", EXPLORE_DIR / "papers"),
          ("concept", EXPLORE_DIR / "concepts")),
    include_course=False,
    index_file=INDEX_DIR / "explore_library.pkl",
)
CORPORA = {c.name: c for c in (BASE, EXPLORE)}

_TOKEN_RE = __import__("re").compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class Index(Protocol):
    def build(self) -> None: ...
    def load(self) -> None: ...
    def search(self, query: str, k: int) -> list[tuple[NoteRef, float]]: ...
    def resolve(self, slug: str) -> NoteRef | None: ...
    def outgoing_links(self, ref: NoteRef, edge_types: tuple[str, ...]) -> list[str]: ...


def _iter_note_files(corpus: Corpus = BASE):
    for kind, directory in corpus.dirs:
        for path in sorted(directory.glob("*.md")):
            if path.name.startswith("_"):  # skip templates
                continue
            yield kind, path
    if not corpus.include_course:
        return
    # Course content is nested (course/<slug>/{goal,plan,schedule,progress,modules/*}.md),
    # so recurse. Slug uniqueness for these is handled in build() via the rel path.
    # The per-course library (course/<slug>/library/**) is fetched curriculum material
    # and stays OUT of the index until /tutor promotes a file into the personal sources/.
    for path in sorted(COURSE_DIR.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        if "library" in path.relative_to(COURSE_DIR).parts:
            continue
        yield "course", path


def _slug_for(kind: str, path: Path) -> str:
    """Index slug for a file. Course files use their path under course/ so every
    ``goal.md``/``plan.md``/``module`` across courses stays unique; others use the stem.
    """
    if kind == "course":
        return slugify(str(path.relative_to(COURSE_DIR).with_suffix("")))
    return slugify(path.stem)


def _corpus_signature(corpus: Corpus = BASE) -> dict[str, int]:
    """A fingerprint of the corpus: ``{path: mtime_ns}`` over all note files.

    Changes when any note is added, edited, deleted, or renamed — used to detect
    a stale persisted index and trigger an automatic rebuild.
    """
    return {str(path): path.stat().st_mtime_ns for _, path in _iter_note_files(corpus)}


class BM25Index:
    """Lexical BM25 index over note text, with a slug->NoteRef metadata table.

    Bound to one ``Corpus`` (default the personal ``BASE``); ``explore_library/``
    is indexed by passing ``EXPLORE``. Each corpus persists to its own file.
    """

    def __init__(self, corpus: Corpus = BASE) -> None:
        self._corpus = corpus
        self._bm25: BM25Plus | None = None
        self._refs: list[NoteRef] = []
        self._by_slug: dict[str, NoteRef] = {}
        self._alias: dict[str, str] = {}  # alias slug -> canonical slug
        self._signature: dict[str, int] = {}  # corpus fingerprint at build time

    # -- build / persistence -------------------------------------------------
    def build(self) -> None:
        """Scan the corpus once, fit BM25, and persist the index to disk."""
        refs: list[NoteRef] = []
        corpus: list[list[str]] = []
        import frontmatter  # local import; only needed at build time

        for kind, path in _iter_note_files(self._corpus):
            ref = ref_from_path(path, kind)
            ref.slug = _slug_for(kind, path)  # keep nested course slugs unique
            refs.append(ref)
            post = frontmatter.load(path)
            corpus.append(_tokenize(f"{ref.title}\n{post.content}"))

        self._refs = refs
        self._bm25 = BM25Plus(corpus) if corpus else None
        self._by_slug = {r.slug: r for r in refs}
        self._alias = {a: r.slug for r in refs for a in r.aliases}
        self._signature = _corpus_signature(self._corpus)
        self._persist()

    def _persist(self) -> None:
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        with open(self._corpus.index_file, "wb") as fh:
            pickle.dump(
                {
                    "bm25": self._bm25,
                    "refs": self._refs,
                    "by_slug": self._by_slug,
                    "alias": self._alias,
                    "signature": self._signature,
                },
                fh,
            )

    def load(self) -> None:
        """Load the persisted index, (re)building it if missing or stale.

        The index auto-rebuilds whenever the corpus fingerprint has changed since
        it was built (note added/edited/deleted/renamed), so callers always query
        a current index without a manual ``--reindex``.
        """
        if not self._corpus.index_file.exists():
            self.build()
            return
        try:
            with open(self._corpus.index_file, "rb") as fh:
                data = pickle.load(fh)
        except Exception:
            # Unreadable/incompatible pickle (e.g. a moved module or format
            # change) — rebuild from scratch rather than crash.
            self.build()
            return
        if data.get("signature") != _corpus_signature(self._corpus):
            self.build()  # stale: corpus changed since last build
            return
        self._bm25 = data["bm25"]
        self._refs = data["refs"]
        self._by_slug = data["by_slug"]
        self._alias = data["alias"]
        self._signature = data["signature"]

    # -- query ---------------------------------------------------------------
    def search(self, query: str, k: int) -> list[tuple[NoteRef, float]]:
        if not self._refs or self._bm25 is None:
            return []
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)
        query_terms = set(tokens)
        # Rank by BM25 score, but only keep notes that actually share a term with
        # the query. (On a tiny corpus BM25 IDF collapses to <=0, so a raw
        # score>0 filter would drop everything — token overlap is the reliable
        # signal of a real lexical match.)
        hits = [
            (ref, float(score))
            for ref, score, freqs in zip(self._refs, scores, self._bm25.doc_freqs)
            if query_terms.intersection(freqs)
        ]
        hits.sort(key=lambda rs: rs[1], reverse=True)
        return hits[:k]

    def resolve(self, slug: str) -> NoteRef | None:
        s = slugify(slug)
        if s in self._by_slug:
            return self._by_slug[s]
        if s in self._alias:
            return self._by_slug[self._alias[s]]
        return None

    def outgoing_links(self, ref: NoteRef, edge_types: tuple[str, ...]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for edge_type in edge_types:
            for slug in ref.links.get(edge_type, []):
                if slug and slug not in seen:
                    seen.add(slug)
                    out.append(slug)
        return out


class MilvusIndex:
    """Vector-search backend over Milvus Lite. **Not yet implemented.**

    Intended shape (same ``Index`` interface, so the orchestrator is unchanged):

        from pymilvus import MilvusClient
        client = MilvusClient(config.store_uri)          # e.g. "./milvus.db"

        # build(): embed each note's text and upsert {id, vector, ref-metadata}
        # search(): client.search(vector=embed(query), limit=k) -> NoteRefs
        # resolve()/outgoing_links(): served from the same metadata table

    Embeddings would come from a pluggable embedder (e.g. Voyage ``voyage-3``).
    """

    def _not_ready(self):
        raise NotImplementedError(
            "Milvus vector backend not implemented yet. Use retriever='bm25'. "
            "See MilvusIndex docstring for the intended implementation."
        )

    def build(self) -> None:
        self._not_ready()

    def load(self) -> None:
        self._not_ready()

    def search(self, query: str, k: int):
        self._not_ready()

    def resolve(self, slug: str):
        self._not_ready()

    def outgoing_links(self, ref, edge_types):
        self._not_ready()


def get_index(config: RetrievalConfig) -> Index:
    corpus = CORPORA.get(getattr(config, "corpus", "base"), BASE)
    if config.retriever == "bm25":
        return BM25Index(corpus)
    if config.retriever == "vector":
        return MilvusIndex()
    raise ValueError(f"Unknown retriever backend: {config.retriever!r}")

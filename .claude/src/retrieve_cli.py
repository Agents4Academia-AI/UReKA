"""Knowledge-base retrieval CLI — pure BM25 retrieval + index maintenance.

No Claude API access: this only does lexical retrieval and graph resolution over
the persisted index. The agentic "read each note and follow relevant wikilinks"
expansion lives in the /retrieve skill.

Usage (always via the env-agnostic launcher ``sh .claude/src/pyrun``):
    sh .claude/src/pyrun .claude/src/retrieve_cli.py --reindex
    sh .claude/src/pyrun .claude/src/retrieve_cli.py --retrieve "RLHF reward model"   # seeds (file<TAB>title)
    sh .claude/src/pyrun .claude/src/retrieve_cli.py --resolve "tool use" "planning"  # wikilink -> file path
"""

import argparse
import sys
from pathlib import Path

# Put `.claude/` (the dir holding the `src` package) on the path so
# `from src.retrieve...` resolves. parents[1] == .claude/, parents[2] == repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _ensure_venv() -> None:
    """Defensive fallback: re-exec under the project venv if deps aren't importable.

    Normally this CLI is launched via ``sh .claude/src/pyrun`` (the env-agnostic
    launcher), which already selects an interpreter that has the deps — so this is
    a no-op. It only matters when the script is run *directly* with a bare
    interpreter that lacks ``frontmatter``/``rank_bm25``: if a repo-local ``.venv``
    has them, re-exec with it. If the deps are already available (venv active, or
    installed system-wide / via conda) this is a no-op. The ``!= sys.executable``
    guard prevents an infinite re-exec loop when we're *already* the venv interpreter.
    """
    try:
        import frontmatter  # noqa: F401
        import rank_bm25  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    import os

    root = Path(__file__).resolve().parents[2]  # repo root holds .venv/
    for cand in (root / ".venv/bin/python", root / ".venv/Scripts/python.exe"):
        if cand.exists() and str(cand) != sys.executable:
            os.execv(str(cand), [str(cand), str(Path(__file__).resolve()), *sys.argv[1:]])
    # No venv to fall back on — let the import below raise its normal error.


_ensure_venv()

from src.retrieve.config import RetrievalConfig  # noqa: E402
from src.retrieve.index import get_index  # noqa: E402
from src.retrieve.notes import slugify  # noqa: E402
from src.retrieve.retriever import resolve as _resolve  # noqa: E402
from src.retrieve.retriever import retrieve as _retrieve  # noqa: E402


def retrieve(query: str) -> list[dict]:
    """Seed notes for a query (file/slug/title/score), no expansion."""
    return _retrieve(query)


def resolve_in_dir(directory: Path, link: str) -> Path | None:
    """Map a wikilink/slug to a page file inside an *unindexed* library directory.

    Pure filesystem lookup (no index, no API key) for the concept-web closure
    loop over a per-course library (`course/<slug>/library/`), which stays out of
    the BM25 index. Uses the canonical ``slugify`` so resolution agrees with how
    pages are named. The library mirrors the vault's type-subfolder layout, so a
    page exists iff one of ``concepts/<slug>.md`` / ``papers/<slug>.md`` /
    ``sources/<slug>.md`` exists (flat ``<slug>.md`` kept as a fallback).
    """
    slug = slugify(link)
    candidates = (
        directory / "concepts" / f"{slug}.md",
        directory / "papers" / f"{slug}.md",
        directory / "sources" / f"{slug}.md",
        directory / f"{slug}.md",
    )
    for cand in candidates:
        if cand.exists():
            return cand
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Retrieve notes from the knowledge base (BM25; no LLM)."
    )
    parser.add_argument("--retrieve", metavar="QUERY", help="Print seed notes for QUERY as 'file<TAB>title', one per line.")
    parser.add_argument("--resolve", metavar="LINK", nargs="+", help="Resolve each wikilink/slug to its note file ('link<TAB>path|NONE').")
    parser.add_argument("--resolve-dir", metavar=("DIR", "LINK"), nargs="+",
                        help="Index-free: resolve each wikilink to a page in DIR "
                             "(first arg = dir, rest = links; 'link<TAB>path|NONE'). "
                             "For unindexed library / explore_library dirs.")
    parser.add_argument("--reindex", action="store_true", help="(Re)build the search index, then exit unless --retrieve/--resolve given.")
    parser.add_argument("--retriever", default="bm25", help="Backend: bm25 (default) | vector (future).")
    parser.add_argument("--corpus", default="base", choices=("base", "explore"),
                        help="Which index to use: 'base' (personal vault, default) or "
                             "'explore' (explore_library/, separately indexed).")
    parser.add_argument("-k", "--top-k", type=int, default=5, help="Number of seed notes for --retrieve.")
    args = parser.parse_args()

    config = RetrievalConfig(retriever=args.retriever, top_k=args.top_k, corpus=args.corpus)

    if args.resolve_dir:
        directory = Path(args.resolve_dir[0])
        links = args.resolve_dir[1:]
        if not links:
            parser.error("--resolve-dir needs a directory followed by one or more links")
        for link in links:
            path = resolve_in_dir(directory, link)
            print(f"{link}\t{path or 'NONE'}")
        sys.exit(0)

    if args.reindex:
        get_index(config).build()
        print(f"Index built at .index/ (corpus: {args.corpus})")
        if not args.retrieve and not args.resolve:
            sys.exit(0)

    if args.resolve:
        for link in args.resolve:
            path = _resolve(link, config)
            print(f"{link}\t{path or 'NONE'}")
    elif args.retrieve:
        seeds = _retrieve(args.retrieve, config)
        if not seeds:
            print("No seed notes found.")
        else:
            for s in seeds:
                print(f"{s['file']}\t{s['title']}")
    else:
        parser.error("provide --retrieve, --resolve, --resolve-dir, and/or --reindex")

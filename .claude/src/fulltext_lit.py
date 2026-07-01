"""Full-text rendering over the `prior` package — read core papers to Markdown.

Given a scoped corpus (the JSONL `explore_lit.py` writes), fetch each paper's
full text via the pinned `prior` package's cascade (arXiv / OA PDF / Unpaywall /
publisher / institutional) and render one Markdown file per paper for reading.
This replaces the old `prior/scripts/fullpaper.py` script so the skills depend
only on the pip-installed package — no sibling `../prior` checkout.

Like `explore_lit.py`, we load a gitignored ``.env`` BEFORE importing `prior`
(its config reads env vars at import time). No API key is required.

Usage (always via the env-agnostic launcher ``sh .claude/src/pyrun``):
    # from an explore corpus (one Paper dict per line)
    sh .claude/src/pyrun --need prior .claude/src/fulltext_lit.py --corpus .autoexplore/raw/topic.jsonl --out .autoexplore/fulltext

    # restrict to a subset of ids (arXiv id / DOI / OpenAlex id, one per line)
    sh .claude/src/pyrun --need prior .claude/src/fulltext_lit.py --corpus corpus.jsonl --out ft --ids ids.txt

Or as a library:
    from fulltext_lit import render_fulltext
    n = render_fulltext("corpus.jsonl", "ft/")
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the repo root (.claude/src/ -> repo root) before importing
# `prior`, so PRIOR_LLM_BACKEND / PRIOR_DATA_DIR / etc. apply (mirrors explore_lit).
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

from prior import config, fulltext  # noqa: E402  (must come after load_dotenv)
from prior.models import Paper  # noqa: E402

from explore_lit import slugify  # noqa: E402  (reuse the canonical slug rule)


def _read_corpus(corpus_path: Path) -> list[Paper]:
    """Load the explore JSONL (one ``Paper.to_dict()`` per line) into Papers."""
    papers: list[Paper] = []
    for line in corpus_path.read_text().splitlines():
        line = line.strip()
        if line:
            papers.append(Paper.from_dict(json.loads(line)))
    return papers


def _matches(paper: Paper, wanted: set[str]) -> bool:
    """True if any of the paper's identifiers is in the wanted-id set."""
    cands = {paper.id, paper.doi, paper.pdf_url, paper.url}
    return bool(wanted & {c for c in cands if c})


def render_fulltext(corpus_path: str | Path, out_dir: str | Path, *,
                    ids: list[str] | None = None, progress=print) -> int:
    """Fetch + render full text for the corpus; return the count rendered.

    Writes ``<out_dir>/<slug>.md`` per paper that has retrievable full text,
    with a small frontmatter header (id/title/url/doi) followed by the text.
    Papers with no retrievable full text are skipped (reported by ``progress``).
    """
    config.ensure_dirs()
    papers = _read_corpus(Path(corpus_path))
    if ids:
        wanted = set(ids)
        papers = [p for p in papers if _matches(p, wanted)]

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Parallel fetch (I/O-bound, no LLM) — populates the package's text cache.
    fulltext.fetch_many(papers, progress=progress)

    rendered = 0
    skipped: list[str] = []
    for p in papers:
        text = fulltext.fetch(p)  # cache hit after fetch_many
        if not text:
            skipped.append(p.title or p.id)
            continue
        header = (
            "---\n"
            f"id: {p.id}\n"
            f"title: {json.dumps(p.title or '')}\n"
            f"url: {p.url or ''}\n"
            f"doi: {p.doi or ''}\n"
            f"year: {p.year or ''}\n"
            "---\n\n"
        )
        (out / f"{slugify(p.title or p.id)}.md").write_text(header + text)
        rendered += 1

    if skipped:
        progress(f"  no full text for {len(skipped)}: " + "; ".join(skipped[:5])
                 + (" ..." if len(skipped) > 5 else ""))
    return rendered


def main() -> None:
    ap = argparse.ArgumentParser(description="Render papers' full text to Markdown.")
    ap.add_argument("--corpus", required=True, help="explore JSONL (one Paper dict per line)")
    ap.add_argument("--out", required=True, help="output dir for the Markdown renders")
    ap.add_argument("--ids", default=None,
                    help="optional file of ids (arXiv/DOI/OpenAlex/url) to restrict to, one per line")
    args = ap.parse_args()

    ids = None
    if args.ids:
        ids = [ln.strip() for ln in Path(args.ids).read_text().splitlines() if ln.strip()]

    n = render_fulltext(args.corpus, args.out, ids=ids)
    print(f"DONE | {n} papers rendered -> {args.out}")


if __name__ == "__main__":
    main()

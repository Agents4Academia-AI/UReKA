"""Resource-pull CLI — Wikipedia search/fetch, credibility scoring, paper pull.

Thin, mostly-stdlib CLI over ``.claude/src/resources/`` (mirrors
``retrieve_cli.py``). Used by the `/web` and `/curriculum` skills. Emits JSONL
(one object per line) so the skill can parse results without scraping prose.

Usage (always via the env-agnostic launcher ``sh .claude/src/pyrun``):
    # Search Wikipedia (curated registry) → candidate lines
    sh .claude/src/pyrun .claude/src/resources_cli.py --wikipedia "diffusion models"

    # Fetch one Wikipedia article's full plain-text content for ingestion
    sh .claude/src/pyrun .claude/src/resources_cli.py --wiki-page "Diffusion model"

    # Score one or more URLs' credibility (deterministic domain-tier prior)
    sh .claude/src/pyrun .claude/src/resources_cli.py --score https://lilianweng.github.io/posts/...

    # Pull papers for a topic (delegates to explore_lit.py / the prior scoper)
    sh .claude/src/pyrun .claude/src/resources_cli.py --papers "diffusion models" --hops 1
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Put `.claude/` on the path so `from src.resources...` resolves (mirrors retrieve_cli).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.resources import credibility, wikipedia  # noqa: E402
from src.resources.registries import AWESOME_HUBS  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def cmd_wikipedia(topic: str, limit: int) -> None:
    hits = wikipedia.search(topic, limit=limit)
    if not hits:
        print("No Wikipedia results.", file=sys.stderr)
        return
    for h in hits:
        cred = credibility.score(h["url"])
        _emit({
            "kind": "wikipedia",
            "title": h["title"],
            "url": h["url"],
            "snippet": h["snippet"],
            "score": cred["score"],
            "tier": cred["tier"],
            "rationale": cred["rationale"],
        })


def cmd_wiki_page(title: str) -> None:
    page = wikipedia.fetch(title)
    if not page:
        print(f"Wikipedia page not found: {title!r}", file=sys.stderr)
        sys.exit(1)
    cred = credibility.score(page["url"], has_references=bool(page.get("references")))
    page.update({"kind": "wikipedia", "score": cred["score"],
                 "tier": cred["tier"], "rationale": cred["rationale"]})
    _emit(page)


def cmd_score(urls: list[str]) -> None:
    for url in urls:
        _emit(credibility.score(url))


def cmd_hubs(area: str) -> None:
    for hub in AWESOME_HUBS.get(area, []):
        _emit({"kind": "awesome-hub", "area": area, "url": hub})


# Child scripts (explore_lit / fulltext_lit) need the `prior` package; route them
# through the env-agnostic launcher so they run under whatever environment has it
# (venv / uv / conda / system / PKM_PYTHON), not just a repo-local .venv.
_PYRUN_PRIOR = ["sh", ".claude/src/pyrun", "--need", "prior"]


def cmd_papers(topic: str, hops: int, per_query: int, out: str | None) -> None:
    """Delegate paper discovery to explore_lit.py (the prior scoper)."""
    args = [*_PYRUN_PRIOR, ".claude/src/explore_lit.py", "--topic", topic,
            "--hops", str(hops), "--per-query", str(per_query)]
    if out:
        args += ["--out", out]
    # Inherit stdout/stderr so the user sees explore_lit's progress + DONE line.
    proc = subprocess.run(args, cwd=str(_REPO_ROOT))
    sys.exit(proc.returncode)


def cmd_fulltext(corpus: str, out: str, ids: str | None) -> None:
    """Delegate full-text rendering to fulltext_lit.py (the prior fulltext cascade)."""
    args = [*_PYRUN_PRIOR, ".claude/src/fulltext_lit.py", "--corpus", corpus, "--out", out]
    if ids:
        args += ["--ids", ids]
    proc = subprocess.run(args, cwd=str(_REPO_ROOT))
    sys.exit(proc.returncode)


def main() -> None:
    ap = argparse.ArgumentParser(description="Pull + score grounded learning resources.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--wikipedia", metavar="TOPIC", help="Search Wikipedia; emit scored candidates.")
    g.add_argument("--wiki-page", metavar="TITLE", help="Fetch one Wikipedia article's full text.")
    g.add_argument("--score", metavar="URL", nargs="+", help="Credibility-score each URL.")
    g.add_argument("--hubs", metavar="AREA", help="List curated awesome-list hubs for an area.")
    g.add_argument("--papers", metavar="TOPIC", help="Pull papers via explore_lit.py (prior scoper).")
    g.add_argument("--fulltext", metavar="CORPUS", help="Render full text for a paper corpus JSONL via fulltext_lit.py.")
    ap.add_argument("-k", "--limit", type=int, default=5, help="Max Wikipedia hits (default 5).")
    ap.add_argument("--hops", type=int, default=0,
                    help="Citation snowball hops for --papers (default 0 = search only — "
                         "fastest; bump to 1 for depth at the cost of time).")
    ap.add_argument("--per-query", type=int, default=20, help="Per-query results for --papers (default 20).")
    ap.add_argument("--out", default=None, help="Output path: JSONL for --papers, render dir for --fulltext.")
    ap.add_argument("--ids", default=None, help="Optional id-subset file for --fulltext (one id per line).")
    args = ap.parse_args()

    if args.wikipedia:
        cmd_wikipedia(args.wikipedia, args.limit)
    elif args.wiki_page:
        cmd_wiki_page(args.wiki_page)
    elif args.score:
        cmd_score(args.score)
    elif args.hubs:
        cmd_hubs(args.hubs)
    elif args.papers:
        cmd_papers(args.papers, args.hops, args.per_query, args.out)
    elif args.fulltext:
        if not args.out:
            ap.error("--fulltext requires --out <render dir>")
        cmd_fulltext(args.fulltext, args.out, args.ids)


if __name__ == "__main__":
    main()

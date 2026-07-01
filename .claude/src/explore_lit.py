"""Literature exploration over the `prior` Stage-1 scoper.

Given a topic definition (what's in scope / out of scope), run the full
recall-then-precision + citation-snowball pipeline and return the scoped corpus.
This is a thin wrapper around ``prior.scoper.explore`` so we control where the
result goes; the heavy lifting lives in the pinned `prior` package (see
.claude/requirements.txt).

Environment is loaded from a local, gitignored ``.env`` (see ``.env.example``).
We load it BEFORE importing `prior`, because `prior.config` reads env vars at
import time. Real environment variables always take precedence over ``.env``.

Usage (always via the env-agnostic launcher ``sh .claude/src/pyrun``):
    sh .claude/src/pyrun --need prior .claude/src/explore_lit.py --topic "$(cat topic.txt)" --hops 3
    sh .claude/src/pyrun --need prior .claude/src/explore_lit.py --topic "..." --hops 0   # search only

Or as a library:
    from explore_lit import explore
    papers, stats = explore("<topic def>", hops=3)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the repo root (two levels up: .claude/src/ -> repo root) before
# `prior` is imported, so PRIOR_LLM_BACKEND / PRIOR_CONTACT_EMAIL / etc. apply.
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

from prior import config, scoper  # noqa: E402  (must come after load_dotenv)


def slugify(text: str, *, max_words: int = 8) -> str:
    """Turn a topic definition into a filesystem-safe slug.

    Lowercases, keeps alphanumerics, collapses everything else to single
    hyphens, and caps the length so a long topic blurb yields a short filename.
    Falls back to ``"papers"`` if nothing usable remains.
    """
    words = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-").split("-")
    slug = "-".join(w for w in words if w)[:80]  # also clip overall length
    slug = "-".join(slug.split("-")[:max_words]).strip("-")
    return slug or "papers"


def explore(topic_def: str, *, hops: int = 3, per_query: int = 25,
            model: str | None = None, progress=print):
    """Run Stage-1 exploration and return ``(papers, stats)``.

    ``papers`` is a list of plain dicts (``Paper.to_dict()``); ``stats`` carries
    the saturation curve and a capture-recapture completeness estimate.
    """
    config.ensure_dirs()
    corpus, _dropped, stats = scoper.explore(
        topic_def, hops=hops, per_query=per_query, model=model, progress=progress)
    return [p.to_dict() for p in corpus], stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Scope a literature corpus for a topic.")
    ap.add_argument("--topic", required=True, help="in-/out-of-scope topic definition")
    ap.add_argument("--hops", type=int, default=3, help="citation snowball hops (0 = search only)")
    ap.add_argument("--per-query", type=int, default=25)
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", default=None,
                    help="output JSONL path (default: $PRIOR_DATA_DIR/raw/<topic-slug>.jsonl)")
    args = ap.parse_args()

    papers, stats = explore(
        args.topic, hops=args.hops, per_query=args.per_query, model=args.model)

    out = Path(args.out) if args.out else (config.RAW / f"{slugify(args.topic)}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(p) for p in papers) + "\n")
    print(f"DONE | {len(papers)} scoped papers -> {out} | "
          f"curve {stats['curve']} | completeness {stats['completeness']}")


if __name__ == "__main__":
    main()

"""Grounded multi-source resource-pull engine (papers + web).

Pure-stdlib helpers that the `/web` and `/curriculum` skills lean on to pull
*verifiable, widely-used* learning material and score how trustworthy each
candidate is — no API key, no LLM:

- `wikipedia`  — MediaWiki API client (the canonical "curated registry" tier).
- `registries` — curated map of canonical/reputable source domains → tier.
- `credibility` — deterministic credibility score for a URL (pluggable: the
  skill escalates borderline cases to a cheap LLM judgment).

Paper discovery is *not* re-implemented here; it lives in
``.claude/src/explore_lit.py`` (the `prior` scoper). The CLI
``.claude/src/resources_cli.py`` ties these together.
"""

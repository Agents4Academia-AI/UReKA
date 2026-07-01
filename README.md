# UReKA: Yo**u**r Personal **Re**search **K**nowledge Management **A**gent

> Ingests annotated research sources (Zotero PDFs, Notion notes, Obsidian notes, arXiv papers, web pages), extracts structured knowledge, and builds an interlinked knowledge base of paper pages and concept pages — queryable in natural language. Also supports building full learning courses with `/goal` → `/curriculum` → `/tutor`.

---

## Architecture

```
sources (Zotero PDFs, Notion, Obsidian, arXiv, web)
    │
    ▼  ingest — /zotero, /notion, /obsidian, /alphaxiv, /web
    ├──▶ sources/   objective text
    └──▶ notes/     personal notes + pdf annotations
              │
              ▼  /collate <topic|paper> — synthesise sources + notes into a page
          papers/<slug>.md   or   concepts/<slug>.md
          (objective summary + personal notes/annotations woven in)
              │
   /edit ─────┤  co-edit any papers/ or concepts/ page in place
              │
              ▼  /ask — synthesise a cited answer from the knowledge base (+ flag gaps)

course/<slug>/   — a learning course, three-stage pipeline:
   /goal <topic>       → goal.md   (scope + knowledge audit)
   /curriculum <slug>  → plan, schedule, modules, per-course library
   /tutor <slug>       → session-by-session teaching, flashcards, mastery tracking
```

## Setup

### Python (retrieval index — no API key needed)

```bash
python -m venv .venv && .venv/bin/pip install -r .claude/requirements.txt
```

Skills call Python via `sh .claude/src/pyrun …`, which always uses `.venv/bin/python` — no activation needed.

### Environment variables

```bash
cp .env.example .env
```

Then edit `.env` — at minimum set your contact email for polite API access:

```bash
PRIOR_LLM_BACKEND=claude-code   # uses your local Claude Code login, no API key needed
PRIOR_CONTACT_EMAIL=you@uni.com
PRIOR_DATA_DIR=.cache
```

See [`.env.example`](.env.example) for all options. `.env` is gitignored — never commit it.

### MCP servers (for Zotero + Notion ingestion)

The project ships an `.mcp.json` that registers three MCP servers. Zotero and pdf-tools are
picked up automatically — approve them when Claude Code prompts on first session.

Notion uses HTTP + OAuth and must be added manually once:

```bash
claude mcp add --transport http notion https://mcp.notion.com/mcp
```

Then run `/mcp` in Claude Code to authenticate. After that it's persisted and you don't need to run it again.

- **`zotero`** — local Zotero library access for `/zotero` (needs the Zotero desktop app running; `zotero-mcp-server` is installed by `requirements.txt`).
- **`pdf-tools`** — local PDF body-text + ink-annotation extraction for `/zotero` (`pdf_tools.py`, also installed via `requirements.txt`).
- **`notion`** — live Notion workspace fetch for `/notion` (HTTP MCP, registered above).

## Day-to-day usage

All work is done through Claude Code skills:

```
# Ingest a source
/notion "My reading note title"         live fetch from Notion workspace
/obsidian /path/to/your/note.md         any local .md file
/zotero                                  pick a PDF from Zotero
/alphaxiv 2507.05024                     arXiv paper via AlphaXiv API
/web https://en.wikipedia.org/wiki/...   vetted web page with credibility score

# Build knowledge pages
/collate "attention is all you need"     synthesise sources + notes → papers/ or concepts/
/edit papers/attention.md               co-edit a page in place

# Query the base
/ask "how does ReAct reduce hallucination?"
/retrieve RLHF                           list relevant notes (no synthesis)

# Build a learning course
/goal "understand diffusion models" by 2026-08-01 5 h/week
/tutor diffusion-models
```

## Structure

| Path | What |
|------|------|
| `sources/` | Ingested objective text (`zotero_*`, `alphaxiv_*`, `web_*`) |
| `notes/` | Ingested personal notes + annotations (`zotero_*`, `notion_*`, `obsidian_*`) |
| `papers/` | Paper pages — objective summary + personal notes |
| `concepts/` | Concept pages synthesised across the base |
| `course/<slug>/` | Learning course: `goal.md`, `plan.md`, `schedule.md`, `modules/`, `progress.md`, `library/` |
| `explore_library/` | Standalone `/autoexplore` corpus (separately indexed, not the personal base) |
| `.claude/src/` | All Python tooling — BM25 retrieval, ingestion helpers, course utilities, web resources (pure Python, no LLM) |
| `.claude/skills/` | Claude Code skills (`/collate`, `/edit`, `/ask`, `/retrieve`, `/goal`, `/curriculum`, `/tutor`, ingestion helpers) |
| [`.claude/AGENTS.md`](.claude/AGENTS.md) | Full architecture and conventions |

## Learn More

- [BLOG.md](BLOG.md) — overview of the problem, what we built, and design decisions
- [ROADMAP.md](ROADMAP.md) — current state, next steps, and how to contribute

## Acknowledgements

Built during [Agents4Academia](https://github.com/Agents4Academia-AI), 15–26 June 2026.

# UReKA — Roadmap & Vision

> **Vision:** A personal AI research companion that grows with you — turning annotated sources into structured knowledge, connecting ideas across papers, and teaching you new fields at the pace you set. All from your editor, all on your own files.

---

## 📍 Current State (v0.1 — June 2026)

- **Ingestion pipeline** — Zotero PDFs (body text + ink annotations), Notion pages, Obsidian notes, arXiv papers via AlphaXiv, credibility-scored web sources
- **Knowledge synthesis** — <code style="background:#d4f0e8;border:1px solid #66aa88;padding:1px 6px;border-radius:4px">/collate</code> produces cited, cross-linked `papers/` and `concepts/` pages; <code style="background:#d4f0e8;border:1px solid #66aa88;padding:1px 6px;border-radius:4px">/edit</code> co-edits in place
- **Q&A** — <code style="background:#fff8e6;border:1px solid #ccaa44;padding:1px 6px;border-radius:4px">/ask</code> synthesises cited answers from across the knowledge base and flags gaps; powered by BM25 + wikilink-expansion retrieval (pure Python, no API call), also callable directly via <code style="background:#fff8e6;border:1px solid #ccaa44;padding:1px 6px;border-radius:4px">/retrieve</code>
- **Learning courses** — the full <code style="background:#fff8e6;border:1px solid #ccaa44;padding:1px 6px;border-radius:4px">/goal</code> → <code style="background:#fff8e6;border:1px solid #ccaa44;padding:1px 6px;border-radius:4px">/curriculum</code> → <code style="background:#fff8e6;border:1px solid #ccaa44;padding:1px 6px;border-radius:4px">/tutor</code> pipeline: goal-setting, knowledge audit, concept-web building, module sequencing, session-by-session teaching with optional adaptive flashcards and mastery tracking
- **Autonomous concept-web builder** — <code style="background:#ede8f5;border:1px solid #9b8ec4;padding:1px 6px;border-radius:4px">/autoexplore</code> reads papers full-text, decomposes them into interlinked pages, and synthesises a capstone page
  - The library structure (how pages are grouped into folders) is amenable to personal preference — you can adapt it to organise by concept, by paper, or however fits your workflow
  - Currently `/curriculum` always runs its own `/autoexplore` call into a per-course library, independent of `explore_library/` — this can be changed so it searches existing content first, depending on how contained or shared you want the libraries to be

---

## 🚀 Next Steps

| Item | Notes |
|------|-------|
| **Modularise & streamline** | Audit skill overlap; reduce approval prompts during skill runs — some workflows (e.g. `/autoexplore`) interrupt frequently and could be streamlined |
| **Reduce token usage** | Shift more work to deterministic Python so LLM calls are reserved for synthesis and judgement; decide full-text vs metadata per ingestion route (full-text is richer but costly — worth auditing where metadata is sufficient) |
| **Improve annotation extraction** | Better extraction of handwritten maths in PDF annotations. Test and improve robustness when annotations are dense (many marks per page, overlapping) |
| **Handwritten note ingestion** | Standalone handwritten notes (photos of lecture notes, notebooks etc.), not just PDF marginalia. Key challenge: handwritten notes are non-linear and unstructured — ideas jump around the page, order isn't logical — so ingestion needs to reconstruct meaning, not just transcribe text |
| **Browser tab logging** | Capture what you're reading in the browser; potentially create a "reading list" in `explore_library/` or another appropriate location |
| **Agents4Academia integration** | Tighter integration with sibling agents (e.g. `prior`) — hand off to and receive from other agents in the ecosystem |
| **Community testing** | Get others to run it on their own data, surface real-world failures |

---

## 🔭 Longer Term

- **Personalised knowledge graph** — visualise the knowledge base weighted by your annotations and mastery level, so the graph reflects not just what you've read but how deeply you understand it; concepts with rich personal notes and high mastery score appear prominently, gaps (dangling `[[wikilinks]]` without pages) are surfaced, and connections reflect *your* linking of ideas rather than just co-citation
- **Live literature monitoring** — watch arXiv RSS / Semantic Scholar feeds for new papers in your tracked concept areas and surface them in a `to_read/` queue
- **Export** — convert `papers/` or `concepts/` pages to LaTeX or other formats for drop-in use in manuscripts
- **Agent handoffs** — <code style="background:#fff8e6;border:1px solid #ccaa44;padding:1px 6px;border-radius:4px">/goal</code> hands off to a remote agent to run <code style="background:#fff8e6;border:1px solid #ccaa44;padding:1px 6px;border-radius:4px">/curriculum</code> in the background and notify you when the course is ready — important since `/curriculum` + `/autoexplore` can take a long time

---

## 🛠️ How to Contribute

UReKA is built as a set of [Claude Code](https://claude.ai/code) skills (in `.claude/skills/`) on top of a pure-Python retrieval core (`.claude/src/`). Both layers are independent — you can contribute to either without touching the other.

### Where to Start

See [Next Steps](#-next-steps) above for what needs doing. Here's where to look in the codebase for each:

| Next Step | Where to start |
|-----------|----------------|
| Improve annotation extraction | `.claude/src/ingestion/pdf_tools.py`, `.claude/skills/zotero/SKILL.md` |
| Handwritten note ingestion | `.claude/src/ingestion/pdf_tools.py`, `.claude/skills/` |
| Browser tab logging | `.claude/skills/web/SKILL.md`, `explore_library/` |
| Agents4Academia integration | `.claude/src/fulltext_lit.py`, `.claude/src/explore_lit.py` |
| Reduce token usage | `.claude/skills/`, `.claude/src/retrieve/` |
| Modularise & streamline | `.claude/skills/collate/SKILL.md`, `.claude/skills/zotero/SKILL.md` |
| Community testing | Open an issue or discussion on GitHub |

### Architecture Areas

**Python retrieval core** (`.claude/src/retrieve/`) — pure Python, no LLM, no API key. `BM25Index` in `index.py` is the only concrete backend; a `MilvusIndex` stub is already there for anyone who wants to add dense retrieval. `RetrievalConfig` in `config.py` wires everything together.

**Ingestion MCP servers** (`.claude/src/ingestion/pdf_tools.py`) — a [FastMCP](https://github.com/jlowin/fastmcp) server exposing `extract_pdf_text` and `extract_ink_annotations`. Adding a new extraction tool means adding a `@mcp.tool()` function here and registering it in `.mcp.json`.

**Claude Code skills** (`.claude/skills/`) — each skill is a markdown file that Claude Code reads as a prompt when you type `/skill-name`. Skills can call Python scripts, read/write files, use MCP tools, and spawn sub-skills. The simplest way to add a new ingestion source is to copy an existing skill (e.g. `.claude/skills/collate/SKILL.md`) and adapt it.

**Web resource engine** (`.claude/src/resources/`) — credibility tiers, curated registries, Wikipedia client. Adding a new registry means adding a row to the registry file and a resolver in `resources_cli.py`.

### Running Locally

```bash
git clone https://github.com/Agents4Academia-AI/UReKA
cd UReKA
python -m venv .venv && .venv/bin/pip install -r .claude/requirements.txt
cp .env.example .env   # set PRIOR_CONTACT_EMAIL at minimum
```

Skills require [Claude Code](https://claude.ai/code). Open the repo in VS Code, Cursor, or any environment where Claude Code runs.

### PR Conventions

- **Branch naming:** `name/feature` (e.g. `name/handwritten-ingest`)
- **No direct pushes to `main`** — open a PR
- **Skill changes:** test manually with a small `sources/` corpus before opening a PR; note which skills you ran and what the output looked like
- **New dependencies:** add to `requirements.txt` with a pinned version and a one-line comment explaining why it's needed
- **Do not commit:** `.env`, API keys, or generated index files (`.index/` is gitignored)

### Questions and Discussion

Open an issue on GitHub or start a discussion in the repo. The `AGENTS.md` file (`.claude/AGENTS.md`) is the canonical architecture reference — read it before making structural changes.

---

*Built during [Agents4Academia](https://github.com/Agents4Academia-AI), 15–26 June 2026.*

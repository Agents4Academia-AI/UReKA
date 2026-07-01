# AGENTS.md — PKM: Personal Research Knowledge Management

Auto-loaded each session via `.claude/CLAUDE.md` (which imports `@AGENTS.md`). Keep it short.

## What we're building

This PKM agent ingests annotated research sources (Zotero PDFs, Notion notes,
Obsidian notes), extracts structured `.md` files, and builds an interlinked
knowledge base of paper pages and concept pages — queryable in natural language.

## Architecture

```
sources (Zotero, Notion, Obsidian, arXiv, web)
    │
    ▼  ingest — /zotero, /notion, /obsidian, /alphaxiv (helper skills)
    ├──▶ sources/   objective paper text extracted from pdfs
    └──▶ notes/     personal notes + pdf annotations
              │
              ▼  /collate — synthesise ingested sources + notes into a page
          papers/<slug>.md   or   concepts/<slug>.md
          (objective summary + the user's subjective notes / annotations)
              │
   /edit ─────┤  co-edit any papers/ or concepts/ page in place
              │
              ▼  retrieve — .claude/src/retrieve/ + /retrieve skill (python, no LLM)
          BM25 seeds over sources/ + notes/ + papers/ + concepts/,
          then follow relevant wikilinks (skill) → relevant notes
              │
              ▼  /ask — synthesise a cited answer from the retrieved notes (+ flag gaps)

course/<slug>/   ◀── a learning course, built and driven by a 3-stage pipeline
   goal.md       ◀── /goal <topic> [by <deadline>] [<H> h/week]
   │                 target + scope (in/out) + knowledge audit
   │                 → on completion, auto-hands off to /curriculum (goal+curriculum are linked)
   ▼
   plan.md · schedule.md · modules/ · library/   ◀── /curriculum <slug>
   │                 build a concept web (via /autoexplore, --hops 0) → course/<slug>/library/
   │                 (per-course, NOT indexed, never personal base): library/{sources,papers,concepts}/,
   │                 sequence modules, schedule, compile cited docs, initialize progress
   ▼
   progress.md   ◀── /tutor <slug>
                     per scheduled hour-block (`## Week W · Hour H`; hours are a budget,
                     not a per-day rate):
                       1. reading list — the actual paper / blog / Wikipedia links to go read
                          (in Zotero / Notion / Obsidian), each with a one-line TLDR of why &
                          what you'll learn, plus the library/ summary as a quick-browse
                       2. teach the session's module content
                       3. suggest (in prose, no pop-up) ingesting the session's material into
                          the personal base, dedup-checked against papers/concepts/sources
                       4. if opted to test → adaptive flashcards (streak-graded spaced rep +
                          Bloom escalation); else honor system → trust what was ingested
                       5. update knowledge level (from curriculum + what's now in the personal
                          base) → recap → advance to next day/module
                     → on mastery, suggest promoting library/ source → personal sources/
```

## File format

Every file follows a template in `.claude/Templates/` (dev tooling, lives under
`.claude/` alongside the skills). The nine templates:

- `.claude/Templates/source.md`, `.claude/Templates/note.md` — ingested inputs. Frontmatter:
  `type`, `title`, `concepts_mentioned`, and `source_links:` (a **list** — local file paths or URLs for remote sources like AlphaXiv;
  one ingested file may draw on several), followed by `## Content`.
- `.claude/Templates/paper.md`, `.claude/Templates/concept.md` — synthesised pages: richer
  frontmatter (`created`, `sources:`, `related_papers`/`related_concepts`) plus a
  templated body with inline citations.
- `.claude/Templates/goal.md`, `.claude/Templates/curriculum.md`, `.claude/Templates/module.md`,
  `.claude/Templates/progress.md`, `.claude/Templates/web_source.md` — the learning-course pages
  (written by `/goal`, `/curriculum`, `/tutor`) and credibility-scored web sources.

## Skills (Claude Code interactive use)

- `/collate <topic|paper>` — synthesise the already-ingested `sources/` + `notes/` for
  a topic into a single page, auto-detecting **paper vs concept** → `papers/<slug>.md`
  or `concepts/<slug>.md` (weaving Zotero annotations in as `[!note]`/`[!question]`
  callouts); updates an existing page in place when a new source is added. Ingest first
  via the helper skills, then hand off to `/edit` for co-editing.
- `/edit <page path>` — co-edit a `papers/` or `concepts/` page in place: action
  `@claude: ...` comments, follow chat instructions, or build on the user's
  own edits; grounded only in the page's cited sources, gaps flagged not invented
- `/ask <question>` — retrieve relevant notes, synthesise a cited answer, and flag
  gaps in the base (optionally web-searching what's missing)
- `/retrieve <topic>` — list the notes relevant to a topic (file + one-line why)
  across all four dirs; no synthesis
- `/autoexplore <query>` — autonomous concept-web builder: search papers + the
  credibility-scored web, read papers full-text (via the pip `prior` package —
  `explore_lit.py` + `fulltext_lit.py`, no `../prior` checkout), decompose into an interlinked
  web of `papers/<slug>.md` + `concepts/<slug>.md` pages (vault-style type subfolders), and
  finish with a synthesis page. **Never writes the personal base**: standalone →
  `explore_library/` (one accumulating corpus, **separately indexed** — `--corpus explore`);
  when invoked by `/curriculum` → `course/<slug>/library/` (`--hops 0`, **not** indexed).
  During a build, dangling `[[wikilinks]]` are resolved against `<dest>` with the index-free
  `retrieve_cli --resolve-dir` (always fresh, no per-link reindex). Work artifacts (corpus
  JSONL, logs) go to `<dest>/.work/` (gitignored); full-text renders go to `<dest>/sources/`.
- **A learning course** lives under `course/<slug>/` and is built + driven by a
  three-stage pipeline (`/goal` → `/curriculum` → `/tutor`), like a university course:
  - `/goal <topic> [by <deadline>] [<H> h/week]` — set the goal: define the **target**
    and **scope** (in/out), audit the knowledge base, and classify coverage
    (covered/pulled/revisit/untested/missing) → `course/<slug>/goal.md`. On completion
    it **auto-hands off to `/curriculum <slug>`** (the two stages are linked — a goal
    always builds its curriculum). `/goal edit <slug>` adjusts it.
  - `/curriculum <slug>` — build the curriculum on that goal: **build a concept web of
    vetted resources via `/autoexplore`** (papers read full-text + Wikipedia + blogs +
    tutorials, decomposed into an interlinked web of `concepts/`+`papers/` pages), sequence them into
    modules (foundational→core→advanced), schedule against the timeline, compile a cited doc
    per module, and initialize progress → `course/<slug>/` (`plan.md` + `schedule.md` +
    `modules/<n>-<slug>.md` + `progress.md`). **The concept web goes to the per-course library
    `course/<slug>/library/`** (one library per course, not in the personal base or the
    index — `/autoexplore` runs with `--hops 0` and is told never to write the personal base);
    modules cite `../library/…` and `plan.md` cites `library/…`. Each pulled resource records
    its **canonical URL** so `/tutor` can hand the learner an actual reading list. Orchestrates
    `/autoexplore`, `/web`, `/alphaxiv`, `/collate`, `/retrieve`.
  - `/tutor <slug>` — learn **session by session**, one scheduled hour-block at a time
    (`## Week W · Hour H`; the week's hours are a budget, not a per-day rate). For each
    block: (1) present a **reading list** of the session's *actual* resources — paper /
    blog / Wikipedia **links** to go read and annotate in Zotero / Notion / Obsidian —
    each with a one-line TLDR of why it's recommended and what you'll learn, plus the
    `library/` summary as a quick-browse; (2) **teach** the session's module content;
    (3) **suggest ingesting** the session's material into the personal base (`/zotero`,
    `/notion`, `/obsidian`, `/alphaxiv`, `/web`) — **in prose, no pop-up box** —
    recommending a filename close to the real title (e.g. *attention is all you need*)
    and, if the resource may already exist in `papers/`/`concepts/`/`sources/`,
    suggesting an **update** (re-ingest for new annotations, or re-collate) instead of a
    duplicate; (4) if the learner opted to **test**, drill **adaptive flashcards**
    (streak-graded spaced repetition + Bloom escalation: remember→understand→apply→
    analyze→evaluate, scored confident/partial/wrong) and update the knowledge level from
    both the curriculum material and what's now in the personal base; if they opted out,
    use an **honor system** — trust that ingested material was read and update the
    knowledge level from the new personal-base material alone; (5) recap, suggest next
    steps, and **advance to the next hour-block/module**. Tracks per-item/module/course mastery
    → `course/<slug>/progress.md`, synced into `goal.md`, and **suggests promoting
    mastered `library/` sources into the personal `sources/`**. Modes: next / `hour <N>`
    / `review` / `drill [module|topic]`. First run sets the test-vs-honor preference and
    the opt-in `/edit` re-test cadence (`session-end` | `after-3-edits` | `never`).
- `/zotero`, `/notion`, `/obsidian`, `/alphaxiv`, `/web` — **helper** ingestion skills
  (invoked by `/collate` / `/curriculum`, or run directly): a pdf → `sources/`
  (+ annotations → `notes/`);
  a note → `notes/`; an arXiv ID/URL → `sources/` via the AlphaXiv API; a vetted web
  page (Wikipedia/blog/tutorial/docs) → `sources/web_*` with a **credibility score**.
  All five are working: `/zotero` extracts via the Zotero MCP plus the local
  `pdf-tools` MCP server (`.claude/src/ingestion/pdf_tools.py` — body text + ink
  annotations); `/notion` fetches live via the Notion MCP or reads a local export;
  `/obsidian` reads a local `.md`. **Note:** `/alphaxiv` is *not* used inside `/autoexplore` —
  that skill renders full paper text via `fulltext_lit.py` and writes `fulltext_source`
  files directly to `<dest>/sources/`, which supersedes the abstract-only alphaxiv output.

Skills live in `.claude/skills/`.

## Page conventions

Shared rules for writing `papers/` and `concepts/` pages — `/collate` (and
`/curriculum`'s module docs) follow these (and `/edit`/`/ask` follow the relevant
ones). They live here, in
one place, so the skills don't each duplicate them; if this section isn't already in
context when a skill runs, `Read` AGENTS.md before writing.

- **Grounding & citations.** Neutral encyclopedic tone, no first person, no facts
  unsupported by the cited files. Cite each claim inline with a relative link to the
  `sources/`/`notes/`/`papers/` file it came from (e.g.
  `... ([ReAct](../sources/zotero_react.md))`). The `sources:` frontmatter lists only
  files actually cited in the body. Web sources (`sources/web_*`, pulled by `/web`)
  carry a `credibility` score/tier in their frontmatter so any fact drawn from them is
  auditable; prefer canonical/reputable sources and never cite unattributable content.
- **Mathematics.** Be mathematical where the material is — define the key quantities
  and include the **critical equations/derivations** needed to understand it (with a
  brief explanation of each step), grounded in the sources, never invented. Write all
  math in **LaTeX** so it renders in Obsidian and VS Code: inline `$ ... $`, display
  `$$ ... $$`; use LaTeX for every symbol/expression, not plain text or Unicode (e.g.
  `$\sqrt{d_k}$`, not `sqrt(d_k)`).
- **Cross-linking.** Link existing pages under a "Related …" section with relative
  links; `related_papers`/`related_concepts` reference only items that already have
  pages. List page-worthy but not-yet-written topics as `[[wikilinks]]`.
- **Review (wrap-up).** After writing: (1) report what was done and any material left
  out; (2) ask the user whether they're happy or want to co-edit — loop via
  `/edit <page>` until they're happy. **Do not reindex manually** — the background
  poller rebuilds the index automatically after edits settle, and any query lazily
  rebuilds if needed.

## Retrieval (`.claude/src/retrieve/` + the `/retrieve` skill)

Retrieval is split between **pure Python** (lexical search + index, no LLM) and
the **`/retrieve` skill** (the wikilink-following judgement, done by Claude):

**Python — `.claude/src/retrieve/` (needs no API key):**
- `index.py` — persists a BM25 index + slug→metadata/link table under `.index/`
  (gitignored), auto-rebuilt when the corpus changes. A `Corpus` is a named set of dirs +
  its own index file, so there are **two independent indexes**: `base` (the personal vault —
  `sources/`, `notes/`, `papers/`, `concepts/` + `course/` docs, excl. `library/`;
  `.index/bm25.pkl`) and `explore` (the standalone `explore_library/{sources,papers,concepts}/`;
  `.index/explore_library.pkl`). Per-course `library/` dirs are indexed by **neither** — they
  resolve by filesystem. Backend is pluggable (`BM25Index` now; `MilvusIndex` stub).
- `retriever.py` — `retrieve(query)` returns the BM25 **seed** notes;
  `resolve(link)` maps a wikilink/slug to its note file (`None` if dangling).
- `config.py:RetrievalConfig` — `retriever`, `top_k`.
- CLI `.claude/src/retrieve_cli.py`: `--retrieve "<query>"` (seeds, `file<TAB>title`),
  `--resolve <link>…` (link→file via the index), `--reindex`. All take `--corpus base|explore`
  (default `base`) to pick which index. Plus `--resolve-dir <dir> <link>…` — an **index-free**
  filesystem resolver (`<dir>/{concepts,papers,sources}/<slug>.md`) for unindexed per-course
  `library/` dirs, used by the `/autoexplore` closure loop.

**`/retrieve` skill (no API key — Claude reads the notes):** gets seeds from
`--retrieve`, then expands by reading each note and following only the
`[[wikilinks]]` it judges relevant (resolving them via `--resolve`), and returns
the relevant notes as files + a one-line why each. Used directly, and as the
gathering step for `/collate` and `/ask`.

## How to run

Setup (once):

```bash
python -m venv .venv && .venv/bin/pip install -r .claude/requirements.txt
```

No API key is required: the Python side is pure BM25, and the skills run inside
Claude Code using its own auth.

**Running the Python tooling — always via `sh .claude/src/pyrun`.** The skills (and the
examples below) never call `.venv/bin/python` directly — they go through the thin launcher
`.claude/src/pyrun`, which resolves the repo root and calls `.venv/bin/python` regardless of
the working directory. Usage: `sh .claude/src/pyrun [--need <pkg>] <script.py> [args…]`
(the `--need` flag is accepted but ignored — kept so existing call sites don't break).

Day to day, the system is driven through Claude Code skills. Open a source in Zotero / Notion / Obsidian, then work the loop:

```text
/zotero ReAct                                 # ingest a Zotero pdf + annotations → sources/ + notes/
/collate ReAct                                # synthesise sources + notes → papers/react.md or concepts/…
/edit papers/react.md                         # co-edit a page: comments, chat, or direct edits
/ask "how does ReAct reduce hallucination?"   # cited answer from the base, with gaps flagged
/retrieve RLHF                                # just list the notes relevant to a topic
```

The retrieval index is pure Python (no API key) and can also be driven directly:

```bash
sh .claude/src/pyrun .claude/src/retrieve_cli.py --reindex                    # rebuild after pages change
sh .claude/src/pyrun .claude/src/retrieve_cli.py --retrieve "RLHF reward model"
sh .claude/src/pyrun .claude/src/retrieve_cli.py --resolve "tool use"         # wikilink/slug → file
```

### Background reindexing

You rarely need `--reindex` by hand. A `SessionStart` hook
(`.claude/settings.json`) launches `.claude/src/reindex_poller.py`, a stdlib-only poller
that watches `sources/`, `notes/`, `papers/`, `concepts/`, `course/` and rebuilds the index a
few minutes **after edits settle** — so a burst of page edits coalesces into one
rebuild and nothing blocks while you work. A `SessionEnd` hook stops it. It's
idempotent (one poller at a time) and cross-platform. Manage it directly with:

```bash
sh .claude/src/pyrun .claude/src/reindex_poller.py --status     # running?
sh .claude/src/pyrun .claude/src/reindex_poller.py --stop       # stop it
sh .claude/src/pyrun .claude/src/reindex_poller.py --start      # start it (the hook does this for you)
```

Tunables (env): `REINDEX_POLL_INTERVAL` (60s), `REINDEX_QUIET_PERIOD` (180s),
`REINDEX_MAX_IDLE` (1h self-exit). Even if the poller isn't running, the index
still auto-rebuilds lazily on the next query when it detects the corpus changed.

## File structure

All dev tooling (including templates) lives under `.claude/`. `README.md`,
`BLOG.md`, `ROADMAP.md`, and `LICENSE` stay at the root for GitHub. The repo can sit at the root of an Obsidian
vault or as a subfolder inside one — either works; Obsidian hides `.claude/` as a
dot-prefixed directory.

| Path | What |
|------|------|
| `sources/` | Personal ingested objective text (`zotero_*`, `alphaxiv_*`, `web_*`) — your curated base, indexed |
| `course/<slug>/library/{sources,papers,concepts}/` | **Per-course library** — the concept web `/curriculum` builds for this course via `/autoexplore` (vault-style type subfolders), **not indexed** (resolved by filesystem via `--resolve-dir`); `sources/` holds both structured `alphaxiv_*`/`web_*` files and raw full-text renders (`<title-slug>.md`); each source records its canonical URL for `/tutor`'s reading list; graduates into `sources/` when `/tutor` promotes a mastered item. Work artifacts (JSONL, logs) in `.work/` (gitignored). |
| `explore_library/{sources,papers,concepts}/` | **Standalone `/autoexplore` corpus** — one *accumulating* concept web (not per-query) built for ad-hoc queries, **separately indexed** (`.index/explore_library.pkl`, queried via `--corpus explore`) so it scales on its own; never the personal base; `sources/` holds structured `alphaxiv_*`/`web_*` files and full-text renders; promote into personal `sources/`/`papers/`/`concepts/` by hand if wanted. Work artifacts (JSONL, logs) in `.work/` (gitignored). |
| `notes/` | Ingested personal notes + pdf annotations (`zotero_*`, `notion_*`, `obsidian_*`) |
| `papers/` | Paper pages (objective summary + personal notes) |
| `concepts/` | Concept pages synthesised across the base |
| `course/<slug>/` | A learning course: `goal.md` (/goal) + `plan.md`·`schedule.md`·`modules/*.md`·`library/` (/curriculum) + `progress.md` (/tutor) |
| `.claude/Templates/` | Page/source templates (`source`, `note`, `paper`, `concept`, `web_source`, `goal`, `curriculum`, `module`, `progress`) |
| `.claude/CLAUDE.md` | Claude Code's auto-loaded memory; imports `@AGENTS.md` |
| `.claude/AGENTS.md` | This file — architecture and conventions |
| `.claude/requirements.txt` | Python deps for the retrieval tooling |
| `.claude/src/pyrun` | Thin Python launcher (POSIX `sh`) — resolves repo root and calls `.venv/bin/python`; all skills invoke scripts via `sh .claude/src/pyrun …` |
| `.claude/src/retrieve/` | Configurable retrieval pipeline (BM25 index + lookup) |
| `.claude/src/retrieve_cli.py` | Thin CLI over `.claude/src/retrieve/` (`--retrieve`, `--resolve`, `--resolve-dir` for unindexed library dirs, `--reindex`) |
| `.claude/src/explore_lit.py` | Literature scoper wrapper (papers via the pip-installed `prior` package → JSONL) |
| `.claude/src/fulltext_lit.py` | Full-text render wrapper (papers → Markdown via `prior.fulltext`; replaces the old `prior/scripts/fullpaper.py`, no `../prior` checkout) |
| `.claude/src/ingestion/pdf_tools.py` | `pdf-tools` MCP server (FastMCP) for `/zotero` — `extract_pdf_text` (body text, page by page) + `extract_ink_annotations` (handwritten strokes → PNG crops in `notes/`) |
| `.claude/src/resources/` | Web resource-pull engine (Wikipedia client, credibility tiers, registries) |
| `.claude/src/resources_cli.py` | CLI over `resources/` (`--wikipedia`, `--wiki-page`, `--score`, `--papers`) |
| `.claude/src/reindex_poller.py` | Background polling reindexer (launched by the `SessionStart` hook) |
| `.claude/skills/` | Claude Code skills (`/collate`, `/edit`, `/ask`, `/retrieve`, `/goal`, `/curriculum`, `/tutor`, `/autoexplore`, ingestion helpers) |
| `.claude/src/curriculum_utils.py` | Pure-stdlib course logic: goal/progress parsing, streak-graded queue, Bloom, mastery |
| `.claude/settings.json` | Team hooks — `SessionStart`/`SessionEnd` start/stop the reindexer; permissions allowlist for auto-approved writes and shell commands |
| `.mcp.json` | Project MCP servers — `zotero` (`zotero-mcp-server`, local Zotero), `pdf-tools` (`pdf_tools.py`), `notion` (Notion HTTP MCP) |
| `.index/` | Generated BM25 indexes (`bm25.pkl` = personal base, `explore_library.pkl` = `explore_library/`) + poller runtime state (gitignored) |

## Conventions

- Python 3.11+, snake_case functions, PascalCase classes
- Page-writing rules (citations, math/LaTeX, cross-linking, wrap-up) live in
  **Page conventions** above
- Branches: `name/feature` — one session per branch, PR to merge
- Do not commit `.env` or API keys
- Do not push directly to `main`
- **Inspect files with the native Read / Grep / Glob tools, not shell** (`cat`,
  `head`, `tail`, `grep`, `find`, `awk`, `sed`, `ls`). Claude Code auto-approves a
  *single* read-only command, but it prompts the user on **compound lines** (`a && b`,
  pipes, `for…do…done`, `if…fi`, heredocs) and on `awk`/`python -c` one-liners — so
  bundling trivial reads into a shell pipeline forces needless approvals. One native
  tool call per inspection instead; reserve `Bash` for the allowlisted project scripts
  (`.claude/src/*.py`, `.claude/skills/**/scripts/*.py`) and genuinely shell-only work
  (git, `cp`, `mkdir`). This keeps the permission prompts limited to commands that
  actually mutate state or run arbitrary code.
- **Run allowlisted scripts as a *single* command — never chain a verification onto
  them.** The allowlist matches each sub-command of a compound line independently, so
  `script … ; python -c "json.load(…)"` re-prompts even when `script` is allowed: the
  `python -c` half isn't allowlisted (and shouldn't be — it's arbitrary code). These
  scripts print to **stdout**, which comes straight back in the tool result — so run the
  bare command and read its output there; do **not** redirect to a scratch file and
  `python -c`/`cat` it back. If output genuinely must land on disk for a downstream step,
  write it to `<dest>/.work/` (gitignored), not the session scratchpad or a `>` redirect.
- **Never append `2>&1` to `pyrun` calls.** The Bash tool already captures both stdout
  and stderr; adding `2>&1` causes the allowlist pattern `Bash(sh .claude/src/pyrun:*)`
  to fail to match (shell redirections break the pattern), forcing an unnecessary
  permission prompt.
- **Never run `sh .claude/src/pyrun … -c "…"` one-liners.** The `-c` flag with inline
  Python (e.g. to find the interpreter or check a dep) always triggers a permission
  prompt because the semicolons inside the string look like compound commands. Use a
  script file instead, or just trust `pyrun` — it already resolves the correct
  interpreter.

## Off-limits

- `.env` — never commit
- `main` branch — PR only

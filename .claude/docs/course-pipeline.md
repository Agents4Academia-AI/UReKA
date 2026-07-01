# Course pipeline — mechanics & nuances

Deep-dive reference for the learning course (`/goal` → `/curriculum` → `/tutor`). `AGENTS.md` keeps the one-paragraph version; the subtle behaviour that's easy to forget lives here. Source of truth is always the skill files under `.claude/skills/{goal,curriculum,tutor}/SKILL.md` — this doc explains *why* and flags the gaps.

---

## The two stores (the distinction the whole design hinges on)

| Store | What | Indexed by BM25? | Lifetime |
|---|---|---|---|
| `sources/`, `notes/`, `papers/`, `concepts/` | **Personal KB** — your durable, searchable base | ✅ yes | permanent |
| `course/<slug>/library/` | **Per-course library** — objective material fetched *for this course* | ❌ **no** | per-course; reused if found, graduates on mastery |
| `course/<slug>/` | The course itself (`goal.md`, `plan.md`, `schedule.md`, `modules/`, `progress.md`) | `course/` is watched by the reindex poller | per-course |

The library is **per-course**: `course/<slug>/library/` with type-subfolders `sources/`, `papers/`, `concepts/` (same layout as the personal vault). Module docs cite it at `../library/{sources,papers,concepts}/<slug>.md`; `plan.md` at `library/{sources,papers,concepts}/<slug>.md`.

**Why two stores:** fetched course material is *not* dumped into your indexed base. It sits in the per-course library until you prove you've absorbed it; then `/tutor` offers to **promote** it into `sources/`. This keeps the searchable KB free of material you only skimmed once.

---

## What `/tutor` actually teaches from

`/tutor` **never opens a PDF or fetches a URL** — its allowed-tools are only
`Read, Write(course/**), Write(sources/**), Glob, date, cp`. There is no `WebFetch`
and no PDF tool. Two consequences:

1. **The lecture is the compiled module doc.** Step 5 (Teach) reads straight from
   `course/<slug>/modules/<n>-<slug>.md` and synthesises it; flashcards are generated
   live from that same doc. "Never invent" — it teaches only what the cited module
   content covers.
2. **The reading list points at the *real* sources.** Step 4 hands the learner the
   day's actual paper / blog / Wikipedia **links** (pulled from each
   `library/<file>.md` frontmatter `url:` / `source_links:`) to go download and
   annotate themselves in Zotero / Notion / Obsidian. The `library/` summary is
   offered only as a quick-browse.

### How complete is the underlying material? It depends on source type

`/curriculum` runs `/autoexplore` to populate the library. `/autoexplore` fetches each source and full-text renders papers via `fulltext_lit.py` (arXiv / OA PDF / Unpaywall / publisher cascade). Library sources therefore differ in depth like this:

```
PAPER (arXiv/OA)     →  fulltext_lit.py  →  full Markdown render             ← COMPLETE
PAPER (paywalled)    →  falls back to     →  abstract + AI overview only      ← THIN
                        alphaxiv_*.md
WIKIPEDIA            →  /web wiki        →  full plain-text extract           ← COMPLETE
BLOG / tutorial      →  /web url         →  full WebFetch'd markdown          ← COMPLETE
```

Full-text renders land at `course/<slug>/library/sources/<title-slug>.md`; the structured alphaxiv source (`alphaxiv_<slug>.md`) is kept alongside as a fallback. For most arXiv papers the render is complete; for paywalled-only papers `/tutor` is limited to the abstract. This is exactly why the reading-list + ingest steps exist: annotations and personal understanding come from reading the primary source yourself, then ingesting those annotations.

---

## `testing_mode`: test vs honor

Set on `/tutor`'s first run (Step 2), stored in `goal.md` frontmatter
(`testing_mode: unset | test | honor`), overridable per session.

- **`test`** — adaptive flashcards, scored `confident` / `partial` / `wrong`. Mastery
  is *measured*.
- **`honor`** — no flashcards. Items the learner ingested into the personal base are
  marked `Score: read` (the honor marker), `Last tested` = today, `Streak` stays 0.
  Trust is that you only ingest what you actually finished.

**Key asymmetry:** `read` (honor) ≠ `confident` (tested).
- `coverage_pct` counts **confident only** — honor `read` items do **not** raise it.
- In the goal audit, `read` items map to **`untested`** (read, not tested), not
  `covered`. Switching to `test` mode later is how you convert them to true coverage.

---

## Spaced repetition (test track)

An item is **due** when `days_since(Last tested) ≥ interval(streak)`:

| Streak | Retest interval |
|--------|-----------------|
| 0 | 1 day |
| 1 | 3 days |
| 2 | 7 days |
| 3+ | 14 days |

Queue priority (first → last): **wrong → partial → untested → confident & due**.
Confident-but-not-due items are skipped; within a tier, oldest `Last tested` first.
Streak: `confident` → +1; `partial`/`wrong` → reset to 0.

- **today** — due items from today's module + resurfaced due items from *mastered*
  earlier modules.
- **review** — every due item across all modules (skips teaching/ingest).
- **drill [module|topic]** — every item in the named module/topic, due or not.

---

## Bloom level — what it is and how it's set

Each item carries a **Bloom level** (a `Bloom` column in `progress.md`'s Item Progress; "Bloom reached" in the Module Mastery table). It tracks **depth of understanding**, separate from whether you got the answer right.

The ladder:

```
remember → understand → apply → analyze → evaluate
(recall a   (explain    (use it   (break it   (judge /
 definition) it)         in a new   apart,      compare,
                         problem)   relate)     critique)
```

### It is NOT calculated — there's no formula

"Bloom reached" is a **state advanced by judgment**, driven by two things together (`tutor/SKILL.md` Steps 7A.1–7A.2):

1. **The level of the question posed.** When `/tutor` generates a flashcard, it picks
   a level — roughly tied to the question *type*:

   | Question type | Bloom level |
   |---|---|
   | Definition | remember |
   | Mechanism | understand |
   | Application | apply |
   | Comparison | analyze |
   | (judge / critique / trade-off) | evaluate |

2. **Whether you answered it `confident`.** The rule: **raise the item's Bloom reached
   when the learner correctly answers a prompt one level higher than its current
   level.** A `partial`/`wrong` answer does not raise it (it resets the *streak*,
   which is a separate axis).

### How it escalates

- An item sits at its current level → tutor poses a card at that level.
- If the item's **module is already mastered**, tutor deliberately poses the **next
  level up** to push depth (a `remember` definition becomes an `apply`/`analyze`
  prompt).
- A `confident` answer at the higher level bumps "Bloom reached" up one rung.
- The **Module Mastery** "Bloom reached" is the **max** across that module's items —
  the deepest rung any item has hit. Reported in the end-of-module milestone recap.

So two items can both be `confident` but at different depths: one at `remember` (you can recite it), one at `analyze` (you can pull it apart). Bloom is what distinguishes them. Mastery % and streak gate *whether* the tutor escalates; the correct answer at the harder level is what actually moves Bloom.

---

## Mastery gating & promotion to the personal base

**Module mastered** ⟺ ≥80% of its items `confident`, each with streak ≥2. A downstream module's items stay `locked` until its prerequisite module is mastered. Gating is **advisory** — the tutor recommends staying but lets you advance.

**Promotion** (Step 10) graduates a `course/<slug>/library/<file>.md` into the
personal `sources/`. A file is **eligible** when any of:

- **Covered** — its backing items are all `confident` (100%), even before streaks hit
  the ≥2 mastered bar. Offered as soon as a module hits 100% confident.
- **Mastered** — its module is formally `mastered`.
- **Ingested + annotated** — the learner ingested it into the personal base this
  course (the main path on the honor track).

On **yes**: `cp course/<slug>/library/<file>.md sources/<file>.md` (the library copy
stays so the course still references it). Once in `sources/` it enters the index, so a future `/goal` audit finds it as `covered`/`untested` — no re-fetch — and it can be synthesised via `/collate`. Never promote silently; never promote material that isn't at least 100% covered (test) or ingested+read (honor). If the learner already ingested the real source via Step 6, that personal page is the durable copy and no library promotion is needed.

---

## `coverage_pct` vs `course_mastery_pct`

Both in `progress.md` frontmatter, synced into `goal.md`:

- `coverage_pct` = **confident** items ÷ all items (honor `read` items excluded).
- `course_mastery_pct` = **mean of per-module mastery %**.

---

## What "end of a session" means (two different sessions)

The phrase appears in two unrelated contexts.

### 1. A `/tutor` learning session = one sitting of the skill

"End of the session" = the flashcard **question loop finishes**, which happens when the **queue empties** or the learner types **"done"**. No timer — it's the skill's own control flow. The end-of-session steps (recap → write progress → promotion offer → advance) run after that.

### 2. A Claude Code session = the whole CLI session

Bounded by the harness hooks in `.claude/settings.json`:

```
SessionStart hook ─▶ reindex_poller.py --start   (session begins)
SessionEnd   hook ─▶ reindex_poller.py --stop    (session ends)
```

The `tutor_prompt_mode: session-end` cadence is about *this* session: when `/edit` finishes on a page a course covers, it reminds you **once per CLI session** to re-run `/tutor`. It tracks "already reminded" with the flag file `course/<slug>/.session_reminded` (and `.edit_count` for the `after-3-edits` mode). The `SessionStart` hook deletes both flag files so reminders reset each session.

---


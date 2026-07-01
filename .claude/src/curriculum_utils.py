"""
Utility helpers for the /goal, /curriculum and /tutor skills.
Pure stdlib — no API key, no LLM required.

These functions are the reference implementation for the file formats and the
spaced-repetition / mastery logic documented in the skill SKILL.md files. The
LLM writes the questions and reframes them by Bloom level; this module only
computes due-ness, target Bloom level, queue order, and mastery aggregates.

File model (one folder per course under `course/<slug>/`):
  goal.md      — /goal:       Target, Scope, Subgoals, Knowledge Audit
  plan.md      — /curriculum: Module Map, Resources, Weekly Plan
  schedule.md  — /curriculum: day-by-day sessions
  modules/     — /curriculum: compiled cited learning content
  progress.md  — /tutor:      Module Mastery + Item Progress (the spaced-rep substrate)
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = {"covered", "pulled", "revisit", "untested", "missing"}
VALID_SCORES = {"confident", "partial", "wrong", "untested", "—"}
VALID_PROMPT_MODES = {"session-end", "after-3-edits", "never", "unset"}

# Bloom's taxonomy levels, ordered from shallow to deep. /tutor escalates a
# mastered item to the next level up to deepen understanding over the course.
BLOOM_ORDER = ["remember", "understand", "apply", "analyze", "evaluate"]
VALID_BLOOM = set(BLOOM_ORDER)

# goal.md (written by /goal)
REQUIRED_GOAL_FIELDS = {
    "title", "type", "topic", "created", "deadline",
    "hours_per_week", "status", "tutor_prompt_mode",
}
REQUIRED_GOAL_SECTIONS = {"Target", "Scope", "Subgoals", "Knowledge Audit"}

# progress.md (written by /tutor)
REQUIRED_PROGRESS_FIELDS = {"curriculum", "last_updated", "coverage_pct"}

# Streak-graded spaced repetition: an item's retest interval (in days) grows
# with its confidence streak. Shaky items return soon; mastered items rarely.
# Streaks >= max key are capped at the longest interval.
RETEST_INTERVALS = {0: 1, 1: 3, 2: 7, 3: 14}
RETEST_DAYS = RETEST_INTERVALS[max(RETEST_INTERVALS)]  # 14 — longest interval / cap

# A module is "mastered" once this fraction of its items are confident, each
# with at least this many consecutive confident scores.
MASTERY_THRESHOLD = 0.80
MASTERY_MIN_STREAK = 2

# ---------------------------------------------------------------------------
# Low-level parsing helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract key: value pairs from YAML frontmatter (between --- delimiters)."""
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def _extract_h2_sections(text: str) -> set[str]:
    """Return the set of ## heading titles in a markdown document."""
    return {m.group(1).strip() for m in re.finditer(r"^## (.+)$", text, re.MULTILINE)}


def _parse_table_after_heading(text: str, heading: str) -> list[dict[str, str]]:
    """
    Find the first markdown table that follows a heading (any level) containing
    `heading`, and parse it into a list of row dicts keyed by column header.
    Returns [] if no matching heading or table is found.
    """
    pattern = re.compile(rf"^#+\s+{re.escape(heading)}", re.MULTILINE)
    m = pattern.search(text)
    if not m:
        return []
    block = text[m.end():]
    table_lines: list[str] = []
    for line in block.splitlines():
        if line.strip().startswith("|"):
            table_lines.append(line.strip())
        elif table_lines:
            break
    if len(table_lines) < 3:
        return []
    headers = [h.strip() for h in table_lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:  # skip separator row
        values = [v.strip() for v in line.strip("|").split("|")]
        if len(values) == len(headers):
            rows.append(dict(zip(headers, values)))
    return rows


def _parse_date(raw: str) -> date | None:
    """Parse a YYYY-MM-DD string; return None for '—', empty, or unparseable."""
    if not raw or raw.strip() in ("—", ""):
        return None
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _streak_of(row: dict) -> int:
    """Read an item's confidence streak from its row; default 0 if absent/bad."""
    try:
        return max(0, int(str(row.get("Streak", "0")).strip()))
    except (ValueError, TypeError):
        return 0

# ---------------------------------------------------------------------------
# goal.md
# ---------------------------------------------------------------------------

def parse_goal_md(path: str | Path) -> dict:
    """
    Parse and validate a goal.md file (written by /goal).

    Returns a dict with:
      'frontmatter'  — dict of frontmatter key/value pairs
      'sections'     — set of ## section titles present
      'audit_rows'   — list of dicts from the Knowledge Audit table
      'errors'       — list of validation error strings (empty = valid)
    """
    text = Path(path).read_text()
    fm = _parse_frontmatter(text)
    sections = _extract_h2_sections(text)
    audit_rows = _parse_table_after_heading(text, "Knowledge Audit")
    errors: list[str] = []

    for field in REQUIRED_GOAL_FIELDS:
        if field not in fm:
            errors.append(f"missing frontmatter field: {field!r}")

    for section in REQUIRED_GOAL_SECTIONS:
        if section not in sections:
            errors.append(f"missing section: '## {section}'")

    for row in audit_rows:
        status = row.get("Status", "")
        if status not in VALID_STATUSES:
            errors.append(f"invalid Status {status!r} for item {row.get('Item')!r}")
        score = row.get("Score", "")
        if score not in VALID_SCORES:
            errors.append(f"invalid Score {score!r} for item {row.get('Item')!r}")

    mode = fm.get("tutor_prompt_mode", "")
    if mode and mode not in VALID_PROMPT_MODES:
        errors.append(f"invalid tutor_prompt_mode: {mode!r}")

    return {"frontmatter": fm, "sections": sections, "audit_rows": audit_rows, "errors": errors}

# ---------------------------------------------------------------------------
# progress.md
# ---------------------------------------------------------------------------

def parse_progress_md(path: str | Path) -> dict:
    """
    Parse and validate a progress.md file (written by /tutor).

    Returns a dict with:
      'frontmatter' — dict of frontmatter key/value pairs
      'modules'     — list of dicts from the Module Mastery table
      'items'       — list of dicts from the Item Progress table
      'errors'      — list of validation error strings (empty = valid)
    """
    text = Path(path).read_text()
    fm = _parse_frontmatter(text)
    modules = _parse_table_after_heading(text, "Module Mastery")
    items = _parse_table_after_heading(text, "Item Progress")
    errors: list[str] = []

    for field in REQUIRED_PROGRESS_FIELDS:
        if field not in fm:
            errors.append(f"missing frontmatter field: {field!r}")

    if "coverage_pct" in fm:
        pct_str = fm["coverage_pct"].rstrip("%")
        try:
            pct = int(pct_str)
            if not 0 <= pct <= 100:
                errors.append(f"coverage_pct out of range: {pct}")
        except ValueError:
            errors.append(f"coverage_pct not an integer: {fm['coverage_pct']!r}")

    for row in items:
        score = row.get("Score", "")
        if score not in VALID_SCORES:
            errors.append(f"invalid Score {score!r} for item {row.get('Item')!r}")
        bloom = row.get("Bloom", "—")
        if bloom not in VALID_BLOOM and bloom not in ("—", ""):
            errors.append(f"invalid Bloom {bloom!r} for item {row.get('Item')!r}")

    return {"frontmatter": fm, "modules": modules, "items": items, "errors": errors}

# ---------------------------------------------------------------------------
# Spaced repetition — streak-graded retest scheduling
# ---------------------------------------------------------------------------

def retest_interval(streak: int) -> int:
    """Days until a confident item is due again, given its streak (capped)."""
    s = max(0, int(streak))
    return RETEST_INTERVALS.get(s, RETEST_DAYS)


def is_due(row: dict, today: date | None = None) -> bool:
    """
    Whether an item should be tested now.

    wrong / partial / untested (and unknown scores) are always due. A confident
    item is due once `retest_interval(streak)` days have passed since it was last
    tested (an item with no recorded test date is treated as due).
    """
    if today is None:
        today = date.today()
    score = row.get("Score", "untested")
    if score != "confident":
        return True
    lt = _parse_date(row.get("Last tested", "—"))
    if lt is None:
        return True
    return (today - lt).days >= retest_interval(_streak_of(row))


def build_tutor_queue(items: list[dict], today: date | None = None) -> list[dict]:
    """
    Order progress items into the tutor test queue.

    Priority (0 = first in queue):
      0  wrong
      1  partial
      2  untested  (score == 'untested' or '—', or an unknown score)
      3  confident and due per its streak-graded retest interval

    Confident items not yet due (tested more recently than their streak interval
    allows) are excluded entirely.

    Within each priority tier, items with the oldest last-tested date come first
    (None / missing date is treated as maximally old — 9999 days ago).

    Items dict must have keys 'Score' and 'Last tested' (and optionally 'Streak').
    Does not mutate the input list.
    """
    if today is None:
        today = date.today()

    def _tier(row: dict) -> int | None:
        score = row.get("Score", "untested")
        if score == "wrong":
            return 0
        if score == "partial":
            return 1
        if score in ("untested", "—"):
            return 2
        if score == "confident":
            return 3 if is_due(row, today) else None
        return 2  # unknown score → treat as untested

    def _age(row: dict) -> int:
        lt = _parse_date(row.get("Last tested", "—"))
        return (today - lt).days if lt else 9999

    queue: list[tuple[int, int, dict]] = []
    for row in items:
        tier = _tier(row)
        if tier is None:
            continue
        queue.append((tier, -_age(row), row))  # negate age so oldest sorts first

    queue.sort(key=lambda x: (x[0], x[1]))
    return [row for _, _, row in queue]

# ---------------------------------------------------------------------------
# Bloom escalation
# ---------------------------------------------------------------------------

def next_bloom(level: str) -> str:
    """Return the next Bloom level up, capped at 'evaluate'.

    An unknown / unset level ('—', '') starts the learner at 'remember'.
    """
    level = (level or "").strip()
    if level not in VALID_BLOOM:
        return BLOOM_ORDER[0]
    idx = BLOOM_ORDER.index(level)
    return BLOOM_ORDER[min(idx + 1, len(BLOOM_ORDER) - 1)]

# ---------------------------------------------------------------------------
# Mastery aggregation
# ---------------------------------------------------------------------------

def coverage_pct(items: list[dict]) -> int:
    """Return (confident count / total count) × 100, rounded to nearest integer."""
    if not items:
        return 0
    n_confident = sum(1 for row in items if row.get("Score") == "confident")
    return round(n_confident / len(items) * 100)


def module_mastery(items_for_module: list[dict]) -> dict:
    """
    Aggregate one module's item rows into a mastery summary.

    Returns a dict with:
      'mastery_pct'   — confident / total × 100 (int)
      'items'         — number of items
      'confident'     — number of confident items
      'bloom_reached' — deepest Bloom level reached across the items ('—' if none)
      'status'        — 'mastered' | 'in-progress' | 'available'

    'mastered' requires `mastery_pct >= MASTERY_THRESHOLD` AND every confident
    item carrying a streak of at least MASTERY_MIN_STREAK. The cross-module
    'locked' state is the caller's concern (it depends on module order), not
    computable from a single module's items.
    """
    total = len(items_for_module)
    if total == 0:
        return {"mastery_pct": 0, "items": 0, "confident": 0,
                "bloom_reached": "—", "status": "available"}

    confident = [r for r in items_for_module if r.get("Score") == "confident"]
    n_conf = len(confident)
    pct = round(n_conf / total * 100)

    # deepest Bloom reached
    reached_idx = -1
    for r in items_for_module:
        b = (r.get("Bloom", "—") or "").strip()
        if b in VALID_BLOOM:
            reached_idx = max(reached_idx, BLOOM_ORDER.index(b))
    bloom_reached = BLOOM_ORDER[reached_idx] if reached_idx >= 0 else "—"

    tested = any(r.get("Score") in ("confident", "partial", "wrong") for r in items_for_module)
    mastered = (
        pct >= round(MASTERY_THRESHOLD * 100)
        and all(_streak_of(r) >= MASTERY_MIN_STREAK for r in confident)
        and n_conf > 0
    )
    status = "mastered" if mastered else ("in-progress" if tested else "available")

    return {"mastery_pct": pct, "items": total, "confident": n_conf,
            "bloom_reached": bloom_reached, "status": status}


def course_mastery(modules: list[dict]) -> int:
    """
    Mean of per-module mastery percentages (the course progress bar).

    Accepts either module_mastery() outputs (key 'mastery_pct') or parsed
    Module Mastery rows (column 'Mastery %'); rows without a numeric value are
    skipped. Equal weight per module regardless of deck size.
    """
    vals: list[int] = []
    for m in modules:
        raw = m.get("mastery_pct", m.get("Mastery %"))
        if raw in (None, "", "—"):
            continue
        try:
            vals.append(int(str(raw).rstrip("%")))
        except (ValueError, TypeError):
            continue
    return round(sum(vals) / len(vals)) if vals else 0

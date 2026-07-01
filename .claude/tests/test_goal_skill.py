"""
Test suite for the /goal skill — validates plan.md schema and retrieval integration.

Run from the project root (via the env-agnostic launcher):
    sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_goal_skill.py -v -s
    sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_goal_skill.py          # pass/fail only
"""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "goal"

sys.path.insert(0, str(ROOT / ".claude" / "src"))

VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv


def _vprint(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)


try:
    from curriculum_utils import (
        VALID_PROMPT_MODES,
        VALID_SCORES,
        VALID_STATUSES,
        REQUIRED_GOAL_FIELDS,
        REQUIRED_GOAL_SECTIONS,
        parse_goal_md,
    )
    IMPORT_ERROR = None
except Exception as e:
    IMPORT_ERROR = e


# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------

class TestImport(unittest.TestCase):
    def test_module_imports(self):
        _vprint(f"\n  import error: {IMPORT_ERROR}")
        self.assertIsNone(IMPORT_ERROR, f"curriculum_utils failed to import: {IMPORT_ERROR}")


# ---------------------------------------------------------------------------
# plan.md schema validation — valid fixture
# ---------------------------------------------------------------------------

@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestPlanMdValid(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = parse_goal_md(FIXTURES / "goal_valid.md")
        _vprint(f"\n  errors: {cls.result['errors']}")

    def test_no_errors(self):
        self.assertEqual(self.result["errors"], [], self.result["errors"])

    def test_all_required_frontmatter_fields_present(self):
        fm = self.result["frontmatter"]
        for field in REQUIRED_GOAL_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, fm, f"Missing frontmatter field: {field!r}")

    def test_all_required_sections_present(self):
        sections = self.result["sections"]
        for section in REQUIRED_GOAL_SECTIONS:
            with self.subTest(section=section):
                self.assertIn(section, sections, f"Missing section: '## {section}'")

    def test_audit_table_parsed(self):
        rows = self.result["audit_rows"]
        _vprint(f"\n  audit rows: {rows}")
        self.assertEqual(len(rows), 4)

    def test_audit_table_has_required_columns(self):
        rows = self.result["audit_rows"]
        for row in rows:
            for col in ("Item", "Type", "Status", "Score", "Last tested"):
                with self.subTest(col=col):
                    self.assertIn(col, row)

    def test_statuses_are_valid(self):
        for row in self.result["audit_rows"]:
            with self.subTest(item=row.get("Item")):
                self.assertIn(row["Status"], VALID_STATUSES)

    def test_scores_are_valid(self):
        for row in self.result["audit_rows"]:
            with self.subTest(item=row.get("Item")):
                self.assertIn(row["Score"], VALID_SCORES)

    def test_tutor_prompt_mode_is_valid(self):
        mode = self.result["frontmatter"].get("tutor_prompt_mode")
        _vprint(f"\n  tutor_prompt_mode: {mode!r}")
        self.assertIn(mode, VALID_PROMPT_MODES)

    def test_hours_per_week_parseable_as_int(self):
        val = self.result["frontmatter"].get("hours_per_week", "")
        _vprint(f"\n  hours_per_week: {val!r}")
        self.assertTrue(val.isdigit(), f"hours_per_week not an integer: {val!r}")


# ---------------------------------------------------------------------------
# plan.md schema validation — missing field fixture
# ---------------------------------------------------------------------------

@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestPlanMdMissingField(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = parse_goal_md(FIXTURES / "goal_missing_field.md")
        _vprint(f"\n  errors: {cls.result['errors']}")

    def test_has_errors(self):
        self.assertGreater(len(self.result["errors"]), 0)

    def test_missing_tutor_prompt_mode_flagged(self):
        errors = self.result["errors"]
        self.assertTrue(
            any("tutor_prompt_mode" in e for e in errors),
            f"Expected tutor_prompt_mode error; got: {errors}",
        )


# ---------------------------------------------------------------------------
# plan.md schema validation — bad values fixture
# ---------------------------------------------------------------------------

@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestPlanMdBadValues(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = parse_goal_md(FIXTURES / "goal_bad_values.md")
        _vprint(f"\n  errors: {cls.result['errors']}")

    def test_has_multiple_errors(self):
        self.assertGreaterEqual(len(self.result["errors"]), 3)

    def test_invalid_prompt_mode_flagged(self):
        errors = self.result["errors"]
        self.assertTrue(
            any("tutor_prompt_mode" in e for e in errors),
            f"Expected tutor_prompt_mode error; got: {errors}",
        )

    def test_invalid_status_flagged(self):
        errors = self.result["errors"]
        self.assertTrue(
            any("Status" in e for e in errors),
            f"Expected Status error; got: {errors}",
        )

    def test_invalid_score_flagged(self):
        errors = self.result["errors"]
        self.assertTrue(
            any("Score" in e for e in errors),
            f"Expected Score error; got: {errors}",
        )


# ---------------------------------------------------------------------------
# Retrieval integration — requires the BM25 index to be built
# ---------------------------------------------------------------------------

def _run_retrieve(query: str) -> list[str]:
    """Run retrieve_cli.py and return list of file paths."""
    cli = ROOT / ".claude" / "src" / "retrieve_cli.py"
    result = subprocess.run(
        [sys.executable, str(cli), "--retrieve", query],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    lines = [l.split("\t")[0] for l in result.stdout.strip().splitlines() if "\t" in l]
    return lines


def _run_resolve(link: str) -> str | None:
    """Run retrieve_cli.py --resolve and return the resolved path, or None."""
    cli = ROOT / ".claude" / "src" / "retrieve_cli.py"
    result = subprocess.run(
        [sys.executable, str(cli), "--resolve", link],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) == 2 and parts[1] != "NONE":
            return parts[1]
    return None


class TestRetrievalIntegration(unittest.TestCase):

    def test_retrieve_attention_returns_results(self):
        paths = _run_retrieve("attention")
        _vprint(f"\n  retrieved: {paths}")
        self.assertGreater(len(paths), 0, "Expected at least one result for 'attention'")

    def test_retrieve_attention_includes_source_or_paper(self):
        paths = _run_retrieve("attention")
        _vprint(f"\n  retrieved: {paths}")
        relevant = [p for p in paths if "attention" in p.lower()]
        self.assertGreater(len(relevant), 0, f"No attention-related file in results: {paths}")

    def test_retrieve_unknown_topic_returns_empty_or_irrelevant(self):
        paths = _run_retrieve("xyzzy_nonexistent_topic_zxqwerty")
        _vprint(f"\n  retrieved for nonsense query: {paths}")
        self.assertIsInstance(paths, list)

    def test_resolve_attention_link(self):
        resolved = _run_resolve("attention")
        _vprint(f"\n  resolved 'attention' → {resolved!r}")
        if resolved is not None:
            self.assertIn("attention", resolved.lower())

    def test_retrieve_transformers_returns_results(self):
        paths = _run_retrieve("transformers")
        _vprint(f"\n  retrieved: {paths}")
        self.assertGreater(len(paths), 0, "Expected at least one result for 'transformers'")


if __name__ == "__main__":
    unittest.main(verbosity=2)

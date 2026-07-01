"""
Test suite for the merged learning-progress logic in curriculum_utils:
Bloom escalation, module mastery, and course-level aggregation.

Run from the project root (via the env-agnostic launcher):
    sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_progress.py -v -s
    sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_progress.py          # pass/fail only
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "progress"

sys.path.insert(0, str(ROOT / ".claude" / "src"))

VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv


def _vprint(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)


try:
    from curriculum_utils import (
        BLOOM_ORDER,
        MASTERY_MIN_STREAK,
        course_mastery,
        module_mastery,
        next_bloom,
        parse_progress_md,
    )
    IMPORT_ERROR = None
except Exception as e:
    IMPORT_ERROR = e


class TestImport(unittest.TestCase):
    def test_module_imports(self):
        _vprint(f"\n  import error: {IMPORT_ERROR}")
        self.assertIsNone(IMPORT_ERROR, f"curriculum_utils failed to import: {IMPORT_ERROR}")


# ---------------------------------------------------------------------------
# Bloom escalation
# ---------------------------------------------------------------------------

@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestNextBloom(unittest.TestCase):

    def test_escalates_one_level(self):
        self.assertEqual(next_bloom("remember"), "understand")
        self.assertEqual(next_bloom("understand"), "apply")
        self.assertEqual(next_bloom("apply"), "analyze")
        self.assertEqual(next_bloom("analyze"), "evaluate")

    def test_caps_at_evaluate(self):
        self.assertEqual(next_bloom("evaluate"), "evaluate")

    def test_unset_starts_at_remember(self):
        self.assertEqual(next_bloom("—"), BLOOM_ORDER[0])
        self.assertEqual(next_bloom(""), BLOOM_ORDER[0])
        self.assertEqual(next_bloom("not-a-level"), BLOOM_ORDER[0])


# ---------------------------------------------------------------------------
# Module mastery
# ---------------------------------------------------------------------------

@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestModuleMastery(unittest.TestCase):

    def test_empty_module_is_available(self):
        m = module_mastery([])
        self.assertEqual(m["status"], "available")
        self.assertEqual(m["mastery_pct"], 0)
        self.assertEqual(m["bloom_reached"], "—")

    def test_all_confident_high_streak_is_mastered(self):
        items = [
            {"Score": "confident", "Bloom": "apply", "Streak": "3"},
            {"Score": "confident", "Bloom": "understand", "Streak": "2"},
        ]
        m = module_mastery(items)
        _vprint(f"\n  mastery: {m}")
        self.assertEqual(m["mastery_pct"], 100)
        self.assertEqual(m["status"], "mastered")
        self.assertEqual(m["bloom_reached"], "apply")  # deepest reached

    def test_confident_but_low_streak_not_mastered(self):
        items = [
            {"Score": "confident", "Bloom": "remember", "Streak": str(MASTERY_MIN_STREAK - 1)},
            {"Score": "confident", "Bloom": "remember", "Streak": "3"},
        ]
        m = module_mastery(items)
        _vprint(f"\n  mastery: {m}")
        self.assertEqual(m["mastery_pct"], 100)
        self.assertNotEqual(m["status"], "mastered")
        self.assertEqual(m["status"], "in-progress")

    def test_below_threshold_is_in_progress(self):
        items = [
            {"Score": "confident", "Bloom": "remember", "Streak": "3"},
            {"Score": "partial", "Bloom": "remember", "Streak": "0"},
            {"Score": "wrong", "Bloom": "remember", "Streak": "0"},
        ]
        m = module_mastery(items)
        _vprint(f"\n  mastery: {m}")
        self.assertEqual(m["mastery_pct"], 33)
        self.assertEqual(m["status"], "in-progress")

    def test_untested_module_is_available(self):
        items = [
            {"Score": "untested", "Bloom": "—", "Streak": "0"},
            {"Score": "untested", "Bloom": "—", "Streak": "0"},
        ]
        m = module_mastery(items)
        self.assertEqual(m["status"], "available")
        self.assertEqual(m["confident"], 0)


# ---------------------------------------------------------------------------
# Course-level aggregation
# ---------------------------------------------------------------------------

@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestCourseMastery(unittest.TestCase):

    def test_mean_of_module_mastery_dicts(self):
        modules = [{"mastery_pct": 100}, {"mastery_pct": 0}]
        self.assertEqual(course_mastery(modules), 50)

    def test_reads_parsed_table_rows(self):
        modules = [{"Mastery %": "80"}, {"Mastery %": "40"}, {"Mastery %": "—"}]
        # '—' row skipped → mean(80, 40) = 60
        self.assertEqual(course_mastery(modules), 60)

    def test_empty_is_zero(self):
        self.assertEqual(course_mastery([]), 0)

    def test_matches_fixture_modules(self):
        prog = parse_progress_md(FIXTURES / "progress_valid.md")
        # fixture modules: 100 and 0 → mean 50
        self.assertEqual(course_mastery(prog["modules"]), 50)


if __name__ == "__main__":
    unittest.main(verbosity=2)

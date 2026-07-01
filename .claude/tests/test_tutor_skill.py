"""
Test suite for the /tutor skill — validates progress.md schema, streak-graded
queue ordering, and coverage percentage calculation.

Run from the project root (via the env-agnostic launcher):
    sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_tutor_skill.py -v -s
    sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_tutor_skill.py          # pass/fail only
"""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "progress"

sys.path.insert(0, str(ROOT / ".claude" / "src"))

VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv

# Fixed "today" used in all queue tests so results are deterministic.
TODAY = date(2026, 6, 23)


def _vprint(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)


try:
    from curriculum_utils import (
        RETEST_INTERVALS,
        VALID_SCORES,
        build_tutor_queue,
        coverage_pct,
        is_due,
        parse_progress_md,
        retest_interval,
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
# progress.md schema — valid fixture
# ---------------------------------------------------------------------------

@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestProgressValid(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = parse_progress_md(FIXTURES / "progress_valid.md")
        _vprint(f"\n  errors: {cls.result['errors']}")

    def test_no_errors(self):
        self.assertEqual(self.result["errors"], [], self.result["errors"])

    def test_required_frontmatter_fields(self):
        fm = self.result["frontmatter"]
        for field in ("curriculum", "last_updated", "coverage_pct"):
            with self.subTest(field=field):
                self.assertIn(field, fm)

    def test_items_parsed(self):
        items = self.result["items"]
        _vprint(f"\n  items: {items}")
        self.assertEqual(len(items), 2)

    def test_modules_parsed(self):
        modules = self.result["modules"]
        _vprint(f"\n  modules: {modules}")
        self.assertEqual(len(modules), 2)

    def test_items_have_required_columns(self):
        for item in self.result["items"]:
            for col in ("Item", "Type", "Module", "Score", "Bloom", "Last tested", "Streak"):
                with self.subTest(col=col):
                    self.assertIn(col, item)

    def test_scores_are_valid(self):
        for item in self.result["items"]:
            with self.subTest(item=item.get("Item")):
                self.assertIn(item["Score"], VALID_SCORES)

    def test_coverage_pct_is_integer_in_range(self):
        pct_str = self.result["frontmatter"]["coverage_pct"].rstrip("%")
        pct = int(pct_str)
        _vprint(f"\n  coverage_pct: {pct}")
        self.assertGreaterEqual(pct, 0)
        self.assertLessEqual(pct, 100)


# ---------------------------------------------------------------------------
# progress.md schema — invalid cases
# ---------------------------------------------------------------------------

@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestProgressInvalid(unittest.TestCase):

    HEADER = ("# Progress — Test\n\n## Item Progress\n\n"
              "| Item | Type | Module | Score | Bloom | Last tested | Streak |\n"
              "|------|------|--------|-------|-------|-------------|--------|\n")

    def _make_file(self, content: str) -> Path:
        """Write content to a tmp file and return its path."""
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".md")
        os.write(fd, content.encode())
        os.close(fd)
        return Path(path)

    def test_coverage_pct_out_of_range_flagged(self):
        path = self._make_file(
            "---\ncurriculum: test\nlast_updated: 2026-06-23\ncoverage_pct: 150\n---\n" + self.HEADER
        )
        result = parse_progress_md(path)
        _vprint(f"\n  errors: {result['errors']}")
        self.assertTrue(any("coverage_pct" in e for e in result["errors"]))
        path.unlink()

    def test_invalid_score_flagged(self):
        path = self._make_file(
            "---\ncurriculum: test\nlast_updated: 2026-06-23\ncoverage_pct: 50\n---\n" + self.HEADER
            + "| thing | concept | 1 | excellent | remember | 2026-06-01 | 0 |\n"
        )
        result = parse_progress_md(path)
        _vprint(f"\n  errors: {result['errors']}")
        self.assertTrue(any("Score" in e for e in result["errors"]))
        path.unlink()

    def test_invalid_bloom_flagged(self):
        path = self._make_file(
            "---\ncurriculum: test\nlast_updated: 2026-06-23\ncoverage_pct: 50\n---\n" + self.HEADER
            + "| thing | concept | 1 | confident | genius | 2026-06-01 | 3 |\n"
        )
        result = parse_progress_md(path)
        _vprint(f"\n  errors: {result['errors']}")
        self.assertTrue(any("Bloom" in e for e in result["errors"]))
        path.unlink()

    def test_missing_curriculum_field_flagged(self):
        path = self._make_file(
            "---\nlast_updated: 2026-06-23\ncoverage_pct: 50\n---\n" + self.HEADER
        )
        result = parse_progress_md(path)
        _vprint(f"\n  errors: {result['errors']}")
        self.assertTrue(any("curriculum" in e for e in result["errors"]))
        path.unlink()


# ---------------------------------------------------------------------------
# Streak-graded retest scheduling
# ---------------------------------------------------------------------------

@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestRetestInterval(unittest.TestCase):

    def test_intervals_grow_with_streak(self):
        self.assertEqual(retest_interval(0), 1)
        self.assertEqual(retest_interval(1), 3)
        self.assertEqual(retest_interval(2), 7)
        self.assertEqual(retest_interval(3), 14)

    def test_high_streak_caps_at_longest(self):
        self.assertEqual(retest_interval(9), RETEST_INTERVALS[max(RETEST_INTERVALS)])

    def test_non_confident_always_due(self):
        for score in ("wrong", "partial", "untested", "—"):
            with self.subTest(score=score):
                self.assertTrue(is_due({"Score": score, "Last tested": "2026-06-23",
                                        "Streak": "9"}, today=TODAY))

    def test_confident_due_after_interval(self):
        # streak 0 → interval 1: tested yesterday is due, tested today is not.
        yest = (TODAY - timedelta(days=1)).strftime("%Y-%m-%d")
        today_s = TODAY.strftime("%Y-%m-%d")
        self.assertTrue(is_due({"Score": "confident", "Last tested": yest, "Streak": "0"}, today=TODAY))
        self.assertFalse(is_due({"Score": "confident", "Last tested": today_s, "Streak": "0"}, today=TODAY))

    def test_high_streak_confident_not_due_soon(self):
        # streak 3 → interval 14: tested 7 days ago is NOT due.
        wk = (TODAY - timedelta(days=7)).strftime("%Y-%m-%d")
        self.assertFalse(is_due({"Score": "confident", "Last tested": wk, "Streak": "3"}, today=TODAY))


# ---------------------------------------------------------------------------
# Tutor queue ordering
# ---------------------------------------------------------------------------

@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestTutorQueueOrdering(unittest.TestCase):
    """
    Fixture progress_queue_order.md contains (today = 2026-06-23):
      wrong item        — wrong,     last tested 2026-06-22, streak 0           → tier 0
      partial old       — partial,   last tested 2026-06-10, streak 0           → tier 1
      partial recent    — partial,   last tested 2026-06-21, streak 0           → tier 1
      untested item     — untested,  last tested —                             → tier 2
      confident old     — confident, last tested 2026-06-01, streak 5 (int 14) → due  → tier 3
      confident recent  — confident, last tested 2026-06-22, streak 3 (int 14) → not due → SKIP
    """

    @classmethod
    def setUpClass(cls):
        prog = parse_progress_md(FIXTURES / "progress_queue_order.md")
        cls.items = prog["items"]
        cls.queue = build_tutor_queue(cls.items, today=TODAY)
        _vprint(f"\n  queue order: {[r['Item'] for r in cls.queue]}")

    def test_wrong_is_first(self):
        self.assertEqual(self.queue[0]["Item"], "wrong item")

    def test_partial_before_untested(self):
        names = [r["Item"] for r in self.queue]
        self.assertLess(names.index("partial old"), names.index("untested item"))

    def test_partial_before_confident_old(self):
        names = [r["Item"] for r in self.queue]
        self.assertLess(names.index("partial old"), names.index("confident old"))

    def test_untested_before_confident_old(self):
        names = [r["Item"] for r in self.queue]
        self.assertLess(names.index("untested item"), names.index("confident old"))

    def test_recent_confident_excluded(self):
        names = [r["Item"] for r in self.queue]
        _vprint(f"\n  queue names: {names}")
        self.assertNotIn("confident recent", names)

    def test_old_confident_included(self):
        names = [r["Item"] for r in self.queue]
        self.assertIn("confident old", names)

    def test_older_partial_before_newer_partial(self):
        """partial old (13 days ago) should sort before partial recent (2 days ago)."""
        names = [r["Item"] for r in self.queue]
        self.assertLess(names.index("partial old"), names.index("partial recent"))

    def test_queue_length(self):
        """5 items queued: wrong, partial old, partial recent, untested, confident old."""
        _vprint(f"\n  queue: {[r['Item'] for r in self.queue]}")
        self.assertEqual(len(self.queue), 5)

    def test_queue_does_not_mutate_input(self):
        original_names = [r["Item"] for r in self.items]
        build_tutor_queue(self.items, today=TODAY)  # run again
        self.assertEqual([r["Item"] for r in self.items], original_names)


# ---------------------------------------------------------------------------
# Tutor queue — edge cases
# ---------------------------------------------------------------------------

@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestTutorQueueEdgeCases(unittest.TestCase):

    def test_empty_items_returns_empty_queue(self):
        self.assertEqual(build_tutor_queue([], today=TODAY), [])

    def test_recent_well_known_confident_returns_empty(self):
        # Both confident with healthy streaks, tested within their intervals → not due.
        items = [
            {"Item": "a", "Score": "confident", "Last tested": "2026-06-22", "Streak": "3"},  # int 14
            {"Item": "b", "Score": "confident", "Last tested": "2026-06-21", "Streak": "2"},  # int 7
        ]
        queue = build_tutor_queue(items, today=TODAY)
        _vprint(f"\n  queue (should be empty): {queue}")
        self.assertEqual(queue, [])

    def test_low_streak_confident_resurfaces_quickly(self):
        # streak 0 → interval 1: tested yesterday is due again.
        items = [{"Item": "shaky", "Score": "confident",
                  "Last tested": (TODAY - timedelta(days=1)).strftime("%Y-%m-%d"), "Streak": "0"}]
        queue = build_tutor_queue(items, today=TODAY)
        self.assertEqual([r["Item"] for r in queue], ["shaky"])

    def test_unknown_score_treated_as_untested(self):
        items = [
            {"Item": "mystery", "Score": "excellent", "Last tested": "—", "Streak": "0"},
            {"Item": "known", "Score": "partial", "Last tested": "2026-06-20", "Streak": "0"},
        ]
        queue = build_tutor_queue(items, today=TODAY)
        names = [r["Item"] for r in queue]
        _vprint(f"\n  queue: {names}")
        self.assertIn("mystery", names)
        self.assertIn("known", names)

    def test_none_last_tested_treated_as_oldest(self):
        """Untested (no date) should sort after a partial by tier, regardless of date."""
        items = [
            {"Item": "partial old", "Score": "partial", "Last tested": "2026-05-23", "Streak": "0"},
            {"Item": "untested", "Score": "untested", "Last tested": "—", "Streak": "0"},
        ]
        queue = build_tutor_queue(items, today=TODAY)
        names = [r["Item"] for r in queue]
        _vprint(f"\n  queue: {names}")
        self.assertEqual(names.index("partial old"), 0)
        self.assertEqual(names.index("untested"), 1)


# ---------------------------------------------------------------------------
# Coverage percentage
# ---------------------------------------------------------------------------

@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestCoveragePct(unittest.TestCase):

    def test_all_confident(self):
        items = [{"Score": "confident"}, {"Score": "confident"}, {"Score": "confident"}]
        self.assertEqual(coverage_pct(items), 100)

    def test_none_confident(self):
        items = [{"Score": "partial"}, {"Score": "wrong"}, {"Score": "untested"}]
        self.assertEqual(coverage_pct(items), 0)

    def test_half_confident(self):
        items = [{"Score": "confident"}, {"Score": "partial"}]
        self.assertEqual(coverage_pct(items), 50)

    def test_empty_list(self):
        self.assertEqual(coverage_pct([]), 0)

    def test_rounds_correctly(self):
        items = [{"Score": "confident"}] + [{"Score": "partial"}] * 2
        pct = coverage_pct(items)
        _vprint(f"\n  1/3 → {pct}%")
        self.assertEqual(pct, 33)

    def test_matches_fixture_coverage_pct(self):
        """The valid fixture says coverage_pct: 50 — verify our function agrees."""
        prog = parse_progress_md(FIXTURES / "progress_valid.md")
        computed = coverage_pct(prog["items"])
        declared = int(prog["frontmatter"]["coverage_pct"].rstrip("%"))
        _vprint(f"\n  computed={computed}  declared={declared}")
        self.assertEqual(computed, declared)


if __name__ == "__main__":
    unittest.main(verbosity=2)

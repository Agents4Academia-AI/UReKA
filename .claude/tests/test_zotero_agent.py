"""
Test suite for .claude/src/ingestion/zotero_agent.py

Run from the project root (via the env-agnostic launcher):
    sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_zotero_agent.py -v -s   # verbose with detail output
    sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_zotero_agent.py          # pass/fail only
"""

import json
import sys
import unittest
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / ".claude" / "src"))

VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv


def _vprint(*args, **kwargs):
    """Print only when running in verbose mode (-v / --verbose)."""
    if VERBOSE:
        print(*args, **kwargs)


# ---------------------------------------------------------------------------
# Import guard — surfaces missing deps before any test runs
# ---------------------------------------------------------------------------
try:
    from ingestion.pdf_tools import (
        INK_CROPS_DIR,
        _get_nearby_text,
        extract_ink_annotations,
        extract_pdf_text,
    )
    IMPORT_ERROR = None
except Exception as e:
    IMPORT_ERROR = e

REACT_PDF = ROOT / "raw_test_sources" / "ReAct.pdf"
ATTN_PDF  = ROOT / "raw_test_sources" / "NIPS-2017-attention-is-all-you-need-Paper.pdf"


# ---------------------------------------------------------------------------

class TestImport(unittest.TestCase):
    def test_module_imports(self):
        _vprint(f"\n  import error: {IMPORT_ERROR}")
        self.assertIsNone(
            IMPORT_ERROR,
            f"Module failed to import: {IMPORT_ERROR}\n"
            "Make sure you have run: pip install fastmcp pymupdf",
        )


@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestExtractPdfText(unittest.TestCase):

    def test_returns_string(self):
        result = extract_pdf_text(str(REACT_PDF))
        _vprint(f"\n  type={type(result).__name__}  chars={len(result):,}")
        self.assertIsInstance(result, str)

    def test_non_empty(self):
        result = extract_pdf_text(str(REACT_PDF))
        _vprint(f"\n  chars={len(result):,}")
        self.assertGreater(len(result), 100)

    def test_has_page_headers(self):
        result = extract_pdf_text(str(REACT_PDF))
        headers = [l for l in result.splitlines() if l.startswith("=== PAGE")]
        _vprint(f"\n  page headers: {headers}")
        self.assertIn("=== PAGE 1 /", result)

    def test_page_count_in_header(self):
        result = extract_pdf_text(str(REACT_PDF))
        first_line = result.split("\n")[0]
        _vprint(f"\n  first header: {first_line!r}")
        self.assertRegex(first_line, r"=== PAGE \d+ / \d+ ===")

    def test_contains_paper_content(self):
        result = extract_pdf_text(str(REACT_PDF))
        _vprint(f"\n  first 400 chars:\n    {result[:400].replace(chr(10), ' ')}")
        self.assertIn("ReAct", result)

    def test_second_pdf(self):
        result = extract_pdf_text(str(ATTN_PDF))
        _vprint(f"\n  Attention PDF first 400 chars:\n    {result[:400].replace(chr(10), ' ')}")
        self.assertIn("=== PAGE 1 /", result)
        self.assertIn("Attention", result)

    def test_missing_file_raises(self):
        with self.assertRaises(Exception) as ctx:
            extract_pdf_text("nonexistent_file.pdf")
        _vprint(f"\n  exception: {type(ctx.exception).__name__}: {ctx.exception}")


@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestExtractInkAnnotations(unittest.TestCase):

    def test_returns_valid_json(self):
        raw = extract_ink_annotations(str(REACT_PDF))
        data = json.loads(raw)
        _vprint(f"\n  raw length={len(raw)}  items={len(data)}")
        self.assertIsInstance(data, list)

    def test_empty_list_for_unannotated_pdf(self):
        raw = extract_ink_annotations(str(REACT_PDF))
        data = json.loads(raw)
        _vprint(f"\n  annotations found: {len(data)}")
        self.assertEqual(data, [], "Expected no ink annotations in clean test PDF")

    def test_schema_when_annotations_present(self):
        raw = extract_ink_annotations(str(REACT_PDF))
        data = json.loads(raw)
        _vprint(f"\n  annotation objects: {json.dumps(data, indent=2)[:600]}")
        for item in data:
            with self.subTest(item=item):
                self.assertIn("page_num", item)
                self.assertIn("surrounding_ctx", item)
                self.assertIn("label", item)
                self.assertIn("ink_crop_path", item)
                self.assertIsInstance(item["page_num"], int)
                self.assertGreater(item["page_num"], 0)
                self.assertTrue(
                    Path(item["ink_crop_path"]).exists(),
                    f"Crop not saved: {item['ink_crop_path']}",
                )

    def test_missing_file_raises(self):
        with self.assertRaises(Exception) as ctx:
            extract_ink_annotations("nonexistent_file.pdf")
        _vprint(f"\n  exception: {type(ctx.exception).__name__}: {ctx.exception}")


@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestGetNearbyText(unittest.TestCase):

    def setUp(self):
        import fitz
        self.doc = fitz.open(str(REACT_PDF))
        self.page = self.doc[0]

    def tearDown(self):
        self.doc.close()

    def test_returns_string(self):
        import fitz
        rect = fitz.Rect(0, 0, 200, 200)
        result = _get_nearby_text(self.page, rect)
        _vprint(f"\n  result: {result[:200]!r}")
        self.assertIsInstance(result, str)

    def test_whole_page_rect_returns_content(self):
        import fitz
        rect = self.page.rect
        result = _get_nearby_text(self.page, rect, expand_pt=0)
        _vprint(f"\n  full-page nearby text ({len(result)} chars): {result[:300]!r}")
        self.assertGreater(len(result), 50)

    def test_empty_rect_no_expansion_returns_empty(self):
        import fitz
        rect = fitz.Rect(0, 0, 1, 1)
        result = _get_nearby_text(self.page, rect, expand_pt=0)
        _vprint(f"\n  tiny-rect result: {result!r}")
        self.assertIsInstance(result, str)


@unittest.skipIf(IMPORT_ERROR, "skipped — import failed")
class TestInkAnnotationFixture(unittest.TestCase):
    """Tests that use a real ink-annotated PDF created by the ink_pdf fixture.

    Pytest injects the fixture via conftest.py; when run with unittest directly
    these tests are skipped gracefully.
    """

    ink_pdf = None  # set by pytest fixture injection (see conftest.py)

    def _require_fixture(self):
        if self.ink_pdf is None:
            self.skipTest("ink_pdf fixture not injected — run via pytest")

    def test_strokes_grouped_into_one_cluster(self):
        """23 individual letter strokes should cluster into a single handwriting group."""
        self._require_fixture()
        data = json.loads(extract_ink_annotations(str(self.ink_pdf)))
        _vprint(f"\n  clusters found: {len(data)}")
        for i, item in enumerate(data):
            _vprint(f"  cluster {i}: stroke_count={item['stroke_count']}  label={item['label']!r}")
        self.assertEqual(len(data), 1)

    def test_cluster_contains_multiple_strokes(self):
        self._require_fixture()
        data = json.loads(extract_ink_annotations(str(self.ink_pdf)))
        _vprint(f"\n  stroke_count: {data[0]['stroke_count']}")
        self.assertGreater(data[0]["stroke_count"], 1)

    def test_page_num_is_positive(self):
        self._require_fixture()
        data = json.loads(extract_ink_annotations(str(self.ink_pdf)))
        _vprint(f"\n  page_num: {data[0]['page_num']}")
        self.assertGreater(data[0]["page_num"], 0)

    def test_surrounding_ctx_is_non_empty(self):
        self._require_fixture()
        data = json.loads(extract_ink_annotations(str(self.ink_pdf)))
        ctx = data[0]["surrounding_ctx"]
        _vprint(f"\n  surrounding_ctx: {ctx!r}")
        self.assertGreater(len(ctx.strip()), 0)

    def test_crop_file_is_saved(self):
        self._require_fixture()
        data = json.loads(extract_ink_annotations(str(self.ink_pdf)))
        crop_path = Path(data[0]["ink_crop_path"])
        _vprint(f"\n  crop saved at: {crop_path}  exists={crop_path.exists()}")
        self.assertTrue(crop_path.exists(), f"PNG crop not found: {crop_path}")

    def test_crop_is_valid_png(self):
        self._require_fixture()
        data = json.loads(extract_ink_annotations(str(self.ink_pdf)))
        crop_path = Path(data[0]["ink_crop_path"])
        header = crop_path.read_bytes()[:8]
        _vprint(f"\n  PNG header bytes: {header.hex()}")
        self.assertEqual(header, b"\x89PNG\r\n\x1a\n")

    @pytest.fixture(autouse=True)
    def _inject_ink_pdf(self, ink_pdf):
        self.ink_pdf = ink_pdf


if __name__ == "__main__":
    unittest.main(verbosity=2)

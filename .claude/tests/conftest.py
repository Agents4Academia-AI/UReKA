"""
Shared pytest fixtures for the knowledge-management test suite.
"""

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

INK_PDF = ROOT / "raw_test_sources" / "ink_test.pdf"


@pytest.fixture(scope="session")
def ink_pdf():
    """
    Path to a hand-annotated PDF with at least one Ink annotation
    whose label (Zotero comment field) is 'Catch this ink'.

    Create raw_test_sources/ink_test.pdf manually — draw a squiggle
    on any page in Zotero or a PDF editor and set the comment to
    'Catch this ink' — then run the tests.
    """
    if not INK_PDF.exists():
        pytest.skip(f"ink_test.pdf not found — create {INK_PDF} to run ink tests")
    return INK_PDF

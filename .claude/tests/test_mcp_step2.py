"""
MCP-protocol tests for Step 2 of the /zotero skill:
  Gather metadata and annotations when a Zotero entry exists.

Our tools (extract_pdf_text, extract_ink_annotations) are called through the
fastmcp Client so the full MCP request/response cycle is exercised.

Zotero-mcp integration tests require a running Zotero desktop instance and a
known citation key (e.g. "yao2022react") — set ZOTERO_CITATION_KEY=<citekey> to enable.

Run from the project root (via the env-agnostic launcher; picks whatever env has the deps):
    sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_mcp_step2.py -v -s
"""

import asyncio
import json
import os
import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / ".claude" / "src"))

VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv
ZOTERO_CITATION_KEY = os.environ.get("ZOTERO_CITATION_KEY", "zhang_using_2026")


def _vprint(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)


# ---------------------------------------------------------------------------
# Import guards
# ---------------------------------------------------------------------------

try:
    from ingestion.pdf_tools import mcp
    AGENT_ERROR = None
except Exception as e:
    mcp = None
    AGENT_ERROR = e

try:
    from fastmcp import Client
    MCP_CLIENT_OK = True
except Exception:
    Client = None
    MCP_CLIENT_OK = False


def _call(tool_name: str, args: dict):
    """Run a tool call through the fastmcp Client synchronously."""
    async def _run():
        async with Client(mcp) as client:
            return await client.call_tool(tool_name, args)
    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Step 2a — extract_pdf_text via MCP protocol
# ---------------------------------------------------------------------------

@pytest.mark.skipif(AGENT_ERROR or not MCP_CLIENT_OK, reason="agent import or fastmcp Client unavailable")
class TestExtractPdfTextMCP:

    def test_tool_is_listed(self):
        async def _run():
            async with Client(mcp) as client:
                return await client.list_tools()
        tools = asyncio.run(_run())
        names = [t.name for t in tools]
        _vprint(f"\n  registered tools: {names}")
        assert "extract_pdf_text" in names

    def test_returns_text_content(self, ink_pdf):
        result = _call("extract_pdf_text", {"pdf_path": str(ink_pdf)})
        text = result.content[0].text
        _vprint(f"\n  content[:300]: {text[:300]!r}")
        assert isinstance(text, str)
        assert len(text) > 10

    def test_page_header_present(self, ink_pdf):
        result = _call("extract_pdf_text", {"pdf_path": str(ink_pdf)})
        text = result.content[0].text
        _vprint(f"\n  first line: {text.splitlines()[0]!r}")
        assert "=== PAGE 1 /" in text

    def test_body_text_extracted(self, ink_pdf):
        result = _call("extract_pdf_text", {"pdf_path": str(ink_pdf)})
        text = result.content[0].text
        _vprint(f"\n  body text snippet: {text[50:200]!r}")
        assert "attention" in text.lower()

    def test_missing_file_returns_error(self):
        with pytest.raises(Exception):
            _call("extract_pdf_text", {"pdf_path": "no_such_file.pdf"})


# ---------------------------------------------------------------------------
# Step 2b — extract_ink_annotations via MCP protocol
# ---------------------------------------------------------------------------

@pytest.mark.skipif(AGENT_ERROR or not MCP_CLIENT_OK, reason="agent import or fastmcp Client unavailable")
class TestExtractInkAnnotationsMCP:

    def test_tool_is_listed(self):
        async def _run():
            async with Client(mcp) as client:
                return await client.list_tools()
        tools = asyncio.run(_run())
        names = [t.name for t in tools]
        _vprint(f"\n  registered tools: {names}")
        assert "extract_ink_annotations" in names

    def test_returns_json_string(self, ink_pdf):
        result = _call("extract_ink_annotations", {"pdf_path": str(ink_pdf)})
        raw = result.content[0].text
        _vprint(f"\n  raw result: {raw}")
        data = json.loads(raw)
        assert isinstance(data, list)

    def test_catches_ink_annotation(self, ink_pdf):
        result = _call("extract_ink_annotations", {"pdf_path": str(ink_pdf)})
        data = json.loads(result.content[0].text)
        _vprint(f"\n  annotations: {json.dumps(data, indent=2)}")
        assert len(data) == 1
        assert data[0]["stroke_count"] > 1  # handwriting = many strokes clustered

    def test_surrounding_ctx_via_mcp(self, ink_pdf):
        result = _call("extract_ink_annotations", {"pdf_path": str(ink_pdf)})
        data = json.loads(result.content[0].text)
        ctx = data[0]["surrounding_ctx"]
        _vprint(f"\n  surrounding_ctx: {ctx!r}")
        assert "attention" in ctx.lower()

    def test_crop_path_exists_on_disk(self, ink_pdf):
        result = _call("extract_ink_annotations", {"pdf_path": str(ink_pdf)})
        data = json.loads(result.content[0].text)
        crop = Path(data[0]["ink_crop_path"])
        _vprint(f"\n  crop path: {crop}  exists={crop.exists()}")
        assert crop.exists()

    def test_missing_file_returns_error(self):
        with pytest.raises(Exception):
            _call("extract_ink_annotations", {"pdf_path": "no_such_file.pdf"})


# ---------------------------------------------------------------------------
# Step 2c — zotero-mcp integration (requires Zotero running + ZOTERO_CITATION_KEY)
# ---------------------------------------------------------------------------

def _zotero_mcp():
    """Return the zotero-mcp FastMCP server instance."""
    try:
        from zotero_mcp._app import mcp as _mcp
        return _mcp
    except Exception as e:
        pytest.skip(f"Could not import zotero-mcp server: {e}")


def _zcall(tool_name: str, args: dict):
    """Call a zotero-mcp tool through the MCP Client (local mode)."""
    os.environ.setdefault("ZOTERO_LOCAL", "true")

    async def _run():
        async with Client(_zotero_mcp()) as client:
            return await client.call_tool(tool_name, args)
    try:
        return asyncio.run(_run())
    except Exception as e:
        pytest.skip(f"zotero-mcp tool '{tool_name}' failed (is Zotero running?): {e}")


def _resolve_item_key(citation_key: str) -> str:
    """Look up a Zotero item key from a citation key via zotero-mcp."""
    import re
    result = _zcall("zotero_search_by_citation_key", {"citekey": citation_key})
    text = result.content[0].text
    _vprint(f"\n  search result: {text[:300]}")
    for line in text.splitlines():
        m = re.search(r'\b([A-Z0-9]{8})\b', line)
        if m:
            return m.group(1)
    pytest.skip(f"No item key found for citation key: {citation_key!r}")


@pytest.mark.skipif(not ZOTERO_CITATION_KEY, reason="no citation key set")
class TestZoteroMCPIntegration:
    """
    Hits the live zotero-mcp tools (requires Zotero desktop running in local mode).
    Resolves the citation key to an item key first, then validates metadata and annotations.

    Example:
        ZOTERO_CITATION_KEY=yao2022react pytest tests/test_mcp_step2.py::TestZoteroMCPIntegration -v -s
    """

    @pytest.fixture(autouse=True)
    def _resolve_key(self):
        self.item_key = _resolve_item_key(ZOTERO_CITATION_KEY)
        _vprint(f"\n  citation_key={ZOTERO_CITATION_KEY!r} -> item_key={self.item_key!r}")

    def test_get_item_metadata_returns_title(self):
        result = _zcall("zotero_get_item_metadata", {"item_key": self.item_key})
        text = result.content[0].text
        _vprint(f"\n  metadata snippet: {text[:400]}")
        assert isinstance(text, str)
        assert len(text) > 20

    def test_get_annotations_returns_list(self):
        result = _zcall("zotero_get_annotations", {"item_key": self.item_key})
        text = result.content[0].text
        _vprint(f"\n  annotations snippet: {text[:400]}")
        assert isinstance(text, str)

    def test_get_annotations_schema(self):
        """Response must mention annotation fields or explicitly say none found."""
        result = _zcall("zotero_get_annotations", {"item_key": self.item_key})
        text = result.content[0].text
        _vprint(f"\n  full annotations:\n{text[:800]}")
        assert "annotation" in text.lower()

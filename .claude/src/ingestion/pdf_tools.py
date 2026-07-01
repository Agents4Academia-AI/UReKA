"""
MCP server exposing two PDF extraction tools for the /zotero skill.

Tools
-----
extract_pdf_text
    Full body text, page by page.  Used when there is no matching Zotero
    entry and zotero_read_pdf_pages cannot be called (Case 2 / Case 4 fallback).

extract_ink_annotations
    Ink/handwritten stroke annotations only.  Always run on the raw PDF
    regardless of whether a Zotero entry exists.  Crops are saved to
    <output_dir>/crop_p<N>_c<M>.png so they live alongside the note files.
    output_dir defaults to notes/.ink_crops/<pdf_stem>/.

Run as an MCP stdio server (registered in .mcp.json as the `pdf-tools` server):
    sh .claude/src/pyrun --need pymupdf4llm .claude/src/ingestion/pdf_tools.py
"""

import base64
import json
from pathlib import Path
from typing import Any

import fitz  # pymupdf
import pymupdf4llm
from fastmcp import FastMCP

mcp = FastMCP("zotero-pdf")

INK_CROPS_DIR = Path("notes/.ink_crops")

# Minimum cluster bounding-box area (pt²) — blobs smaller than this are spurious
MIN_CLUSTER_BBOX_PT2 = 200
# If a page has this many clusters or more, render it as a single whole-page image
HEAVY_PAGE_CLUSTER_COUNT = 4
# If cluster bounding boxes together cover this fraction of the page, render whole page
HEAVY_PAGE_COVERAGE = 0.35


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_nearby_text(page: fitz.Page, rect: fitz.Rect, expand_pt: int = 90) -> str:
    """Return concatenated text from blocks within expand_pt points of rect."""
    expanded = fitz.Rect(
        rect.x0 - expand_pt,
        rect.y0 - expand_pt,
        rect.x1 + expand_pt,
        rect.y1 + expand_pt,
    )
    nearby: list[str] = []
    for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
        if fitz.Rect(x0, y0, x1, y1).intersects(expanded) and text.strip():
            nearby.append(text.strip())
    return " ".join(nearby)


def _cluster_bbox(cluster: list) -> fitz.Rect:
    """Union bounding box of all strokes in a cluster."""
    r = cluster[0].rect
    for a in cluster[1:]:
        r = r | a.rect
    return r


def _cluster_ink_annots(annots: list, gap_pt: int = 20) -> list[list]:
    """Group ink annotations whose bounding boxes are within gap_pt of each other.

    Uses union-find so that transitively close strokes (a near b, b near c)
    are merged into one cluster — important for multi-word handwriting where
    individual letter strokes may have small gaps between them.
    """
    n = len(annots)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for i in range(n):
        expanded_i = fitz.Rect(
            annots[i].rect.x0 - gap_pt,
            annots[i].rect.y0 - gap_pt,
            annots[i].rect.x1 + gap_pt,
            annots[i].rect.y1 + gap_pt,
        )
        for j in range(i + 1, n):
            if expanded_i.intersects(annots[j].rect):
                union(i, j)

    groups: dict[int, list] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(annots[i])

    return list(groups.values())


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
def extract_pdf_text(pdf_path: str) -> str:
    # """Extract full body text from a PDF file, page by page.

    # Use this when there is no matching Zotero entry and zotero_read_pdf_pages
    # cannot be called (Cases 2 and 4 in the body text strategy).

    # Returns text with '=== PAGE N ===' headers separating pages.
    # Pages with no extractable text are omitted.
    # """
    # doc = fitz.open(pdf_path)
    # total = len(doc)
    # sections: list[str] = []
    # for i, page in enumerate(doc, start=1):
    #     text = page.get_text().strip()
    #     if text:
    #         sections.append(f"=== PAGE {i} / {total} ===\n\n{text}")
    # doc.close()
    # return "\n\n".join(sections)
    """
    Uses pymupdf4llm to preserve document structure: headings, columns, tables,
    lists, and bold/italic — suitable for a verbatim mirror-copy of the PDF.

    Headings are demoted by 2 levels (# → ###, ## → ####, …) so they nest
    correctly under the ## Content section in the source file.
    """
    import re
    md = pymupdf4llm.to_markdown(pdf_path)
    # Demote headings: prepend ## to every ATX heading line
    return re.sub(r"^(#{1,4})\s", lambda m: "##" + m.group(0), md, flags=re.MULTILINE)


@mcp.tool()
def extract_ink_annotations(pdf_path: str, output_dir: str = "") -> str:
    """Extract ink/handwritten stroke annotations from a PDF.

    Iterates every page and finds annotations of type 'Ink'.  For each one:
    - Saves a 200-dpi PNG crop of the annotation region to
      <output_dir>/crop_p<N>_c<M>.png.  Pass output_dir as the paper's
      note folder (e.g. "notes/attention-is-all-you-need") so crops live
      alongside the note files.  Defaults to notes/.ink_crops/<pdf_stem>/.
      The crop height extends 2× the ink annotation's own height above and
      below it (dynamic padding, not a fixed point value).
    - Captures all text blocks visible within the crop region as surrounding context.

    Returns a JSON array, one object per ink annotation:
    {
      "page_num":        1-indexed page number,
      "surrounding_ctx": nearby text blocks (empty string if none),
      "label":           annot.info["content"] if set, else "",
      "ink_crop_path":   relative path to the saved PNG crop
    }

    Always run this on the raw PDF regardless of Zotero match status.
    The skill should Read each ink_crop_path as an image to transcribe
    the handwriting.
    """
    import re
    doc = fitz.open(pdf_path)
    pdf_stem = Path(pdf_path).stem
    # Sanitize stem for use in filenames; truncate to keep paths short
    safe_stem = re.sub(r"[^\w\-]", "_", pdf_stem)[:40].strip("_")
    crop_dir = Path(output_dir) if output_dir else INK_CROPS_DIR / pdf_stem
    crop_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []

    for page_num, page in enumerate(doc, start=1):
        ink_annots = [a for a in page.annots() if a.type[1] == "Ink"]
        if not ink_annots:
            continue

        clusters = _cluster_ink_annots(ink_annots, gap_pt=20)

        # Filter spurious single-dot/blob clusters
        bboxes = [_cluster_bbox(c) for c in clusters]
        pairs = [
            (c, b) for c, b in zip(clusters, bboxes)
            if (b.x1 - b.x0) * (b.y1 - b.y0) >= MIN_CLUSTER_BBOX_PT2
        ]
        if not pairs:
            continue
        clusters, bboxes = zip(*pairs)
        clusters, bboxes = list(clusters), list(bboxes)

        # Decide: render individual crops or the whole page
        page_area = page.rect.width * page.rect.height
        union_all = bboxes[0]
        for b in bboxes[1:]:
            union_all = union_all | b
        coverage = (union_all.x1 - union_all.x0) * (union_all.y1 - union_all.y0) / page_area

        if len(clusters) >= HEAVY_PAGE_CLUSTER_COUNT or coverage >= HEAVY_PAGE_COVERAGE:
            # Heavily annotated page — render full page as one image
            crop_path = crop_dir / f"page_{safe_stem}_p{page_num}.png"
            page.get_pixmap(dpi=300).save(str(crop_path))
            surrounding_ctx = page.get_text().strip()
            label = next(
                (a.info.get("content", "").strip()
                 for c in clusters for a in c
                 if a.info.get("content", "").strip()),
                "",
            )
            results.append({
                "page_num": page_num,
                "page_width": page.rect.width,
                "page_height": page.rect.height,
                "bbox": {"x0": union_all.x0, "y0": union_all.y0,
                         "x1": union_all.x1, "y1": union_all.y1},
                "stroke_count": sum(len(c) for c in clusters),
                "surrounding_ctx": surrounding_ctx,
                "label": label,
                "ink_crop_path": str(crop_path),
                "whole_page": True,
            })
        else:
            for cluster_idx, (cluster, union_rect) in enumerate(zip(clusters, bboxes)):
                label = next(
                    (a.info.get("content", "").strip() for a in cluster
                     if a.info.get("content", "").strip()),
                    "",
                )

                ink_h = union_rect.y1 - union_rect.y0
                padded = fitz.Rect(
                    0,
                    max(0, union_rect.y0 - 2 * ink_h),
                    page.rect.width,
                    min(page.rect.height, union_rect.y1 + 2 * ink_h),
                )
                surrounding_ctx = _get_nearby_text(page, padded, expand_pt=0)

                crop_path = crop_dir / f"crop_{safe_stem}_p{page_num}_c{cluster_idx}.png"
                page.get_pixmap(clip=padded, dpi=200).save(str(crop_path))

                results.append({
                    "page_num": page_num,
                    "page_width": page.rect.width,
                    "page_height": page.rect.height,
                    "bbox": {"x0": union_rect.x0, "y0": union_rect.y0,
                             "x1": union_rect.x1, "y1": union_rect.y1},
                    "stroke_count": len(cluster),
                    "surrounding_ctx": surrounding_ctx,
                    "label": label,
                    "ink_crop_path": str(crop_path),
                    "whole_page": False,
                })

    doc.close()
    return json.dumps(results, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()

---
type: zotero_source | alphaxiv_source | fulltext_source | web_source
title: <title of the paper or page>
concepts_mentioned: [concept1, concept2, ...]
source_links:
  - /absolute/path/to/file.pdf   # local PDF path (zotero_source)
  # or
  - https://...              # canonical URL (alphaxiv_source, fulltext_source, web_source)
---

## Content

<The source's objective content, following the ingesting skill's layout:
- zotero_source: the paper text extracted from the PDF (and any figures), as
  faithfully as possible — full content, no personal input.
- alphaxiv_source: the abstract, the AlphaXiv AI overview (labelled AI-generated),
  and key metadata — not the full paper text (see the /alphaxiv skill).
- fulltext_source: the complete rendered paper text (title, authors, year header +
  full body), written by autoexplore's fulltext_lit.py step. source_links holds the
  canonical arXiv URL or DOI. Used inside explore_library/ and course/<slug>/library/.
- web_source: a credibility-scored web page (Wikipedia/blog/tutorial/docs); see
  web_source.md template for the additional credibility fields.
Do not summarise unless the source is very long.>

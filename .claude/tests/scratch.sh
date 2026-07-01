# 1. Can the module even be imported?
sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_zotero_agent.py::TestImport::test_module_imports -v

# 2. Does extract_pdf_text return anything?
sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_zotero_agent.py::TestExtractPdfText::test_returns_string -v

# 3. Does it have the right page header format?
sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_zotero_agent.py::TestExtractPdfText::test_page_count_in_header -v

# 4. Does it contain real paper content?
sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_zotero_agent.py::TestExtractPdfText::test_contains_paper_content -v

# 5. Does it work on a second PDF?
sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_zotero_agent.py::TestExtractPdfText::test_second_pdf -v

# 6. Does a missing file raise an error?
sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_zotero_agent.py::TestExtractPdfText::test_missing_file_raises -v

# 7. Does extract_ink_annotations return valid JSON?
sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_zotero_agent.py::TestExtractInkAnnotations::test_returns_valid_json -v

# 8. Does it return empty list for unannotated PDFs?
sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_zotero_agent.py::TestExtractInkAnnotations::test_empty_list_for_unannotated_pdf -v

# 9. Does the nearby-text helper work on a real page?
sh .claude/src/pyrun --need pytest -m pytest .claude/tests/test_zotero_agent.py::TestGetNearbyText::test_whole_page_rect_returns_content -v
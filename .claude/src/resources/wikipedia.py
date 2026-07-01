"""Minimal MediaWiki (Wikipedia) API client — pure stdlib, no API key.

Wikipedia is the canonical encyclopedic "curated registry" tier for the
resource-pull engine: it gives factual, widely-vetted, citation-backed overviews
that ground a curriculum's foundations. We use the public MediaWiki API
(``/w/api.php``) and REST summary endpoint over ``urllib`` so this runs under any
Python with no third-party deps (mirrors ``reindex_poller.py``).

Network failures degrade gracefully (return ``[]`` / ``None``) so callers never
crash on a flaky connection — they just report "no Wikipedia results".
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

API = "https://en.wikipedia.org/w/api.php"
REST_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"
TIMEOUT = 20


def _user_agent() -> str:
    # Wikipedia asks clients to send a descriptive UA with a contact. Reuse the
    # same contact env the `prior` scoper uses for the OpenAlex polite pool.
    contact = os.environ.get("PRIOR_CONTACT_EMAIL", "anonymous")
    return f"knowledge_management-PKM/0.1 (https://github.com/Agents4Academia-AI; {contact})"


def _get(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — any network/parse error → graceful empty
        return None


def _api(params: dict) -> dict | None:
    params = {**params, "format": "json"}
    return _get(f"{API}?{urllib.parse.urlencode(params)}")


def search(topic: str, limit: int = 5) -> list[dict]:
    """Search Wikipedia for ``topic``; return ``[{title, pageid, snippet, url}]``."""
    data = _api({
        "action": "query",
        "list": "search",
        "srsearch": topic,
        "srlimit": max(1, limit),
        "srprop": "snippet",
    })
    if not data:
        return []
    out = []
    for hit in data.get("query", {}).get("search", []):
        title = hit.get("title", "")
        out.append({
            "title": title,
            "pageid": hit.get("pageid"),
            # Strip the HTML markup MediaWiki puts in snippets.
            "snippet": _strip_html(hit.get("snippet", "")),
            "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
        })
    return out


def fetch(title: str) -> dict | None:
    """Fetch an article's plain-text content + metadata.

    Returns ``{title, url, summary, extract, references, lastmod}`` or ``None`` if
    the page can't be retrieved. ``extract`` is the full plain-text article body
    (section headers preserved as ``== Heading ==`` lines); ``references`` is a
    sample of external links cited by the page.
    """
    # Full plain-text extract via the action API.
    data = _api({
        "action": "query",
        "prop": "extracts|info",
        "explaintext": 1,
        "inprop": "url",
        "redirects": 1,
        "titles": title,
    })
    if not data:
        return None
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), None)
    if not page or "missing" in page:
        return None

    resolved = page.get("title", title)
    extract = page.get("extract", "") or ""

    # REST summary for a clean one-paragraph summary + canonical URL + lastmod.
    summary, canon_url, lastmod = "", page.get("fullurl", ""), ""
    rest = _get(REST_SUMMARY + urllib.parse.quote(resolved.replace(" ", "_")))
    if rest:
        summary = rest.get("extract", "") or ""
        canon_url = (rest.get("content_urls", {}).get("desktop", {}).get("page")
                     or canon_url)
        lastmod = rest.get("timestamp", "") or ""

    return {
        "title": resolved,
        "url": canon_url or ("https://en.wikipedia.org/wiki/"
                             + urllib.parse.quote(resolved.replace(" ", "_"))),
        "summary": summary,
        "extract": extract,
        "references": _external_links(resolved),
        "lastmod": lastmod,
    }


def _external_links(title: str, limit: int = 15) -> list[str]:
    """A sample of the page's cited external links (for the References section)."""
    data = _api({
        "action": "query",
        "prop": "extlinks",
        "ellimit": limit,
        "redirects": 1,
        "titles": title,
    })
    if not data:
        return []
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    return [el.get("*", "") for el in page.get("extlinks", []) if el.get("*")]


def _strip_html(text: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", text or "").strip()

"""Local web research module — no API keys needed.

Primary: duckduckgo_search library (handles anti-bot internally).
Fallback: direct DuckDuckGo lite HTML scraping via httpx.
Content extraction: trafilatura.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import quote_plus, unquote

import httpx

logger = logging.getLogger(__name__)

MAX_RESULTS_PER_QUERY = 5
FETCH_TIMEOUT = 15.0
SEARCH_TIMEOUT = 12.0
SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


async def search_web(
    httpx_client: httpx.AsyncClient,
    queries: list[str],
    max_results: int = MAX_RESULTS_PER_QUERY,
) -> list[dict[str, Any]]:
    """Search the web using DuckDuckGo (tries library first, then direct HTML)."""
    seen_urls: set[str] = set()
    all_results: list[dict[str, Any]] = []

    for query in queries[:4]:
        results = _search_library(query, max_results)
        if not results:
            results = await _search_direct(httpx_client, query, max_results)
        for item in results:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(item)

    return all_results


def _search_library(query: str, max_results: int) -> list[dict[str, Any]]:
    """Use ddgs library — most reliable for anti-bot handling."""
    try:
        from ddgs import DDGS
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with DDGS() as ddgs:
                raw = list(ddgs.text(query, max_results=max_results))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in raw
        ]
    except Exception as exc:
        logger.debug("ddgs library failed: %s", exc)
        return []


async def _search_direct(
    httpx_client: httpx.AsyncClient,
    query: str,
    max_results: int,
) -> list[dict[str, Any]]:
    """Fallback: direct HTTP to DuckDuckGo lite."""
    url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
    try:
        resp = await httpx_client.get(
            url,
            headers=SEARCH_HEADERS,
            timeout=SEARCH_TIMEOUT,
            follow_redirects=True,
        )
        if resp.status_code == 202:
            return []
        resp.raise_for_status()
        return _parse_ddg_lite(resp.text, max_results)
    except Exception as exc:
        logger.debug("Direct DuckDuckGo search failed: %s", exc)
        return []


def _parse_ddg_lite(html: str, max_results: int) -> list[dict[str, Any]]:
    """Parse DuckDuckGo lite results (table-based layout)."""
    results: list[dict[str, Any]] = []
    rows = re.findall(
        r'<tr[^>]*?\bclass="[^"]*?result[^"]*?"[^>]*?>(.*?)</tr>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    for row in rows[:max_results]:
        link_m = re.search(
            r'<a[^>]*?\srel="nofollow"[^>]*?\shref="([^"]+)"[^>]*?>(.+?)</a>',
            row,
            re.DOTALL,
        )
        snippet_m = re.search(
            r'<td[^>]*?\bclass="[^"]*?result-snippet[^"]*?"[^>]*?>(.+?)</td>',
            row,
            re.DOTALL,
        )
        url = _clean_url(link_m.group(1)) if link_m else ""
        if url:
            results.append({
                "title": _strip_html(link_m.group(2)) if link_m else url,
                "url": url,
                "snippet": _strip_html(snippet_m.group(1)) if snippet_m else "",
            })
    return results


def _clean_url(raw: str) -> str:
    """Decode DuckDuckGo redirect URL."""
    url = unquote(raw)
    url = re.sub(r'^//duckduckgo\.com/l/\?uddg=', '', url)
    m = re.search(r'uddg=([^&]+)', url)
    if m:
        url = unquote(m.group(1))
    url = re.sub(r'&rut=[^&]+', '', url)
    return url if url.startswith("http") else ""


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#x27;", "'")
    text = re.sub(r'&[a-z]+;', ' ', text)
    return text.strip()


async def extract_page_content(
    httpx_client: httpx.AsyncClient,
    url: str,
    timeout: float = FETCH_TIMEOUT,
) -> str | None:
    """Fetch a URL and extract readable text using trafilatura."""
    import trafilatura

    try:
        resp = await httpx_client.get(
            url,
            timeout=timeout,
            headers={"User-Agent": SEARCH_HEADERS["User-Agent"], "Accept": "text/html"},
            follow_redirects=True,
        )
        resp.raise_for_status()
        text = trafilatura.extract(
            resp.text,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            favor_precision=True,
        )
        return text.strip()[:3000] if text else None
    except Exception as exc:
        logger.debug("Content extraction failed for %s: %s", url, exc)
        return None


def build_fallback_patterns(
    search_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build patterns from search snippets when full extraction is unavailable."""
    patterns: list[dict[str, Any]] = []
    for item in search_results:
        snippet = item.get("snippet", "").strip()
        if not snippet:
            continue
        patterns.append({
            "source_url": item.get("url", ""),
            "title": item.get("title", ""),
            "claim": snippet[:300],
            "risk": "Moderate",
            "relevance": "Medium",
        })
    return patterns

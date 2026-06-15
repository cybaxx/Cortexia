#!/usr/bin/env python3
"""
Fetch top news stories for Cortexia weekly briefing.

Supports multiple backends:
  --rss URL           Fetch from RSS/Atom feed
  --newsapi KEY       Fetch top headlines from NewsAPI.org (requires pip install newsapi-python)
  --text FILE         Read stories from text file (one per line)
  --csv FILE          Read from CSV with columns: title, text, domain, city

If no source is given, prints a template JSON to stdout.

Examples:
  python scripts/news_fetcher.py --rss "https://feeds.bbci.co.uk/news/rss.xml" > stories.json
  python scripts/news_fetcher.py --rss "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml" -n 10
  python scripts/news_fetcher.py --text headlines.txt --domain public_health --city la
  python scripts/news_fetcher.py --template
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_LIMIT = 10


def _parse_rss(xml_text: str) -> list[dict[str, Any]]:
    """Extract title + description from RSS 2.0 or Atom feed."""
    root = ET.fromstring(xml_text)
    stories: list[dict[str, Any]] = []

    # RSS 2.0
    for item in root.iter("item"):
        title_el = item.find("title")
        desc_el = item.find("description")
        link_el = item.find("link")
        title = (title_el.text or "").strip() if title_el is not None else ""
        desc = (desc_el.text or "").strip() if desc_el is not None else ""
        link = (link_el.text or "").strip() if link_el is not None else ""
        if title and desc:
            stories.append({"title": title, "text": _strip_html(desc), "source_url": link or None})

    # Atom
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//atom:entry", ns) or root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title_el = entry.find("atom:title", ns) or entry.find("{http://www.w3.org/2005/Atom}title")
        summary_el = entry.find("atom:summary", ns) or entry.find("{http://www.w3.org/2005/Atom}summary")
        link_el = entry.find("atom:link", ns) or entry.find("{http://www.w3.org/2005/Atom}link")
        title = (title_el.text or "").strip() if title_el is not None and title_el.text else ""
        desc = (summary_el.text or "").strip() if summary_el is not None and summary_el.text else ""
        link = link_el.get("href", "") if link_el is not None else ""
        if title and desc:
            stories.append({"title": title, "text": _strip_html(desc), "source_url": link or None})

    return stories


def _strip_html(text: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def _fetch_rss(url: str, limit: int) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        r = await client.get(url, headers={"User-Agent": "CortexiaBriefing/0.3"})
        r.raise_for_status()
    stories = _parse_rss(r.text)
    return stories[:limit]


async def _fetch_newsapi(api_key: str, limit: int, country: str = "us") -> list[dict[str, Any]]:
    url = f"https://newsapi.org/v2/top-headlines?country={country}&pageSize={limit}&apiKey={api_key}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()

    stories: list[dict[str, Any]] = []
    for article in data.get("articles", []):
        title = (article.get("title") or "").strip()
        desc = (article.get("description") or "").strip()
        content = (article.get("content") or "").strip()
        text = f"{title}. {desc} {content}".strip()
        url = article.get("url")
        if title and len(text) >= 12:
            stories.append({"title": title, "text": text, "source_url": url})
    return stories[:limit]


def _read_text(path: str) -> list[dict[str, Any]]:
    lines = Path(path).read_text().splitlines()
    stories: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            stories.append({"title": line[:120], "text": line})
    return stories


def _read_csv(path: str) -> list[dict[str, Any]]:
    stories: list[dict[str, Any]] = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            title = row.get("title", row.get("headline", "")).strip()
            text = row.get("text", row.get("content", row.get("body", ""))).strip()
            if title and text:
                stories.append({
                    "title": title,
                    "text": text,
                    "source_url": row.get("source_url", row.get("url", "")).strip() or None,
                    "speaker_context": row.get("speaker_context", "").strip() or None,
                    "domain": row.get("domain", "").strip() or None,
                    "city_id": row.get("city_id", row.get("city", "")).strip() or None,
                    "message_complexity": float(row.get("message_complexity", 0)) or None,
                })
    return stories


def _print_template() -> None:
    template = [
        {
            "title": "Short headline for the claim",
            "text": "Full text of the claim or article. At least 12 characters.",
            "source_url": "https://example.com/article",
            "speaker_context": "e.g. Facebook post with 2,400 shares",
            "domain": "political",
            "city_id": "la",
            "message_complexity": 0.5,
        }
    ]
    print(json.dumps(template, indent=2))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch news stories for Cortexia briefing")
    parser.add_argument("--rss", help="RSS/Atom feed URL")
    parser.add_argument("--newsapi", help="NewsAPI.org API key")
    parser.add_argument("--text", help="Text file with one headline per line")
    parser.add_argument("--csv", help="CSV file with title,text,domain,city columns")
    parser.add_argument("--template", action="store_true", help="Print template JSON and exit")
    parser.add_argument("-n", "--limit", type=int, default=DEFAULT_LIMIT, help=f"Max stories (default {DEFAULT_LIMIT})")
    parser.add_argument("--country", default="us", help="Country code for NewsAPI (default us)")
    args = parser.parse_args()

    if args.template:
        _print_template()
        return

    stories: list[dict[str, Any]] = []

    if args.rss:
        print(f"Fetching RSS: {args.rss}", file=sys.stderr)
        stories = await _fetch_rss(args.rss, args.limit)
    elif args.newsapi:
        print(f"Fetching NewsAPI top headlines ({args.country})", file=sys.stderr)
        stories = await _fetch_newsapi(args.newsapi, args.limit, args.country)
    elif args.text:
        stories = _read_text(args.text)[: args.limit]
    elif args.csv:
        stories = _read_csv(args.csv)[: args.limit]
    else:
        parser.print_help()
        print("\nNo source specified. Use --template for a JSON template.", file=sys.stderr)
        sys.exit(1)

    print(f"Fetched {len(stories)} stories", file=sys.stderr)
    print(json.dumps(stories, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

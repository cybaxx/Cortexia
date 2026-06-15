#!/usr/bin/env python3
"""
Weekly briefing batch runner for Cortexia.

Runs information-epidemiology simulations on multiple news stories and
produces a consolidated report.

Usage:
    python scripts/weekly_briefing.py stories.json
    python scripts/weekly_briefing.py stories.json -o ./briefings -p 2
    python scripts/weekly_briefing.py --headline "Claim text here" --domain public_health

Input JSON format (array of story objects):
    [
      {
        "title": "Short headline",
        "text": "Full claim / article text (min 12 chars)",
        "source_url": "https://...",
        "speaker_context": "Optional source context",
        "domain": "political|public_health|urban|corporate",
        "city_id": "la|sf|sd|sj|sac",
        "message_complexity": 0.5
      }
    ]

Environment variables for long-running CPU embedding:
    CORTEXIA_TRIBE_TIMEOUT=900   (seconds, default 900 for CPU)
    CORTEXIA_TOTAL_TIMEOUT=1200  (seconds, default 1200)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


def _ensure_timeouts() -> None:
    """Bump timeouts for CPU-bound text embedding on Apple Silicon.

    The FastAPI config reads these from the environment (pydantic-settings).
    Default config max is 600s for tribe, 900s for total.
    """
    os.environ.setdefault("simulate_tribe_timeout_seconds", "600")
    os.environ.setdefault("simulate_total_timeout_seconds", "900")


DEFAULT_DOMAIN = "political"
DEFAULT_CITY = "la"
DEFAULT_GOAL = (
    "Understand how this claim spreads, identify vulnerable audience segments, "
    "and recommend interventions that reduce harm."
)

DOMAINS = {"political", "public_health", "urban", "corporate"}
CITIES = {"la", "sf", "sd", "sj", "sac"}


def _load_stories(path: str) -> list[dict[str, Any]]:
    with open(path) as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("stories", data.get("items", [data]))
    if not isinstance(data, list):
        raise ValueError("Input must be a JSON array of story objects.")
    return data


def _parse_headline(raw: str) -> dict[str, Any]:
    """Quick single-headline mode: --headline 'text' --domain political"""
    return {"text": raw.strip()}


def _normalize_story(raw: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    text = str(raw.get("text") or raw.get("content") or raw.get("body") or "").strip()
    title = str(raw.get("title") or raw.get("headline") or text[:80]).strip()
    domain = str(raw.get("domain") or args.domain or DEFAULT_DOMAIN).strip()
    city = str(raw.get("city_id") or args.city or DEFAULT_CITY).strip().lower()
    goal = str(raw.get("case_goal") or args.goal or DEFAULT_GOAL).strip()
    complexity = float(raw.get("message_complexity", args.complexity))

    if domain not in DOMAINS:
        print(f"Warning: unknown domain '{domain}', using '{DEFAULT_DOMAIN}'")
        domain = DEFAULT_DOMAIN
    if city not in CITIES:
        print(f"Warning: unknown city '{city}', using '{DEFAULT_CITY}'")
        city = DEFAULT_CITY

    return {
        "title": title,
        "text": text,
        "source_url": raw.get("source_url") or raw.get("url") or None,
        "speaker_context": raw.get("speaker_context") or None,
        "domain": domain,
        "city_id": city,
        "case_goal": goal,
        "message_complexity": complexity,
    }


async def _run_one(
    story: dict[str, Any],
    index: int,
    total: int,
    semaphore: asyncio.Semaphore,
    output_dir: Path | None,
) -> dict[str, Any]:
    async with semaphore:
        from app.services.api_simulation import run_simulation_http

        title = story["title"]
        text = story["text"]

        if len(text) < 12:
            return {
                "index": index,
                "title": title,
                "error": "Text too short (min 12 characters).",
                "skipped": True,
            }

        print(f"\n[{index}/{total}] {title[:100]}")
        print(f"  domain={story['domain']}  city={story['city_id']}  complexity={story['message_complexity']}")

        t0 = time.monotonic()
        try:
            result = await run_simulation_http(
                city_id=story["city_id"],
                domain=story["domain"],
                case_goal=story["case_goal"],
                evidence={
                    "text_input": text,
                    "source_url": story["source_url"],
                    "speaker_context": story["speaker_context"],
                    "transcript": None,
                    "edited_analysis_text": None,
                    "audio_input": None,
                },
                message_complexity=story["message_complexity"],
            )
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - t0
            print(f"  TIMEOUT after {elapsed:.0f}s")
            return {"index": index, "title": title, "error": "Pipeline timeout.", "elapsed_s": round(elapsed)}
        except Exception as exc:
            elapsed = time.monotonic() - t0
            print(f"  FAILED after {elapsed:.0f}s: {exc}")
            return {"index": index, "title": title, "error": str(exc), "elapsed_s": round(elapsed)}

        elapsed = time.monotonic() - t0
        run_id = result.get("run_id")
        summary = result.get("summary", {})
        spread = result.get("spread_model", {})

        print(f"  done in {elapsed:.0f}s  run_id={run_id}")
        print(f"  agents: {summary.get('total', '?')}  "
              f"adopted={spread.get('belief_adoption_rate', '?')}%  "
              f"risk={spread.get('spread_risk', '?')}")

        entry = {
            "index": index,
            "title": title,
            "domain": story["domain"],
            "city_id": story["city_id"],
            "elapsed_s": round(elapsed),
            "run_id": run_id,
            "summary": summary,
            "spread_risk": spread.get("spread_risk"),
            "adoption_rate": spread.get("belief_adoption_rate"),
            "case_summary": result.get("case_summary"),
            "result": result,
        }

        if output_dir:
            slug = _slug(title)
            out_path = output_dir / f"{index:02d}-{slug}.json"
            out_path.write_text(json.dumps(entry, indent=2, default=str))
            print(f"  saved → {out_path.name}")

        return entry


def _slug(title: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60]


def _build_markdown_report(results: list[dict[str, Any]], started_at: str) -> str:
    lines: list[str] = []
    lines.append(f"# Cortexia Weekly Briefing")
    lines.append(f"**{started_at}**  |  {len(results)} stories analyzed\n")

    valid = [r for r in results if not r.get("skipped") and not r.get("error")]
    errors = [r for r in results if r.get("error")]
    skipped = [r for r in results if r.get("skipped")]

    if valid:
        high = sum(1 for r in valid if r.get("spread_risk") == "High")
        moderate = sum(1 for r in valid if r.get("spread_risk") == "Moderate")
        low = sum(1 for r in valid if r.get("spread_risk") == "Low")
        lines.append(f"## Risk Breakdown")
        lines.append(f"| Level | Count |")
        lines.append(f"|-------|-------|")
        lines.append(f"| High | {high} |")
        lines.append(f"| Moderate | {moderate} |")
        lines.append(f"| Low | {low} |")
        lines.append("")

        total_adopted = sum(
            r.get("adoption_rate", 0) or 0 for r in valid
        )
        avg_adoption = total_adopted / len(valid) if valid else 0
        lines.append(f"**Average adoption rate:** {avg_adoption:.1f}%\n")

    lines.append("## Story-by-Story\n")
    for r in results:
        idx = r["index"]
        title = r["title"]
        if r.get("skipped"):
            lines.append(f"### {idx}. {title}  ⏭️ SKIPPED")
            lines.append(f"_{r['error']}_\n")
        elif r.get("error"):
            lines.append(f"### {idx}. {title}  ❌ FAILED")
            lines.append(f"_{r['error']}_\n")
        else:
            risk = r.get("spread_risk", "?")
            adoption = r.get("adoption_rate", "?")
            emoji = {"High": "🔴", "Moderate": "🟡", "Low": "🟢"}.get(risk, "⚪")
            summary = (r.get("case_summary") or {}).get("key_finding", "")
            lines.append(f"### {idx}. {title}")
            lines.append(f"{emoji} **Risk: {risk}**  |  Adoption: {adoption}%  |  {r['elapsed_s']:.0f}s")
            if summary:
                lines.append(f"> {summary}")
            lines.append("")

    if errors:
        lines.append("## Errors\n")
        for r in errors:
            lines.append(f"- **{r['title']}**: {r['error']}")

    lines.append(f"\n---\n*Generated by Cortexia weekly briefing*")
    return "\n".join(lines)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Cortexia weekly briefing")
    parser.add_argument("input", nargs="?", help="JSON file with story array")
    parser.add_argument("--headline", help="Quick single-headline mode")
    parser.add_argument("--domain", default=DEFAULT_DOMAIN, help=f"Default domain ({', '.join(sorted(DOMAINS))})")
    parser.add_argument("--city", default=DEFAULT_CITY, help=f"Default city ({', '.join(sorted(CITIES))})")
    parser.add_argument("--goal", help="Default case goal")
    parser.add_argument("--complexity", type=float, default=0.5, help="Message complexity 0-1")
    parser.add_argument("-o", "--output", help="Output directory for individual results")
    parser.add_argument("-p", "--parallel", type=int, default=1, help="Concurrent simulations")
    parser.add_argument("--no-report", action="store_true", help="Skip markdown report")
    args = parser.parse_args()

    _ensure_timeouts()

    if args.headline:
        stories = [_normalize_story(_parse_headline(args.headline), args)]
    elif args.input:
        raw = _load_stories(args.input)
        stories = [_normalize_story(s, args) for s in raw]
    else:
        parser.print_help()
        sys.exit(1)

    if not stories:
        print("No stories to process.")
        sys.exit(1)

    output_dir = None
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sem = asyncio.Semaphore(max(1, args.parallel))

    print(f"Cortexia Weekly Briefing — {len(stories)} stories, parallel={args.parallel}")
    print(f"TRIBE runtime: {os.environ.get('TRIBE_RUNTIME_MODE', 'framework')}")
    print(f"Timeouts: tribe={os.environ.get('simulate_tribe_timeout_seconds', '?')}s  "
          f"total={os.environ.get('simulate_total_timeout_seconds', '?')}s")
    print("=" * 60)

    global_t0 = time.monotonic()

    tasks = [
        _run_one(story, i + 1, len(stories), sem, output_dir)
        for i, story in enumerate(stories)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    global_elapsed = time.monotonic() - global_t0
    succeeded = sum(1 for r in results if not r.get("error") and not r.get("skipped"))
    failed = sum(1 for r in results if r.get("error"))
    skipped = sum(1 for r in results if r.get("skipped"))

    print(f"\n{'=' * 60}")
    print(f"Done in {global_elapsed:.0f}s  |  {succeeded} ok  {failed} failed  {skipped} skipped")

    if not args.no_report:
        report = _build_markdown_report(results, started_at)
        report_path = output_dir / "weekly-briefing.md" if output_dir else Path("weekly-briefing.md")
        report_path.write_text(report)
        print(f"Report → {report_path}")

    if output_dir:
        summary_path = output_dir / "results.json"
        summary_path.write_text(json.dumps(
            [{"index": r["index"], "title": r["title"], "spread_risk": r.get("spread_risk"),
              "adoption_rate": r.get("adoption_rate"), "error": r.get("error"),
              "elapsed_s": r.get("elapsed_s")} for r in results],
            indent=2,
        ))
        print(f"Summary → {summary_path}")


if __name__ == "__main__":
    asyncio.run(_main())

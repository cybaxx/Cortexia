#!/usr/bin/env python3
"""Batch-run simulations on 2026 policy/public health stories."""

import json
import sys
import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000/api/simulate"

STORIES = [
    {
        "id": "immigration",
        "domain": "Public Policy",
        "city_id": "houston-tx",
        "case_goal": "Assess how border security and immigration reform messaging spreads",
        "message_complexity": 0.7,
        "evidence": {
            "text_input": "A federal immigration bill expands border security funding while creating a pathway to citizenship for undocumented residents. Supporters call it a balanced compromise. Opponents say it rewards illegal immigration and fails to secure the border.",
            "speaker_context": "Bipartisan lawmakers promote the bill as a middle-ground solution. Immigration advocacy groups and border state officials are divided on the provisions."
        }
    },
    {
        "id": "healthcare",
        "domain": "Public Health",
        "city_id": "miami-fl",
        "case_goal": "Assess how a drug pricing reform campaign spreads",
        "message_complexity": 0.6,
        "evidence": {
            "text_input": "Congress passed legislation allowing Medicare to negotiate drug prices directly with pharmaceutical companies. Insulin is capped at $35 per month. Supporters say it will save lives. Pharma lobbyists warn it will stifle innovation and reduce new drug development.",
            "speaker_context": "Patient advocacy groups celebrate the reform. Pharmaceutical industry runs ads warning of reduced research funding and fewer new treatments."
        }
    },
    {
        "id": "climate",
        "domain": "Public Policy",
        "city_id": "phoenix-az",
        "case_goal": "Assess how a climate resilience and clean energy transition plan spreads",
        "message_complexity": 0.6,
        "evidence": {
            "text_input": "A federal climate plan mandates 50% renewable energy by 2035, funds electric vehicle charging networks, and provides grants for communities transitioning away from fossil fuel jobs. Supporters say it addresses the climate crisis. Critics call it a job-killing government overreach that raises energy costs.",
            "speaker_context": "Environmental groups push for faster transition. Energy industry and manufacturing unions warn of economic disruption in fossil-fuel-dependent communities."
        }
    },
    {
        "id": "housing",
        "domain": "Public Policy",
        "city_id": "los-angeles-ca",
        "case_goal": "Assess how a housing affordability and homelessness intervention plan spreads",
        "message_complexity": 0.6,
        "evidence": {
            "text_input": "The city proposes zoning reforms to allow higher-density housing, rent stabilization measures, and $500M for homeless shelter construction and mental health services. Supporters say it addresses the housing crisis. Homeowner groups warn it will lower property values and change neighborhood character.",
            "speaker_context": "Housing advocates and homelessness organizations support the plan. Neighborhood associations and property owner groups organize opposition."
        }
    },
    {
        "id": "election",
        "domain": "Public Policy",
        "city_id": "chicago-il",
        "case_goal": "Assess how an election integrity and voting access reform spreads",
        "message_complexity": 0.6,
        "evidence": {
            "text_input": "New voting laws require voter ID, limit mail-in ballots, and reduce early voting days. Supporters say it prevents fraud and restores confidence in elections. Opponents call it voter suppression that disproportionately affects minority and elderly voters.",
            "speaker_context": "State officials promote the laws as election security measures. Civil rights organizations challenge them in court as unconstitutional restrictions on voting rights."
        }
    },
    {
        "id": "ai_regulation",
        "domain": "Public Policy",
        "city_id": "new-york-ny",
        "case_goal": "Assess how AI regulation and tech accountability measures spread",
        "message_complexity": 0.7,
        "evidence": {
            "text_input": "Congress is considering an AI safety bill requiring algorithmic transparency, bias testing for automated decision systems, and liability for AI-generated harms. Tech companies say it will slow innovation. Consumer advocates say it is necessary to protect the public from unaccountable AI systems.",
            "speaker_context": "Tech industry lobbyists push for voluntary standards instead of regulation. Consumer protection groups and researchers argue self-regulation has failed and federal oversight is needed."
        }
    },
]


async def run_batch():
    timeout = httpx.Timeout(1800.0, connect=10.0)
    results = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        for story in STORIES:
            print(f"\n{'='*60}")
            print(f"Running: {story['id']} — {story['case_goal'][:80]}")
            print(f"City: {story['city_id']} | Domain: {story['domain']}")
            start = time.perf_counter()

            try:
                resp = await client.post(API, json=story)
                resp.raise_for_status()
                data = resp.json()
                elapsed = time.perf_counter() - start
                summary = data.get("summary", {})
                mr = data.get("macro_result", {})
                
                result = {
                    "id": story["id"],
                    "run_id": data.get("run_id"),
                    "risk": mr.get("risk_level"),
                    "score": mr.get("score"),
                    "adopted": summary.get("adopted", 0),
                    "rejected": summary.get("rejected", 0),
                    "neutral": summary.get("neutral", 0),
                    "total": summary.get("total", 0),
                    "adoption_pct": round(summary.get("adopted", 0) / max(1, summary.get("total", 1)) * 100),
                    "elapsed_s": round(elapsed, 1),
                    "case_goal": story["case_goal"],
                    "city": story["city_id"],
                    "domain": story["domain"],
                }
                results.append(result)

                print(f"  Risk: {result['risk']} ({result['score']})")
                print(f"  A={result['adopted']} R={result['rejected']} N={result['neutral']} ({result['adoption_pct']}%)")
                print(f"  Pipeline: {result['elapsed_s']:.0f}s")

            except Exception as e:
                print(f"  FAILED: {e}")
                results.append({
                    "id": story["id"],
                    "error": str(e),
                    "case_goal": story["case_goal"],
                })

    # Summary table
    print(f"\n{'='*80}")
    print(f"{'Story':<20} {'City':<16} {'Risk':<10} {'Score':<6} {'A':<4} {'R':<4} {'N':<4} {'Adopt%':<7} {'Time':<8}")
    print("-" * 80)
    for r in results:
        if "error" in r:
            print(f"{r['id']:<20} {'ERROR':<16} {r['error'][:50]}")
        else:
            print(f"{r['id']:<20} {r['city']:<16} {r['risk']:<10} {r['score']:<6} "
                  f"{r['adopted']:<4} {r['rejected']:<4} {r['neutral']:<4} "
                  f"{r['adoption_pct']:<6}% {r['elapsed_s']:<8.0f}s")

    # Save results
    out_path = Path(__file__).resolve().parent.parent / "batch_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_batch())

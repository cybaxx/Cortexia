#!/usr/bin/env python3
"""Manage the Cortexia vector database.

Usage:
    source .venv/bin/activate
    python scripts/vector_import.py status          # Show collection stats
    python scripts/vector_import.py import-runs     # Re-index all runs
    python scripts/vector_import.py import-agents   # Re-index all agents
    python scripts/vector_import.py import-all      # Index everything
    python scripts/vector_import.py search <query>  # Test a semantic search
    python scripts/vector_import.py clear           # Clear and re-index
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.services.vector_store import (
    _get_collection,
    index_agent,
    index_all_existing_runs,
    index_run,
    is_available,
    search_runs,
)
from app.pipeline_store import fetch_case_run, list_recent_runs


def cmd_status():
    if not is_available():
        print("Vector store unavailable.")
        return
    runs_col = _get_collection("cortexia_runs")
    agents_col = _get_collection("cortexia_agents")
    print(f"Runs:   {runs_col.count() if runs_col else 0}")
    print(f"Agents: {agents_col.count() if agents_col else 0}")
    print(f"Path:   {BACKEND_DIR / 'vector_db'}")


def cmd_search(query: str):
    results = search_runs(query, limit=5)
    print(f"Search: \"{query}\"")
    print("-" * 60)
    for r in results:
        bar = "█" * int(r["similarity"] * 20)
        print(f"  #{r['run_id']:>4}  {r['similarity']:.0%}  {bar}")
        print(f"         {r['domain']} / {r['city_id']} / {r.get('risk_level','?')}")
        print(f"         {r['snippet'][:100]}")
        print()


def cmd_import_agents():
    if not is_available():
        print("Vector store unavailable.")
        return
    runs = list_recent_runs(limit=200)
    total = 0
    for run in runs:
        rid = run["id"]
        record = fetch_case_run(rid)
        if not record:
            continue
        agents = (record.get("response") or {}).get("agents", [])
        for agent in agents[:12]:
            if index_agent(run_id=rid, agent=agent):
                total += 1
    print(f"Indexed {total} agents from {len(runs)} runs.")


def cmd_import_runs():
    indexed = index_all_existing_runs()
    print(f"Indexed {indexed} runs.")


def cmd_clear():
    import shutil
    vdb = BACKEND_DIR / "vector_db"
    if vdb.exists():
        shutil.rmtree(vdb)
        print("Cleared vector DB. Restart backend to re-index.")
    else:
        print("No vector DB found.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        cmd_status()
    elif cmd == "search":
        query = " ".join(sys.argv[2:])
        cmd_search(query)
    elif cmd == "import-runs":
        cmd_import_runs()
    elif cmd == "import-agents":
        cmd_import_agents()
    elif cmd == "import-all":
        cmd_import_runs()
        cmd_import_agents()
    elif cmd == "clear":
        cmd_clear()
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: status, search, import-runs, import-agents, import-all, clear")

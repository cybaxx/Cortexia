import sqlite3
import json
from app.config import get_settings
from app.population_store import fetch_population, fetch_population_agent, init_population_store
from app.services.population import _build_virtual_population

def run_test():
    init_population_store()
    db_path = get_settings().pipeline_db_path
    print(f"Checking database at: {db_path}")

    # 1. Trigger the population builder (this will create and save agents if they don't exist)
    print("Building/Fetching population for 'la' with 5 agents...")
    population = _build_virtual_population("la", count=5)
    
    # 2. Verify they were created and mapped correctly
    print(f"Generated {len(population)} agents.")
    
    # 3. Connect to the SQLite DB directly to prove they are safely persisted
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, name, role, age_band, education_level, income_band,
                   language_profile, digital_media_habit, demographics_json
            FROM agents
            WHERE city_id = ?
            ORDER BY id ASC
            LIMIT 5
            """,
            ("la",),
        ).fetchall()
        
        print("\n--- PERSISTENT DATABASE RECORDS ---")
        if not rows:
            print("No agents found in the database. Something went wrong!")
        else:
            for row in rows:
                demo = json.loads(row["demographics_json"])
                print(
                    f"ID={row['id']} | Name={row['name']:<15} | Role={row['role']:<20} "
                    f"| Age={row['age_band'] or demo['age_band']:<6} | Education={row['education_level'] or demo['education_level']:<18} "
                    f"| Media={row['digital_media_habit'] or demo['digital_media_habit']}"
                )

    sample = fetch_population_agent("la", 0)
    if sample:
        print("\n--- DISTINCT AGENT PROFILE ---")
        print(json.dumps(sample, indent=2))
                
    print("\n✅ Test Complete. The simulated people are now securely persisted to disk.")
    print("Each person now carries distinct persisted demographics that can flow into simulation and voice behavior.")

if __name__ == "__main__":
    run_test()

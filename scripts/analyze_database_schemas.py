"""
Extract schema information from all Jarvis databases.
Phase 1 Task 2 - Schema Analysis
"""

import sqlite3
import json
from pathlib import Path
from collections import defaultdict

# Database paths
databases = [
    "data/jarvis.db",
    "data/jarvis_admin.db",
    "data/jarvis_memory.db",
    "data/telegram_memory.db",
    "data/jarvis_x_memory.db",
    "data/jarvis_spam_protection.db",
    "data/treasury_trades.db",
    "data/llm_costs.db",
    "data/metrics.db",
    "data/health.db",
    "data/bot_health.db",
    "data/sentiment.db",
    "data/research.db",
    "data/cache/file_cache.db",
    "data/rate_limiter.db",
    "data/custom.db",
    "data/community/achievements.db",
    "data/whales.db",
    "data/call_tracking.db",
    "data/distributions.db",
    "data/raid_bot.db",
    "data/backtests.db",
    "data/tax.db",
    "bots/twitter/engagement.db",
    "database.db",
]

def extract_schema(db_path):
    """Extract schema from a single database."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        schema_info = {
            "database": db_path,
            "table_count": len(tables),
            "tables": {}
        }
        
        for (table_name,) in tables:
            # Get table info
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            row_count = cursor.fetchone()[0]
            
            schema_info["tables"][table_name] = {
                "columns": [
                    {
                        "name": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "default": col[4],
                        "pk": bool(col[5])
                    }
                    for col in columns
                ],
                "row_count": row_count
            }
        
        conn.close()
        return schema_info
        
    except Exception as e:
        return {
            "database": db_path,
            "error": str(e)
        }

def main():
    """Extract schemas from all databases."""
    results = []
    
    print("Extracting schemas from 25 databases...")
    print("=" * 60)
    
    for db_path in databases:
        full_path = Path(db_path)
        if not full_path.exists():
            print(f"⚠️  SKIP: {db_path} (not found)")
            continue
        
        print(f"📊 Analyzing: {db_path}")
        schema = extract_schema(db_path)
        
        if "error" in schema:
            print(f"   ❌ ERROR: {schema['error']}")
        else:
            print(f"   ✅ {schema['table_count']} tables found")
            total_rows = sum(t["row_count"] for t in schema["tables"].values())
            print(f"   📈 {total_rows:,} total rows")
        
        results.append(schema)
    
    # Save results
    output_file = ".planning/phases/01-database-consolidation/schema_analysis.json"
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "=" * 60)
    print(f"✅ Schema analysis complete!")
    print(f"📁 Saved to: {output_file}")
    
    # Print summary
    print("\n📊 SUMMARY")
    print("=" * 60)
    total_tables = sum(s.get("table_count", 0) for s in results if "error" not in s)
    total_dbs = len([s for s in results if "error" not in s])
    errors = len([s for s in results if "error" in s])
    
    print(f"Databases analyzed: {total_dbs}")
    print(f"Total tables: {total_tables}")
    print(f"Errors: {errors}")

if __name__ == "__main__":
    main()

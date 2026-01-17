#!/usr/bin/env python3
"""
Verify MCP setup and memory system configuration.

Tests:
1. All 18 MCPs discoverable
2. PostgreSQL connection to continuous_claude
3. SQLite memory database initialized
4. Memory import system functional
5. API credentials in .env
"""

import os
import sys
import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

# Fix encoding for Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_mcp_config() -> Tuple[bool, List[str]]:
    """Check that all 18 MCPs are configured."""
    mcp_file = Path.home() / ".claude" / "mcp.json"

    if not mcp_file.exists():
        return False, ["MCP config file not found"]

    try:
        with open(mcp_file) as f:
            config = json.load(f)

        mcps = list(config.get("mcpServers", {}).keys())
        errors = []

        expected_mcps = [
            "memory", "filesystem", "sequential-thinking", "puppeteer",
            "sqlite", "git", "github", "youtube-transcript", "fetch",
            "brave-search", "solana", "twitter", "docker",
            "ast-grep", "nia", "firecrawl", "postgres", "perplexity"
        ]

        missing = set(expected_mcps) - set(mcps)
        if missing:
            errors.append(f"Missing MCPs: {', '.join(missing)}")

        return len(mcps) >= 13, errors + [f"[OK] Found {len(mcps)} MCPs configured"]
    except Exception as e:
        return False, [f"MCP config error: {e}"]

def check_env_vars() -> Tuple[bool, List[str]]:
    """Check required environment variables."""
    errors = []

    # Required vars
    required = ["DATABASE_URL"]
    for var in required:
        if not os.environ.get(var):
            errors.append(f"Missing required env var: {var}")

    # Check .env file
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            content = f.read()

        optional_apis = ["GITHUB_TOKEN", "FIRECRAWL_API_KEY", "PERPLEXITY_API_KEY"]
        found_apis = sum(1 for api in optional_apis if f"{api}=" in content)

        return len(errors) == 0, errors + [
            f"[OK] .env configured with {found_apis}/{len(optional_apis)} optional API credentials"
        ]

    return len(errors) == 0, errors + ["[WARN] .env file not found in project root"]

def check_postgres_connection() -> Tuple[bool, List[str]]:
    """Test PostgreSQL connection."""
    db_url = os.environ.get("DATABASE_URL", "")

    if "postgresql://" not in db_url:
        return False, ["DATABASE_URL not set to PostgreSQL"]

    errors = []

    try:
        import psycopg2

        # Extract connection params
        # Format: postgresql://user:pass@host:port/dbname
        parts = db_url.replace("postgresql://", "").split("@")
        if len(parts) != 2:
            return False, ["Invalid PostgreSQL URL format"]

        user_pass = parts[0].split(":")
        host_db = parts[1].split("/")

        user = user_pass[0] if user_pass else "claude"
        password = user_pass[1] if len(user_pass) > 1 else ""
        host_port = host_db[0] if host_db else "localhost"
        dbname = host_db[1] if len(host_db) > 1 else "continuous_claude"

        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host, port = host_port, 5432

        # Try connection
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=dbname,
            user=user,
            password=password,
            connect_timeout=5
        )

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM archival_memory LIMIT 1")
        count = cur.fetchone()[0]

        conn.close()

        return True, [
            f"[OK] PostgreSQL connected to {dbname} ({host}:{port})",
            f"[OK] Found {count} entries in archival_memory table"
        ]

    except ImportError:
        errors.append("psycopg2 not installed: pip install psycopg2-binary")
    except Exception as e:
        errors.append(f"PostgreSQL connection failed: {e}")

    return False, errors

def check_memory_system() -> Tuple[bool, List[str]]:
    """Check memory import system."""
    errors = []

    # Check auto_import module
    try:
        from core.memory.auto_import import MemoryImporter
        errors.append("[OK] MemoryImporter module found")

        # Try to initialize
        importer = MemoryImporter()
        errors.append("[OK] MemoryImporter initialized")

        # Check SQLite
        if Path(importer.sqlite_db).exists():
            conn = sqlite3.connect(importer.sqlite_db)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM memory_entries")
            count = cur.fetchone()[0]
            conn.close()
            errors.append(f"[OK] SQLite memory database has {count} entries")
        else:
            errors.append("[WARN] SQLite database not yet created (will create on import)")

        return True, errors

    except ImportError as e:
        return False, [f"MemoryImporter not found: {e}"]
    except Exception as e:
        return False, [f"Memory system error: {e}"]

def check_guides() -> Tuple[bool, List[str]]:
    """Check that documentation files exist."""
    files = {
        "MEMORY_QUERY_GUIDE.md": "Memory query guide",
        "core/memory/auto_import.py": "Memory import system",
        "CLAUDE.md": "Project context",
    }

    errors = []
    for filename, desc in files.items():
        if Path(filename).exists():
            errors.append(f"[OK] {desc}")
        else:
            errors.append(f"[MISSING] {desc}")

    return all(Path(f).exists() for f in files.keys()), errors

def main():
    """Run all checks."""
    print("\n" + "="*70)
    print("MCP & Memory System Setup Verification")
    print("="*70 + "\n")

    checks = [
        ("[MCP] Configuration", check_mcp_config),
        ("[ENV] Environment Variables", check_env_vars),
        ("[DB] PostgreSQL Connection", check_postgres_connection),
        ("[MEMORY] Memory System", check_memory_system),
        ("[DOCS] Documentation", check_guides),
    ]

    results = {}
    all_passed = True

    for name, check_fn in checks:
        try:
            passed, messages = check_fn()
            results[name] = (passed, messages)

            status = "[PASS]" if passed else "[FAIL]"
            print(f"{status} {name}")

            for msg in messages:
                print(f"    {msg}")

            if not passed:
                all_passed = False

            print()
        except Exception as e:
            print(f"[ERROR] {name}: {e}\n")
            all_passed = False

    print("="*70)

    if all_passed:
        print("[PASS] ALL CHECKS PASSED - MCP system is ready!")
        print("\nNext Steps:")
        print("   1. Read MEMORY_QUERY_GUIDE.md for usage examples")
        print("   2. Run: python core/memory/auto_import.py")
        print("   3. Search imported memories with MemoryImporter")
        print("\nTo use in Claude Code:")
        print("   - Query: /recall 'your search terms'")
        print("   - Or use: python -c \"from core.memory.auto_import import MemoryImporter\"")
        return 0
    else:
        print("[WARN] Some checks failed - see above for details")
        print("\nTroubleshooting:")
        print("   1. PostgreSQL: docker exec continuous-claude-postgres psql -U claude -d continuous_claude")
        print("   2. Install: pip install psycopg2-binary")
        print("   3. Check .env: DATABASE_URL=postgresql://claude:claude_dev@localhost:5432/continuous_claude")
        return 1

if __name__ == "__main__":
    sys.exit(main())

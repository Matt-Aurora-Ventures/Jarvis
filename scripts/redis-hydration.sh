#!/bin/bash
# Jarvis Redis Hydration Script
# Syncs hot state from persistent storage to Redis for sub-millisecond recovery
#
# Schedule via cron: 0 */6 * * * /bin/bash /home/jarvis/Jarvis/scripts/redis-hydration.sh

set -euo pipefail

JARVIS_HOME="${JARVIS_HOME:-/home/jarvis/Jarvis}"
LOG_FILE="${JARVIS_HOME}/logs/redis-hydration.log"
VENV_PYTHON="${JARVIS_HOME}/venv/bin/python3"

# Start logging
exec >> "${LOG_FILE}" 2>&1

echo "=========================================="
echo "Redis Hydration Started: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "=========================================="

cd "${JARVIS_HOME}"

# Load environment
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Check if Redis is available
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

if ! redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping > /dev/null 2>&1; then
    echo "WARNING: Redis not available at ${REDIS_HOST}:${REDIS_PORT}, skipping hydration"
    exit 0
fi

echo "Redis connection: OK"

# Hydrate from PostgreSQL if available
${VENV_PYTHON} << 'PYTHON_SCRIPT'
import os
import sys
import json
import redis
from datetime import datetime

sys.path.insert(0, os.environ.get('JARVIS_HOME', '/home/jarvis/Jarvis'))

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))

try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    r.ping()
    print(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    print(f"Redis connection failed: {e}")
    sys.exit(0)

hydrated_count = 0

# 1. Hydrate recent conversation context from PostgreSQL
try:
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Get recent episodic memories (last 24h)
        cur.execute("""
            SELECT id, content, context, tags, created_at
            FROM archival_memory
            WHERE created_at > NOW() - INTERVAL '24 hours'
            ORDER BY created_at DESC
            LIMIT 100
        """)

        for row in cur.fetchall():
            memory_id, content, context, tags, created_at = row
            key = f"jarvis:memory:{memory_id}"
            r.hset(key, mapping={
                'content': content or '',
                'context': context or '',
                'tags': json.dumps(tags or []),
                'created_at': created_at.isoformat() if created_at else ''
            })
            r.expire(key, 86400)  # 24 hour TTL
            hydrated_count += 1

        cur.close()
        conn.close()
        print(f"Hydrated {hydrated_count} memories from PostgreSQL")
except ImportError:
    print("psycopg2 not available, skipping PostgreSQL hydration")
except Exception as e:
    print(f"PostgreSQL hydration error: {e}")

# 2. Hydrate active session context from JSON files
state_files = [
    ('jarvis:state:positions', 'bots/treasury/.positions.json'),
    ('jarvis:state:grok', 'bots/twitter/.grok_state.json'),
    ('jarvis:state:trust_ladder', 'data/trust_ladder.json'),
    ('jarvis:state:context', 'bots/data/context_state.json'),
]

for redis_key, file_path in state_files:
    full_path = os.path.join(os.environ.get('JARVIS_HOME', '/home/jarvis/Jarvis'), file_path)
    try:
        if os.path.exists(full_path):
            with open(full_path) as f:
                data = json.load(f)
            r.set(redis_key, json.dumps(data))
            r.expire(redis_key, 3600)  # 1 hour TTL
            print(f"Hydrated {redis_key} from {file_path}")
            hydrated_count += 1
    except Exception as e:
        print(f"Failed to hydrate {redis_key}: {e}")

# 3. Set hydration timestamp
r.set('jarvis:hydration:last', datetime.utcnow().isoformat())

print(f"Total items hydrated: {hydrated_count}")
PYTHON_SCRIPT

echo "Redis hydration completed: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "=========================================="

#!/bin/bash
# Jarvis Nightly Self-Evolution Reflection Cycle
# Runs at 4:00 AM UTC to analyze the day's performance and improve
# Part of the Learning Loop: Observe -> Predict -> Act -> Measure -> REFLECT -> IMPROVE
#
# Schedule via cron: 0 4 * * * /bin/bash /home/jarvis/Jarvis/scripts/self-evolution-reflect.sh

set -euo pipefail

# Configuration
JARVIS_HOME="${JARVIS_HOME:-/home/jarvis/Jarvis}"
LOG_DIR="${JARVIS_HOME}/logs"
DATA_DIR="${JARVIS_HOME}/data"
REFLECTION_LOG="${LOG_DIR}/reflection_$(date +%Y%m%d_%H%M%S).log"
VENV_PYTHON="${JARVIS_HOME}/venv/bin/python3"

# Ensure directories exist
mkdir -p "${LOG_DIR}" "${DATA_DIR}"

# Start logging
exec > >(tee -a "${REFLECTION_LOG}") 2>&1

echo "=========================================="
echo "JARVIS NIGHTLY REFLECTION CYCLE"
echo "Started: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "=========================================="

cd "${JARVIS_HOME}"

# Load environment
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Phase 1: MEASURE - Collect metrics from the past 24 hours
echo ""
echo "=== PHASE 1: MEASURE ==="
echo "Collecting performance metrics from the past 24 hours..."

# Trading performance (if treasury module exists)
if [ -f "${JARVIS_HOME}/bots/treasury/trading.py" ]; then
    echo "Analyzing trading performance..."
    ${VENV_PYTHON} -c "
import json
from pathlib import Path
from datetime import datetime, timedelta

try:
    positions_file = Path('${JARVIS_HOME}/bots/treasury/.positions.json')
    if positions_file.exists():
        with open(positions_file) as f:
            positions = json.load(f)
        print(f'  Total positions: {len(positions)}')
        # Calculate P&L if possible
        total_pnl = sum(p.get('pnl_pct', 0) for p in positions.values() if isinstance(p, dict))
        print(f'  Aggregate P&L: {total_pnl:.2f}%')
    else:
        print('  No position data found')
except Exception as e:
    print(f'  Trading analysis error: {e}')
" 2>&1 || echo "  Trading analysis unavailable"
fi

# Communication effectiveness (X/Twitter engagement)
echo "Analyzing X/Twitter engagement..."
${VENV_PYTHON} -c "
import json
from pathlib import Path

try:
    grok_state = Path('${JARVIS_HOME}/bots/twitter/.grok_state.json')
    if grok_state.exists():
        with open(grok_state) as f:
            state = json.load(f)
        print(f'  Total posts today: {state.get(\"posts_today\", 0)}')
        print(f'  Daily cost: \${state.get(\"daily_cost_usd\", 0):.2f}')
    else:
        print('  No engagement data found')
except Exception as e:
    print(f'  Engagement analysis error: {e}')
" 2>&1 || echo "  Engagement analysis unavailable"

# Phase 2: REFLECT - Analyze what worked and what didn't
echo ""
echo "=== PHASE 2: REFLECT ==="
echo "Analyzing patterns and outcomes..."

# Use self_learning module if available
if [ -f "${JARVIS_HOME}/core/autonomy/self_learning.py" ]; then
    echo "Running self-learning pattern analysis..."
    ${VENV_PYTHON} -c "
import sys
sys.path.insert(0, '${JARVIS_HOME}')
try:
    from core.autonomy.self_learning import SelfLearningEngine
    engine = SelfLearningEngine()
    # Analyze patterns from the last 24 hours
    patterns = engine.analyze_patterns(hours=24)
    print(f'  Patterns identified: {len(patterns) if patterns else 0}')
    if patterns:
        for p in patterns[:3]:  # Top 3 patterns
            print(f'    - {p.get(\"description\", \"Unknown pattern\")}')
except Exception as e:
    print(f'  Self-learning analysis error: {e}')
" 2>&1 || echo "  Self-learning module not available"
fi

# Use confidence_scorer if available
if [ -f "${JARVIS_HOME}/core/confidence_scorer.py" ]; then
    echo "Scoring prediction accuracy..."
    ${VENV_PYTHON} -c "
import sys
sys.path.insert(0, '${JARVIS_HOME}')
try:
    from core.confidence_scorer import ConfidenceScorer
    scorer = ConfidenceScorer()
    accuracy = scorer.calculate_accuracy(hours=24)
    print(f'  Prediction accuracy (24h): {accuracy:.1f}/10' if accuracy else '  No predictions to score')
except Exception as e:
    print(f'  Confidence scoring error: {e}')
" 2>&1 || echo "  Confidence scorer not available"
fi

# Phase 3: IMPROVE - Store learnings in semantic memory
echo ""
echo "=== PHASE 3: IMPROVE ==="
echo "Storing learnings in semantic memory..."

# Store reflection results in memory system
${VENV_PYTHON} -c "
import sys
import json
from datetime import datetime
sys.path.insert(0, '${JARVIS_HOME}')

reflection_summary = {
    'timestamp': datetime.utcnow().isoformat(),
    'type': 'NIGHTLY_REFLECTION',
    'metrics_collected': True,
    'patterns_analyzed': True,
    'learnings_stored': True
}

try:
    # Try to store in memory system
    from core.memory.memory_system import MemorySystem
    memory = MemorySystem()
    memory.store_learning(
        learning_type='WORKING_SOLUTION',
        content=f'Nightly reflection completed at {datetime.utcnow().isoformat()}',
        context='self-evolution cycle',
        tags=['reflection', 'nightly', 'self-evolution']
    )
    print('  Learnings stored in semantic memory')
except ImportError:
    # Fallback: store to JSON file
    from pathlib import Path
    reflections_file = Path('${DATA_DIR}/reflections.json')
    reflections = []
    if reflections_file.exists():
        with open(reflections_file) as f:
            reflections = json.load(f)
    reflections.append(reflection_summary)
    # Keep last 30 days
    reflections = reflections[-30:]
    with open(reflections_file, 'w') as f:
        json.dump(reflections, f, indent=2)
    print('  Learnings stored to local file (memory system unavailable)')
except Exception as e:
    print(f'  Memory storage error: {e}')
" 2>&1 || echo "  Memory storage failed"

# Phase 4: UPDATE TRUST LADDER
echo ""
echo "=== PHASE 4: TRUST LADDER STATUS ==="
echo "Checking autonomous action count..."

${VENV_PYTHON} -c "
import sys
import json
from pathlib import Path
sys.path.insert(0, '${JARVIS_HOME}')

try:
    trust_file = Path('${DATA_DIR}/trust_ladder.json')
    if trust_file.exists():
        with open(trust_file) as f:
            trust = json.load(f)
    else:
        trust = {'successful_actions': 0, 'major_errors': 0, 'level': 0}

    level = trust.get('level', 0)
    actions = trust.get('successful_actions', 0)
    errors = trust.get('major_errors', 0)

    # Level thresholds
    levels = {
        0: ('Supervised', 0),
        1: ('Assisted', 10),
        2: ('Monitored', 50),
        3: ('Autonomous', 200),
        4: ('Trusted', 1000)
    }

    level_name, threshold = levels.get(level, ('Unknown', 0))
    next_level = level + 1
    if next_level in levels:
        next_name, next_threshold = levels[next_level]
        progress = actions - threshold
        needed = next_threshold - threshold
        pct = (progress / needed * 100) if needed > 0 else 100
        print(f'  Current Level: {level} ({level_name})')
        print(f'  Successful Actions: {actions}')
        print(f'  Major Errors: {errors}')
        print(f'  Progress to Level {next_level} ({next_name}): {pct:.1f}%')
    else:
        print(f'  Current Level: {level} ({level_name}) - MAX LEVEL')
        print(f'  Successful Actions: {actions}')
except Exception as e:
    print(f'  Trust ladder check error: {e}')
" 2>&1 || echo "  Trust ladder check failed"

# Phase 5: CLEANUP
echo ""
echo "=== PHASE 5: CLEANUP ==="
echo "Cleaning old logs and temporary files..."

# Remove logs older than 7 days
find "${LOG_DIR}" -name "reflection_*.log" -mtime +7 -delete 2>/dev/null || true
find "${LOG_DIR}" -name "*.log" -size +100M -delete 2>/dev/null || true

echo "  Old logs cleaned"

# Summary
echo ""
echo "=========================================="
echo "REFLECTION CYCLE COMPLETE"
echo "Finished: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Log saved to: ${REFLECTION_LOG}"
echo "=========================================="

# Send summary to Telegram if configured
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_ADMIN_IDS:-}" ]; then
    admin_id=$(echo "${TELEGRAM_ADMIN_IDS}" | cut -d',' -f1)
    if [ -n "${admin_id}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${admin_id}" \
            -d "text=Nightly reflection cycle completed at $(date -u '+%H:%M UTC'). Check logs for details." \
            -d "parse_mode=HTML" > /dev/null 2>&1 || true
    fi
fi

exit 0

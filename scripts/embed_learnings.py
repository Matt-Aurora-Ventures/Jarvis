#!/usr/bin/env python3
"""
Embed Learnings from This Session
Extracts lessons and permanently embeds them into the codebase
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Key learnings from this session
LEARNINGS = {
    "gateway_config_persistence": {
        "problem": "Gateway strips unknown keys during validation on startup",
        "wrong_solution": "Using chattr +i to lock config file - doesn't work",
        "correct_solution": "Fix WebSocket binding to 127.0.0.1, then use config.apply RPC",
        "root_cause": "server.impl.js lines 87 and 106 - validation/migration logic removes unknown keys",
        "lesson": "Always use the proper RPC API instead of manual config file editing",
        "file": "scripts/ralph_wiggum_secure_gateway_fix.sh",
        "confidence": "high"
    },

    "backup_strategy": {
        "problem": "Risk of data loss during gateway restarts and fixes",
        "solution": "Dual backup system - local Windows + VPS, both with checksums",
        "implementation": [
            "local_backup_system.ps1 - Windows backup with robocopy",
            "vps_backup_system.sh - VPS backup with scp sync",
            "Both generate SHA256 checksums for integrity",
            "Both keep last 10 backups, auto-cleanup old ones"
        ],
        "lesson": "Never touch production config without comprehensive backups",
        "confidence": "high"
    },

    "security_requirements": {
        "problem": "Need to secure automated task execution from Telegram",
        "measures": [
            "Command sanitization (remove ;|`$()",
            "Dangerous command blocking (rm -rf, dd, wget|sh, etc.)",
            "Timeout enforcement (300s max per task)",
            "Consecutive failure detection (pause after 3 fails)",
            "Credential validation (min length, not placeholders)",
            "File permission restrictions (600 for logs, 700 for archives)",
            "Backup checksums (SHA256)"
        ],
        "lesson": "Security must be built in, not bolted on",
        "file": "scripts/ralph_wiggum_secure_tasks.sh",
        "confidence": "high"
    },

    "ralph_wiggum_pattern": {
        "concept": "Continuous improvement loop until user says stop",
        "implementation": "Loop that: does task → marks complete → finds next task → repeats",
        "benefits": [
            "Handles open-ended goals",
            "Discovers new tasks during execution",
            "Re-scans for new work when done",
            "Maintains momentum"
        ],
        "lesson": "Don't stop after one task - keep iterating on improvements",
        "file": ".claude/rules/ralph-wiggum-loop.md",
        "confidence": "high"
    },

    "telegram_task_extraction": {
        "problem": "Need to extract ALL tasks from multiple Telegram channels",
        "solution": "Scan ALL channels (main + Friday + Jarvis) + voice transcripts",
        "implementation": [
            "Use Telegram Bot API to get message history",
            "Filter messages for task patterns (add, fix, create, etc.)",
            "Prioritize based on role (admin = high, member = normal)",
            "Include voice transcripts (last 30 days)",
            "Compile into master task list with metadata"
        ],
        "lesson": "Comprehensive extraction prevents missed requirements",
        "file": "scripts/ralph_wiggum_secure_tasks.sh",
        "confidence": "high"
    },

    "coordination_between_agents": {
        "problem": "Multiple agents (VPS + local) need to coordinate",
        "solution": "Clear separation of concerns with sync points",
        "pattern": [
            "VPS agent: Gateway config, server setup, task extraction",
            "Local agent: File operations, backup, monitoring",
            "Sync: Backups transferred bidirectionally",
            "Communication: Via shared MASTER_TASK_LIST.md"
        ],
        "lesson": "Define clear boundaries and sync points between agents",
        "confidence": "medium"
    }
}

def create_learning_file(learning_id, learning_data, output_dir):
    """Create a markdown file for each learning"""
    filename = output_dir / f"{learning_id}.md"

    content = f"""# Learning: {learning_id.replace('_', ' ').title()}

**Date**: {datetime.now().strftime('%Y-%m-%d')}
**Confidence**: {learning_data.get('confidence', 'unknown')}

## Problem

{learning_data.get('problem', 'N/A')}

"""

    if 'wrong_solution' in learning_data:
        content += f"""## Wrong Solution

{learning_data['wrong_solution']}

"""

    if 'correct_solution' in learning_data:
        content += f"""## Correct Solution

{learning_data['correct_solution']}

"""

    if 'root_cause' in learning_data:
        content += f"""## Root Cause

{learning_data['root_cause']}

"""

    if 'solution' in learning_data:
        content += f"""## Solution

{learning_data['solution']}

"""

    if 'implementation' in learning_data:
        impl = learning_data['implementation']
        if isinstance(impl, list):
            content += "## Implementation\n\n"
            for item in impl:
                content += f"- {item}\n"
            content += "\n"
        else:
            content += f"""## Implementation

{impl}

"""

    if 'measures' in learning_data:
        content += "## Security Measures\n\n"
        for measure in learning_data['measures']:
            content += f"- {measure}\n"
        content += "\n"

    if 'benefits' in learning_data:
        content += "## Benefits\n\n"
        for benefit in learning_data['benefits']:
            content += f"- {benefit}\n"
        content += "\n"

    if 'pattern' in learning_data:
        pattern = learning_data['pattern']
        if isinstance(pattern, list):
            content += "## Pattern\n\n"
            for item in pattern:
                content += f"- {item}\n"
            content += "\n"
        else:
            content += f"""## Pattern

{pattern}

"""

    if 'lesson' in learning_data:
        content += f"""## Lesson Learned

**{learning_data['lesson']}**

"""

    if 'file' in learning_data:
        content += f"""## Implementation File

See: [`{learning_data['file']}`]({learning_data['file']})

"""

    content += f"""---

*This learning was automatically extracted and embedded from session on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    with open(filename, 'w') as f:
        f.write(content)

    print(f"✅ Created: {filename}")

def create_learnings_index(learnings, output_dir):
    """Create an index of all learnings"""
    filename = output_dir / "INDEX.md"

    content = f"""# Session Learnings Index

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Learnings**: {len(learnings)}

## Learnings by Category

"""

    # Group by confidence
    high_conf = [k for k, v in learnings.items() if v.get('confidence') == 'high']
    medium_conf = [k for k, v in learnings.items() if v.get('confidence') == 'medium']
    low_conf = [k for k, v in learnings.items() if v.get('confidence') == 'low']

    if high_conf:
        content += "### High Confidence\n\n"
        for learning_id in high_conf:
            title = learning_id.replace('_', ' ').title()
            content += f"- [{title}]({learning_id}.md)\n"
        content += "\n"

    if medium_conf:
        content += "### Medium Confidence\n\n"
        for learning_id in medium_conf:
            title = learning_id.replace('_', ' ').title()
            content += f"- [{title}]({learning_id}.md)\n"
        content += "\n"

    if low_conf:
        content += "### Low Confidence\n\n"
        for learning_id in low_conf:
            title = learning_id.replace('_', ' ').title()
            content += f"- [{title}]({learning_id}.md)\n"
        content += "\n"

    content += """---

## How to Use

These learnings are permanently embedded in the codebase. Reference them when:
- Making similar changes
- Debugging related issues
- Onboarding new team members
- Avoiding past mistakes

"""

    with open(filename, 'w') as f:
        f.write(content)

    print(f"✅ Created: {filename}")

def store_in_memory_system(learnings):
    """Store learnings in the OPC memory system"""
    try:
        import subprocess

        opc_dir = Path(__file__).parent.parent / "opc"

        if not opc_dir.exists():
            print("⚠️  OPC directory not found, skipping memory storage")
            return

        for learning_id, learning_data in learnings.items():
            content = learning_data.get('lesson', '')
            context = learning_data.get('problem', '')

            cmd = [
                "uv", "run", "python",
                "scripts/core/store_learning.py",
                "--session-id", f"gateway_fix_{datetime.now().strftime('%Y%m%d')}",
                "--type", "WORKING_SOLUTION",
                "--content", content,
                "--context", context,
                "--tags", f"{learning_id},gateway,security,backup",
                "--confidence", learning_data.get('confidence', 'medium')
            ]

            try:
                result = subprocess.run(
                    cmd,
                    cwd=opc_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    print(f"✅ Stored in memory: {learning_id}")
                else:
                    print(f"⚠️  Memory storage failed for {learning_id}: {result.stderr}")

            except Exception as e:
                print(f"⚠️  Could not store {learning_id} in memory: {e}")

    except Exception as e:
        print(f"⚠️  Memory system not available: {e}")

def main():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("📚 EMBEDDING SESSION LEARNINGS")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    # Output directory
    project_root = Path(__file__).parent.parent
    learnings_dir = project_root / ".claude" / "learnings" / datetime.now().strftime("%Y%m%d")
    learnings_dir.mkdir(parents=True, exist_ok=True)

    print(f"📁 Output directory: {learnings_dir}")
    print()

    # Create individual learning files
    print("📝 Creating learning files...")
    for learning_id, learning_data in LEARNINGS.items():
        create_learning_file(learning_id, learning_data, learnings_dir)

    print()

    # Create index
    print("📇 Creating index...")
    create_learnings_index(LEARNINGS, learnings_dir)

    print()

    # Store in memory system
    print("🧠 Storing in memory system...")
    store_in_memory_system(LEARNINGS)

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ LEARNINGS EMBEDDED SUCCESSFULLY")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print(f"📊 Summary:")
    print(f"  Total learnings: {len(LEARNINGS)}")
    print(f"  Location: {learnings_dir}")
    print(f"  Index: {learnings_dir}/INDEX.md")

if __name__ == "__main__":
    main()

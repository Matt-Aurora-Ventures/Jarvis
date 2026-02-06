#!/usr/bin/env python3
"""GRU Integration Test Suite - Phase 9.17"""
import json
import subprocess
import sqlite3
import sys
sys.path.insert(0, "/root/clawdbots")

print("=== GRU INTEGRATION TEST SUITE ===\n")
passed = 0
failed = 0

def check(name, fn):
    global passed, failed
    try:
        result = fn()
        print(f"[PASS] {name}: {result}")
        passed += 1
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        failed += 1

# 1. Services
def test_services():
    for bot in ["clawdmatt", "clawdjarvis", "clawdfriday"]:
        r = subprocess.run(["systemctl", "is-active", bot], capture_output=True, text=True)
        assert r.stdout.strip() == "active", f"{bot} is {r.stdout.strip()}"
    return "all 3 active"
check("Services", test_services)

# 2. Allowlist
def test_allowlist():
    from bots.shared.allowlist import load_allowlist
    al = load_allowlist()
    return f"{len(al)} users"
check("Allowlist", test_allowlist)

# 3. SuperMemory + FTS5
def test_supermemory():
    db = sqlite3.connect("/root/clawdbots/data/supermemory.db")
    count = db.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    fts = db.execute("SELECT COUNT(*) FROM facts_fts WHERE facts_fts MATCH 'bot'").fetchone()[0]
    db.close()
    return f"{count} facts, FTS5={fts} matches"
check("SuperMemory+FTS5", test_supermemory)

# 4. Plugin Registry
def test_plugins():
    from bots.shared.plugin_registry import PluginRegistry
    reg = PluginRegistry()
    tools = reg.discover()
    return f"{len(tools)} tools from {len(reg.list_providers())} providers"
check("Plugin Registry", test_plugins)

# 5. Task Spawner
def test_spawner():
    from bots.shared.task_spawner import detect_parallel_needs
    bots = detect_parallel_needs("analyze trading and tweet about it")
    return f"detected {bots}"
check("Task Spawner", test_spawner)

# 6. Kaizen
def test_kaizen():
    from bots.shared.kaizen import Kaizen, KaizenEngine
    k = Kaizen()
    skills = k.capability.get_skills()
    ke = KaizenEngine("clawdmatt")
    ke.run_cycle()
    return f"{len(skills)} skills, cycle OK"
check("Kaizen", test_kaizen)

# 7. Local Storage
def test_storage():
    from bots.shared.local_storage import LocalStorage
    for bot in ["matt", "jarvis", "friday"]:
        s = LocalStorage(bot)
        s.stats()
    return "3 bot DBs OK"
check("Local Storage", test_storage)

# 8. Morning Brief
def test_brief():
    from bots.shared.morning_brief import MorningBrief
    mb = MorningBrief()
    brief = mb.generate_brief_sync()
    return f"{len(brief)} chars"
check("Morning Brief", test_brief)

# 9. Log Monitor
def test_logs():
    from bots.shared.log_monitor import LogMonitor
    lm = LogMonitor()
    lm.get_health_report()
    return "report OK"
check("Log Monitor", test_logs)

# 10. Action Confirmation
def test_confirm():
    from bots.shared.action_confirmation import ActionConfirmation
    ActionConfirmation()
    return "initialized"
check("Action Confirmation", test_confirm)

# 11. Handoff Protocol
def test_handoff():
    from handoff_protocol import HandoffProtocol
    hp = HandoffProtocol("matt")
    result = hp.route_task("deploy the trading bot")
    return f"routed to {result['to']}"
check("Handoff Protocol", test_handoff)

# 12. Cron
def test_cron():
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    crons = [l for l in r.stdout.strip().split("\n") if l.strip() and not l.startswith("#")]
    return f"{len(crons)} jobs"
check("Cron Jobs", test_cron)

print(f"\n=== RESULTS: {passed} PASSED, {failed} FAILED out of {passed+failed} ===")

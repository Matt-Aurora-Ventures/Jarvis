"""Enable remaining flags and run comprehensive verification."""
import sys
sys.path.insert(0, "/root/clawdbots")

print("=== ENABLING FEATURE FLAGS ===")
from bots.shared.feature_flags import FeatureFlags
ff = FeatureFlags("system")
ff.set_flag("sleep_compute", True, scope="global")
ff.set_flag("moltbook", True, scope="global")
print("  sleep_compute = ON")
print("  moltbook = ON")

print("\n=== MODULE IMPORT VERIFICATION ===")
modules = {
    "message_queue": "from bots.shared.message_queue import MessageQueue",
    "feature_flags": "from bots.shared.feature_flags import FeatureFlags",
    "response_templates": "from bots.shared.response_templates import render",
    "utils": "from bots.shared.utils import truncate, format_sol",
    "sleep_compute": "from bots.shared.sleep_compute import SleepComputeManager",
    "moltbook": "from bots.shared.moltbook import store_learning",
    "plugin_registry": "from bots.shared.plugin_registry import PluginRegistry",
    "task_spawner": "from bots.shared.task_spawner import TaskSpawner",
    "kaizen": "from bots.shared.kaizen import KaizenEngine",
    "local_storage": "from bots.shared.local_storage import LocalStorage",
    "supermemory": "from bots.shared.supermemory import SuperMemory",
    "allowlist": "from bots.shared.allowlist import load_allowlist",
    "cost_tracker": "from bots.shared.cost_tracker import CostTracker",
    "self_healing": "from bots.shared.self_healing import SelfHealing",
    "error_handler": "from bots.shared.error_handler import ErrorHandler",
    "morning_brief": "from bots.shared.morning_brief import MorningBrief",
    "log_monitor": "from bots.shared.log_monitor import LogMonitor",
    "analytics": "from bots.shared.analytics import BotAnalytics",
    "heartbeat": "from bots.shared.heartbeat import HeartbeatMonitor",
    "rate_limiter": "from bots.shared.rate_limiter import RateLimiter",
}

passed = 0
failed = 0
for name, imp in modules.items():
    try:
        exec(imp)
        print(f"  [OK] {name}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        failed += 1

print(f"\n=== FEATURE FLAGS STATUS ===")
all_flags = ff.list_flags()
for f in sorted(all_flags, key=lambda x: x["name"]):
    status = "ON" if f["enabled"] else "OFF"
    print(f"  {f['name']} = {status} (scope={f['scope']})")

print(f"\n=== RESULTS: {passed}/{passed+failed} modules importable ===")

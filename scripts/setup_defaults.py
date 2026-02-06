"""Set up default feature flags and clean up message queue test data."""
import sys
sys.path.insert(0, "/root/clawdbots")

from bots.shared.feature_flags import FeatureFlags
from bots.shared.message_queue import MessageQueue

# Set default feature flags
ff = FeatureFlags("system")
defaults = {
    "kaizen_v2": (True, "global"),
    "supermemory_fts5": (True, "global"),
    "plugin_registry": (True, "global"),
    "task_spawner": (True, "global"),
    "cost_tracking": (True, "global"),
    "self_healing": (True, "global"),
    "message_queue": (True, "global"),
    "sleep_compute": (False, "global"),  # Not yet activated
    "moltbook": (False, "global"),       # Not yet activated
    "campaign_orchestrator": (False, "global"),  # Not yet activated
}

for flag, (enabled, scope) in defaults.items():
    ff.set_flag(flag, enabled, scope=scope)
    status = "ON" if enabled else "OFF"
    print(f"  {flag} = {status}")

print(f"\n{len(defaults)} default flags set")

# Clean up test messages
for bot in ["matt", "jarvis", "friday"]:
    mq = MessageQueue(bot)
    mq.cleanup(days=0)
print("Message queue cleaned up")

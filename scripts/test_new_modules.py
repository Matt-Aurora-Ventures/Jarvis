"""Test the 4 new shared modules."""
import sys
sys.path.insert(0, "/root/clawdbots")

passed = 0

# MessageQueue
try:
    from bots.shared.message_queue import MessageQueue
    mq = MessageQueue("matt")
    mid = mq.send("jarvis", {"type": "test", "msg": "hello"})
    count = MessageQueue("jarvis").peek()
    print(f"[PASS] MessageQueue: sent={mid}, jarvis_unread={count}")
    passed += 1
except Exception as e:
    print(f"[FAIL] MessageQueue: {e}")

# FeatureFlags
try:
    from bots.shared.feature_flags import FeatureFlags
    ff = FeatureFlags("matt")
    ff.set_flag("kaizen_v2", True)
    ff.set_flag("sleep_compute", False)
    assert ff.is_enabled("kaizen_v2") == True
    assert ff.is_enabled("sleep_compute") == False
    print(f"[PASS] FeatureFlags: {len(ff.list_flags())} flags")
    passed += 1
except Exception as e:
    print(f"[FAIL] FeatureFlags: {e}")

# ResponseTemplates
try:
    from bots.shared.response_templates import render, list_templates
    out = render("error", bot_name="matt", error="test error")
    assert "test error" in out
    tmpl_count = len(list_templates())
    print(f"[PASS] Templates: {tmpl_count} templates, render OK")
    passed += 1
except Exception as e:
    print(f"[FAIL] Templates: {e}")

# Utils
try:
    from bots.shared.utils import truncate, format_sol, format_usd, is_founder, sanitize_input
    assert len(truncate("x" * 5000, 100)) == 100
    assert format_sol(1.2345) == "1.2345 SOL"
    assert is_founder(8527130908) == True
    assert is_founder(123) == False
    print(f"[PASS] Utils: all helpers working")
    passed += 1
except Exception as e:
    print(f"[FAIL] Utils: {e}")

print(f"\n=== {passed}/4 PASSED ===")

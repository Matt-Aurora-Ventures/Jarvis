import datetime as dt
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from core import (
    config as config_module,
    guardian,
    hotkeys,
    interview,
    missions,
    observer,
    orchestrator,
    passive,
    reporting,
    state,
    voice,
    mcp_loader,
    resource_monitor,
)
import core.jarvis as jarvis_module

# Self-improving integration (optional)
try:
    from core.self_improving import integration as self_improving
    SELF_IMPROVING_AVAILABLE = True
except ImportError:
    SELF_IMPROVING_AVAILABLE = False


def _timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _log_message(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(f"[{_timestamp()}] {message}\n")


def _safe_print(message: str) -> None:
    """Print message with a safe encoding fallback for Windows consoles."""
    try:
        print(message)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe = message.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(safe)


def _parse_time(value: str) -> tuple[int, int]:
    try:
        hour, minute = value.split(":")
        return int(hour), int(minute)
    except Exception as e:
        return 0, 0


def _should_run_report(
    report_name: str, schedule: dict, now: dt.datetime, last_run: dict
) -> bool:
    if report_name not in schedule:
        return False
    today_dash = now.strftime("%Y-%m-%d")
    today_compact = now.strftime("%Y%m%d")
    if last_run.get(report_name) in (today_dash, today_compact):
        return False
    hour, minute = _parse_time(schedule[report_name])
    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now >= scheduled


def _send_notification(title: str, message: str) -> None:
    """Send a system notification (cross-platform)."""
    try:
        from core.platform import send_notification
        send_notification(title, message)
    except Exception:
        pass


def _generate_startup_report(
    component_status: dict[str, dict], ok_count: int, fail_count: int
) -> str:
    """Generate detailed startup report with failure guidance.

    Args:
        component_status: Dict of component name -> {"ok": bool, "error": str}
        ok_count: Number of successful components
        fail_count: Number of failed components

    Returns:
        Human-readable startup report with fix suggestions
    """
    lines = [
        "",
        "=" * 50,
        "  JARVIS DAEMON STARTUP REPORT",
        "=" * 50,
        "",
    ]

    # Status summary
    total = len(component_status)
    if fail_count == 0:
        lines.append(f"✅ All {total} components started successfully!")
    else:
        lines.append(f"⚠️  {ok_count}/{total} components OK, {fail_count} FAILED")

    lines.append("")

    # Component details
    for name, status in component_status.items():
        if status["ok"]:
            lines.append(f"  ✓ {name}")
        else:
            lines.append(f"  ✗ {name}: {status['error']}")

    # Provide fix suggestions for common failures
    if fail_count > 0:
        lines.extend([
            "",
            "-" * 50,
            "HOW TO FIX:",
            "",
        ])

        fix_map = {
            "mcp": "Check MCP server configs in lifeos/config/mcp.config.json",
            "voice": "Run: lifeos voice diagnose (or check pyaudio, piper installs)",
            "brain": "Check orchestrator logs, ensure providers are configured",
            "jarvis": "Check boot sequence errors in logs/daemon.log",
            "hotkeys": "pynput may need accessibility permissions on macOS",
            "passive": "Check passive observer config in lifeos/config/config.yaml",
            "observer": "Observer may need keyboard monitoring permissions",
            "resource_monitor": "Check psutil installation (pip install psutil)",
            "missions": "Check mission config in lifeos/config/config.yaml",
            "proactive": "Check proactive module dependencies",
            "self_improving": "Optional module - not critical for operation",
        }

        for name, status in component_status.items():
            if status["error"]:
                fix = fix_map.get(name, "Check logs for details")
                lines.append(f"  {name}: {fix}")

        lines.extend([
            "",
            "For full logs: cat lifeos/logs/daemon.log",
            "=" * 50,
        ])

    return "\n".join(lines)


def run() -> None:
    config = config_module.load_config()
    logs_dir = config_module.resolve_path(
        config.get("paths", {}).get("logs_dir", "lifeos/logs")
    )
    log_path = logs_dir / "daemon.log"
    running = True

    # Track component startup status
    component_status = {
        "brain": {"ok": False, "error": None},  # P0: The orchestrator brain loop
        "mcp": {"ok": False, "error": None},
        "jarvis": {"ok": False, "error": None},
        "voice": {"ok": False, "error": None},
        "hotkeys": {"ok": False, "error": None},
        "passive": {"ok": False, "error": None},
        "observer": {"ok": False, "error": None},
        "resource_monitor": {"ok": False, "error": None},
        "missions": {"ok": False, "error": None},
        "proactive": {"ok": False, "error": None},
        "self_improving": {"ok": False, "error": None},  # Reflexion-based learning
    }

    voice_manager = voice.VoiceManager()
    hotkey_manager = hotkeys.HotkeyManager(voice.start_chat_session)
    mcp_manager = None

    passive_cfg = config.get("passive", {})
    log_interval = int(passive_cfg.get("log_interval_seconds", 60))
    passive_observer = passive.PassiveObserver(log_interval_seconds=log_interval)

    interview_cfg = config.get("interview", {})
    interview_interval = int(interview_cfg.get("interval_minutes", 120))
    interview_scheduler = interview.InterviewScheduler(min_interval_minutes=interview_interval)

    def _handle_stop(_signum, _frame) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    state.write_pid(os.getpid())
    state.update_state(
        running=True,
        voice_enabled=config.get("voice", {}).get("enabled", True),
        voice_mode=config.get("voice", {}).get("mode", "unknown"),
        mic_status="not_initialized",
        passive_enabled=passive_cfg.get("enabled", True),
        interview_enabled=interview_cfg.get("enabled", True),
        last_report_at=state.read_state().get("last_report_at", "none"),
        updated_at=_timestamp(),
    )
    _log_message(log_path, "LifeOS daemon started.")

    # Start MCP servers
    try:
        mcp_manager = mcp_loader.start_mcp_servers()
        component_status["mcp"]["ok"] = True
        _log_message(log_path, "MCP servers started.")
    except Exception as e:
        component_status["mcp"]["error"] = str(e)[:100]
        _log_message(log_path, f"MCP loader FAILED: {str(e)[:100]}")

    # P0: Start the Brain (Orchestrator loop)
    brain = None
    try:
        brain = orchestrator.get_orchestrator()
        brain.start()
        component_status["brain"]["ok"] = True
        _log_message(log_path, "Brain (Orchestrator) started - single decision loop active.")
    except Exception as e:
        component_status["brain"]["error"] = str(e)[:100]
        _log_message(log_path, f"Brain startup FAILED: {str(e)[:100]}")

    # Run Jarvis boot sequence
    try:
        boot_result = jarvis_module.boot_sequence()
        component_status["jarvis"]["ok"] = True
        _log_message(log_path, f"Jarvis boot #{boot_result['boot_count']} complete.")
        if boot_result.get("discoveries"):
            _log_message(log_path, f"Discovered resources: {', '.join(boot_result['discoveries'])}")
    except Exception as e:
        component_status["jarvis"]["error"] = str(e)[:100]
        _log_message(log_path, f"Jarvis boot FAILED: {str(e)[:100]}")

    # Auto-evolve: check for and apply pending improvements
    try:
        from core import evolution
        evolve_result = evolution.auto_evolve_on_boot()
        if evolve_result.get("improvements_applied", 0) > 0:
            _log_message(log_path, f"Auto-evolved: {evolve_result['improvements_applied']} improvements applied")
    except Exception as e:
        _log_message(log_path, f"Auto-evolve warning: {str(e)[:100]}")

    # Start proactive monitoring (suggestions every 15 minutes)
    try:
        from core import proactive
        proactive.start_monitoring(interval_minutes=15)
        component_status["proactive"]["ok"] = True
        _log_message(log_path, "Proactive monitoring started (15 min intervals)")
    except Exception as e:
        component_status["proactive"]["error"] = str(e)[:100]
        _log_message(log_path, f"Proactive monitor FAILED: {str(e)[:100]}")

    # Start self-improving scheduler (nightly reflection at 3am)
    si_scheduler = None
    if SELF_IMPROVING_AVAILABLE:
        try:
            # Callback for proactive suggestions
            def on_suggestion(suggestion):
                _log_message(log_path, f"Proactive suggestion: {suggestion.message[:100]}...")
                # Future: Send to Telegram via tg_bot.services

            si_scheduler = self_improving.start_scheduler(on_suggestion=on_suggestion)
            component_status["self_improving"]["ok"] = True
            _log_message(log_path, "Self-improving scheduler started (3am nightly reflection)")
        except Exception as e:
            component_status["self_improving"]["error"] = str(e)[:100]
            _log_message(log_path, f"Self-improving scheduler FAILED: {str(e)[:100]}")
    else:
        component_status["self_improving"]["ok"] = True  # Not available is OK
        _log_message(log_path, "Self-improving module not available (optional)")

    # Start voice manager
    try:
        voice_manager.start()
        component_status["voice"]["ok"] = True
        _log_message(log_path, "Voice manager started.")
    except Exception as e:
        component_status["voice"]["error"] = str(e)[:100]
        _log_message(log_path, f"Voice manager FAILED: {str(e)[:100]}")

    # Start hotkey manager
    try:
        hotkey_manager.start()
        component_status["hotkeys"]["ok"] = True
        _log_message(log_path, "Hotkey manager started.")
    except Exception as e:
        component_status["hotkeys"]["error"] = str(e)[:100]
        _log_message(log_path, f"Hotkey manager FAILED: {str(e)[:100]}")

    if passive_cfg.get("enabled", True):
        try:
            passive_observer.start()
            component_status["passive"]["ok"] = True
            _log_message(log_path, "Passive observation started.")
        except Exception as e:
            component_status["passive"]["error"] = str(e)[:100]
            _log_message(log_path, f"Passive observer FAILED: {str(e)[:100]}")
    else:
        component_status["passive"]["ok"] = True  # Disabled is OK

    # Start deep observer for full activity logging
    if config.get("observer", {}).get("enabled", True):
        try:
            deep_observer = observer.start_observer()
            component_status["observer"]["ok"] = True
            _log_message(log_path, "Deep observer started (lite mode).")
        except Exception as e:
            component_status["observer"]["error"] = str(e)[:100]
            _log_message(log_path, f"Deep observer FAILED: {str(e)[:100]}")
    else:
        component_status["observer"]["ok"] = True  # Disabled is OK

    # Start resource monitor
    if config.get("resource_monitor", {}).get("enabled", True):
        try:
            resource_monitor.start_monitor()
            component_status["resource_monitor"]["ok"] = True
            _log_message(log_path, "Resource monitor started.")
        except Exception as e:
            component_status["resource_monitor"]["error"] = str(e)[:100]
            _log_message(log_path, f"Resource monitor FAILED: {str(e)[:100]}")
    else:
        component_status["resource_monitor"]["ok"] = True  # Disabled is OK

    mission_cfg = config.get("missions", {})
    mission_poll = int(mission_cfg.get("poll_seconds", 120))
    mission_scheduler = None
    if mission_cfg.get("enabled", True):
        try:
            mission_scheduler = missions.start_scheduler(poll_seconds=mission_poll)
            component_status["missions"]["ok"] = True
            _log_message(log_path, "Mission scheduler started.")
        except Exception as e:
            component_status["missions"]["error"] = str(e)[:100]
            _log_message(log_path, f"Mission scheduler FAILED: {str(e)[:100]}")
    else:
        component_status["missions"]["ok"] = True  # Disabled is OK

    # Summarize startup status
    ok_count = sum(1 for c in component_status.values() if c["ok"])
    fail_count = sum(1 for c in component_status.values() if c["error"])
    failed_components = [name for name, status in component_status.items() if status["error"]]

    # Include brain status in state
    brain_status = {}
    if brain:
        try:
            brain_status = brain.get_state()
        except Exception:
            brain_status = {"error": "failed to get status"}

    state.update_state(
        component_status=component_status,
        startup_ok=ok_count,
        startup_failed=fail_count,
        brain_status=brain_status,
    )

    # Generate detailed startup report
    startup_report = _generate_startup_report(component_status, ok_count, fail_count)

    if fail_count > 0:
        _log_message(log_path, f"⚠ Startup: {ok_count} OK, {fail_count} FAILED: {', '.join(failed_components)}")
        _log_message(log_path, startup_report)
        # Print to console so user sees failures even if not watching logs
        _safe_print(startup_report)
        _send_notification("Jarvis Warning", f"{fail_count} component(s) failed: {', '.join(failed_components)}")
    else:
        _log_message(log_path, f"✓ Startup complete: {ok_count}/{len(component_status)} components OK")
        _send_notification("Jarvis Ready", f"All {ok_count} components started successfully")

    while running:
        cfg = config_module.load_config()
        tz_name = str(cfg.get("timezone", "UTC"))

        reports_cfg = cfg.get("reports", {})
        if reports_cfg.get("enabled", True):
            schedule = reports_cfg.get(
                "schedule", {"morning": "07:30", "afternoon": "15:00"}
            )
            now = dt.datetime.now(ZoneInfo(tz_name))
            last_report = state.read_state().get("last_report_dates", {})

            if _should_run_report("morning", schedule, now, last_report):
                content = reporting.generate_report_text("morning", dry_run=False)
                reporting.save_report("morning", content)
                _log_message(log_path, "Scheduled morning report generated.")
                _send_notification("LifeOS", "Morning report ready!")

            if _should_run_report("afternoon", schedule, now, last_report):
                content = reporting.generate_report_text("afternoon", dry_run=False)
                reporting.save_report("afternoon", content)
                _log_message(log_path, "Scheduled afternoon report generated.")
                _send_notification("LifeOS", "Afternoon report ready!")

        int_cfg = cfg.get("interview", {})
        if int_cfg.get("enabled", True) and int_cfg.get("notifications", True):
            prompt = interview_scheduler.check_schedule()
            if prompt:
                _send_notification("LifeOS Check-in", prompt[:100])
                _log_message(log_path, "Interview prompt sent.")

        time.sleep(5)

    _log_message(log_path, "LifeOS daemon stopping...")

    # Stop the brain first (graceful shutdown of decision loop)
    if brain:
        try:
            brain.stop()
            _log_message(log_path, "Brain (Orchestrator) stopped.")
        except Exception as e:
            _log_message(log_path, f"Brain shutdown warning: {str(e)[:100]}")

    passive_observer.stop()
    if passive_observer.is_alive():
        passive_observer.join(timeout=2)

    if mission_scheduler:
        missions.stop_scheduler()

    voice_manager.stop()
    voice_manager.join(timeout=2)

    hotkey_manager.stop()
    hotkey_manager.join(timeout=2)

    if mcp_manager:
        try:
            mcp_loader.stop_mcp_servers()
            _log_message(log_path, "MCP servers stopped.")
        except Exception as e:
            _log_message(log_path, f"MCP shutdown warning: {str(e)[:100]}")

    # Stop self-improving scheduler
    if si_scheduler and SELF_IMPROVING_AVAILABLE:
        try:
            self_improving.stop_scheduler()
            self_improving.close()
            _log_message(log_path, "Self-improving scheduler stopped.")
        except Exception as e:
            _log_message(log_path, f"Self-improving shutdown warning: {str(e)[:100]}")

    resource_monitor.stop_monitor()

    state.update_state(running=False, passive_enabled=False, updated_at=_timestamp())
    state.clear_pid()
    _log_message(log_path, "LifeOS daemon stopped.")


if __name__ == "__main__":
    run()

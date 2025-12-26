import datetime as dt
import os
import signal
import subprocess
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from core import (
    config as config_module,
    guardian,
    hotkeys,
    interview,
    jarvis,
    missions,
    observer,
    passive,
    reporting,
    state,
    voice,
)


def _timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _log_message(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(f"[{_timestamp()}] {message}\n")


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
    """Send a macOS notification."""
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            check=False,
            timeout=5,
        )
    except Exception as e:
        pass


def run() -> None:
    config = config_module.load_config()
    logs_dir = config_module.resolve_path(
        config.get("paths", {}).get("logs_dir", "lifeos/logs")
    )
    log_path = logs_dir / "daemon.log"
    running = True

    voice_manager = voice.VoiceManager()
    hotkey_manager = hotkeys.HotkeyManager(voice.start_chat_session)

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

    # Run Jarvis boot sequence
    try:
        boot_result = jarvis.boot_sequence()
        _log_message(log_path, f"Jarvis boot #{boot_result['boot_count']} complete.")
        if boot_result.get("discoveries"):
            _log_message(log_path, f"Discovered resources: {', '.join(boot_result['discoveries'])}")
        if boot_result.get("suggestions"):
            _send_notification("Jarvis Ready", boot_result["suggestions"][0][:80] if boot_result["suggestions"] else "Ready to help!")
    except Exception as e:
        _log_message(log_path, f"Jarvis boot warning: {str(e)[:100]}")

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
        _log_message(log_path, "Proactive monitoring started (15 min intervals)")
    except Exception as e:
        _log_message(log_path, f"Proactive monitor warning: {str(e)[:100]}")

    voice_manager.start()
    hotkey_manager.start()

    if passive_cfg.get("enabled", True):
        passive_observer.start()
        _log_message(log_path, "Passive observation started.")

    # Start deep observer for full activity logging
    if config.get("observer", {}).get("enabled", True):
        deep_observer = observer.start_observer()
        _log_message(log_path, "Deep observer started (logging all activity).")

    mission_cfg = config.get("missions", {})
    mission_poll = int(mission_cfg.get("poll_seconds", 120))
    mission_scheduler = None
    if mission_cfg.get("enabled", True):
        try:
            mission_scheduler = missions.start_scheduler(poll_seconds=mission_poll)
            _log_message(log_path, "Mission scheduler started.")
        except Exception as e:
            _log_message(log_path, f"Mission scheduler warning: {str(e)[:120]}")

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

    passive_observer.stop()
    if passive_observer.is_alive():
        passive_observer.join(timeout=2)

    if mission_scheduler:
        missions.stop_scheduler()

    voice_manager.stop()
    voice_manager.join(timeout=2)

    hotkey_manager.stop()
    hotkey_manager.join(timeout=2)

    state.update_state(running=False, passive_enabled=False, updated_at=_timestamp())
    state.clear_pid()
    _log_message(log_path, "LifeOS daemon stopped.")


if __name__ == "__main__":
    run()

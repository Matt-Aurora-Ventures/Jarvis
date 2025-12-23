import datetime as dt
import os
import signal
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from core import config as config_module
from core import hotkeys, reporting, state, voice


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
    except Exception:
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


def run() -> None:
    config = config_module.load_config()
    logs_dir = config_module.resolve_path(
        config.get("paths", {}).get("logs_dir", "lifeos/logs")
    )
    log_path = logs_dir / "daemon.log"
    running = True
    voice_manager = voice.VoiceManager()
    hotkey_manager = hotkeys.HotkeyManager(voice.start_chat_session)

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
        last_report_at=state.read_state().get("last_report_at", "none"),
        updated_at=_timestamp(),
    )
    _log_message(log_path, "LifeOS daemon started.")
    voice_manager.start()
    hotkey_manager.start()

    while running:
        cfg = config_module.load_config()
        tz_name = str(cfg.get("timezone", "UTC"))
        reports_cfg = cfg.get("reports", {})
        if not reports_cfg.get("enabled", True):
            time.sleep(5)
            continue
        schedule = reports_cfg.get(
            "schedule", {"morning": "07:30", "afternoon": "15:00"}
        )
        now = dt.datetime.now(ZoneInfo(tz_name))
        last_report = state.read_state().get("last_report_dates", {})

        if _should_run_report("morning", schedule, now, last_report):
            content = reporting.generate_report_text("morning", dry_run=False)
            reporting.save_report("morning", content)
            _log_message(log_path, "Scheduled morning report generated.")

        if _should_run_report("afternoon", schedule, now, last_report):
            content = reporting.generate_report_text("afternoon", dry_run=False)
            reporting.save_report("afternoon", content)
            _log_message(log_path, "Scheduled afternoon report generated.")

        time.sleep(5)

    _log_message(log_path, "LifeOS daemon stopped.")
    voice_manager.stop()
    voice_manager.join(timeout=2)
    hotkey_manager.stop()
    hotkey_manager.join(timeout=2)
    state.update_state(running=False, updated_at=_timestamp())
    state.clear_pid()


if __name__ == "__main__":
    run()

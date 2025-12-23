import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

from core import (
    commands,
    config,
    context_router,
    diagnostics,
    memory,
    overnight,
    output,
    reporting,
    research,
    safety,
    state,
    voice,
)

ROOT = Path(__file__).resolve().parents[1]


def _daemon_python() -> str:
    venv_python = ROOT / "venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _render(
    plain: Dict[str, str],
    technical: Dict[str, str],
    glossary: Optional[Dict[str, str]] = None,
) -> None:
    print(output.render(plain, technical, glossary))


def capture_status_text() -> str:
    payload = _status_payload()
    plain = {
        "What I did": "Checked whether LifeOS is running and read key status values.",
        "Why I did it": "You asked for current system status.",
        "What happens next": "Use `lifeos on` or `lifeos off` to change state.",
        "What I need from you": "Nothing right now.",
    }
    technical = {
        "Modules/files involved": "core/state.py, core/config.py",
        "Key concepts/terms": "Daemon state, config defaults",
        "Commands executed (or would execute in dry-run)": "None",
        "Risks/constraints": "Read-only.",
    }
    glossary = {
        "Daemon": "A background process that keeps LifeOS running.",
        "Dry-run": "A preview mode that does not change anything.",
    }
    rendered = output.render(plain, technical, glossary)
    status_lines = ["Status:"]
    for key, value in payload.items():
        status_lines.append(f"- {key}: {value}")
    return f"{rendered}\n\n" + "\n".join(status_lines)


def _format_observations(observations) -> str:
    if not observations:
        return "Findings:\n- No critical issues detected."
    lines = ["Findings:"]
    for obs in observations:
        lines.append(f"- What: {obs.title}")
        lines.append(f"  Why it matters: {obs.why_it_matters}")
        lines.append(f"  Confidence: {obs.confidence}")
        lines.append(f"  Next: {obs.next_step}")
    return "\n".join(lines)


def _format_processes(processes) -> str:
    if not processes:
        return "Top Processes:\n- No process data available."
    lines = ["Top Processes (by memory):"]
    for proc in processes:
        lines.append(
            f"- {proc['name']} (pid {proc['pid']}): {proc['mem_mb']} MB, CPU {proc['cpu']}%"
        )
    return "\n".join(lines)


def _format_ports(ports) -> str:
    if not ports:
        return "Listening Ports:\n- No listening ports detected."
    lines = ["Listening Ports:"]
    for port in ports:
        lines.append(f"- {port['name']} (pid {port['pid']}): {port['address']}")
    return "\n".join(lines)


def _format_profile(profile) -> str:
    if not profile:
        return "System Profile:\n- Unavailable"
    return (
        "System Profile:\n"
        f"- OS: {profile.os_version}\n"
        f"- CPU load: {profile.cpu_load:.2f}\n"
        f"- RAM total: {profile.ram_total_gb:.1f} GB\n"
        f"- RAM free: {profile.ram_free_gb:.1f} GB\n"
        f"- Disk free: {profile.disk_free_gb:.1f} GB"
    )


def capture_diagnostics_text(dry_run: bool = True) -> str:
    cfg = config.load_config()
    limit = int(cfg.get("diagnostics", {}).get("top_processes", 5))
    data = diagnostics.run_diagnostics(limit=limit)
    observations = data.get("observations", [])
    processes = data.get("processes", [])
    ports = data.get("ports", [])
    profile = data.get("profile")
    allow_web = cfg.get("research", {}).get("allow_web", False)

    plain = {
        "What I did": "Scanned running processes and listening ports (read-only).",
        "Why I did it": "You asked for a safety-focused system check.",
        "What happens next": "Review findings and decide if any actions are needed.",
        "What I need from you": "Nothing right now.",
    }
    technical = {
        "Modules/files involved": "core/diagnostics.py, core/system_profiler.py",
        "Key concepts/terms": "Process scan, port scan",
        "Commands executed (or would execute in dry-run)": "lsof -iTCP -sTCP:LISTEN -P -n",
        "Risks/constraints": "Read-only; no system changes.",
    }
    glossary = {"Port": "A network entry point used by apps to communicate."}
    rendered = output.render(plain, technical, glossary)
    research_lines = ["Research Runner:"]
    if observations:
        for obs in observations:
            result = research.evaluate_issue(obs.title, allow_web=allow_web)
            research_lines.append(f"- {obs.title}: {result['status']} ({result['note']})")
    else:
        research_lines.append("- No items queued for research.")

    details = "\n\n".join(
        [
            _format_observations(observations),
            _format_processes(processes),
            _format_ports(ports),
            _format_profile(profile),
            "\n".join(research_lines),
        ]
    )
    return f"{rendered}\n\n{details}"


def capture_summarize_text(dry_run: bool = True) -> str:
    context = safety.SafetyContext(apply=not dry_run, dry_run=dry_run)
    pending = memory.get_pending_entries()
    recent = memory.get_recent_entries()
    entries = pending if pending else recent
    summary = memory.summarize_entries(entries)
    routed = context_router.route_entries(entries)
    needs_routing = sum(
        1
        for items in routed.values()
        for item in items
        if item.startswith("[Needs routing]")
    )

    plain = {
        "What I did": "Prepared a summary and routing plan for memory entries.",
        "Why I did it": "Summarize keeps memory organized and lightweight.",
        "What happens next": (
            "Confirm APPLY to write summaries into context files and clear the pending queue."
            if dry_run
            else "Writing summaries into context files and clearing the pending queue."
        ),
        "What I need from you": "Type APPLY to confirm." if dry_run else "Nothing right now.",
    }
    technical = {
        "Modules/files involved": "core/memory.py, core/context_router.py",
        "Key concepts/terms": "Routing rules, summaries",
        "Commands executed (or would execute in dry-run)": (
            "Append bullets to context markdown files; clear pending memory queue"
        ),
        "Risks/constraints": "Write action requires APPLY.",
    }
    glossary = {"Routing": "Choosing which context file each note should live in."}
    rendered = output.render(plain, technical, glossary)
    routing_note = ""
    if needs_routing:
        routing_note = f"\nRouting Questions: {needs_routing} item(s) need manual routing."

    if dry_run:
        preview = summary or "(No entries to summarize.)"
        return f"{rendered}{routing_note}\n\nSummary Preview:\n{preview}"

    written = context_router.apply_routes(routed, context)
    if pending:
        memory.clear_pending_entries(context)
    written_lines = "\n".join([str(path) for path in written]) or "(No files written.)"
    return f"{rendered}{routing_note}\n\nWrote updates to:\n{written_lines}"


def capture_report_text(kind: str, dry_run: bool = True) -> str:
    report_text = reporting.generate_report_text(kind, dry_run=dry_run)
    planned_path = reporting.plan_report_path(kind)

    plain = {
        "What I did": f"Prepared a {kind} report.",
        "Why I did it": "Reports keep you focused and truthfully aligned.",
        "What happens next": (
            "Confirm APPLY to save the report to disk."
            if dry_run
            else "Report saved to disk."
        ),
        "What I need from you": "Type APPLY to confirm." if dry_run else "Nothing right now.",
    }
    technical = {
        "Modules/files involved": "core/reporting.py, core/context_loader.py",
        "Key concepts/terms": "Scheduled reports, context budget",
        "Commands executed (or would execute in dry-run)": "Write markdown report file",
        "Risks/constraints": "Write action requires APPLY.",
    }
    rendered = output.render(plain, technical)

    if dry_run:
        return f"{rendered}\n\nReport Preview:\n{report_text}\nWould save to: {planned_path}"

    path = reporting.save_report(kind, report_text)
    return f"{rendered}\n\nReport:\n{report_text}\nSaved to: {path}"


def capture_overnight_text(dry_run: bool = True) -> str:
    context = safety.SafetyContext(apply=not dry_run, dry_run=dry_run)
    result = overnight.run_overnight(context)

    plain = {
        "What I did": "Prepared the overnight automation plan.",
        "Why I did it": "Overnight runs summarize, diagnose, and plan safely.",
        "What happens next": (
            "Confirm APPLY to write summaries and save the report."
            if dry_run
            else "Overnight run completed."
        ),
        "What I need from you": "Type APPLY to confirm." if dry_run else "Nothing right now.",
    }
    technical = {
        "Modules/files involved": "core/overnight.py, core/diagnostics.py",
        "Key concepts/terms": "Overnight pipeline, safe mode",
        "Commands executed (or would execute in dry-run)": "Summarize + report generation",
        "Risks/constraints": "Write action requires APPLY.",
    }
    rendered = output.render(plain, technical)

    if dry_run:
        summary = result.get("summary", "") or "(No entries to summarize.)"
        return f"{rendered}\n\nSummary Preview:\n{summary}"

    report_path = result.get("report_path")
    return f"{rendered}\n\nOvernight report saved to: {report_path}"


def _status_payload() -> Dict[str, str]:
    cfg = config.load_config()
    running = state.is_running()
    current = state.read_state()
    voice_cfg = cfg.get("voice", {})
    memory_cfg = cfg.get("memory", {})
    memory_state = memory.load_memory_state()
    voice_enabled = current.get("voice_enabled", voice_cfg.get("enabled", False))
    hotkey_cfg = cfg.get("hotkeys", {})

    return {
        "running": "yes" if running else "no",
        "voice_enabled": "yes" if voice_enabled else "no",
        "voice_mode": current.get("voice_mode", voice_cfg.get("mode", "unknown")),
        "mic_status": current.get("mic_status", "unknown"),
        "voice_error": current.get("voice_error", "none"),
        "chat_active": "yes" if current.get("chat_active", False) else "no",
        "hotkeys_enabled": "yes"
        if current.get("hotkeys_enabled", hotkey_cfg.get("enabled", False))
        else "no",
        "hotkey_combo": current.get(
            "hotkey_combo", hotkey_cfg.get("chat_activation", "ctrl+shift+up")
        ),
        "hotkey_error": current.get("hotkey_error", "none"),
        "memory_target_cap": str(memory_cfg.get("target_cap", "unknown")),
        "memory_cap": str(memory_state.get("memory_cap", "unknown")),
        "recent_entries": str(memory_state.get("recent_count", "0")),
        "pending_entries": str(memory_state.get("pending_count", "0")),
        "last_report_at": current.get("last_report_at", "none"),
    }


def cmd_status(_args: argparse.Namespace) -> None:
    print(capture_status_text())


def _resolve_mode(args: argparse.Namespace) -> safety.SafetyContext:
    return safety.resolve_mode(args.apply, args.dry_run)


def cmd_on(args: argparse.Namespace) -> None:
    if state.is_running():
        plain = {
            "What I did": "Checked for a running LifeOS daemon.",
            "Why I did it": "Starting twice can create duplicate processes.",
            "What happens next": "Use `lifeos status` to confirm settings.",
            "What I need from you": "Nothing right now.",
        }
        technical = {
            "Modules/files involved": "core/state.py",
            "Key concepts/terms": "PID tracking",
            "Commands executed (or would execute in dry-run)": "None",
            "Risks/constraints": "No changes made.",
        }
        _render(plain, technical)
        return

    context = _resolve_mode(args)
    python_cmd = _daemon_python()
    planned_cmd = f"{python_cmd} -m core.daemon"
    plain = {
        "What I did": "Prepared to start the LifeOS background daemon.",
        "Why I did it": "This keeps scheduling and voice modes ready while ON.",
        "What happens next": (
            "Confirm APPLY to start the background process."
            if context.dry_run
            else "Starting the background process now."
        ),
        "What I need from you": "Type APPLY to confirm." if context.dry_run else "Nothing.",
    }
    technical = {
        "Modules/files involved": "core/daemon.py, core/state.py",
        "Key concepts/terms": "Background daemon, PID file",
        "Commands executed (or would execute in dry-run)": planned_cmd,
        "Risks/constraints": "Starts a background process.",
    }
    glossary = {"Apply": "An explicit confirmation to make real changes."}

    if context.dry_run:
        _render(plain, technical, glossary)
        return

    if not safety.allow_action(context, "Start LifeOS background daemon"):
        plain["What I did"] = "Canceled start because APPLY was not confirmed."
        plain["What happens next"] = "Run again with `lifeos on --apply`."
        plain["What I need from you"] = "Type APPLY when prompted."
        _render(plain, technical, glossary)
        return

    cfg = config.load_config()
    logs_dir = config.resolve_path(cfg.get("paths", {}).get("logs_dir", "lifeos/logs"))
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "daemon.out"
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"

    with open(log_path, "a", encoding="utf-8") as handle:
        subprocess.Popen(
            [python_cmd, "-m", "core.daemon"],
            cwd=str(ROOT),
            stdout=handle,
            stderr=handle,
            start_new_session=True,
            env=env,
        )

    plain["What I did"] = "Started the LifeOS background daemon."
    plain["What happens next"] = "Use `lifeos status` to verify it is running."
    plain["What I need from you"] = "Nothing right now."
    _render(plain, technical, glossary)


def cmd_off(args: argparse.Namespace) -> None:
    pid = state.read_pid()
    if not pid or not state.is_running():
        plain = {
            "What I did": "Checked for a running LifeOS daemon.",
            "Why I did it": "Stop only applies when something is running.",
            "What happens next": "Use `lifeos on` to start the system.",
            "What I need from you": "Nothing right now.",
        }
        technical = {
            "Modules/files involved": "core/state.py",
            "Key concepts/terms": "PID tracking",
            "Commands executed (or would execute in dry-run)": "None",
            "Risks/constraints": "No changes made.",
        }
        _render(plain, technical)
        return

    context = _resolve_mode(args)
    planned_cmd = f"SIGTERM {pid}"
    plain = {
        "What I did": "Prepared to stop the LifeOS background daemon.",
        "Why I did it": "You requested LifeOS to turn OFF.",
        "What happens next": (
            "Confirm APPLY to stop the background process."
            if context.dry_run
            else "Stopping the background process now."
        ),
        "What I need from you": "Type APPLY to confirm." if context.dry_run else "Nothing.",
    }
    technical = {
        "Modules/files involved": "core/state.py",
        "Key concepts/terms": "SIGTERM, PID file",
        "Commands executed (or would execute in dry-run)": planned_cmd,
        "Risks/constraints": "Stops the background process.",
    }
    glossary = {"SIGTERM": "A polite signal asking a process to shut down."}

    if context.dry_run:
        _render(plain, technical, glossary)
        return

    if not safety.allow_action(context, "Stop LifeOS background daemon"):
        plain["What I did"] = "Canceled stop because APPLY was not confirmed."
        plain["What happens next"] = "Run again with `lifeos off --apply`."
        plain["What I need from you"] = "Type APPLY when prompted."
        _render(plain, technical, glossary)
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    state.clear_pid()
    state.update_state(running=False)
    plain["What I did"] = "Stopped the LifeOS background daemon."
    plain["What happens next"] = "Use `lifeos status` to confirm OFF state."
    plain["What I need from you"] = "Nothing right now."
    _render(plain, technical, glossary)


def cmd_stub(args: argparse.Namespace, name: str, next_phase: str) -> None:
    planned_action = "Implementation will arrive in the next phase."
    plain, technical, glossary = commands.not_implemented(name, planned_action, next_phase)
    _render(plain, technical, glossary)


def cmd_log(args: argparse.Namespace) -> None:
    text = args.text.strip()
    if not text:
        plain = {
            "What I did": "Checked for a log entry and found it was empty.",
            "Why I did it": "Logging requires text to capture.",
            "What happens next": "Re-run with a message to log.",
            "What I need from you": "Provide the text you want to log.",
        }
        technical = {
            "Modules/files involved": "core/cli.py",
            "Key concepts/terms": "Input validation",
            "Commands executed (or would execute in dry-run)": "None",
            "Risks/constraints": "No changes made.",
        }
        _render(plain, technical)
        return

    context = _resolve_mode(args)
    if not context.dry_run and not safety.allow_action(context, "Append memory entry"):
        plain = {
            "What I did": "Canceled log because APPLY was not confirmed.",
            "Why I did it": "Safety gate requires explicit confirmation.",
            "What happens next": "Run `lifeos log --apply` again.",
            "What I need from you": "Type APPLY when prompted.",
        }
        technical = {
            "Modules/files involved": "core/safety.py",
            "Key concepts/terms": "Apply token",
            "Commands executed (or would execute in dry-run)": "None",
            "Risks/constraints": "No changes made.",
        }
        _render(plain, technical)
        return

    recent, overflow = memory.append_entry(text, "cli_log", context)
    summary = f"Recent count: {len(recent)}; overflow queued: {len(overflow)}."
    plain = {
        "What I did": "Prepared a memory log entry." if context.dry_run else "Captured a memory log entry.",
        "Why I did it": "You asked to record a note in your memory buffer.",
        "What happens next": "Use `lifeos summarize` to route notes into context docs.",
        "What I need from you": "Confirm APPLY to save." if context.dry_run else "Nothing right now.",
    }
    technical = {
        "Modules/files involved": "core/memory.py",
        "Key concepts/terms": "JSONL memory buffer, adaptive cap",
        "Commands executed (or would execute in dry-run)": "Append to lifeos/memory/recent.jsonl",
        "Risks/constraints": "Write action requires APPLY.",
    }
    glossary = {"JSONL": "A file format with one JSON object per line."}
    _render(plain, technical, glossary)
    print("")
    print(summary)


def cmd_capture(args: argparse.Namespace) -> None:
    context = _resolve_mode(args)
    if context.dry_run:
        plain = {
            "What I did": "Prepared an interactive capture session.",
            "Why I did it": "Capture lets you type a note in the terminal.",
            "What happens next": "Re-run with --apply to capture the input.",
            "What I need from you": "Confirm APPLY and then type your note.",
        }
        technical = {
            "Modules/files involved": "core/cli.py",
            "Key concepts/terms": "Interactive prompt",
            "Commands executed (or would execute in dry-run)": "None",
            "Risks/constraints": "No changes made.",
        }
        _render(plain, technical)
        return

    if not safety.allow_action(context, "Capture memory entry"):
        plain = {
            "What I did": "Canceled capture because APPLY was not confirmed.",
            "Why I did it": "Safety gate requires explicit confirmation.",
            "What happens next": "Run `lifeos capture --apply` again.",
            "What I need from you": "Type APPLY when prompted.",
        }
        technical = {
            "Modules/files involved": "core/safety.py",
            "Key concepts/terms": "Apply token",
            "Commands executed (or would execute in dry-run)": "None",
            "Risks/constraints": "No changes made.",
        }
        _render(plain, technical)
        return

    text = input("Enter your note: ").strip()
    if not text:
        plain = {
            "What I did": "Stopped capture because the note was empty.",
            "Why I did it": "Empty notes are not saved.",
            "What happens next": "Re-run `lifeos capture --apply`.",
            "What I need from you": "Provide a note to save.",
        }
        technical = {
            "Modules/files involved": "core/cli.py",
            "Key concepts/terms": "Input validation",
            "Commands executed (or would execute in dry-run)": "None",
            "Risks/constraints": "No changes made.",
        }
        _render(plain, technical)
        return

    recent, overflow = memory.append_entry(text, "cli_capture", context)
    plain = {
        "What I did": "Captured your note into the memory buffer.",
        "Why I did it": "You asked to save a note interactively.",
        "What happens next": "Use `lifeos summarize` to route notes.",
        "What I need from you": "Nothing right now.",
    }
    technical = {
        "Modules/files involved": "core/memory.py",
        "Key concepts/terms": "JSONL memory buffer",
        "Commands executed (or would execute in dry-run)": "Append to lifeos/memory/recent.jsonl",
        "Risks/constraints": "Write already confirmed.",
    }
    _render(plain, technical)
    print("")
    print(f"Recent count: {len(recent)}; overflow queued: {len(overflow)}.")


def cmd_summarize(args: argparse.Namespace) -> None:
    context = _resolve_mode(args)
    if context.dry_run:
        print(capture_summarize_text(dry_run=True))
        return

    if not safety.allow_action(context, "Apply summary routing"):
        return

    print(capture_summarize_text(dry_run=False))


def cmd_report(args: argparse.Namespace) -> None:
    context = _resolve_mode(args)
    kind = "daily"
    if args.morning:
        kind = "morning"
    elif args.afternoon:
        kind = "afternoon"
    elif args.weekly:
        kind = "weekly"

    if context.dry_run:
        print(capture_report_text(kind=kind, dry_run=True))
        return

    if not safety.allow_action(context, "Generate report"):
        return

    print(capture_report_text(kind=kind, dry_run=False))


def cmd_diagnostics(args: argparse.Namespace) -> None:
    _ = args
    print(capture_diagnostics_text(dry_run=True))


def cmd_overnight(args: argparse.Namespace) -> None:
    context = _resolve_mode(args)
    if context.dry_run:
        print(capture_overnight_text(dry_run=True))
        return

    if not safety.allow_action(context, "Run overnight automation"):
        return

    print(capture_overnight_text(dry_run=False))


def cmd_talk(_args: argparse.Namespace) -> None:
    response = voice.listen_once()
    print(response)


def cmd_chat(_args: argparse.Namespace) -> None:
    voice.chat_session()


def cmd_listen(args: argparse.Namespace) -> None:
    context = _resolve_mode(args)
    desired = args.state
    if context.dry_run:
        plain = {
            "What I did": f"Prepared to turn listening {desired}.",
            "Why I did it": "You requested a voice listening toggle.",
            "What happens next": "Confirm APPLY to update the listening state.",
            "What I need from you": "Type APPLY to confirm.",
        }
        technical = {
            "Modules/files involved": "core/state.py",
            "Key concepts/terms": "Voice toggle",
            "Commands executed (or would execute in dry-run)": "Update lifeos/logs/state.json",
            "Risks/constraints": "Write action requires APPLY.",
        }
        _render(plain, technical)
        return

    if not safety.allow_action(context, "Toggle voice listening"):
        return

    enabled = desired == "on"
    state.update_state(voice_enabled=enabled, mic_status="idle" if enabled else "off")
    plain = {
        "What I did": f"Turned listening {desired}.",
        "Why I did it": "You requested a voice listening toggle.",
        "What happens next": "Use `lifeos status` to confirm.",
        "What I need from you": "Nothing right now.",
    }
    technical = {
        "Modules/files involved": "core/state.py",
        "Key concepts/terms": "Voice toggle",
        "Commands executed (or would execute in dry-run)": "Update lifeos/logs/state.json",
        "Risks/constraints": "None.",
    }
    _render(plain, technical)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lifeos")
    subparsers = parser.add_subparsers(dest="command", required=True)

    mode_parser = argparse.ArgumentParser(add_help=False)
    mode_parser.add_argument("--apply", action="store_true")
    mode_parser.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("status")
    subparsers.add_parser("on", parents=[mode_parser])
    subparsers.add_parser("off", parents=[mode_parser])

    log_parser = subparsers.add_parser("log", parents=[mode_parser])
    log_parser.add_argument("text", nargs="?", default="")

    subparsers.add_parser("capture", parents=[mode_parser])
    subparsers.add_parser("summarize", parents=[mode_parser])

    report_parser = subparsers.add_parser("report", parents=[mode_parser])
    report_parser.add_argument("--morning", action="store_true")
    report_parser.add_argument("--afternoon", action="store_true")
    report_parser.add_argument("--daily", action="store_true")
    report_parser.add_argument("--weekly", action="store_true")

    subparsers.add_parser("overnight", parents=[mode_parser])

    subparsers.add_parser("diagnostics", parents=[mode_parser])

    subparsers.add_parser("talk")
    subparsers.add_parser("chat")

    listen_parser = subparsers.add_parser("listen", parents=[mode_parser])
    listen_parser.add_argument("state", choices=["on", "off"])

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args)
        return
    if args.command == "on":
        cmd_on(args)
        return
    if args.command == "off":
        cmd_off(args)
        return
    if args.command == "log":
        cmd_log(args)
        return
    if args.command == "capture":
        cmd_capture(args)
        return
    if args.command == "summarize":
        cmd_summarize(args)
        return
    if args.command == "report":
        cmd_report(args)
        return
    if args.command == "overnight":
        cmd_overnight(args)
        return
    if args.command == "diagnostics":
        cmd_diagnostics(args)
        return
    if args.command == "talk":
        cmd_talk(args)
        return
    if args.command == "chat":
        cmd_chat(args)
        return
    if args.command == "listen":
        cmd_listen(args)
        return

    parser.print_help()


if __name__ == "__main__":
    main()

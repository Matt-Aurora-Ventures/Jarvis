import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from jarvis_cli.actions import register_actions_subparser
from core import (
    action_feedback,
    commands,
    config,
    context_router,
    diagnostics,
    evolution,
    git_ops,
    guardian,
    interview,
    jarvis,
    mcp_doctor_simple,
    memory,
    notes_manager,
    notion_ingest,
    objectives,
    orchestrator,
    overnight,
    output,
    opportunity_engine,
    passive,
    providers,
    reporting,
    research,
    rpc_diagnostics,
    safety,
    secrets,
    solana_scanner,
    strategy_scores,
    state,
    swap_simulator,
    task_manager,
    trading_notion,
    trading_youtube,
    voice,
)
from core.agents.registry import get_registry, initialize_agents
from core.agents.base import AgentRole, AgentTask
from core.economics import get_cost_tracker, get_revenue_tracker, get_economics_db, EconomicsDashboard

ROOT = Path(__file__).resolve().parents[1]


def _daemon_python() -> str:
    venv311 = ROOT / "venv311" / "bin" / "python"
    if venv311.exists():
        return str(venv311)
    venv_python = ROOT / "venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _resolve_user_path(value: Optional[str], fallback: Path) -> Path:
    if not value:
        return fallback
    expanded = Path(os.path.expanduser(value))
    if expanded.is_absolute():
        return expanded
    return (ROOT / expanded).resolve()


def _trading_symbol_map_path() -> Path:
    cfg = config.load_config()
    daemon_cfg = cfg.get("trading_daemon", {})
    return _resolve_user_path(
        daemon_cfg.get("symbol_map_path"),
        Path.home() / ".lifeos" / "trading" / "symbol_map.json",
    )


def _load_symbol_map(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items()}
    return {}


def _save_symbol_map(path: Path, data: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _looks_like_solana_address(value: str) -> bool:
    if not value:
        return False
    if not (32 <= len(value) <= 44):
        return False
    base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
    return all(char in base58_chars for char in value)


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
    passive_cfg = cfg.get("passive", {})
    interview_cfg = cfg.get("interview", {})
    memory_state = memory.load_memory_state()
    voice_enabled = current.get("voice_enabled", voice_cfg.get("enabled", False))
    hotkey_cfg = cfg.get("hotkeys", {})

    interview_stats = interview.get_interview_stats()

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
        "passive_enabled": "yes"
        if current.get("passive_enabled", passive_cfg.get("enabled", False))
        else "no",
        "passive_keyboard": "yes" if current.get("passive_keyboard", False) else "no",
        "passive_idle_seconds": str(int(current.get("passive_idle_seconds", 0))),
        "interview_enabled": "yes"
        if current.get("interview_enabled", interview_cfg.get("enabled", False))
        else "no",
        "interviews_today": str(interview_stats.get("today", 0)),
        "memory_target_cap": str(memory_cfg.get("target_cap", "unknown")),
        "memory_cap": str(memory_state.get("memory_cap", "unknown")),
        "recent_entries": str(memory_state.get("recent_count", "0")),
        "pending_entries": str(memory_state.get("pending_count", "0")),
        "last_report_at": current.get("last_report_at", "none"),
    }


def cmd_status(args: argparse.Namespace) -> None:
    print(capture_status_text())

    # Show component status if verbose or if there are failures
    if getattr(args, "verbose", False):
        current = state.read_state()
        component_status = current.get("component_status", {})
        startup_ok = current.get("startup_ok", 0)
        startup_failed = current.get("startup_failed", 0)
        brain_status = current.get("brain_status", {})
        running = current.get("running", False)
        daemon_heartbeat = current.get("daemon_heartbeat", "unknown")
        daemon_uptime = current.get("daemon_uptime_seconds", 0)
        updated_at = current.get("updated_at", "unknown")
        pid = state.read_pid()

        if not running:
            print("\n⚠️  Daemon is not running. Start with: lifeos on")
            return

        print("\n" + "=" * 60)
        print("  DAEMON HEALTH STATUS")
        print("=" * 60)

        # Show daemon info
        print(f"\nDaemon Process:")
        print(f"  • PID: {pid if pid else 'unknown'}")
        print(f"  • Uptime: {_format_uptime(daemon_uptime)}")
        print(f"  • Last heartbeat: {daemon_heartbeat}")
        print(f"  • Last state update: {updated_at}")

        if component_status:
            # Group components by status
            ok_components = []
            failed_components = []

            for name, status in sorted(component_status.items()):
                if status.get("ok"):
                    ok_components.append(name)
                elif status.get("error"):
                    failed_components.append((name, status['error']))

            # Show successful components
            if ok_components:
                print("\n✓ Running Components:")
                for name in ok_components:
                    print(f"  • {name}")

            # Show failed components with details
            if failed_components:
                print("\n✗ Failed Components:")
                for name, error in failed_components:
                    print(f"  • {name}")
                    print(f"    Error: {error}")

            # Show brain status if available
            if brain_status:
                print("\n" + "-" * 60)
                print("Brain (Orchestrator):")
                phase = brain_status.get("phase", "unknown")
                cycle_count = brain_status.get("cycle_count", 0)
                errors = brain_status.get("errors_in_row", 0)
                brain_running = brain_status.get("running", False)

                brain_icon = "✓" if brain_running and errors == 0 else "⚠️"
                print(f"  {brain_icon} Phase: {phase}")
                print(f"  • Cycles completed: {cycle_count}")
                print(f"  • Status: {'Running' if brain_running else 'Stopped'}")
                if errors > 0:
                    print(f"  ⚠️  Consecutive errors: {errors}")

            # Summary
            print("\n" + "=" * 60)
            total = len(component_status)
            if startup_failed == 0:
                print(f"✅ All {total} components healthy")
            else:
                print(f"⚠️  {startup_ok}/{total} components OK, {startup_failed} failed")
                print("\n💡 To fix issues, check: lifeos/logs/daemon.log")
            print("=" * 60)
        else:
            print("\n(No component status available - daemon may not have started yet)")


def _format_uptime(seconds: int) -> str:
    """Format uptime in human-readable format."""
    if seconds == 0:
        return "just started"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


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

    topic, body = notes_manager.extract_topic_and_body(text)
    note_path, summary_path, _ = notes_manager.save_note(
        topic=topic,
        content=f"# {topic.title()}\n\n{body}",
        fmt="md",
        tags=["cli", "capture"],
        source="cli.capture",
        metadata={"command": "lifeos capture"},
    )
    recent, overflow = memory.append_entry(text, "cli_capture", context)
    plain = {
        "What I did": "Captured your note into the memory buffer and saved it locally.",
        "Why I did it": "You asked to save a note interactively.",
        "What happens next": "Use `lifeos summarize` to route notes or open the saved file.",
        "What I need from you": "Nothing right now.",
    }
    technical = {
        "Modules/files involved": "core/memory.py, core/notes_manager.py",
        "Key concepts/terms": "JSONL memory buffer, local note store",
        "Commands executed (or would execute in dry-run)": (
            "Append to lifeos/memory/recent.jsonl; write markdown under data/notes/"
        ),
        "Risks/constraints": "Write already confirmed.",
    }
    _render(plain, technical)
    print("")
    print(f"Recent count: {len(recent)}; overflow queued: {len(overflow)}.")
    print(f"Saved note: {note_path}\nSummary: {summary_path}")


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


def cmd_rpc_diagnostics(args: argparse.Namespace) -> None:
    payload = rpc_diagnostics.run_solana_rpc_diagnostics(
        include_simulation=not args.no_sim,
    )
    if args.json:
        print(json.dumps(payload, indent=2))
        return

    endpoints = payload.get("endpoints", [])
    print("Solana RPC Diagnostics:")
    for endpoint in endpoints:
        name = endpoint.get("name", "unknown")
        health_ok = endpoint.get("health_ok")
        health_ms = endpoint.get("health_ms")
        blockhash_ms = endpoint.get("blockhash_ms")
        simulate_ok = endpoint.get("simulate_ok")
        simulate_error = endpoint.get("simulate_error")
        simulate_hint = endpoint.get("simulate_hint")
        print(
            f"- {name}: health={health_ok} ({health_ms}ms), "
            f"blockhash={blockhash_ms}ms, simulate={simulate_ok}"
        )
        if simulate_error and simulate_error not in {"skipped", "simulation_unavailable"}:
            print(f"  simulate_error: {simulate_error}")
        if simulate_hint:
            print(f"  simulate_hint: {simulate_hint}")


def cmd_simulate_exit(args: argparse.Namespace) -> None:
    payload = swap_simulator.simulate_exit_intent(
        intent_id=args.intent_id,
        symbol=args.symbol,
        size_pct=args.size_pct,
        endpoint=args.endpoint,
        write_report=not args.no_report,
    )
    if args.json:
        print(json.dumps(payload, indent=2))
        return
    if payload.get("error"):
        print(f"Simulation failed: {payload['error']}")
        return

    report_path = payload.get("report_path")
    print("Swap Simulation:")
    print(
        f"- Intent: {payload.get('intent_id')} {payload.get('symbol')} "
        f"{payload.get('size_pct')}% qty"
    )
    if report_path:
        print(f"- Report: {report_path}")
    results = payload.get("results") or []
    for result in results:
        endpoint = result.get("endpoint")
        success = result.get("success")
        error = result.get("error")
        error_hint = result.get("error_hint")
        error_class = result.get("error_class")
        print(f"- {endpoint}: success={success} class={error_class}")
        if error:
            print(f"  error: {error}")
        if error_hint:
            print(f"  hint: {error_hint}")


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


def cmd_voice(args: argparse.Namespace) -> int:
    """Handle voice subcommand (e.g., `lifeos voice doctor`)."""
    action = getattr(args, 'voice_action', None)

    if action == 'doctor':
        print("=" * 50)
        print("LifeOS Voice Pipeline Diagnostics")
        print("=" * 50)
        print()

        # Run comprehensive diagnostics
        diagnostics = voice.diagnose_voice_pipeline()

        # Format and print the report
        report = voice.format_voice_doctor_report(diagnostics)
        print(report)

        # Return exit code based on operational status
        if diagnostics.get('overall', {}).get('operational'):
            return 0
        else:
            return 1

    # Unknown action
    print("Usage: lifeos voice doctor")
    return 0


def cmd_secret(args: argparse.Namespace) -> None:
    key_map = {
        "gemini": "google_api_key",
        "openai": "openai_api_key",
    }
    target_key = key_map.get(args.provider)
    if not target_key:
        return

    data = {}
    if secrets.KEYS_PATH.exists():
        try:
            with open(secrets.KEYS_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as e:
            data = {}

    data[target_key] = args.key
    secrets.KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(secrets.KEYS_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)

    try:
        os.chmod(secrets.KEYS_PATH, 0o600)
    except Exception as e:
        pass

    plain = {
        "What I did": f"Saved your {args.provider} API key securely.",
        "Why I did it": "You asked to configure your API credentials.",
        "What happens next": "The system will use this key for AI tasks.",
        "What I need from you": "Nothing right now.",
    }
    technical = {
        "Modules/files involved": "core/secrets.py, secrets/keys.json",
        "Key concepts/terms": "JSON storage, file permissions (0600)",
        "Commands executed": f"Write to {secrets.KEYS_PATH}",
        "Risks/constraints": "Key is stored in plain text JSON locally.",
    }
    _render(plain, technical)


def cmd_activity(args: argparse.Namespace) -> None:
    """Show recent activity summary."""
    hours = getattr(args, "hours", 4)
    summary = passive.summarize_activity(hours=hours)
    recent = passive.load_recent_activity(hours=hours)

    plain = {
        "What I did": f"Retrieved activity summary for the last {hours} hours.",
        "Why I did it": "You asked for an activity report.",
        "What happens next": "Review your activity patterns.",
        "What I need from you": "Nothing right now.",
    }
    technical = {
        "Modules/files involved": "core/passive.py, data/activity_logs/",
        "Key concepts/terms": "Passive observation, activity tracking",
        "Commands executed (or would execute in dry-run)": "Read activity logs",
        "Risks/constraints": "Read-only.",
    }
    _render(plain, technical)
    print("")
    print(summary)
    print(f"\nTotal log entries: {len(recent)}")


def cmd_checkin(args: argparse.Namespace) -> None:
    """Start an interactive check-in session."""
    context = _resolve_mode(args)

    prompt = interview.generate_interview_prompt()
    print("LifeOS Check-in")
    print("=" * 40)
    print(prompt)
    print("")

    if context.dry_run:
        plain = {
            "What I did": "Prepared a check-in prompt.",
            "Why I did it": "You asked for a check-in.",
            "What happens next": "Run with --apply to record your response.",
            "What I need from you": "Type APPLY to confirm.",
        }
        technical = {
            "Modules/files involved": "core/interview.py",
            "Key concepts/terms": "Check-in, context capture",
            "Commands executed (or would execute in dry-run)": "None",
            "Risks/constraints": "Write action requires APPLY.",
        }
        _render(plain, technical)
        return

    if not safety.allow_action(context, "Record check-in response"):
        return

    response = input("Your response: ").strip()
    if not response:
        print("No response provided.")
        return

    questions = prompt.split("\n")
    result = interview.process_interview_response(
        response=response,
        questions_asked=questions,
        context=context,
    )

    plain = {
        "What I did": "Recorded your check-in response.",
        "Why I did it": "Building context about your current state.",
        "What happens next": "Response saved to memory and interview log.",
        "What I need from you": "Nothing right now.",
    }
    technical = {
        "Modules/files involved": "core/interview.py, core/memory.py",
        "Key concepts/terms": "Check-in, context building",
        "Commands executed (or would execute in dry-run)": "Append to interview log and memory",
        "Risks/constraints": "None.",
    }
    _render(plain, technical)
    print(f"\nStatus: {result.get('status', 'unknown')}")


def cmd_evolve(args: argparse.Namespace) -> None:
    """Trigger self-improvement based on a request."""
    context = _resolve_mode(args)
    request = getattr(args, "request", "") or ""

    if not request:
        stats = evolution.get_evolution_stats()
        skills = evolution.list_skills()

        plain = {
            "What I did": "Retrieved self-improvement stats.",
            "Why I did it": "You asked about my evolution capabilities.",
            "What happens next": "Use 'lifeos evolve \"add skill to...\"' to request improvements.",
            "What I need from you": "Tell me what capability to add.",
        }
        technical = {
            "Modules/files involved": "core/evolution.py",
            "Key concepts/terms": "Self-improvement, skill generation",
            "Commands executed (or would execute in dry-run)": "None",
            "Risks/constraints": "Read-only.",
        }
        _render(plain, technical)
        print(f"\nEvolution Stats:")
        print(f"- Total improvements: {stats.get('total_improvements', 0)}")
        print(f"- Skills created: {stats.get('skills_created', 0)}")
        print(f"\nInstalled Skills ({len(skills)}):")
        for skill in skills:
            print(f"  - {skill['name']}: {skill['description'][:50]}")
        return

    if context.dry_run:
        proposal = evolution.propose_improvement_from_request(request)
        if proposal:
            print("Proposed Improvement (dry-run):")
            print(f"  Title: {proposal.title}")
            print(f"  Category: {proposal.category}")
            print(f"  Description: {proposal.description}")
            print(f"  Rationale: {proposal.rationale}")
            if proposal.code:
                print(f"\n  Code Preview:\n{proposal.code[:300]}...")
            print("\nRun with --apply to implement this.")
        else:
            print("Could not generate an improvement proposal.")
        return

    if not safety.allow_action(context, "Apply self-improvement"):
        return

    result = evolution.evolve_from_conversation(
        user_text=request,
        conversation_history=[],
        context=context,
    )
    print(result)


def cmd_task(args):
    """Handle task commands."""
    tm = task_manager.get_task_manager()
    
    if args.task_action == "add":
        priority = task_manager.TaskPriority(args.priority)
        task = tm.add_task(args.title, priority)
        print(f"Task added: {task.id}")
        print(f"Title: {task.title}")
        print(f"Priority: {task.priority.value}")
        print(f"Status: {task.status.value}")
        
    elif args.task_action == "list":
        status_filter = None
        priority_filter = None
        
        if args.status:
            status_filter = task_manager.TaskStatus(args.status)
        if args.priority:
            priority_filter = task_manager.TaskPriority(args.priority)
        
        tasks = tm.list_tasks(status=status_filter, priority=priority_filter, limit=args.limit)
        
        if not tasks:
            print("No tasks found.")
            return
        
        print(f"\n{'ID':<8} {'Priority':<10} {'Status':<12} {'Title'}")
        print("-" * 70)
        for task in tasks:
            print(f"{task.id[:7]:<8} {task.priority.value:<10} {task.status.value:<12} {task.title}")
            
    elif args.task_action == "complete":
        if tm.complete_task(args.task_id):
            print(f"Task {args.task_id} marked as complete.")
        else:
            print(f"Task {args.task_id} not found.")
            
    elif args.task_action == "start":
        if tm.start_task(args.task_id):
            print(f"Task {args.task_id} marked as in progress.")
        else:
            print(f"Task {args.task_id} not found.")
            
    elif args.task_action == "status":
        stats = tm.get_stats()
        print("\nTask Statistics:")
        print(f"Total: {stats['total']}")
        print(f"Pending: {stats['pending']}")
        print(f"In Progress: {stats['in_progress']}")
        print(f"Completed: {stats['completed']}")
        print(f"Cancelled: {stats['cancelled']}")
        
        print("\nBy Priority:")
        print(f"Urgent: {stats['by_priority']['urgent']}")
        print(f"High: {stats['by_priority']['high']}")
        print(f"Medium: {stats['by_priority']['medium']}")
        print(f"Low: {stats['by_priority']['low']}")


def cmd_agent(args: argparse.Namespace) -> None:
    goal = " ".join(args.goal).strip()
    if not goal:
        print("Goal is required.")
        return
    try:
        from core import agent_graph
    except Exception as exc:
        print(f"Agent module unavailable: {exc}")
        return
    cfg = config.load_config()
    agent_cfg = cfg.get("agent", {})
    execute = bool(args.execute or agent_cfg.get("execute_default", False))
    max_cycles = args.max_cycles if args.max_cycles is not None else int(agent_cfg.get("max_cycles", 2))
    max_step_retries = (
        args.max_step_retries
        if args.max_step_retries is not None
        else int(agent_cfg.get("max_step_retries", 1))
    )
    agent = agent_graph.GraphAgent()
    result = agent.run(
        goal=goal,
        execute=execute,
        max_cycles=max_cycles,
        max_step_retries=max_step_retries,
    )
    print(json.dumps(result, indent=2))


def cmd_jarvis(args: argparse.Namespace) -> None:
    """Jarvis commands - interview, discover, research, profile."""
    action = getattr(args, "action", "status")

    if action == "interview":
        questions = jarvis.conduct_interview()
        print("=== Jarvis Interview ===")
        print(questions)
        print("\n(Your responses help me understand and serve you better)")

    elif action == "discover":
        print("Discovering latest free AI resources...")
        resources = jarvis.discover_free_ai_resources()
        if resources:
            print(f"\nFound {len(resources)} resources:")
            for r in resources:
                print(f"  - {r.name} ({r.provider}): {r.description[:60]}")
        else:
            print("Could not discover resources at this time.")

    elif action == "research":
        print("Researching trading strategies...")
        result = jarvis.research_trading_strategies()
        print("\n=== Trading Research ===")
        print(result)

    elif action == "profile":
        profile = jarvis.get_user_profile()
        print("=== User Profile ===")
        print(f"Name: {profile.name}")
        print(f"LinkedIn: {profile.linkedin}")
        print(f"Trading Focus: {profile.trading_focus}")
        print(f"\nGoals:")
        for g in profile.primary_goals:
            print(f"  - {g}")
        print(f"\nInterests:")
        for i in profile.interests:
            print(f"  - {i}")
        print(f"\nMentor Channels: {', '.join(profile.mentor_channels)}")

    elif action == "suggest":
        print("Generating proactive suggestions...")
        suggestions = jarvis.generate_proactive_suggestions()
        if suggestions:
            print("\n=== Suggestions for You ===")
            for i, s in enumerate(suggestions, 1):
                print(f"{i}. {s}")
        else:
            print("Could not generate suggestions at this time.")

    else:
        print("Jarvis Status:")
        profile = jarvis.get_user_profile()
        print(f"  User: {profile.name}")
        print(f"  Mission: Help you make money and achieve your goals")
        print(f"  Safety: Active (cannot harm self or computer)")
        print(f"\nCommands:")
        print(f"  lifeos jarvis interview  - Get interviewed to update profile")
        print(f"  lifeos jarvis discover   - Find new free AI resources")
        print(f"  lifeos jarvis research   - Research trading strategies")
        print(f"  lifeos jarvis profile    - View your profile")
        print(f"  lifeos jarvis suggest    - Get proactive suggestions")


def cmd_doctor(args: argparse.Namespace) -> None:
    """Run system health diagnostics with actionable fixes."""
    # MCP-only mode
    if getattr(args, "mcp", False):
        print("=" * 60)
        print("MCP DOCTOR - COMPREHENSIVE SERVER DIAGNOSTICS")
        print("=" * 60)
        print()
        
        results = mcp_doctor_simple.run_all_tests()
        mcp_doctor_simple.print_summary(results)
        
        # Exit with appropriate code for scripting
        all_healthy = all(r.passed for r in results.values())
        if not all_healthy:
            print("\nFor detailed MCP troubleshooting, see MCP_DOCTOR.md")
        return
        
    # Voice-only mode
    if getattr(args, "voice", False):
        print("=" * 50)
        print("LifeOS Voice Pipeline Diagnostics")
        print("=" * 50)
        print()
        print(voice.get_voice_doctor_summary())
        print("=" * 50)
        return

    # Validate API keys mode - makes actual API calls
    if getattr(args, "validate_keys", False):
        print("=" * 60)
        print("API KEY VALIDATION")
        print("=" * 60)
        print()
        print("Validating API keys with actual API calls...")
        print("(This may take a few seconds)")
        print()

        validation_results = providers.validate_api_keys()

        # Display results
        valid_count = 0
        invalid_count = 0
        missing_count = 0
        error_count = 0

        for provider, info in validation_results.items():
            if info["valid"]:
                print(f"  [OK] {provider.upper()}: Valid")
                valid_count += 1
            elif info["status"] == "missing":
                print(f"  [--] {provider.upper()}: Missing")
                missing_count += 1
            elif info["status"] == "invalid":
                print(f"  [XX] {provider.upper()}: {info['message']}")
                invalid_count += 1
            else:
                print(f"  [!!] {provider.upper()}: {info['message']}")
                error_count += 1

        print()

        # Show fixes for issues
        issues = [(p, i) for p, i in validation_results.items() if not i["valid"]]
        if issues:
            print("Issues found:")
            for provider, info in issues:
                if info.get("fix"):
                    print(f"  - {provider.upper()}: {info['fix']}")
            print()

        # Summary
        total = len(validation_results)
        print("=" * 60)
        if valid_count == total:
            print(f"All {total} providers validated successfully!")
        else:
            print(f"{valid_count} of {total} providers valid")
            if missing_count:
                print(f"  {missing_count} missing (not configured)")
            if invalid_count:
                print(f"  {invalid_count} invalid (need attention)")
            if error_count:
                print(f"  {error_count} errors (network/API issues)")

        # Exit code for scripting
        if invalid_count > 0:
            print()
            print("Exit code: 1 (invalid keys found)")
            sys.exit(1)
        print("=" * 60)
        return

    print("=" * 50)
    print("LifeOS Doctor - System Health Check")
    print("=" * 50)
    print()

    # 1. Check Python version
    py_version = sys.version_info
    py_ok = py_version >= (3, 10)
    print(f"Python Version: {py_version.major}.{py_version.minor}.{py_version.micro}")
    if not py_ok:
        print("  ⚠ Python 3.10+ recommended")
    else:
        print("  ✓ OK")
    print()

    # 2. Check providers
    print(providers.get_provider_summary())
    print()

    # 3. Check MCP servers
    print("MCP Servers:")
    try:
        mcp_results = mcp_doctor_simple.run_all_tests()
        mcp_healthy_count = sum(1 for r in mcp_results.values() if r.passed)
        mcp_total_count = len(mcp_results)
        print(f"  Overall: {mcp_healthy_count}/{mcp_total_count} servers healthy")
        
        for server_name, result in mcp_results.items():
            status = "✓" if result.passed else "✗"
            print(f"  {status} {server_name}")
            if not result.passed:
                print(f"    Error: {result.error}")
    except Exception as e:
        print(f"  ✗ MCP testing failed: {e}")
    print()

    # 4. Check config
    print("Configuration:")
    try:
        cfg = config.load_config()
        print("  ✓ Config loaded successfully")
        voice_enabled = cfg.get("voice", {}).get("enabled", False)
        print(f"  Voice enabled: {voice_enabled}")
        observer_mode = cfg.get("observer", {}).get("mode", "lite")
        print(f"  Observer mode: {observer_mode}")
    except Exception as e:
        print(f"  ✗ Config error: {e}")
    print()

    # 4. Check secrets
    print("API Keys Configured:")
    key_status = secrets.list_configured_keys()
    for name, configured in key_status.items():
        icon = "✓" if configured else "✗"
        status = "set" if configured else "not set"
        note = ""
        if name == "groq" and not configured:
            note = " (RECOMMENDED - free, fast)"
        elif name == "openai" and not configured:
            note = " (optional - paid)"
        elif name == "gemini" and not configured:
            note = " (optional - has quota issues)"
        print(f"  {icon} {name}: {status}{note}")
    print()

    # 5. Check daemon state
    print("Daemon Status:")
    running = state.is_running()
    current = state.read_state()
    print(f"  Running: {'yes' if running else 'no'}")
    if running:
        print(f"  Voice mode: {current.get('voice_mode', 'unknown')}")
        print(f"  Mic status: {current.get('mic_status', 'unknown')}")
        voice_error = current.get('voice_error', '')
        if voice_error and voice_error != 'none':
            print(f"  Voice error: {voice_error}")
    print()

    # 6. Check required directories
    print("Data Directories:")
    dirs_to_check = [
        ("Config", ROOT / "lifeos" / "config"),
        ("Memory", ROOT / "lifeos" / "memory"),
        ("Logs", ROOT / "lifeos" / "logs"),
        ("Secrets", ROOT / "secrets"),
        ("Data", ROOT / "data"),
    ]
    for name, path in dirs_to_check:
        exists = path.exists()
        icon = "✓" if exists else "✗"
        print(f"  {icon} {name}: {path}")
        if not exists:
            print(f"    Create with: mkdir -p {path}")
    print()

    # 7. Quick test
    if getattr(args, "test", False):
        print("Running Quick Test...")
        health = providers.check_provider_health()
        available = [k for k, v in health.items() if v["available"]]
        if available:
            print(f"  Testing {available[0]}...")
            try:
                result = providers.generate_text("Say 'hello' in one word.", max_output_tokens=10)
                if result:
                    print(f"  ✓ Response: {result.strip()[:50]}")
                else:
                    print("  ✗ No response received")
            except Exception as e:
                print(f"  ✗ Test failed: {e}")
        else:
            print("  ⚠ No providers available to test")
        print()

    # Summary
    print("=" * 50)
    health = providers.check_provider_health()
    available = [k for k, v in health.items() if v["available"]]
    if available:
        print(f"✓ System ready - {len(available)} provider(s) available")
        print(f"  Primary: {available[0]}")
    else:
        print("✗ System NOT ready - no providers available!")
        print()
        print("Quick Fix (Groq - free, fast):")
        print("  1. Go to: https://console.groq.com")
        print("  2. Create account and get API key")
        print("  3. Run: export GROQ_API_KEY='your-key-here'")
        print("  4. Run: lifeos doctor --test")
    print("=" * 50)


def cmd_brain(args: argparse.Namespace) -> None:
    """Brain/Orchestrator status and control."""
    action = args.action

    if action == "status":
        # Get brain status from running daemon or direct
        current_state = state.read_state()
        brain_status = current_state.get("brain_status", {})

        print("=" * 50)
        print("JARVIS BRAIN STATUS")
        print("=" * 50)

        if not brain_status:
            print("Brain status not available (daemon may not be running)")
            print("Run 'lifeos on' to start the daemon with brain loop")
        else:
            print(f"Running: {brain_status.get('running', False)}")
            print(f"Phase: {brain_status.get('phase', 'unknown')}")
            print(f"Cycle count: {brain_status.get('cycle_count', 0)}")
            print(f"Current objective: {brain_status.get('current_objective', 'none')}")
            print(f"Errors in row: {brain_status.get('errors_in_row', 0)}")

        # Show objective summary
        print()
        print("OBJECTIVE QUEUE:")
        obj_manager = objectives.get_manager()
        active = obj_manager.get_active()
        queue = obj_manager.get_queue(limit=5)
        summary = obj_manager.status_summary()

        if active:
            print(f"  [ACTIVE] {active.id}: {active.description[:50]}")
            print(f"           Priority: {active.priority}, Attempts: {active.attempts}")
        else:
            print("  No active objective")

        print(f"  Queue size: {summary['queue_size']}")
        print(f"  Completed: {summary['completed_count']}, Failed: {summary['failed_count']}")
        print(f"  Success rate: {summary['success_rate']:.0%}")

        print("=" * 50)

    elif action == "inject":
        # Inject user input into the brain
        text = args.text
        if not text:
            print("Error: --text required for inject")
            return

        orch = orchestrator.get_orchestrator()
        orch.inject_user_input(text)
        print(f"Injected into brain: {text[:100]}...")

    elif action == "history":
        # Show recent brain activity
        from pathlib import Path
        brain_log = Path(__file__).resolve().parents[1] / "data" / "brain" / "loop_log.jsonl"
        if not brain_log.exists():
            print("No brain history yet")
            return

        print("RECENT BRAIN ACTIVITY:")
        print("-" * 50)
        with open(brain_log, "r") as f:
            lines = f.readlines()[-20:]  # Last 20 entries
            for line in lines:
                try:
                    entry = json.loads(line)
                    event = entry.get("event", "?")
                    cycle = entry.get("cycle", 0)
                    print(f"[{cycle}] {event}: {json.dumps({k: v for k, v in entry.items() if k not in ['event', 'cycle', 'timestamp', 'phase']})[:80]}")
                except json.JSONDecodeError:
                    continue


def cmd_objective(args: argparse.Namespace) -> None:
    """Objective management commands."""
    action = args.objective_action
    obj_manager = objectives.get_manager()

    if action == "add":
        # Create new objective
        description = args.description
        priority = int(args.priority) if args.priority else 5

        # Parse success criteria
        criteria = []
        if args.criteria:
            for c in args.criteria.split(","):
                criteria.append({
                    "description": c.strip(),
                    "metric": "completed",
                    "target": True,
                })
        else:
            criteria = [{
                "description": "objective completed",
                "metric": "completed",
                "target": True,
            }]

        obj = obj_manager.create_objective(
            description=description,
            success_criteria=criteria,
            priority=priority,
            source=objectives.ObjectiveSource.USER,
        )
        print(f"Created objective: {obj.id}")
        print(f"  Description: {obj.description}")
        print(f"  Priority: {obj.priority}")
        print(f"  Criteria: {len(obj.success_criteria)}")

    elif action == "list":
        print("OBJECTIVE QUEUE:")
        print("-" * 50)

        active = obj_manager.get_active()
        if active:
            status = "ACTIVE"
            print(f"[{status}] {active.id}: {active.description}")
            print(f"        Priority: {active.priority}, Attempts: {active.attempts}")
            if active.started_at:
                duration = int((time.time() - active.started_at))
                print(f"        Running for: {duration}s")
            print()

        queue = obj_manager.get_queue(limit=args.limit if hasattr(args, 'limit') else 10)
        if queue:
            print("PENDING:")
            for obj in queue:
                print(f"  [{obj.priority}] {obj.id}: {obj.description[:60]}")
        else:
            print("  (no pending objectives)")

    elif action == "complete":
        obj_id = args.objective_id
        outcome = args.outcome or "Completed via CLI"

        success = obj_manager.complete(obj_id, outcome)
        if success:
            print(f"Completed objective: {obj_id}")
        else:
            print(f"Error: Could not complete {obj_id} (not active?)")

    elif action == "fail":
        obj_id = args.objective_id
        reason = args.reason or "Failed via CLI"
        requeue = args.requeue if hasattr(args, 'requeue') else False

        success = obj_manager.fail(obj_id, reason, requeue=requeue)
        if success:
            action_taken = "requeued" if requeue else "failed"
            print(f"Objective {obj_id} {action_taken}: {reason}")
        else:
            print(f"Error: Could not fail {obj_id}")

    elif action == "history":
        print("OBJECTIVE HISTORY:")
        print("-" * 50)
        history = obj_manager.get_history(limit=args.limit if hasattr(args, 'limit') else 20)
        for obj in reversed(history):
            status_icon = "✓" if obj.status == objectives.ObjectiveStatus.COMPLETED else "✗"
            print(f"  {status_icon} {obj.id}: {obj.description[:50]}")
            if obj.outcome:
                print(f"      Outcome: {obj.outcome[:60]}")
            if obj.failure_reason:
                print(f"      Failed: {obj.failure_reason[:60]}")


def cmd_feedback(args: argparse.Namespace) -> None:
    """Action feedback and learning status."""
    action = args.feedback_action
    loop = action_feedback.get_feedback_loop()

    if action == "metrics":
        metrics = loop.get_metrics()
        print("ACTION METRICS:")
        print("-" * 50)
        if not metrics:
            print("  No action metrics yet")
            return

        for name, m in sorted(metrics.items(), key=lambda x: -x[1].get("total_calls", 0)):
            print(f"  {name}:")
            print(f"    Calls: {m.get('total_calls', 0)}, Success: {m.get('success_rate', 0):.0%}")
            print(f"    Avg duration: {m.get('avg_duration_ms', 0):.0f}ms")
            if m.get("common_errors"):
                print(f"    Common errors: {m['common_errors'][:2]}")

    elif action == "patterns":
        patterns = loop.get_patterns()
        print("LEARNED PATTERNS:")
        print("-" * 50)
        if not patterns:
            print("  No patterns learned yet")
            return

        for p in patterns:
            print(f"  [{p.get('pattern_type')}] {p.get('action_name')}")
            print(f"    {p.get('description')}")
            print(f"    Frequency: {p.get('frequency', 1)}")

    elif action == "recommend":
        action_name = args.action_name
        recs = action_feedback.get_action_recommendations(action_name)
        print(f"RECOMMENDATIONS FOR '{action_name}':")
        print("-" * 50)
        if not recs:
            print("  No recommendations (action performing well)")
        else:
            for r in recs:
                print(f"  - {r}")


def cmd_agents(args: argparse.Namespace) -> None:
    """Multi-agent system management."""
    action = args.agents_action

    # Initialize registry
    try:
        registry = initialize_agents()
    except Exception as e:
        print(f"Error initializing agents: {e}")
        return

    if action == "status":
        print("=" * 60)
        print("JARVIS MULTI-AGENT SYSTEM")
        print("=" * 60)

        # Check self-sufficiency
        self_status = registry.get_self_sufficient_status()
        if self_status["self_sufficient"]:
            print(f"Status: SELF-SUFFICIENT (local: {self_status['local_provider']})")
        else:
            print("Status: CLOUD-DEPENDENT (install Ollama for self-sufficiency)")

        print()
        print("AGENTS:")
        print("-" * 60)

        for agent in registry.get_all():
            status = registry.get_status(agent.role)
            availability = agent.check_provider_availability()

            # Provider status
            providers_str = ", ".join(
                f"{p}{'*' if v else ''}"
                for p, v in availability.items()
            )

            print(f"  [{agent.role.value.upper()}]")
            print(f"    Capabilities: {[c.value for c in agent.capabilities]}")
            print(f"    Providers: {providers_str}")
            print(f"    Tasks: {status.get('total_tasks', 0)}, "
                  f"Success: {status.get('success_rate', 1.0):.0%}")
            print()

        print("Cloud Transformers (optional boosters):")
        for role, cloud in self_status.get("cloud_transformers", {}).items():
            available = [p for p, v in cloud.items() if v]
            if available:
                print(f"  {role}: {', '.join(available)}")

        print("=" * 60)

    elif action == "run":
        role_str = args.role
        task_desc = args.task

        try:
            role = AgentRole(role_str)
        except ValueError:
            print(f"Unknown role: {role_str}")
            print(f"Available: {[r.value for r in AgentRole]}")
            return

        agent = registry.get(role)
        if not agent:
            print(f"Agent {role_str} not registered")
            return

        print(f"Running {role_str} agent...")
        print("-" * 40)

        task = AgentTask(
            id=f"cli_{int(time.time())}",
            objective_id="cli",
            description=task_desc,
            max_steps=10,
            timeout_seconds=120,
        )

        result = registry.execute_with_role(role, task)

        if result.success:
            print(f"SUCCESS ({result.duration_ms}ms, {result.steps_taken} steps)")
            print()
            print(result.output)
        else:
            print(f"FAILED: {result.error}")

    elif action == "research":
        query = args.query
        print(f"Researching: {query}")
        print("-" * 40)

        researcher = registry.get(AgentRole.RESEARCHER)
        if researcher:
            output = researcher.quick_research(query)
            print(output)
        else:
            print("Researcher agent not available")

    elif action == "trade":
        task_desc = args.task or "Analyze crypto market opportunities"
        print(f"Trading task: {task_desc}")
        print("-" * 40)

        task = AgentTask(
            id=f"trade_{int(time.time())}",
            objective_id="trade",
            description=task_desc,
            max_steps=5,
        )

        result = registry.execute_with_role(AgentRole.TRADER, task)
        if result.success:
            print(result.output)
        else:
            print(f"Failed: {result.error}")

    elif action == "improve":
        target = args.target or "Suggest improvements for the codebase"
        print(f"Architecture task: {target}")
        print("-" * 40)

        task = AgentTask(
            id=f"arch_{int(time.time())}",
            objective_id="improve",
            description=target,
            max_steps=5,
        )

        result = registry.execute_with_role(AgentRole.ARCHITECT, task)
        if result.success:
            print(result.output)
        else:
            print(f"Failed: {result.error}")

    elif action == "providers":
        print("PROVIDER AVAILABILITY:")
        print("-" * 50)

        availability = registry.check_all_availability()
        for role, providers in availability.items():
            print(f"  {role}:")
            for provider, available in providers.items():
                icon = "+" if available else "-"
                print(f"    [{icon}] {provider}")
            print()


def cmd_economics(args: argparse.Namespace) -> None:
    """Economics dashboard and P&L tracking."""
    action = args.economics_action

    if action == "status":
        dashboard = EconomicsDashboard()
        status = dashboard.get_status()

        print("=" * 60)
        print("JARVIS ECONOMIC STATUS")
        print("=" * 60)

        # Summary
        status_icon = "+" if status.is_profitable else "-"
        print(f"[{status_icon}] {status.status_message}")
        print()

        # Today
        print("TODAY:")
        print(f"  Costs: ${status.costs_today:.2f}")
        print(f"  Revenue: ${status.revenue_today:.2f}")
        print(f"  Net P&L: ${status.net_pnl_today:+.2f}")
        print(f"  API Calls: {status.api_calls_today}")
        print(f"  Tokens: {status.tokens_today:,}")
        print()

        # 30-Day
        print("30-DAY:")
        print(f"  Net P&L: ${status.net_pnl_30d:+.2f}")
        print(f"  ROI: {status.roi_30d_percent:+.1f}%")
        print()

        # Revenue breakdown
        print("REVENUE SOURCES:")
        print(f"  Trading P&L: ${status.trading_pnl:.2f}")
        print(f"  Time Saved: ${status.time_saved_value:.2f}")
        print()

        # Alerts
        if status.alerts:
            print("ALERTS:")
            for alert in status.alerts:
                print(f"  ! {alert}")
        else:
            print("✓ No alerts")

        print("=" * 60)

    elif action == "report":
        dashboard = EconomicsDashboard()
        days = args.days if hasattr(args, 'days') else 30
        report = dashboard.generate_report(days=days)
        print(report)

    elif action == "costs":
        tracker = get_cost_tracker()
        days = args.days if hasattr(args, 'days') else 7
        summary = tracker.get_summary(days=days)

        print(f"COSTS (Last {days} days):")
        print("-" * 50)
        print(f"  Total: ${summary.total_usd:.4f}")
        print(f"  API Calls: {summary.api_calls}")
        print(f"  Tokens: {summary.total_tokens:,}")
        print()

        if summary.by_provider:
            print("  By Provider:")
            for provider, cost in sorted(summary.by_provider.items(), key=lambda x: -x[1]):
                print(f"    {provider}: ${cost:.4f}")
        print()

        if summary.by_category:
            print("  By Category:")
            for category, cost in sorted(summary.by_category.items(), key=lambda x: -x[1]):
                print(f"    {category}: ${cost:.4f}")

    elif action == "revenue":
        tracker = get_revenue_tracker()
        days = args.days if hasattr(args, 'days') else 7
        summary = tracker.get_summary(days=days)

        print(f"REVENUE (Last {days} days):")
        print("-" * 50)
        print(f"  Total: ${summary.total_usd:.2f}")
        print(f"  Verified: ${summary.verified_revenue:.2f}")
        print(f"  Estimated: ${summary.estimated_value:.2f}")
        print()

        print("  Breakdown:")
        print(f"    Trading P&L: ${summary.trading_pnl:.2f}")
        print(f"    Time Saved: ${summary.time_saved_hours:.1f} hours")
        print()

        if summary.by_category:
            print("  By Category:")
            for category, amount in sorted(summary.by_category.items(), key=lambda x: -x[1]):
                print(f"    {category}: ${amount:.2f}")

    elif action == "alerts":
        dashboard = EconomicsDashboard()
        alerts = dashboard.check_alerts()
        db = get_economics_db()
        unacked = db.get_unacknowledged_alerts()

        print("ECONOMIC ALERTS:")
        print("-" * 50)

        if not alerts and not unacked:
            print("  ✓ No active alerts")
            return

        # Current alerts
        if alerts:
            print("  Current:")
            for alert in alerts:
                print(f"    ! {alert}")

        # Historical unacknowledged
        if unacked:
            print()
            print("  Unacknowledged:")
            for a in unacked[:10]:
                print(f"    [{a['id']}] {a['message']}")
                print(f"         Severity: {a['severity']}")

        print()
        print("  Use 'lifeos economics ack <id>' to acknowledge alerts")

    elif action == "ack":
        alert_id = args.alert_id
        db = get_economics_db()
        db.acknowledge_alert(int(alert_id))
        print(f"Acknowledged alert {alert_id}")

    elif action == "trend":
        dashboard = EconomicsDashboard()
        days = args.days if hasattr(args, 'days') else 7
        trend = dashboard.get_trend(days=days)

        print(f"P&L TREND (Last {days} days):")
        print("-" * 50)

        if not trend.get("dates"):
            print("  No data yet")
            return

        for i, date in enumerate(trend["dates"]):
            cost = trend["costs"][i]
            revenue = trend["revenue"][i]
            net = trend["net_pnl"][i]
            trading = trend["trading"][i]

            icon = "+" if net >= 0 else "-"
            print(f"  {date}: [{icon}] ${net:+.2f}  (costs: ${cost:.2f}, rev: ${revenue:.2f})")

    elif action == "log-time":
        # Log time saved manually
        minutes = float(args.minutes)
        task = args.task

        tracker = get_revenue_tracker()
        value = tracker.log_time_saved(minutes, task)
        print(f"Logged {minutes} minutes saved on '{task}'")
        print(f"Value: ${value:.2f}")

    elif action == "log-trade":
        # Log trading profit/loss manually
        amount = float(args.amount)
        symbol = args.symbol or "UNKNOWN"
        paper = not args.live

        tracker = get_revenue_tracker()
        tracker.log_trading_profit(amount, symbol=symbol, paper=paper)
        mode = "live" if not paper else "paper"
        print(f"Logged {mode} trade: {symbol} ${amount:+.2f}")


def cmd_trading_youtube(args: argparse.Namespace) -> None:
    """YouTube trading channel ingestion."""
    action = args.trading_youtube_action
    cfg = config.load_config()
    yt_cfg = cfg.get("trading_youtube", {})

    if action == "scan":
        channel = args.channel
        limit = args.limit if args.limit is not None else int(yt_cfg.get("limit", 3))
        enqueue = not args.no_enqueue if hasattr(args, "no_enqueue") else bool(yt_cfg.get("enqueue_backtests", True))

        channels = [channel] if channel else yt_cfg.get("channels", [])
        if not channels:
            print("No YouTube channels configured.")
            return

        for channel_url in channels:
            result = trading_youtube.compile_channel_digest(
                channel_url=channel_url,
                limit=limit,
                enqueue_backtests=enqueue,
            )
            print(f"Scanned: {channel_url}")
            if result.get("error"):
                print(f"  Error: {result.get('error')}")
                continue
            print(f"  Videos: {result.get('video_count', 0)}")
            print(f"  Digest: {result.get('note_path')}")
            if enqueue:
                print("  Backtests: queued")

    elif action == "queue":
        queue = trading_youtube.load_queue()
        print(f"Queued backtests: {len(queue)}")
        for entry in queue[:5]:
            print(f"  - {entry.get('symbol')} {entry.get('interval')} {entry.get('strategy')}")

    elif action == "compile":
        channel = args.channel
        limit = args.limit if args.limit is not None else 50
        enqueue = not args.no_enqueue if hasattr(args, "no_enqueue") else True
        channels = [channel] if channel else yt_cfg.get("channels", [])
        if not channels:
            print("No YouTube channels configured.")
            return

        for channel_url in channels:
            result = trading_youtube.compile_channel_strategies(
                channel_url=channel_url,
                limit=limit,
                enqueue_backtests=enqueue,
            )
            print(f"Compiled: {channel_url}")
            if result.get("error"):
                print(f"  Error: {result.get('error')}")
                continue
            print(f"  Videos: {result.get('video_count', 0)}")
            print(f"  Strategies: {result.get('strategies_added', 0)}")
            print(f"  Actions: {result.get('actions_added', 0)}")
            print(f"  Digest: {result.get('digest_path')}")
            print(f"  Strategies file: {result.get('strategies_path')}")
            print(f"  Actions file: {result.get('actions_path')}")

    elif action == "backtest":
        limit = args.limit if args.limit is not None else 3
        results = trading_youtube.run_backtest_queue(limit=limit)
        if not results:
            print("No backtests executed (queue empty or data missing).")
            return
        print(f"Executed {len(results)} backtests:")
        for result in results:
            job = result.get("job", {})
            metrics = result.get("result", {})
            print(
                f"  - {job.get('symbol')} {job.get('interval')} {job.get('strategy')} "
                f"ROI {metrics.get('roi', 0.0)*100:.2f}% Sharpe {metrics.get('sharpe_ratio', 0.0):.2f}"
            )


def cmd_trading_notion(args: argparse.Namespace) -> None:
    """Ingest Notion resources and compile strategies."""
    action = args.trading_notion_action
    cfg = config.load_config()
    notion_cfg = cfg.get("notion_ingest", {})

    if action == "ingest":
        url = args.url or notion_cfg.get("default_url")
        if not url:
            print("No Notion URL provided.")
            return
        
        # Check if using headless scraper
        use_headless = getattr(args, 'headless', False)
        notebooklm_summary = getattr(args, 'notebooklm', False)
        
        if use_headless:
            print("Using headless scraper for full content expansion...")
            if notebooklm_summary:
                print("YouTube videos will be summarized with NotebookLM...")
        
        result = notion_ingest.ingest_notion_page(
            url=url,
            crawl_links=True,
            max_links=int(args.max_links),
            crawl_depth=int(args.crawl_depth),
            max_pages=int(args.max_pages),
            max_chunks=int(args.max_chunks),
            use_headless=use_headless,
            notebooklm_summary=notebooklm_summary,
        )
        if result.get("error"):
            print(f"Notion ingest failed: {result['error']}")
            return
        print("Notion ingest complete:")
        print(f"- Title: {result.get('title')}")
        print(f"- Method: {result.get('method', 'api')}")
        print(f"- Links: {result.get('links')}")
        print(f"- YouTube links: {result.get('youtube_links')}")
        if notebooklm_summary:
            print(f"- YouTube summaries: {result.get('youtube_summaries', 0)}")
        print(f"- Code blocks: {result.get('code_blocks')}")
        print(f"- Action items: {result.get('action_items')}")
        print(f"- Resources crawled: {result.get('resources')}")
        print(f"- Exec: {result.get('exec_path')}")
        print(f"- Note: {result.get('note_path')}")
        if result.get('scraped_files'):
            print("- Scraped files:")
            for key, path in result['scraped_files'].items():
                if path:
                    print(f"  {key}: {path}")

    elif action == "compile":
        exec_path = args.exec_path
        seed_trader = not args.no_seed
        result = trading_notion.compile_notion_strategies(exec_path=exec_path, seed_trader=seed_trader)
        if result.get("error"):
            print(f"Notion compile failed: {result['error']}")
            return
        print("Notion strategies compiled:")
        print(f"- Strategies added: {result.get('strategies_added', 0)}")
        print(f"- Shortlist: {result.get('shortlist', 0)}")
        print(f"- Actions: {result.get('actions', 0)}")
        print(f"- Strategies file: {result.get('strategies_path')}")
        print(f"- Actions file: {result.get('actions_path')}")
        print(f"- Digest: {result.get('note_path')}")


def cmd_solana_scan(args: argparse.Namespace) -> None:
    """Run the Solana meme coin scanner and seed strategies."""
    action = args.solana_action

    if action == "run":
        result = solana_scanner.scan_all(
            trending_limit=int(args.trending_limit),
            new_token_hours=int(args.new_token_hours),
            top_trader_limit=int(args.top_trader_limit),
        )
        if result.get("error"):
            print(f"Solana scan failed: {result['error']}")
            return
        if not args.no_seed:
            solana_scanner.seed_scanner_strategies()
        print("Solana scan complete:")
        print(f"- Trending tokens: {result.get('trending', 0)}")
        print(f"- New listings: {result.get('new_tokens', 0)}")
        print(f"- Top traders: {result.get('top_traders', 0)}")
        print(f"- Trending CSV: {result.get('trending_csv')}")
        print(f"- New tokens CSV: {result.get('new_tokens_csv')}")
        print(f"- Top traders CSV: {result.get('top_traders_csv')}")
        print(f"- Digest: {result.get('note_path')}")

    elif action == "shortlist":
        shortlist = solana_scanner.compile_strategy_shortlist()
        print("Solana strategy shortlist:")
        for item in shortlist:
            print(f"- {item['rank']}. {item['name']} ({item['id']}): {item['why']}")

    elif action == "seed":
        result = solana_scanner.seed_scanner_strategies()
        print(f"Seeded {result.get('strategies_added', 0)} strategies into trading engine.")


def cmd_trading_positions(args: argparse.Namespace) -> None:
    from core.risk_manager import get_risk_manager

    rm = get_risk_manager()
    action = args.trading_positions_action
    symbol_map_path = _trading_symbol_map_path()

    if action == "list":
        open_trades = rm.get_open_trades()
        if not open_trades:
            print("No open positions.")
            return
        print(f"Open positions: {len(open_trades)}")
        for trade in open_trades:
            print(
                f"{trade['id']} | {trade['symbol']} | "
                f"{trade['action']} @ {trade['entry_price']} | "
                f"qty {trade['quantity']} | "
                f"SL {trade.get('stop_loss')} | TP {trade.get('take_profit')}"
            )
        return

    if action == "status":
        stats = rm.get_stats()
        print(json.dumps(stats, indent=2))
        return

    if action == "map":
        symbol_map = _load_symbol_map(symbol_map_path)
        symbol_map[args.symbol] = args.address
        _save_symbol_map(symbol_map_path, symbol_map)
        print(f"Mapped {args.symbol} -> {args.address}")
        print(f"Symbol map: {symbol_map_path}")
        return

    if action == "add":
        symbol = args.symbol
        if args.address:
            symbol_map = _load_symbol_map(symbol_map_path)
            symbol_map[symbol] = args.address
            _save_symbol_map(symbol_map_path, symbol_map)

        entry = float(args.entry)
        stop_loss = args.stop_loss
        take_profit = args.take_profit
        if stop_loss is None and args.stop_loss_pct:
            stop_loss = entry * (1 - (args.stop_loss_pct / 100))
        if take_profit is None and args.take_profit_pct:
            take_profit = entry * (1 + (args.take_profit_pct / 100))

        quantity = args.quantity
        if quantity is None:
            if args.capital is None:
                raise SystemExit("Quantity not provided. Use --quantity or --capital with stop-loss.")
            if stop_loss is None:
                raise SystemExit("Stop-loss required when sizing from capital.")
            sizing = rm.sizer.calculate_position(
                capital=args.capital,
                entry_price=entry,
                stop_loss_price=stop_loss,
                risk_pct=args.risk_pct,
            )
            if "quantity" not in sizing:
                raise SystemExit("Failed to size position.")
            quantity = sizing["quantity"]
            print(f"Sized quantity: {quantity} (position ${sizing.get('position_value')})")

        trade = rm.record_trade(
            symbol=symbol,
            action=args.action,
            entry_price=entry,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=args.strategy or "manual",
        )
        if not _looks_like_solana_address(symbol) and not args.address:
            print("Warning: symbol is not a mint address and no mapping was provided.")
        print(f"Recorded trade {trade.id} for {trade.symbol}")
        return

    if action == "close":
        trade = rm.close_trade(
            args.trade_id,
            exit_price=float(args.exit_price),
            reason=args.reason,
        )
        if not trade:
            print("Trade not found or already closed.")
            return
        print(f"Closed {trade.id} at {trade.exit_price} ({trade.status})")
        return


def cmd_trading_opportunities(args: argparse.Namespace) -> None:
    signals_path = Path(args.signals) if args.signals else None
    payload = opportunity_engine.run_engine(
        signals_path=signals_path,
        refresh_equities=args.refresh_equities,
        capital_usd=float(args.capital_usd),
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2))
        print(f"Wrote opportunities JSON to {output_path}")
        return
    print(json.dumps(payload, indent=2))


def cmd_strategy_scores(args: argparse.Namespace) -> None:
    records = strategy_scores.list_scores(
        limit=int(args.limit),
        min_score=args.min_score,
        sort_key=args.sort,
        descending=not args.asc,
    )
    if args.json:
        print(json.dumps({"scores": records}, indent=2))
        return
    if not records:
        print("No strategy scores recorded yet.")
        return

    print("strategy | score | win% | wins | losses | streak | exec_err | status | gate | updated | reason")
    for record in records:
        strategy_id = str(record.get("strategy_id", "unknown"))
        score = float(record.get("score", 0.0))
        wins = int(record.get("wins", 0))
        losses = int(record.get("losses", 0))
        streak = int(record.get("loss_streak", 0))
        exec_err = int(record.get("execution_errors", 0))
        total = wins + losses
        win_rate = (wins / total * 100.0) if total else 0.0
        allowed, gate_reason = strategy_scores.allow_strategy(strategy_id)
        status = "allowed" if allowed else "blocked"
        gate = gate_reason[:30]
        last_update = record.get("last_update", 0.0) or 0.0
        updated = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_update)) if last_update else "n/a"
        reason = str(record.get("last_reason", ""))[:30]
        print(
            f"{strategy_id} | {score:.1f} | {win_rate:5.1f} | {wins:4d} | {losses:6d} | "
            f"{streak:6d} | {exec_err:8d} | {status:7s} | {gate:30s} | {updated} | {reason}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lifeos")
    subparsers = parser.add_subparsers(dest="command", required=True)

    mode_parser = argparse.ArgumentParser(add_help=False)
    mode_parser.add_argument("--apply", action="store_true")
    mode_parser.add_argument("--dry-run", action="store_true")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--verbose", "-v", action="store_true", help="Show component status details")
    subparsers.add_parser("on", parents=[mode_parser])
    subparsers.add_parser("off", parents=[mode_parser])

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--test", action="store_true", help="Run quick provider test")
    doctor_parser.add_argument("--voice", action="store_true", help="Run voice pipeline diagnostics")
    doctor_parser.add_argument("--mcp", action="store_true", help="Run comprehensive MCP server diagnostics")
    doctor_parser.add_argument("--validate-keys", action="store_true", help="Validate API keys with actual API calls")

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
    rpc_diag_parser = subparsers.add_parser(
        "rpc-diagnostics",
        help="Probe Solana RPC endpoints and simulation health",
    )
    rpc_diag_parser.add_argument("--no-sim", action="store_true", help="Skip simulation probe")
    rpc_diag_parser.add_argument("--json", action="store_true", help="Output JSON")

    simulate_exit_parser = subparsers.add_parser(
        "simulate-exit",
        help="Simulate a Jupiter exit swap for an intent",
    )
    simulate_exit_parser.add_argument("--intent-id", type=str, help="Exit intent id")
    simulate_exit_parser.add_argument("--symbol", type=str, help="Symbol fallback if no intent id")
    simulate_exit_parser.add_argument("--size-pct", type=float, default=100.0, help="Percent of remaining qty")
    simulate_exit_parser.add_argument("--endpoint", type=str, help="RPC endpoint name to target")
    simulate_exit_parser.add_argument("--no-report", action="store_true", help="Skip report file")
    simulate_exit_parser.add_argument("--json", action="store_true", help="Output JSON")

    subparsers.add_parser("talk")
    subparsers.add_parser("chat")

    listen_parser = subparsers.add_parser("listen", parents=[mode_parser])
    listen_parser.add_argument("state", choices=["on", "off"])

    # Voice subcommand with doctor action
    voice_parser = subparsers.add_parser("voice", help="Voice pipeline management")
    voice_subparsers = voice_parser.add_subparsers(dest="voice_action", required=True)
    voice_doctor_parser = voice_subparsers.add_parser("doctor", help="Run voice pipeline diagnostics")

    secret_parser = subparsers.add_parser("secret")
    secret_parser.add_argument("provider", choices=["gemini", "openai"])
    secret_parser.add_argument("key")

    activity_parser = subparsers.add_parser("activity")
    activity_parser.add_argument("--hours", type=int, default=4)

    subparsers.add_parser("checkin", parents=[mode_parser])

    evolve_parser = subparsers.add_parser("evolve", parents=[mode_parser])
    evolve_parser.add_argument("request", nargs="?", default="")

    jarvis_parser = subparsers.add_parser("jarvis")
    jarvis_parser.add_argument("action", nargs="?", default="status",
                               choices=["status", "interview", "discover", "research", "profile", "suggest"])

    agent_parser = subparsers.add_parser("agent")
    agent_parser.add_argument("goal", nargs="+", help="Goal to plan or execute")
    agent_parser.add_argument("--execute", action="store_true", help="Run the plan (default is plan-only)")
    agent_parser.add_argument("--max-cycles", type=int, default=None)
    agent_parser.add_argument("--max-step-retries", type=int, default=None)

    # Task management commands
    task_parser = subparsers.add_parser("task")
    task_subparsers = task_parser.add_subparsers(dest="task_action", required=True)
    
    # task add
    task_add_parser = task_subparsers.add_parser("add")
    task_add_parser.add_argument("title", help="Task title")
    task_add_parser.add_argument("--priority", choices=["low", "medium", "high", "urgent"], default="medium")
    
    # task list
    task_list_parser = task_subparsers.add_parser("list")
    task_list_parser.add_argument("--status", choices=["pending", "in_progress", "completed", "cancelled"])
    task_list_parser.add_argument("--priority", choices=["low", "medium", "high", "urgent"])
    task_list_parser.add_argument("--limit", type=int, default=20)
    
    # task complete
    task_complete_parser = task_subparsers.add_parser("complete")
    task_complete_parser.add_argument("task_id", help="Task ID to complete")
    
    # task start
    task_start_parser = task_subparsers.add_parser("start")
    task_start_parser.add_argument("task_id", help="Task ID to start")
    
    # task status
    task_status_parser = task_subparsers.add_parser("status")

    # P0: Brain/Orchestrator commands
    brain_parser = subparsers.add_parser("brain", help="Brain/Orchestrator status and control")
    brain_parser.add_argument("action", nargs="?", default="status",
                              choices=["status", "inject", "history"])
    brain_parser.add_argument("--text", help="Text to inject (for inject action)")

    # P0: Objective management commands
    objective_parser = subparsers.add_parser("objective", help="Manage objectives")
    objective_subparsers = objective_parser.add_subparsers(dest="objective_action", required=True)

    # objective add
    obj_add_parser = objective_subparsers.add_parser("add")
    obj_add_parser.add_argument("description", help="Objective description")
    obj_add_parser.add_argument("--priority", default="5", help="Priority 1-10 (default 5)")
    obj_add_parser.add_argument("--criteria", help="Comma-separated success criteria")

    # objective list
    obj_list_parser = objective_subparsers.add_parser("list")
    obj_list_parser.add_argument("--limit", type=int, default=10)

    # objective complete
    obj_complete_parser = objective_subparsers.add_parser("complete")
    obj_complete_parser.add_argument("objective_id", help="Objective ID")
    obj_complete_parser.add_argument("--outcome", help="Outcome description")

    # objective fail
    obj_fail_parser = objective_subparsers.add_parser("fail")
    obj_fail_parser.add_argument("objective_id", help="Objective ID")
    obj_fail_parser.add_argument("--reason", help="Failure reason")
    obj_fail_parser.add_argument("--requeue", action="store_true", help="Re-add to queue")

    # objective history
    obj_history_parser = objective_subparsers.add_parser("history")
    obj_history_parser.add_argument("--limit", type=int, default=20)

    # P0: Action feedback commands
    feedback_parser = subparsers.add_parser("feedback", help="Action feedback and learning")
    feedback_subparsers = feedback_parser.add_subparsers(dest="feedback_action", required=True)

    # feedback metrics
    feedback_subparsers.add_parser("metrics")

    # feedback patterns
    feedback_subparsers.add_parser("patterns")

    # feedback recommend
    feedback_rec_parser = feedback_subparsers.add_parser("recommend")
    feedback_rec_parser.add_argument("action_name", help="Action to get recommendations for")

    # P1: Multi-Agent System commands
    agents_parser = subparsers.add_parser("agents", help="Multi-agent system management")
    agents_subparsers = agents_parser.add_subparsers(dest="agents_action", required=True)

    # agents status
    agents_subparsers.add_parser("status", help="Show agent system status")

    # agents run <role> <task>
    agents_run_parser = agents_subparsers.add_parser("run", help="Run specific agent")
    agents_run_parser.add_argument("role", choices=["researcher", "operator", "trader", "architect"])
    agents_run_parser.add_argument("task", help="Task for the agent to execute")

    # agents research <query>
    agents_research_parser = agents_subparsers.add_parser("research", help="Quick research")
    agents_research_parser.add_argument("query", help="What to research")

    # agents trade [task]
    agents_trade_parser = agents_subparsers.add_parser("trade", help="Trading analysis")
    agents_trade_parser.add_argument("--task", help="Trading task")

    # agents improve [target]
    agents_improve_parser = agents_subparsers.add_parser("improve", help="Architecture improvement")
    agents_improve_parser.add_argument("--target", help="What to improve")

    # agents providers
    agents_subparsers.add_parser("providers", help="Show provider availability")

    # P2: Economics commands
    economics_parser = subparsers.add_parser("economics", help="Economic dashboard and P&L tracking")
    economics_subparsers = economics_parser.add_subparsers(dest="economics_action", required=True)

    # economics status
    economics_subparsers.add_parser("status", help="Show current economic status")

    # economics report
    econ_report_parser = economics_subparsers.add_parser("report", help="Generate full P&L report")
    econ_report_parser.add_argument("--days", type=int, default=30, help="Days to include")

    # economics costs
    econ_costs_parser = economics_subparsers.add_parser("costs", help="Show cost breakdown")
    econ_costs_parser.add_argument("--days", type=int, default=7, help="Days to include")

    # economics revenue
    econ_revenue_parser = economics_subparsers.add_parser("revenue", help="Show revenue breakdown")
    econ_revenue_parser.add_argument("--days", type=int, default=7, help="Days to include")

    # economics alerts
    economics_subparsers.add_parser("alerts", help="Show economic alerts")

    # economics ack <id>
    econ_ack_parser = economics_subparsers.add_parser("ack", help="Acknowledge an alert")
    econ_ack_parser.add_argument("alert_id", help="Alert ID to acknowledge")

    # economics trend
    econ_trend_parser = economics_subparsers.add_parser("trend", help="Show P&L trend")
    econ_trend_parser.add_argument("--days", type=int, default=7, help="Days to show")

    # economics log-time <minutes> <task>
    econ_logtime_parser = economics_subparsers.add_parser("log-time", help="Log time saved")
    econ_logtime_parser.add_argument("minutes", type=float, help="Minutes saved")
    econ_logtime_parser.add_argument("task", help="Task description")

    # economics log-trade <amount> [--symbol] [--live]
    econ_logtrade_parser = economics_subparsers.add_parser("log-trade", help="Log trading profit/loss")
    econ_logtrade_parser.add_argument("amount", type=float, help="Profit/loss amount in USD")
    econ_logtrade_parser.add_argument("--symbol", help="Trading symbol (e.g., BTC)")
    econ_logtrade_parser.add_argument("--live", action="store_true", help="Mark as live trade (default: paper)")

    trading_youtube_parser = subparsers.add_parser(
        "trading-youtube",
        help="Ingest YouTube trading channels and queue backtests",
    )
    trading_youtube_subparsers = trading_youtube_parser.add_subparsers(
        dest="trading_youtube_action",
        required=True,
    )
    # trading-youtube scan
    ty_scan_parser = trading_youtube_subparsers.add_parser("scan", help="Scan a channel")
    ty_scan_parser.add_argument("--channel", help="YouTube channel URL")
    ty_scan_parser.add_argument("--limit", type=int, help="Max videos to scan")
    ty_scan_parser.add_argument("--no-enqueue", action="store_true", help="Do not queue backtests")

    # trading-youtube compile
    ty_compile_parser = trading_youtube_subparsers.add_parser("compile", help="Compile strategies from videos")
    ty_compile_parser.add_argument("--channel", help="YouTube channel URL")
    ty_compile_parser.add_argument("--limit", type=int, help="Max videos to scan (default 50)")
    ty_compile_parser.add_argument("--no-enqueue", action="store_true", help="Do not queue backtests")

    # trading-youtube queue
    trading_youtube_subparsers.add_parser("queue", help="Show queued backtests")

    # trading-youtube backtest
    ty_backtest_parser = trading_youtube_subparsers.add_parser("backtest", help="Run queued backtests")
    ty_backtest_parser.add_argument("--limit", type=int, help="Max backtests to run")

    trading_notion_parser = subparsers.add_parser(
        "trading-notion",
        help="Ingest Notion resources and compile strategies",
    )
    trading_notion_subparsers = trading_notion_parser.add_subparsers(
        dest="trading_notion_action",
        required=True,
    )
    tn_ingest_parser = trading_notion_subparsers.add_parser("ingest", help="Ingest Notion page")
    tn_ingest_parser.add_argument("--url", help="Notion page URL")
    tn_ingest_parser.add_argument("--crawl-depth", type=int, default=2, help="Link crawl depth")
    tn_ingest_parser.add_argument("--max-links", type=int, default=400, help="Max links to crawl")
    tn_ingest_parser.add_argument("--max-pages", type=int, default=30, help="Max nested pages to ingest")
    tn_ingest_parser.add_argument("--max-chunks", type=int, default=60, help="Max chunks per page")
    tn_ingest_parser.add_argument("--headless", action="store_true", help="Use Playwright headless scraper for full content")
    tn_ingest_parser.add_argument("--notebooklm", action="store_true", help="Use NotebookLM to summarize YouTube videos")

    tn_compile_parser = trading_notion_subparsers.add_parser("compile", help="Compile strategies from Notion ingest")
    tn_compile_parser.add_argument("--exec-path", help="Override execution JSON path")
    tn_compile_parser.add_argument("--no-seed", action="store_true", help="Do not seed strategies into engine")

    solana_parser = subparsers.add_parser(
        "solana-scan",
        help="Scan Solana meme coins via BirdEye",
    )
    solana_subparsers = solana_parser.add_subparsers(
        dest="solana_action",
        required=True,
    )
    solana_run_parser = solana_subparsers.add_parser("run", help="Run scanner and write CSVs")
    solana_run_parser.add_argument("--trending-limit", type=int, default=200)
    solana_run_parser.add_argument("--new-token-hours", type=int, default=3)
    solana_run_parser.add_argument("--top-trader-limit", type=int, default=100)
    solana_run_parser.add_argument("--no-seed", action="store_true")
    solana_subparsers.add_parser("shortlist", help="Show strategy shortlist")
    solana_subparsers.add_parser("seed", help="Seed scanner strategies into engine")

    trading_positions_parser = subparsers.add_parser(
        "trading-positions",
        help="Manage trading positions and symbol mappings",
    )
    trading_positions_subparsers = trading_positions_parser.add_subparsers(
        dest="trading_positions_action",
        required=True,
    )
    trading_positions_subparsers.add_parser("list", help="List open positions")
    trading_positions_subparsers.add_parser("status", help="Show risk manager stats")

    positions_add_parser = trading_positions_subparsers.add_parser("add", help="Record a new position")
    positions_add_parser.add_argument("--symbol", required=True, help="Token symbol or mint address")
    positions_add_parser.add_argument("--entry", type=float, required=True, help="Entry price")
    positions_add_parser.add_argument("--quantity", type=float, help="Quantity to buy/sell")
    positions_add_parser.add_argument("--action", choices=["BUY", "SELL"], default="BUY")
    positions_add_parser.add_argument("--stop-loss", type=float)
    positions_add_parser.add_argument("--take-profit", type=float)
    positions_add_parser.add_argument("--stop-loss-pct", type=float, help="Stop-loss percent (if price not provided)")
    positions_add_parser.add_argument("--take-profit-pct", type=float, help="Take-profit percent (if price not provided)")
    positions_add_parser.add_argument("--capital", type=float, help="Capital for sizing if quantity omitted")
    positions_add_parser.add_argument("--risk-pct", type=float, help="Risk percent for sizing (default from limits)")
    positions_add_parser.add_argument("--strategy", help="Strategy label")
    positions_add_parser.add_argument("--address", help="Mint address to map to symbol")

    positions_close_parser = trading_positions_subparsers.add_parser("close", help="Close an open position")
    positions_close_parser.add_argument("--trade-id", required=True)
    positions_close_parser.add_argument("--exit-price", type=float, required=True)
    positions_close_parser.add_argument(
        "--reason",
        choices=["CLOSED", "STOPPED_OUT", "TOOK_PROFIT"],
        default="CLOSED",
    )

    positions_map_parser = trading_positions_subparsers.add_parser("map", help="Map symbol to mint address")
    positions_map_parser.add_argument("--symbol", required=True)
    positions_map_parser.add_argument("--address", required=True)

    trading_opportunities_parser = subparsers.add_parser(
        "trading-opportunities",
        help="Generate unified crypto + tokenized equity opportunities JSON",
    )
    trading_opportunities_parser.add_argument("--signals", help="Path to sentiment signals JSON/JSONL")
    trading_opportunities_parser.add_argument("--refresh-equities", action="store_true")
    trading_opportunities_parser.add_argument("--capital-usd", type=float, default=20.0)
    trading_opportunities_parser.add_argument("--output", help="Write JSON output to file")

    strategy_scores_parser = subparsers.add_parser(
        "strategy-scores",
        help="Show strategy performance scores",
    )
    strategy_scores_parser.add_argument("--limit", type=int, default=20)
    strategy_scores_parser.add_argument("--min-score", type=float)
    strategy_scores_parser.add_argument(
        "--sort",
        choices=["score", "wins", "losses", "loss_streak", "execution_errors", "last_update"],
        default="score",
    )
    strategy_scores_parser.add_argument("--asc", action="store_true", help="Sort ascending")
    strategy_scores_parser.add_argument("--json", action="store_true", help="Output JSON")

    # Register actions subcommands from jarvis_cli
    register_actions_subparser(subparsers)

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
    if args.command == "doctor":
        cmd_doctor(args)
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
    if args.command == "rpc-diagnostics":
        cmd_rpc_diagnostics(args)
        return
    if args.command == "simulate-exit":
        cmd_simulate_exit(args)
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
    if args.command == "voice":
        exit_code = cmd_voice(args)
        sys.exit(exit_code)
    if args.command == "secret":
        cmd_secret(args)
        return
    if args.command == "activity":
        cmd_activity(args)
        return
    if args.command == "checkin":
        cmd_checkin(args)
        return
    if args.command == "evolve":
        cmd_evolve(args)
        return
    if args.command == "jarvis":
        cmd_jarvis(args)
        return
    if args.command == "agent":
        cmd_agent(args)
        return
    if args.command == "task":
        cmd_task(args)
        return
    if args.command == "brain":
        cmd_brain(args)
        return
    if args.command == "objective":
        cmd_objective(args)
        return
    if args.command == "feedback":
        cmd_feedback(args)
        return
    if args.command == "agents":
        cmd_agents(args)
        return
    if args.command == "economics":
        cmd_economics(args)
        return
    if args.command == "trading-youtube":
        cmd_trading_youtube(args)
        return
    if args.command == "trading-notion":
        cmd_trading_notion(args)
        return
    if args.command == "solana-scan":
        cmd_solana_scan(args)
        return
    if args.command == "trading-positions":
        cmd_trading_positions(args)
        return
    if args.command == "trading-opportunities":
        cmd_trading_opportunities(args)
        return
    if args.command == "strategy-scores":
        cmd_strategy_scores(args)
        return

    parser.print_help()


if __name__ == "__main__":
    main()

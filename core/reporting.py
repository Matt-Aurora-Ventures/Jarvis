import datetime as dt
from pathlib import Path
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from core import config, context_loader, diagnostics, memory, providers, state

ROOT = Path(__file__).resolve().parents[1]


def _timezone_name(cfg: Dict[str, object]) -> str:
    return str(cfg.get("timezone", "UTC"))


def _reports_dir(cfg: Dict[str, object]) -> Path:
    return ROOT / str(cfg.get("paths", {}).get("reports_dir", "lifeos/reports"))


def _timestamp(tz_name: str) -> str:
    now = dt.datetime.now(ZoneInfo(tz_name))
    return now.strftime("%Y%m%d_%H%M")


def _format_report(
    kind: str,
    plain: str,
    technical: str,
    ask_matt: str,
    glossary: Optional[str] = None,
) -> str:
    lines = [
        f"# LifeOS {kind.title()} Report",
        "",
        "Plain English:",
        plain.strip(),
        "",
        "Technical Notes:",
        technical.strip(),
        "",
        "Ask Matt:",
        ask_matt.strip(),
    ]
    if glossary:
        lines.extend(["", "Glossary:", glossary.strip()])
    return "\n".join(lines).strip() + "\n"


def _fallback_report(kind: str, memory_summary: str, diag_summary: str) -> str:
    plain = "\n".join(
        [
            "Top 5 Actions:",
            "1) Review finances and pick the highest ROI task.",
            "2) Commit one deliverable for the marketing business today.",
            "3) Capture key decisions and outcomes from current work.",
            "4) Reduce distractions and close unused apps/tabs.",
            "5) Plan the next automation to save time overnight.",
            "",
            "Highlights:",
            memory_summary or "- No recent entries available.",
            "",
            "System Improvements Backlog:",
            diag_summary or "- No major issues detected.",
        ]
    )
    technical = "\n".join(
        [
            "- Modules/files involved: core/reporting.py, core/memory.py",
            "- Key concepts/terms: Context routing, adaptive memory cap",
            "- Risks/constraints: Read-only summaries if LLM is unavailable",
        ]
    )
    ask_matt = "\n".join(
        [
            "- What is the single most important money task today?",
            "- Which client/project needs the biggest push right now?",
            "- What should I automate overnight?",
        ]
    )
    glossary = "- ROI: Return on investment (how much value you get for the time/money)."
    return _format_report(kind, plain, technical, ask_matt, glossary)


def _diagnostics_summary(diag_data: Dict[str, object]) -> str:
    observations = diag_data.get("observations", [])
    if not observations:
        return "- No obvious system risks detected."
    lines = []
    for obs in observations[:3]:
        lines.append(f"- {obs.title}: {obs.detail}")
    return "\n".join(lines)


def generate_report_text(kind: str, dry_run: bool = True) -> str:
    cfg = config.load_config()
    context_text = context_loader.load_context(update_state=not dry_run)
    recent_entries = memory.get_recent_entries()
    memory_summary = memory.summarize_entries(recent_entries[-10:])
    diag_data = diagnostics.run_diagnostics(limit=3)
    diag_summary = _diagnostics_summary(diag_data)

    prompt = (
        f"You are LifeOS. Create a {kind} report that is voice-friendly.\n"
        "Output Markdown with these exact sections:\n"
        "Plain English:\n"
        "- Top 5 Actions (numbered 1-5)\n"
        "- Highlights (bullets)\n"
        "- System Improvements Backlog (bullets)\n"
        "Technical Notes:\n"
        "- Modules/files involved\n"
        "- Key concepts/terms\n"
        "- Risks/constraints\n"
        "Ask Matt:\n"
        "- 3 questions\n"
        "Glossary:\n"
        "- 1-3 terms with 1 sentence each\n"
        "\n"
        "Context:\n"
        f"{context_text}\n"
        "\n"
        "Recent Memory Summary:\n"
        f"{memory_summary}\n"
        "\n"
        "Diagnostics Summary:\n"
        f"{diag_summary}\n"
    )

    text = providers.generate_text(prompt, max_output_tokens=700)
    if text:
        return text.strip() + "\n"
    return _fallback_report(kind, memory_summary, diag_summary)


def save_report(kind: str, content: str) -> Path:
    cfg = config.load_config()
    tz_name = _timezone_name(cfg)
    reports_dir = _reports_dir(cfg)
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _timestamp(tz_name)
    path = reports_dir / f"{timestamp}_{kind}.md"
    path.write_text(content, encoding="utf-8")
    last_report_dates = state.read_state().get("last_report_dates", {})
    date_key = timestamp.split("_")[0]
    if len(date_key) == 8:
        date_key = f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}"
    last_report_dates[kind] = date_key
    state.update_state(
        last_report_at=timestamp,
        last_report_kind=kind,
        last_report_dates=last_report_dates,
    )
    return path


def plan_report_path(kind: str) -> Path:
    cfg = config.load_config()
    tz_name = _timezone_name(cfg)
    reports_dir = _reports_dir(cfg)
    timestamp = _timestamp(tz_name)
    return reports_dir / f"{timestamp}_{kind}.md"

from typing import Dict

from core import (
    config,
    context_loader,
    context_router,
    diagnostics,
    memory,
    providers,
    reporting,
    safety,
)


def _fallback_overview(memory_summary: str, diag_summary: str) -> str:
    lines = [
        "# LifeOS Overnight Report",
        "",
        "Plain English:",
        "Top 5 Actions (tomorrow morning):",
        "1) Review finances and pick the top ROI task.",
        "2) Ship one marketing deliverable before noon.",
        "3) Capture learnings and decisions from current work.",
        "4) Close or pause low-ROI tasks.",
        "5) Plan the next automation to save 1+ hour.",
        "",
        "System Improvements Backlog:",
        diag_summary or "- No major system issues detected.",
        "",
        "Scaling Roadmap Note:",
        "- Stay local for now; move to cloud only after stable daily workflows exist.",
        "",
        "Technical Notes:",
        "- Modules/files involved: core/overnight.py, core/memory.py",
        "- Key concepts/terms: Overnight plan, diagnostics snapshot",
        "- Risks/constraints: Safe mode only; no system changes",
        "",
        "Ask User:",
        "- What is the #1 money task to complete by noon?",
        "- Which client/project needs the biggest push?",
        "- What should be automated next?",
        "",
        "Glossary:",
        "- ROI: Return on investment (value gained per unit of time or money).",
    ]
    return "\n".join(lines).strip() + "\n"


def generate_overnight_text(dry_run: bool = True) -> str:
    cfg = config.load_config()
    context_text = context_loader.load_context(update_state=not dry_run)
    entries = memory.get_pending_entries() or memory.get_recent_entries()
    memory_summary = memory.summarize_entries(entries[-20:])
    diag_data = diagnostics.run_diagnostics(limit=3)
    diag_summary = reporting._diagnostics_summary(diag_data)

    prompt = (
        "Create an overnight report that is voice-friendly.\n"
        "Include these sections exactly:\n"
        "Plain English:\n"
        "- Top 5 Actions (tomorrow morning, numbered)\n"
        "- System Improvements Backlog (bullets)\n"
        "- Scaling Roadmap Note (1-3 bullets)\n"
        "Technical Notes:\n"
        "- Modules/files involved\n"
        "- Key concepts/terms\n"
        "- Risks/constraints\n"
        "Ask User:\n"
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
    return _fallback_overview(memory_summary, diag_summary)


def run_overnight(context: safety.SafetyContext) -> Dict[str, object]:
    entries = memory.get_pending_entries() or memory.get_recent_entries()
    routed = context_router.route_entries(entries)
    summary = memory.summarize_entries(entries)

    if context.dry_run:
        return {"summary": summary, "routed": routed, "report_path": None}

    written_paths = context_router.apply_routes(routed, context)
    if memory.get_pending_entries():
        memory.clear_pending_entries(context)

    report_text = generate_overnight_text(dry_run=False)
    report_path = reporting.save_report("overnight", report_text)

    return {
        "summary": summary,
        "routed": routed,
        "written_paths": written_paths,
        "report_path": report_path,
    }

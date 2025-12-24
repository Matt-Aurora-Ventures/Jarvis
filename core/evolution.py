"""
Self-improvement module for LifeOS.
Allows the system to upgrade itself based on conversations and user feedback.
Auto-upgrades on boot and continuously improves.
"""

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, guardian, providers, safety

ROOT = Path(__file__).resolve().parents[1]
EVOLUTION_LOG_PATH = ROOT / "data" / "evolution.jsonl"
IMPROVEMENTS_DIR = ROOT / "data" / "improvements"
SKILLS_DIR = ROOT / "skills"


@dataclass
class ImprovementProposal:
    id: str
    category: str  # skill, config, behavior, module
    title: str
    description: str
    code: Optional[str]
    rationale: str
    timestamp: float
    status: str  # proposed, approved, applied, rejected


def _load_evolution_log() -> List[Dict[str, Any]]:
    if not EVOLUTION_LOG_PATH.exists():
        return []
    entries = []
    try:
        with open(EVOLUTION_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass
    return entries


def _save_evolution_entry(entry: Dict[str, Any]) -> None:
    EVOLUTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(EVOLUTION_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")
    except Exception:
        pass


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return cleaned[:40] or "improvement"


def analyze_conversation_for_improvements(
    conversation_history: List[Dict[str, str]],
    user_feedback: str = "",
) -> Optional[ImprovementProposal]:
    """Analyze a conversation to identify potential self-improvements."""
    if not conversation_history:
        return None

    history_text = "\n".join(
        f"{entry.get('source', 'unknown')}: {entry.get('text', '')[:200]}"
        for entry in conversation_history[-10:]
    )

    prompt = f"""You are LifeOS, a self-improving AI assistant. Analyze this conversation and identify ONE concrete improvement you could make to yourself.

Conversation:
{history_text}

{f"User feedback: {user_feedback}" if user_feedback else ""}

Categories of improvements:
1. skill - A new Python skill module to add a capability
2. config - A configuration change to improve behavior  
3. behavior - A prompt or response pattern to change
4. module - A new core module for significant features

Output JSON only (no markdown):
{{
  "category": "skill|config|behavior|module",
  "title": "Short title",
  "description": "What this improves",
  "rationale": "Why this would help",
  "code": "Python code if category is skill, otherwise null",
  "priority": 1-5
}}

If no improvement is needed, output: {{"category": "none"}}"""

    try:
        response = providers.generate_text(prompt, max_output_tokens=600)
        if not response:
            return None

        clean = response.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```\w*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)

        data = json.loads(clean)
        if data.get("category") == "none":
            return None

        proposal_id = f"{int(time.time())}_{_slugify(data.get('title', 'improvement'))}"

        return ImprovementProposal(
            id=proposal_id,
            category=data.get("category", "skill"),
            title=data.get("title", "Unnamed improvement"),
            description=data.get("description", ""),
            code=data.get("code"),
            rationale=data.get("rationale", ""),
            timestamp=time.time(),
            status="proposed",
        )
    except Exception:
        return None


def propose_improvement_from_request(user_request: str) -> Optional[ImprovementProposal]:
    """Generate an improvement proposal based on a direct user request."""
    prompt = f"""You are LifeOS, a self-improving AI. The user wants you to add or improve something.

User request: {user_request}

Create a concrete improvement. For skills, output working Python code.

Output JSON only (no markdown):
{{
  "category": "skill|config|behavior|module",
  "title": "Short title",
  "description": "What this does",
  "rationale": "Why this helps",
  "code": "Complete Python code if skill, otherwise null"
}}

For skills, the code MUST:
- Define SKILL_NAME and DESCRIPTION at the top
- Have a run(context: dict, **kwargs) -> str function
- Be safe and lightweight
- Import only standard library or existing core modules"""

    try:
        response = providers.generate_text(prompt, max_output_tokens=800)
        if not response:
            return None

        clean = response.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```\w*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)

        data = json.loads(clean)
        proposal_id = f"{int(time.time())}_{_slugify(data.get('title', 'improvement'))}"

        return ImprovementProposal(
            id=proposal_id,
            category=data.get("category", "skill"),
            title=data.get("title", "Unnamed"),
            description=data.get("description", ""),
            code=data.get("code"),
            rationale=data.get("rationale", ""),
            timestamp=time.time(),
            status="proposed",
        )
    except Exception:
        return None


def apply_improvement(
    proposal: ImprovementProposal,
    context: safety.SafetyContext,
) -> Dict[str, Any]:
    """Apply an approved improvement."""
    if context.dry_run:
        return {
            "status": "dry_run",
            "proposal": proposal,
            "message": "Would apply improvement (dry-run mode)",
        }

    if proposal.category == "skill" and proposal.code:
        skill_name = _slugify(proposal.title)
        skill_path = SKILLS_DIR / f"{skill_name}.py"
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)

        code = proposal.code.strip()
        if not code.startswith("SKILL_NAME"):
            code = f'SKILL_NAME = "{proposal.title}"\nDESCRIPTION = "{proposal.description}"\n\n{code}'

        skill_path.write_text(code + "\n", encoding="utf-8")

        _save_evolution_entry({
            "id": proposal.id,
            "category": proposal.category,
            "title": proposal.title,
            "description": proposal.description,
            "rationale": proposal.rationale,
            "path": str(skill_path),
            "timestamp": time.time(),
            "status": "applied",
        })

        return {
            "status": "applied",
            "path": str(skill_path),
            "message": f"Created skill: {skill_path.name}",
        }

    elif proposal.category == "config":
        IMPROVEMENTS_DIR.mkdir(parents=True, exist_ok=True)
        config_path = IMPROVEMENTS_DIR / f"{proposal.id}_config.json"
        config_path.write_text(
            json.dumps({
                "title": proposal.title,
                "description": proposal.description,
                "rationale": proposal.rationale,
                "suggested_changes": proposal.code or proposal.description,
            }, indent=2),
            encoding="utf-8",
        )

        _save_evolution_entry({
            "id": proposal.id,
            "category": proposal.category,
            "title": proposal.title,
            "path": str(config_path),
            "timestamp": time.time(),
            "status": "saved",
        })

        return {
            "status": "saved",
            "path": str(config_path),
            "message": f"Saved config suggestion: {config_path.name}",
        }

    elif proposal.category in ("behavior", "module"):
        IMPROVEMENTS_DIR.mkdir(parents=True, exist_ok=True)
        proposal_path = IMPROVEMENTS_DIR / f"{proposal.id}_proposal.md"
        proposal_path.write_text(
            f"# {proposal.title}\n\n"
            f"**Category:** {proposal.category}\n\n"
            f"**Description:** {proposal.description}\n\n"
            f"**Rationale:** {proposal.rationale}\n\n"
            f"**Code/Details:**\n```\n{proposal.code or 'N/A'}\n```\n",
            encoding="utf-8",
        )

        _save_evolution_entry({
            "id": proposal.id,
            "category": proposal.category,
            "title": proposal.title,
            "path": str(proposal_path),
            "timestamp": time.time(),
            "status": "saved",
        })

        return {
            "status": "saved",
            "path": str(proposal_path),
            "message": f"Saved proposal: {proposal_path.name}",
        }

    return {"status": "unknown_category", "message": "Could not apply improvement"}


def get_evolution_stats() -> Dict[str, Any]:
    """Get statistics about self-improvements."""
    entries = _load_evolution_log()
    skills_created = sum(1 for e in entries if e.get("category") == "skill" and e.get("status") == "applied")
    proposals_saved = sum(1 for e in entries if e.get("status") == "saved")

    return {
        "total_improvements": len(entries),
        "skills_created": skills_created,
        "proposals_saved": proposals_saved,
        "last_improvement": entries[-1] if entries else None,
    }


def list_skills() -> List[Dict[str, str]]:
    """List all installed skills."""
    skills = []
    if not SKILLS_DIR.exists():
        return skills

    for skill_file in SKILLS_DIR.glob("*.py"):
        try:
            content = skill_file.read_text(encoding="utf-8")
            name_match = re.search(r'SKILL_NAME\s*=\s*["\'](.+?)["\']', content)
            desc_match = re.search(r'DESCRIPTION\s*=\s*["\'](.+?)["\']', content)
            skills.append({
                "file": skill_file.name,
                "name": name_match.group(1) if name_match else skill_file.stem,
                "description": desc_match.group(1) if desc_match else "",
            })
        except Exception:
            continue

    return skills


def evolve_from_conversation(
    user_text: str,
    conversation_history: List[Dict[str, str]],
    context: safety.SafetyContext,
) -> str:
    """Main entry point for self-improvement from conversation."""
    evolve_triggers = [
        "improve yourself",
        "upgrade yourself",
        "add ability",
        "add skill",
        "build skill",
        "modify your code",
        "enhance yourself",
        "learn to",
        "teach yourself",
        "evolve",
    ]

    lower_text = user_text.lower()
    is_evolve_request = any(trigger in lower_text for trigger in evolve_triggers)

    if is_evolve_request:
        proposal = propose_improvement_from_request(user_text)
    else:
        proposal = analyze_conversation_for_improvements(
            conversation_history,
            user_feedback=user_text,
        )

    if not proposal:
        return (
            "I analyzed the conversation but didn't identify a concrete improvement to make. "
            "Try asking me to 'add a skill to [do something specific]' or 'improve yourself to [capability]'."
        )

    preview = (
        f"**Proposed Improvement:**\n"
        f"- **Title:** {proposal.title}\n"
        f"- **Category:** {proposal.category}\n"
        f"- **Description:** {proposal.description}\n"
        f"- **Rationale:** {proposal.rationale}\n"
    )

    if context.dry_run:
        return f"{preview}\n\nThis is a preview. Say 'apply' or run with --apply to implement this improvement."

    result = apply_improvement(proposal, context)
    return f"{preview}\n\n**Result:** {result.get('message', 'Unknown')}"


def auto_evolve_on_boot() -> Dict[str, Any]:
    """
    Automatically check for and apply improvements on boot.
    This runs silently and logs results.
    """
    results = {
        "checked": True,
        "improvements_found": 0,
        "improvements_applied": 0,
        "errors": [],
    }
    
    # Check for pending improvements
    pending = _load_evolution_log()
    pending_proposals = [e for e in pending if e.get("status") == "proposed"]
    
    # Auto-apply safe improvements (skills only, with safety check)
    for entry in pending_proposals[-3:]:  # Only process last 3
        if entry.get("category") == "skill":
            try:
                # Validate code safety
                code = entry.get("code", "")
                if code:
                    is_safe, reason = guardian.validate_code_for_safety(code)
                    if is_safe:
                        # Create a minimal proposal and apply
                        proposal = ImprovementProposal(
                            id=entry.get("id", f"auto_{int(time.time())}"),
                            category="skill",
                            title=entry.get("title", "Auto skill"),
                            description=entry.get("description", ""),
                            code=code,
                            rationale=entry.get("rationale", "Auto-applied"),
                            timestamp=time.time(),
                            status="approved",
                        )
                        ctx = safety.SafetyContext(apply=True, dry_run=False)
                        apply_improvement(proposal, ctx)
                        results["improvements_applied"] += 1
            except Exception as e:
                results["errors"].append(str(e)[:100])
    
    results["improvements_found"] = len(pending_proposals)
    return results


def continuous_improvement_check() -> Optional[ImprovementProposal]:
    """
    Periodically analyze system state and propose improvements.
    Called by daemon on schedule.
    """
    # Get recent activity and errors
    log = _load_evolution_log()
    recent_errors = [e for e in log if e.get("status") == "error"][-5:]
    
    if not recent_errors:
        return None
    
    error_summary = "\n".join(
        f"- {e.get('title', 'Unknown')}: {e.get('error', 'No details')[:100]}"
        for e in recent_errors
    )
    
    prompt = f"""You are LifeOS analyzing recent errors to improve yourself.

Recent errors:
{error_summary}

Propose ONE improvement to prevent these errors.

Output JSON only:
{{
  "category": "skill|config|behavior",
  "title": "Short title",
  "description": "What this fixes",
  "rationale": "Why this helps",
  "code": "Python code if skill, otherwise null"
}}

If no improvement needed: {{"category": "none"}}"""

    try:
        response = providers.generate_text(prompt, max_output_tokens=500)
        if not response:
            return None
        
        clean = response.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```\\w*\\n?", "", clean)
            clean = re.sub(r"\\n?```$", "", clean)
        
        data = json.loads(clean)
        if data.get("category") == "none":
            return None
        
        return ImprovementProposal(
            id=f"auto_{int(time.time())}_{_slugify(data.get('title', 'fix'))}",
            category=data.get("category", "behavior"),
            title=data.get("title", "Auto-fix"),
            description=data.get("description", ""),
            code=data.get("code"),
            rationale=data.get("rationale", ""),
            timestamp=time.time(),
            status="proposed",
        )
    except Exception:
        return None

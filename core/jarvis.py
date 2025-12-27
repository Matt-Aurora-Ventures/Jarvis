"""
Jarvis Core - The self-improving autonomous assistant for the user.
Handles boot-time discovery, self-improvement, and goal-oriented operation.
"""

import json
import subprocess
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, guardian, memory, providers, safety

ROOT = Path(__file__).resolve().parents[1]
JARVIS_STATE_PATH = ROOT / "data" / "jarvis_state.json"
DISCOVERIES_PATH = ROOT / "data" / "discoveries.jsonl"
USER_PROFILE_PATH = ROOT / "lifeos" / "context" / "user_profile.md"
MCP_CONFIG_PATH = ROOT / "lifeos" / "config" / "mcp.config.json"
SYSTEM_INSTRUCTIONS_PATH = ROOT / "lifeos" / "config" / "system_instructions.md"
BOOT_REPORTS_DIR = ROOT / "data" / "boot_reports"
DAEMON_LOG_PATH = ROOT / "lifeos" / "logs" / "daemon.log"
EVOLUTION_LOG_PATH = ROOT / "data" / "evolution.jsonl"
MCP_LOG_DIR = ROOT / "lifeos" / "logs" / "mcp"
MISSION_LOG_DIR = ROOT / "lifeos" / "logs" / "missions"


@dataclass
class UserProfile:
    name: str = "User"
    linkedin: str = "yourprofile"
    primary_goals: List[str] = None
    businesses: List[str] = None
    interests: List[str] = None
    trading_focus: str = "crypto algorithmic trading"
    mentor_channels: List[str] = None
    last_interview: float = 0
    
    def __post_init__(self):
        if self.primary_goals is None:
            self.primary_goals = [
                "Make money through automation and smart decisions",
                "Help humanity through technology",
                "Build autonomous systems that work for me",
                "Achieve financial freedom",
            ]
        if self.businesses is None:
            self.businesses = []
        if self.interests is None:
            self.interests = [
                "AI and automation",
                "Crypto trading",
                "Algorithmic trading",
                "Self-improvement",
                "Creative agency workflows",
            ]
        if self.mentor_channels is None:
            self.mentor_channels = ["Moon Dev"]


@dataclass 
class AIResource:
    name: str
    type: str  # model, api, tool
    provider: str
    is_free: bool
    quality_score: int  # 1-10
    description: str
    how_to_use: str
    discovered_at: float


def _load_jarvis_state() -> Dict[str, Any]:
    if not JARVIS_STATE_PATH.exists():
        return {
            "boot_count": 0,
            "last_boot": 0,
            "last_discovery_check": 0,
            "discovered_resources": [],
            "self_improvements": [],
            "user_profile": asdict(UserProfile()),
        }
    try:
        with open(JARVIS_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"boot_count": 0, "last_boot": 0}


def _save_jarvis_state(state: Dict[str, Any]) -> None:
    JARVIS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JARVIS_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _log_discovery(resource: AIResource) -> None:
    DISCOVERIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DISCOVERIES_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(resource)) + "\n")


def get_user_profile() -> UserProfile:
    """Get the current user profile."""
    state = _load_jarvis_state()
    profile_data = state.get("user_profile", {})
    return UserProfile(**profile_data)


def update_user_profile(**kwargs) -> None:
    """Update user profile with new information."""
    state = _load_jarvis_state()
    profile = state.get("user_profile", asdict(UserProfile()))
    profile.update(kwargs)
    state["user_profile"] = profile
    _save_jarvis_state(state)


def discover_free_ai_resources() -> List[AIResource]:
    """Use AI to discover the latest free AI resources and models."""
    safety_prompt = guardian.get_safety_prompt()
    
    prompt = f"""{safety_prompt}

You are researching the LATEST free AI resources available as of late 2024/2025.
List the best FREE AI models and APIs that can be used for:
1. Text generation (conversation, coding, reasoning)
2. Local models that run on 8GB RAM Mac
3. Free API tiers with generous limits

Output JSON array only (no markdown):
[
  {{
    "name": "model name",
    "type": "model|api|tool",
    "provider": "company/source",
    "is_free": true,
    "quality_score": 1-10,
    "description": "what it does",
    "how_to_use": "quick setup instructions"
  }}
]

Focus on: Ollama models, free API tiers (Gemini, Groq, Together.ai, etc.), local models.
Max 5 best options."""

    try:
        response = providers.generate_text(prompt, max_output_tokens=800)
        if not response:
            return []
        
        # Parse JSON from response
        import re
        clean = response.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```\w*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)
        
        data = json.loads(clean)
        resources = []
        for item in data:
            resources.append(AIResource(
                name=item.get("name", ""),
                type=item.get("type", "model"),
                provider=item.get("provider", ""),
                is_free=item.get("is_free", True),
                quality_score=item.get("quality_score", 5),
                description=item.get("description", ""),
                how_to_use=item.get("how_to_use", ""),
                discovered_at=time.time(),
            ))
        return resources
    except Exception as e:
        return []


def research_trading_strategies() -> str:
    """Research crypto trading strategies from Moon Dev and other sources."""
    safety_prompt = guardian.get_safety_prompt()
    profile = get_user_profile()
    
    prompt = f"""{safety_prompt}

You are helping {profile.name} learn about algorithmic crypto trading.
Research focus: Moon Dev's approach to quant trading.

Provide a summary of:
1. Key concepts for starting with $5-100 in crypto trading
2. Safe strategies for beginners (low risk)
3. Tools and APIs for automated trading
4. Risk management principles

Keep it practical and actionable. Output plain text, not JSON."""

    try:
        response = providers.generate_text(prompt, max_output_tokens=600)
        return response or "Could not research trading strategies at this time."
    except Exception as e:
        return f"Research failed: {str(e)[:100]}"


def generate_proactive_suggestions() -> List[str]:
    """Generate proactive suggestions based on user profile and context."""
    safety_prompt = guardian.get_safety_prompt()
    profile = get_user_profile()
    
    prompt = f"""{safety_prompt}

Based on user profile:
- Name: {profile.name}
- Goals: {', '.join(profile.primary_goals[:3])}
- Interests: {', '.join(profile.interests[:3])}
- Trading focus: {profile.trading_focus}

Generate 3 proactive suggestions for what the user might want to do next.
These should be actionable and aligned with their goals.

Output JSON array of strings only:
["suggestion 1", "suggestion 2", "suggestion 3"]"""

    try:
        response = providers.generate_text(prompt, max_output_tokens=200)
        if not response:
            return []
        
        import re
        clean = response.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```\w*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)
        
        return json.loads(clean)
    except Exception as e:
        return []


def conduct_interview() -> str:
    """Conduct an interview to learn more about the user."""
    safety_prompt = guardian.get_safety_prompt()
    profile = get_user_profile()
    
    hour = datetime.now().hour
    if 5 <= hour < 12:
        time_of_day = "morning"
    elif 12 <= hour < 17:
        time_of_day = "afternoon"
    else:
        time_of_day = "evening"
    
    prompt = f"""{safety_prompt}

You are Jarvis, interviewing {profile.name} to better understand and serve them.
Time: {time_of_day}

Generate 3-4 thoughtful interview questions to learn about:
1. Their current projects and priorities
2. Obstacles they're facing
3. How you can help them today

Be conversational and helpful, like a trusted AI assistant.
Output just the questions, numbered."""

    try:
        response = providers.generate_text(prompt, max_output_tokens=250)
        return response or "How can I help you today?"
    except Exception as e:
        return """1. What are you working on today?
2. What's your top priority this week?
3. Is there anything blocking your progress?
4. How can I help you right now?"""


def boot_sequence() -> Dict[str, Any]:
    """Run the Jarvis boot sequence - called when daemon starts."""
    state = _load_jarvis_state()
    state["boot_count"] = state.get("boot_count", 0) + 1
    state["last_boot"] = time.time()
    
    results = {
        "boot_count": state["boot_count"],
        "discoveries": [],
        "suggestions": [],
    }
    
    # Check for new AI resources every 24 hours
    last_discovery = state.get("last_discovery_check", 0)
    if time.time() - last_discovery > 86400:  # 24 hours
        resources = discover_free_ai_resources()
        for r in resources:
            _log_discovery(r)
        state["last_discovery_check"] = time.time()
        results["discoveries"] = [r.name for r in resources]
    
    # Generate proactive suggestions
    suggestions = generate_proactive_suggestions()
    results["suggestions"] = suggestions
    
    boot_report = _build_boot_report(state, results)
    results["boot_report"] = str(boot_report["path"])

    _save_jarvis_state(state)
    return results


def _build_boot_report(state: Dict[str, Any], boot_result: Dict[str, Any]) -> Dict[str, Any]:
    BOOT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().isoformat()

    report: Dict[str, Any] = {
        "timestamp": timestamp,
        "boot_count": state.get("boot_count", 0),
        "capabilities": _summarize_capabilities(),
        "context_snapshot": _load_context_snapshot(state, boot_result),
        "audits": _audit_recent_logs(),
        "self_tests": _run_self_tests(),
    }

    report["remediation"] = _auto_remediate(report["self_tests"])

    report_path = BOOT_REPORTS_DIR / f"boot_report_{int(time.time())}.json"
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    return {"data": report, "path": report_path}


def _summarize_capabilities() -> Dict[str, Any]:
    summary = {"mcp_servers": [], "instruction_highlights": []}
    try:
        with open(MCP_CONFIG_PATH, "r", encoding="utf-8") as handle:
            mcp_cfg = json.load(handle)
        summary["mcp_servers"] = [
            server.get("name", "unknown")
            for server in mcp_cfg.get("servers", [])
            if server.get("enabled", True)
        ]
    except Exception as exc:
        summary["mcp_servers"].append(f"Error reading MCP config: {exc}")

    try:
        with open(SYSTEM_INSTRUCTIONS_PATH, "r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle.readlines() if line.strip()]
        summary["instruction_highlights"] = lines[:10]
    except FileNotFoundError:
        summary["instruction_highlights"].append("System instructions file missing.")
    except Exception as exc:
        summary["instruction_highlights"].append(f"Error reading instructions: {exc}")

    return summary


def _load_context_snapshot(state: Dict[str, Any], boot_result: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = {
        "last_discovery_check": state.get("last_discovery_check"),
        "last_discoveries": boot_result.get("discoveries", []),
        "last_suggestions": boot_result.get("suggestions", []),
        "recent_missions": [],
        "recent_memory_entries": [],
    }

    try:
        mission_logs = sorted(MISSION_LOG_DIR.glob("*.log"), reverse=True)[:2]
        for log_path in mission_logs:
            with open(log_path, "r", encoding="utf-8") as handle:
                lines = handle.readlines()[-5:]
            snapshot["recent_missions"].append({log_path.name: [line.strip() for line in lines]})
    except Exception:
        pass

    try:
        recent_memory = memory.fetch_recent_entries(limit=5)
        snapshot["recent_memory_entries"] = [
            {"timestamp": entry.get("timestamp"), "summary": entry.get("summary", entry.get("text", "")[:120])}
            for entry in recent_memory
        ]
    except Exception:
        pass

    return snapshot


def _audit_recent_logs() -> Dict[str, Any]:
    audits: Dict[str, Any] = {"daemon_warnings": [], "evolution_errors": [], "mcp_errors": []}

    def _tail(path: Path, lines: int = 50) -> List[str]:
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            content = handle.readlines()
        return [line.strip() for line in content[-lines:]]

    for line in _tail(DAEMON_LOG_PATH, 80):
        if "warning" in line.lower() or "error" in line.lower():
            audits["daemon_warnings"].append(line)

    for line in _tail(EVOLUTION_LOG_PATH, 40):
        if "error" in line.lower():
            audits["evolution_errors"].append(line)

    if MCP_LOG_DIR.exists():
        for log_file in sorted(MCP_LOG_DIR.glob("*.log"))[-3:]:
            for line in _tail(log_file, 40):
                if "error" in line.lower() or "failed" in line.lower():
                    audits["mcp_errors"].append(f"{log_file.name}: {line}")

    return audits


def _run_self_tests() -> Dict[str, Dict[str, str]]:
    tests: Dict[str, Dict[str, str]] = {}

    tests["filesystem"] = _test_filesystem_access()
    tests["memory"] = _test_memory_pipeline()
    tests["git"] = _test_git_status()
    tests["shell"] = _test_shell_command()
    tests["puppeteer"] = _test_puppeteer_binary()
    tests["sequential_thinking"] = _test_sequential_thinking_config()

    return tests


def _test_filesystem_access() -> Dict[str, str]:
    temp_file = ROOT / "data" / "self_test_fs.tmp"
    try:
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_file, "w", encoding="utf-8") as handle:
            handle.write("fs-test")
        with open(temp_file, "r", encoding="utf-8") as handle:
            contents = handle.read()
        return {"status": "pass", "detail": f"Read/Write OK ({len(contents)} bytes)."}
    except Exception as exc:
        return {"status": "fail", "detail": f"Filesystem error: {exc}"}
    finally:
        temp_file.unlink(missing_ok=True)


def _test_memory_pipeline() -> Dict[str, str]:
    try:
        memory.append_entry("self-test memory entry", "self_test", safety.SafetyContext(apply=True, dry_run=False))
        recent = memory.fetch_recent_entries(limit=1)
        if recent:
            return {"status": "pass", "detail": "Memory append/fetch OK."}
        return {"status": "fail", "detail": "Memory fetch returned no entries."}
    except Exception as exc:
        return {"status": "fail", "detail": f"Memory error: {exc}"}


def _test_git_status() -> Dict[str, str]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            return {"status": "pass", "detail": "Git status succeeded."}
        return {"status": "fail", "detail": result.stderr.strip() or "git status returned non-zero."}
    except Exception as exc:
        return {"status": "fail", "detail": f"Git error: {exc}"}


def _test_shell_command() -> Dict[str, str]:
    try:
        result = subprocess.run(
            ["pwd"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return {"status": "pass", "detail": f"Shell command OK ({result.stdout.strip()})."}
    except Exception as exc:
        return {"status": "fail", "detail": f"Shell error: {exc}"}


def _test_puppeteer_binary() -> Dict[str, str]:
    try:
        with open(MCP_CONFIG_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        for server in data.get("servers", []):
            if server.get("name") != "puppeteer":
                continue
            command = server.get("command", "")
            args = server.get("args", [])
            if command and command.startswith("/") and Path(command).exists():
                return {"status": "pass", "detail": f"Puppeteer command present at {command}."}
            if command == "node" and args:
                script_path = Path(args[0])
                if script_path.exists():
                    return {"status": "pass", "detail": f"Puppeteer script present at {script_path}."}
            return {"status": "warn", "detail": "Puppeteer MCP configured but binary not found."}
    except Exception as exc:
        return {"status": "fail", "detail": f"Puppeteer check error: {exc}"}

    return {"status": "warn", "detail": "Puppeteer MCP not configured."}


def _test_sequential_thinking_config() -> Dict[str, str]:
    try:
        with open(MCP_CONFIG_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        names = [server.get("name") for server in data.get("servers", [])]
        if "sequential-thinking" in names:
            return {"status": "pass", "detail": "Sequential thinking MCP configured."}
        return {"status": "warn", "detail": "Sequential thinking MCP not configured."}
    except Exception as exc:
        return {"status": "fail", "detail": f"Config read error: {exc}"}


def _auto_remediate(self_tests: Dict[str, Dict[str, str]]) -> List[str]:
    notes: List[str] = []
    needs_restart = any(result["status"] == "fail" for result in self_tests.values())

    if needs_restart:
        try:
            from core import mcp_loader

            mcp_loader.stop_mcp_servers()
            mcp_loader.start_mcp_servers()
            notes.append("Restarted MCP servers after failed self-test.")
        except Exception as exc:
            notes.append(f"Failed to restart MCP servers: {exc}")

    return notes


def get_mission_context() -> str:
    """Get the current mission context for AI prompts."""
    profile = get_user_profile()
    
    return f"""=== JARVIS MISSION CONTEXT ===
User: {profile.name} (LinkedIn: {profile.linkedin})

PRIMARY MISSION:
1. Help {profile.name} make money through automation and smart decisions
2. Help him achieve his life goals
3. Help him help humanity
4. Constantly self-improve to serve him better

CURRENT FOCUS:
- Algorithmic crypto trading (learning from: {', '.join(profile.mentor_channels)})
- DEX-only, low-fee chains with high volume
- Prompt pack building for agency and website work
- Building autonomous systems
- Self-improvement and efficiency

GOALS:
{chr(10).join('- ' + g for g in profile.primary_goals)}

INTERESTS:
{chr(10).join('- ' + i for i in profile.interests)}

SAFETY: Never harm LifeOS or the user's computer. Always act in the user's best interest.
"""

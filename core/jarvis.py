"""
Jarvis Core - The self-improving autonomous assistant for the user.
Handles boot-time discovery, self-improvement, and goal-oriented operation.
"""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, guardian, providers

ROOT = Path(__file__).resolve().parents[1]
JARVIS_STATE_PATH = ROOT / "data" / "jarvis_state.json"
DISCOVERIES_PATH = ROOT / "data" / "discoveries.jsonl"
USER_PROFILE_PATH = ROOT / "lifeos" / "context" / "user_profile.md"


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
    
    _save_jarvis_state(state)
    return results


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
- Building autonomous systems
- Self-improvement and efficiency

GOALS:
{chr(10).join('- ' + g for g in profile.primary_goals)}

INTERESTS:
{chr(10).join('- ' + i for i in profile.interests)}

SAFETY: Never harm LifeOS or the user's computer. Always act in the user's best interest.
"""

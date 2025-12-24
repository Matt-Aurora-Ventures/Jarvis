"""
Interview/Check-in module for LifeOS.
Schedules periodic prompts to capture context from the user.
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, memory, passive, providers, safety, state

ROOT = Path(__file__).resolve().parents[1]
INTERVIEW_LOG_PATH = ROOT / "data" / "interviews.jsonl"


@dataclass
class InterviewQuestion:
    id: str
    question: str
    category: str
    priority: int = 1


DEFAULT_QUESTIONS = [
    InterviewQuestion("current_task", "What are you working on right now?", "focus", 1),
    InterviewQuestion("blockers", "What's blocking you or slowing you down?", "blockers", 2),
    InterviewQuestion("energy", "How's your energy level (1-10)?", "wellbeing", 2),
    InterviewQuestion("next_action", "What's the single most important thing to do next?", "planning", 1),
    InterviewQuestion("learnings", "What did you learn or discover recently?", "learning", 3),
    InterviewQuestion("wins", "Any wins or progress to celebrate?", "wins", 3),
    InterviewQuestion("help_needed", "What could I help you with right now?", "assistance", 2),
]

MORNING_QUESTIONS = [
    InterviewQuestion("morning_intention", "What's your main intention for today?", "planning", 1),
    InterviewQuestion("morning_energy", "How did you sleep? Energy level?", "wellbeing", 1),
    InterviewQuestion("morning_priority", "What's the #1 thing that would make today a success?", "planning", 1),
]

AFTERNOON_QUESTIONS = [
    InterviewQuestion("afternoon_progress", "How's the day going so far?", "focus", 1),
    InterviewQuestion("afternoon_adjust", "Anything you need to adjust for the rest of the day?", "planning", 2),
]

EVENING_QUESTIONS = [
    InterviewQuestion("evening_wins", "What went well today?", "wins", 1),
    InterviewQuestion("evening_learn", "What did you learn?", "learning", 1),
    InterviewQuestion("evening_tomorrow", "What's one thing to tackle first tomorrow?", "planning", 1),
]


def _load_interview_log() -> List[Dict[str, Any]]:
    if not INTERVIEW_LOG_PATH.exists():
        return []
    entries = []
    try:
        with open(INTERVIEW_LOG_PATH, "r", encoding="utf-8") as f:
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


def _save_interview_entry(entry: Dict[str, Any]) -> None:
    INTERVIEW_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(INTERVIEW_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")
    except Exception:
        pass


def _get_last_interview_time() -> float:
    entries = _load_interview_log()
    if not entries:
        return 0.0
    return max(e.get("timestamp", 0) for e in entries)


def _select_questions(time_of_day: str, count: int = 3) -> List[InterviewQuestion]:
    """Select appropriate questions based on time of day."""
    if time_of_day == "morning":
        pool = MORNING_QUESTIONS + [q for q in DEFAULT_QUESTIONS if q.priority == 1]
    elif time_of_day == "afternoon":
        pool = AFTERNOON_QUESTIONS + [q for q in DEFAULT_QUESTIONS if q.priority <= 2]
    elif time_of_day == "evening":
        pool = EVENING_QUESTIONS
    else:
        pool = [q for q in DEFAULT_QUESTIONS if q.priority <= 2]

    seen_categories = set()
    selected = []
    for q in pool:
        if q.category not in seen_categories and len(selected) < count:
            selected.append(q)
            seen_categories.add(q.category)
    return selected


def get_time_of_day() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    return "night"


def should_interview(min_interval_minutes: int = 120) -> bool:
    """Check if enough time has passed since last interview."""
    last = _get_last_interview_time()
    if last == 0:
        return True
    elapsed = time.time() - last
    return elapsed >= (min_interval_minutes * 60)


def generate_interview_prompt(activity_summary: str = "") -> str:
    """Generate a contextual interview prompt."""
    time_of_day = get_time_of_day()
    questions = _select_questions(time_of_day, count=3)

    activity_context = activity_summary or passive.summarize_activity(hours=2)

    prompt_parts = [
        f"Good {time_of_day}! Quick check-in:",
        "",
    ]

    for i, q in enumerate(questions, 1):
        prompt_parts.append(f"{i}. {q.question}")

    if activity_context and "No recent activity" not in activity_context:
        prompt_parts.extend([
            "",
            f"(Based on your recent activity: {activity_context[:200]})",
        ])

    return "\n".join(prompt_parts)


def process_interview_response(
    response: str,
    questions_asked: List[str],
    context: safety.SafetyContext,
) -> Dict[str, Any]:
    """Process user's interview response and store it."""
    timestamp = time.time()

    entry = {
        "timestamp": timestamp,
        "time_of_day": get_time_of_day(),
        "questions": questions_asked,
        "response": response,
        "processed": False,
    }

    if context.dry_run:
        return {"status": "dry_run", "entry": entry}

    _save_interview_entry(entry)

    memory.append_entry(
        text=f"[Check-in] {response}",
        source="interview",
        context=context,
    )

    return {"status": "saved", "entry": entry}


def generate_smart_questions(recent_context: str = "") -> str:
    """Use LLM to generate contextual questions based on recent activity."""
    activity = passive.summarize_activity(hours=4)
    time_of_day = get_time_of_day()

    prompt = f"""You are LifeOS, a personal AI assistant. Generate 2-3 short, helpful check-in questions for the user.

Time: {time_of_day}
Recent activity: {activity}
{f"Additional context: {recent_context}" if recent_context else ""}

Rules:
- Questions should be brief and actionable
- Focus on productivity, wellbeing, or next steps
- Don't be annoying or repetitive
- Make them feel natural, not like a survey

Output just the questions, one per line, numbered."""

    result = providers.generate_text(prompt, max_output_tokens=150)
    if result:
        return result.strip()

    questions = _select_questions(time_of_day)
    return "\n".join(f"{i}. {q.question}" for i, q in enumerate(questions, 1))


def get_interview_stats() -> Dict[str, Any]:
    """Get statistics about interviews for reporting."""
    entries = _load_interview_log()
    if not entries:
        return {"total": 0, "today": 0, "last": None}

    today_start = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
    today_count = sum(1 for e in entries if e.get("timestamp", 0) >= today_start)

    return {
        "total": len(entries),
        "today": today_count,
        "last": datetime.fromtimestamp(entries[-1].get("timestamp", 0)).isoformat() if entries else None,
    }


class InterviewScheduler:
    """Manages scheduled check-ins."""

    def __init__(self, min_interval_minutes: int = 120) -> None:
        self._min_interval = min_interval_minutes
        self._last_prompt_time = 0.0
        self._pending_interview = False

    def check_schedule(self) -> Optional[str]:
        """Check if it's time for an interview. Returns prompt if yes."""
        if not should_interview(self._min_interval):
            return None

        if time.time() - self._last_prompt_time < 300:
            return None

        cfg = config.load_config()
        interview_cfg = cfg.get("interview", {})
        if not interview_cfg.get("enabled", True):
            return None

        current_state = state.read_state()
        if current_state.get("chat_active"):
            return None

        idle_seconds = current_state.get("passive_idle_seconds", 0)
        if idle_seconds > 600:
            return None

        self._last_prompt_time = time.time()
        self._pending_interview = True

        use_smart = interview_cfg.get("smart_questions", False)
        if use_smart:
            return generate_smart_questions()
        return generate_interview_prompt()

    def mark_completed(self) -> None:
        self._pending_interview = False

    def is_pending(self) -> bool:
        return self._pending_interview

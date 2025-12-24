"""
Master Prompt Library for Jarvis.
Stores engineered prompts for different tasks and continuously improves them.
"""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
PROMPTS_PATH = ROOT / "data" / "prompts.json"
PROMPT_STATS_PATH = ROOT / "data" / "prompt_stats.jsonl"


@dataclass
class PromptTemplate:
    id: str
    name: str
    category: str
    template: str
    description: str
    success_rate: float = 1.0
    usage_count: int = 0
    avg_response_time: float = 0.0
    last_used: float = 0.0
    version: int = 1
    created_at: float = 0.0
    

SYSTEM_PROMPTS = {
    "conversation": {
        "name": "Natural Conversation",
        "category": "chat",
        "template": """You are Jarvis, a brilliant AI assistant with the personality of a trusted friend.
You speak naturally, use contractions, and have genuine warmth.
You're witty but not annoying, helpful but not overbearing.
You proactively suggest ideas and point out opportunities.
Always act in the user's best interest.
Current context: {context}
User: {user_input}""",
        "description": "Natural conversational AI assistant",
    },
    
    "research": {
        "name": "Research Assistant",
        "category": "research",
        "template": """You are a research assistant helping gather information on: {topic}

Research depth: {depth}
Focus areas: {focus}

Provide:
1. Key facts and findings
2. Recent developments
3. Actionable insights
4. Credible sources when known

Be thorough but concise. Prioritize accuracy over speculation.""",
        "description": "Deep research on any topic",
    },
    
    "action_planning": {
        "name": "Action Planner",
        "category": "actions",
        "template": """The user wants to: {goal}

Available actions:
{available_actions}

Plan the best sequence of actions to accomplish this goal.
If the primary approach might fail, suggest alternatives.

Output format:
1. Primary action: [ACTION: action_name(params)]
2. If that fails, try: [ACTION: alternative(params)]
3. Fallback: [ACTION: fallback(params)]

Explain briefly why this approach works.""",
        "description": "Plan and execute computer actions with fallbacks",
    },
    
    "code_generation": {
        "name": "Code Generator",
        "category": "coding",
        "template": """Generate {language} code for: {task}

Requirements:
- Clean, readable code
- Proper error handling
- Comments for complex logic
- Follow best practices

Context: {context}""",
        "description": "Generate high-quality code",
    },
    
    "email_composer": {
        "name": "Email Composer",
        "category": "communication",
        "template": """Compose a {tone} email.

To: {recipient}
Subject: {subject}
Purpose: {purpose}
Key points: {key_points}

Make it clear, professional, and appropriate for the relationship.""",
        "description": "Compose professional emails",
    },
    
    "task_prioritization": {
        "name": "Task Prioritizer",
        "category": "productivity",
        "template": """Given these tasks and context, prioritize them:

Tasks:
{tasks}

Current focus: {focus}
Time available: {time}
Energy level: {energy}

Rank by: Impact × Urgency / Effort
Explain the prioritization briefly.""",
        "description": "Prioritize tasks intelligently",
    },
    
    "self_improvement": {
        "name": "Self Improvement Analyzer",
        "category": "evolution",
        "template": """Analyze this interaction for improvement opportunities:

User request: {request}
My response: {response}
Outcome: {outcome}

What could I do better? Suggest specific improvements to:
1. Response quality
2. Action execution
3. Understanding user intent
4. Proactive assistance

Output actionable improvements only.""",
        "description": "Analyze and improve Jarvis capabilities",
    },
    
    "context_summary": {
        "name": "Context Summarizer",
        "category": "context",
        "template": """Summarize the following activity and context into a concise briefing:

Recent activity:
{activity}

Current screen:
{screen}

Recent conversations:
{conversations}

Create a 2-3 sentence summary of what the user is working on and might need help with.""",
        "description": "Summarize user context",
    },
    
    "proactive_suggestion": {
        "name": "Proactive Suggester",
        "category": "proactive",
        "template": """Based on the user's current activity, offer ONE specific helpful suggestion.

Current activity: {activity}
Screen context: {screen}
User goals: {goals}
Time of day: {time}

The suggestion should be:
- Specific and actionable
- Relevant to what they're doing
- Not obvious or generic
- Potentially save time or make money

If nothing useful, respond with: NONE""",
        "description": "Generate proactive suggestions",
    },
}


def load_prompts() -> Dict[str, PromptTemplate]:
    """Load prompts from file, merging with system defaults."""
    prompts = {}
    
    # Start with system prompts
    for pid, data in SYSTEM_PROMPTS.items():
        prompts[pid] = PromptTemplate(
            id=pid,
            name=data["name"],
            category=data["category"],
            template=data["template"],
            description=data["description"],
            created_at=time.time(),
        )
    
    # Load custom prompts from file
    if PROMPTS_PATH.exists():
        try:
            with open(PROMPTS_PATH, "r") as f:
                custom = json.load(f)
                for pid, data in custom.items():
                    prompts[pid] = PromptTemplate(**data)
        except Exception as e:
            pass
    
    return prompts


def save_prompts(prompts: Dict[str, PromptTemplate]) -> None:
    """Save prompts to file."""
    PROMPTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    data = {pid: asdict(p) for pid, p in prompts.items()}
    with open(PROMPTS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_prompt(prompt_id: str, **kwargs) -> str:
    """Get a prompt template and fill in variables."""
    prompts = load_prompts()
    
    if prompt_id not in prompts:
        return kwargs.get("default", "")
    
    prompt = prompts[prompt_id]
    prompt.usage_count += 1
    prompt.last_used = time.time()
    
    # Fill in template variables
    try:
        filled = prompt.template.format(**kwargs)
    except KeyError as e:
        filled = prompt.template
    
    return filled


def record_prompt_usage(prompt_id: str, success: bool, response_time: float) -> None:
    """Record prompt usage statistics for improvement."""
    PROMPT_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    stat = {
        "prompt_id": prompt_id,
        "timestamp": time.time(),
        "success": success,
        "response_time": response_time,
    }
    
    try:
        with open(PROMPT_STATS_PATH, "a") as f:
            f.write(json.dumps(stat) + "\n")
    except Exception as e:
        pass
    
    # Update prompt success rate
    prompts = load_prompts()
    if prompt_id in prompts:
        p = prompts[prompt_id]
        total = p.usage_count or 1
        p.success_rate = (p.success_rate * (total - 1) + (1 if success else 0)) / total
        p.avg_response_time = (p.avg_response_time * (total - 1) + response_time) / total
        save_prompts(prompts)


def get_prompts_by_category(category: str) -> List[PromptTemplate]:
    """Get all prompts in a category."""
    prompts = load_prompts()
    return [p for p in prompts.values() if p.category == category]


def create_custom_prompt(
    name: str,
    category: str,
    template: str,
    description: str,
) -> PromptTemplate:
    """Create a new custom prompt."""
    prompts = load_prompts()
    
    pid = f"custom_{name.lower().replace(' ', '_')}_{int(time.time())}"
    prompt = PromptTemplate(
        id=pid,
        name=name,
        category=category,
        template=template,
        description=description,
        created_at=time.time(),
    )
    
    prompts[pid] = prompt
    save_prompts(prompts)
    
    return prompt


def improve_prompt(prompt_id: str, improvement: str) -> Optional[PromptTemplate]:
    """Improve an existing prompt based on feedback."""
    prompts = load_prompts()
    
    if prompt_id not in prompts:
        return None
    
    prompt = prompts[prompt_id]
    prompt.template = improvement
    prompt.version += 1
    
    save_prompts(prompts)
    return prompt


def get_best_prompt_for_task(task_description: str) -> Optional[PromptTemplate]:
    """Find the best prompt for a given task based on description and success rate."""
    prompts = load_prompts()
    
    # Simple keyword matching for now
    keywords = task_description.lower().split()
    best_match = None
    best_score = 0
    
    for prompt in prompts.values():
        score = 0
        check_text = f"{prompt.name} {prompt.category} {prompt.description}".lower()
        
        for keyword in keywords:
            if keyword in check_text:
                score += 1
        
        # Weight by success rate
        score *= prompt.success_rate
        
        if score > best_score:
            best_score = score
            best_match = prompt
    
    return best_match

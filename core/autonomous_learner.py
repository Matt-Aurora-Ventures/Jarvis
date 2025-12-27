"""
Autonomous Learner for Jarvis.
Enhanced with continuous research engine and prompt distillation.
"""

import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.parse

from core import config, context_manager, evolution, guardian, providers, state, autonomous_controller, research_engine, prompt_distiller

ROOT = Path(__file__).resolve().parents[1]
AUTONOMOUS_LOG_PATH = ROOT / "data" / "autonomous_actions.log"
RESEARCH_CACHE_PATH = ROOT / "data" / "research_cache.json"

# Research topics to continuously monitor
RESEARCH_TOPICS = [
    "autonomous AI agents",
    "prompt engineering techniques",
    "LLM optimization",
    "self-improving AI systems",
    "AI agent architectures",
    "free AI tools and APIs",
    "open source AI projects",
    "AI agent frameworks",
    "multi-agent systems",
    "AI safety and alignment",
]

# Search queries for each topic
SEARCH_QUERIES = {
    "autonomous AI agents": [
        "autonomous agent github 2024",
        "self-improving AI agent open source",
        "autonomous LLM agent framework",
    ],
    "prompt engineering techniques": [
        "prompt engineering best practices 2024",
        "advanced prompting techniques LLM",
        "prompt optimization methods",
    ],
    "LLM optimization": [
        "LLM inference optimization",
        "reduce LLM API costs",
        "LLM performance tuning",
    ],
    "self-improving AI systems": [
        "AI self-improvement code",
        "autonomous code generation",
        "AI that writes its own code",
    ],
    "free AI tools and APIs": [
        "free AI APIs 2024",
        "open source AI tools",
        "no-cost AI services",
    ],
    "open source AI projects": [
        "github AI agents trending",
        "open source LLM projects",
        "AI agent repositories",
    ],
}


def _log_autonomous_action(action: str, details: Dict[str, Any]) -> None:
    """Log autonomous actions for user audit."""
    AUTONOMOUS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details,
    }
    
    with open(AUTONOMOUS_LOG_PATH, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def _search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search using DuckDuckGo (no API key needed)."""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        # DuckDuckGo HTML search
        url = "https://duckduckgo.com/html/"
        params = {
            "q": query,
            "kl": "us-en",
            "num": max_results,
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        results = []
        for result in soup.select(".result")[:max_results]:
            title = result.select_one(".result__title a")
            snippet = result.select_one(".result__snippet")
            
            if title and snippet:
                results.append({
                    "title": title.get_text().strip(),
                    "url": title.get("href", ""),
                    "snippet": snippet.get_text().strip(),
                })
        
        return results
    except Exception as e:
        _log_autonomous_action("search_error", {"query": query, "error": str(e)})
        return []


def _extract_content_from_url(url: str) -> Optional[str]:
    """Extract text content from a URL."""
    try:
        import requests
        from bs4 import BeautifulSoup
        import readability
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        doc = readability.Document(response.content)
        
        # Clean up the HTML
        soup = BeautifulSoup(doc.summary(), "html.parser")
        text = soup.get_text()
        
        # Limit size
        if len(text) > 5000:
            text = text[:5000] + "..."
        
        return text
    except Exception as e:
        _log_autonomous_action("extract_error", {"url": url, "error": str(e)})
        return None


def _process_research_results(topic: str, results: List[Dict[str, str]]) -> Dict[str, Any]:
    """Process research results using AI to extract insights."""
    if not results:
        return {"topic": topic, "insights": [], "actionable_items": []}
    
    # Format results for AI
    results_text = "\n\n".join([
        f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['snippet']}"
        for r in results[:3]  # Limit to top 3 for processing
    ])
    
    prompt = f"""Analyze these research results about {topic}:

{results_text}

Extract:
1. Key insights and trends
2. Actionable improvements for an AI assistant
3. New tools or techniques to adopt
4. Code patterns or architectures mentioned

Output as JSON with keys: insights, actionable_items, tools, patterns"""
    
    try:
        response = providers.ask_llm(prompt, max_output_tokens=1000)
        if response:
            # Try to parse as JSON
            try:
                processed = json.loads(response)
                processed["topic"] = topic
                processed["sources"] = [r["url"] for r in results]
                return processed
            except Exception as e:
                # Fallback if not JSON
                return {
                    "topic": topic,
                    "insights": [response],
                    "actionable_items": [],
                    "tools": [],
                    "patterns": [],
                    "sources": [r["url"] for r in results],
                }
    except Exception as e:
        _log_autonomous_action("processing_error", {"topic": topic, "error": str(e)})
    
    return {"topic": topic, "insights": [], "actionable_items": []}


def _generate_improvement_from_research(research: Dict[str, Any]) -> Optional[evolution.ImprovementProposal]:
    """Generate an improvement proposal from research insights."""
    if not research.get("actionable_items"):
        return None
    
    # Create improvement from first actionable item
    item = research["actionable_items"][0]
    
    prompt = f"""Based on this research insight, create a specific improvement for Jarvis:

Research topic: {research['topic']}
Insight: {item}

Create an improvement proposal with:
- category: skill/config/behavior/module
- title: Brief descriptive title
- description: What to implement and why
- code_snippet: Example implementation if applicable

Output as JSON matching ImprovementProposal format."""
    
    try:
        response = providers.ask_llm(prompt, max_output_tokens=800)
        if response:
            try:
                data = json.loads(response)
                return evolution.ImprovementProposal(
                    category=data.get("category", "skill"),
                    title=data.get("title", "Autonomous improvement"),
                    description=data.get("description", ""),
                    code_snippet=data.get("code_snippet", ""),
                    source="autonomous_research",
                )
            except Exception as e:
                # Create basic improvement
                return evolution.ImprovementProposal(
                    category="skill",
                    title=f"Research-based: {research['topic']}",
                    description=item,
                    source="autonomous_research",
                )
    except Exception as e:
        pass
    
    return None


def _save_research_to_context(research: Dict[str, Any]) -> None:
    """Save research findings to context documents."""
    ctx = context_manager.load_master_context()
    
    # Add to recent topics
    topic = research["topic"]
    if topic not in ctx.recent_topics:
        ctx.recent_topics = [topic] + ctx.recent_topics[:9]
    
    # Add learned patterns
    for pattern in research.get("patterns", []):
        if pattern not in ctx.learned_patterns:
            ctx.learned_patterns.append(pattern)
    
    context_manager.save_master_context(ctx)
    
    # Save detailed research
    research_path = ROOT / "data" / "research" / f"{topic.replace(' ', '_')}.json"
    research_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(research_path, "w") as f:
        json.dump(research, f, indent=2)


def research_topic(topic: str) -> Dict[str, Any]:
    """Research a specific topic."""
    _log_autonomous_action("research_started", {"topic": topic})
    
    # Get queries for this topic
    queries = SEARCH_QUERIES.get(topic, [topic])
    
    all_results = []
    for query in queries[:2]:  # Limit queries
        results = _search_duckduckgo(query)
        all_results.extend(results)
        time.sleep(1)  # Rate limit
    
    # Process results
    processed = _process_research_results(topic, all_results)
    
    # Save to context
    _save_research_to_context(processed)
    
    # Generate improvement if applicable
    improvement = _generate_improvement_from_research(processed)
    if improvement:
        _log_autonomous_action("improvement_generated", {
            "topic": topic,
            "title": improvement.title,
        })
        return {"research": processed, "improvement": improvement}
    
    _log_autonomous_action("research_completed", {"topic": topic})
    return {"research": processed}


def run_autonomous_learning_cycle(dry_run: bool = None) -> None:
    """Run one cycle of autonomous learning."""
    _log_autonomous_action("cycle_started", {})
    
    # Check if computer is idle
    current_state = state.read_state()
    if not current_state.get("passive_observation", False):
        _log_autonomous_action("cycle_skipped", {"reason": "not_idle"})
        return
    
    # Get dry_run preference (default to True for safety)
    if dry_run is None:
        ctx = context_manager.load_master_context()
        dry_run = ctx.preferences.get("autonomous_dry_run", True)
    
    # Pick a topic to research
    ctx = context_manager.load_master_context()
    
    # Rotate through topics
    last_topic = ctx.preferences.get("last_research_topic", "")
    topics = RESEARCH_TOPICS.copy()
    
    if last_topic in topics:
        topics.remove(last_topic)
        topics.insert(0, last_topic)  # Put last topic at end
    
    # Research next topic
    next_topic = topics[0]
    result = research_topic(next_topic)
    
    # Apply improvement if generated
    if "improvement" in result:
        improvement = result["improvement"]
        try:
            # Validate with guardian
            safe, reason = guardian.validate_code_for_safety(improvement.code_snippet or "")
            if not safe:
                _log_autonomous_action("improvement_rejected", {
                    "title": improvement.title,
                    "reason": reason,
                })
            else:
                # Apply improvement (or dry run)
                result = evolution.apply_improvement(improvement, dry_run=dry_run)
                status = result.get("status", "unknown")
                mode = "dry_run" if dry_run else status
                _log_autonomous_action(f"improvement_{mode}", {
                    "title": improvement.title,
                    "status": status,
                    "message": result.get("message", ""),
                })
        except Exception as e:
            _log_autonomous_action("improvement_error", {
                "title": improvement.title,
                "error": str(e),
            })
    
    # Update last research topic
    ctx.preferences["last_research_topic"] = next_topic
    context_manager.save_master_context(ctx)
    
    _log_autonomous_action("cycle_completed", {"topic": next_topic, "dry_run": dry_run})


def start_autonomous_learner() -> threading.Thread:
    """Start the enhanced autonomous learner with continuous research."""
    # Use the new autonomous controller
    controller = autonomous_controller.start_autonomous_controller()
    _log_autonomous_action("enhanced_learner_started", {})
    
    # Return a dummy thread for compatibility
    dummy_thread = threading.Thread(target=lambda: None, daemon=True)
    dummy_thread.start()
    return dummy_thread


def get_autonomous_summary() -> Dict[str, Any]:
    """Get summary of autonomous learning activities."""
    if not AUTONOMOUS_LOG_PATH.exists():
        return {"actions": [], "total": 0}
    
    actions = []
    with open(AUTONOMOUS_LOG_PATH, "r") as f:
        for line in f:
            try:
                actions.append(json.loads(line))
            except Exception as e:
                pass
    
    # Get last 24 hours
    now = time.time()
    day_ago = now - 86400
    recent = [a for a in actions if time.mktime(time.strptime(a["timestamp"][:19], "%Y-%m-%dT%H:%M:%S")) > day_ago]
    
    # Summarize
    summary = {
        "total": len(actions),
        "last_24h": len(recent),
        "last_action": actions[-1] if actions else None,
        "research_topics": list(set(a["details"].get("topic", "") for a in recent if "topic" in a["details"])),
        "improvements_applied": len([a for a in recent if a["action"] == "improvement_applied"]),
        "improvements_dry_run": len([a for a in recent if a["action"] == "improvement_dry_run"]),
    }
    
    return summary


def enable_autonomous_improvements(enable: bool = True) -> None:
    """Enable or disable autonomous improvement application."""
    ctx = context_manager.load_master_context()
    ctx.preferences["autonomous_dry_run"] = not enable
    context_manager.save_master_context(ctx)
    
    _log_autonomous_action("settings_changed", {
        "autonomous_improvements_enabled": enable,
        "dry_run_mode": not enable,
    })

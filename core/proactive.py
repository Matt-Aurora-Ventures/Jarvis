"""
Proactive monitoring module for LifeOS.
Watches user activity and offers solutions every 15 minutes.
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, passive, providers, memory, autonomous_learner

ROOT = Path(__file__).resolve().parents[1]
SUGGESTIONS_LOG = ROOT / "data" / "suggestions.jsonl"
RESEARCH_DIR = ROOT / "data" / "research"


class ProactiveMonitor:
    """Monitors activity and provides proactive suggestions."""
    
    def __init__(self, interval_minutes: int = 15):
        self.interval = interval_minutes * 60
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_suggestion_time = 0
        
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        
    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            
    def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._check_and_suggest()
            except Exception as e:
                pass
            self._stop_event.wait(self.interval)
            
    def _check_and_suggest(self) -> Optional[Dict[str, Any]]:
        """Analyze current state and generate proactive suggestion."""
        # Get recent activity
        activity = passive.summarize_activity(hours=0.5)  # Last 30 min
        screen_context = passive.get_current_screen_context()
        
        # Build context for suggestion
        prompt = f"""You are Jarvis, the user's AI assistant. Analyze their current activity and offer ONE helpful suggestion.

Current Activity (last 30 min):
{activity}

Current Screen:
{screen_context}

Based on what the user is doing, offer ONE specific, actionable suggestion that could:
- Save them time
- Make money
- Improve their workflow
- Point out an opportunity
- Help with their current task

Be conversational and specific. Don't be generic.
If nothing useful to suggest, respond with just: "NONE"

Your suggestion:"""

        try:
            response = providers.generate_text(prompt, max_output_tokens=200)
            if not response or "NONE" in response.upper():
                return None
                
            suggestion = {
                "timestamp": time.time(),
                "datetime": datetime.now().isoformat(),
                "activity_context": activity[:200],
                "suggestion": response.strip(),
                "acted_on": False,
            }
            
            # Log suggestion
            self._log_suggestion(suggestion)
            
            # Notify user (via notification)
            self._notify_user(suggestion["suggestion"])
            
            return suggestion
        except Exception as e:
            return None
            
    def _log_suggestion(self, suggestion: Dict[str, Any]) -> None:
        SUGGESTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(SUGGESTIONS_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(suggestion) + "\n")
        except Exception as e:
            pass
            
    def _notify_user(self, message: str) -> None:
        """Send system notification with suggestion."""
        try:
            from core.platform import send_notification
            send_notification("Jarvis Suggestion", message[:150])
        except Exception:
            pass


def research_topic(topic: str, depth: str = "quick") -> Dict[str, Any]:
    """
    Research a topic and create a document with findings.
    depth: quick (1 search), medium (3 searches), deep (5+ searches)
    """
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    
    results = {
        "topic": topic,
        "timestamp": datetime.now().isoformat(),
        "searches": [],
        "summary": "",
        "document_path": "",
    }
    
    # Determine search count based on depth
    search_counts = {"quick": 1, "medium": 3, "deep": 5}
    num_searches = search_counts.get(depth, 1)
    
    # Generate search queries
    query_prompt = f"""Generate {num_searches} specific search queries to research: "{topic}"
Output just the queries, one per line."""
    
    try:
        queries_response = providers.generate_text(query_prompt, max_output_tokens=200)
        queries = [q.strip() for q in queries_response.strip().split("\n") if q.strip()][:num_searches]
    except Exception as e:
        queries = [topic]
    
    # For each query, simulate research (in real implementation, would use web search)
    all_findings = []
    for query in queries:
        research_prompt = f"""You are a research assistant. Provide key findings about: "{query}"
Include:
- Key facts and statistics
- Recent developments
- Actionable insights
- Sources if known

Be concise but comprehensive."""
        
        try:
            findings = providers.generate_text(research_prompt, max_output_tokens=400)
            results["searches"].append({"query": query, "findings": findings})
            all_findings.append(findings)
        except Exception as e:
            continue
    
    # Generate summary
    if all_findings:
        summary_prompt = f"""Summarize these research findings about "{topic}" into a clear, actionable document:

{chr(10).join(all_findings)}

Create a well-structured summary with:
- Executive Summary (2-3 sentences)
- Key Findings
- Recommendations
- Next Steps"""
        
        try:
            results["summary"] = providers.generate_text(summary_prompt, max_output_tokens=600)
        except Exception as e:
            results["summary"] = "\n\n".join(all_findings)
    
    # Save as document
    safe_topic = "".join(c if c.isalnum() or c in " -_" else "_" for c in topic)[:50]
    doc_path = RESEARCH_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_{safe_topic}.md"
    
    doc_content = f"""# Research: {topic}

**Date:** {results['timestamp']}
**Depth:** {depth}

## Summary

{results['summary']}

## Search Queries Used

{chr(10).join(f"- {s['query']}" for s in results['searches'])}

## Detailed Findings

"""
    for search in results["searches"]:
        doc_content += f"### {search['query']}\n\n{search['findings']}\n\n"
    
    try:
        doc_path.write_text(doc_content, encoding="utf-8")
        results["document_path"] = str(doc_path)
    except Exception as e:
        pass
    
    return results


def create_document(title: str, content_request: str, doc_type: str = "markdown") -> Dict[str, Any]:
    """Create a document based on user request."""
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    
    prompt = f"""Create a {doc_type} document titled "{title}".

User's request: {content_request}

Create professional, well-structured content. Use proper formatting."""

    try:
        content = providers.generate_text(prompt, max_output_tokens=1000)
    except Exception as e:
        content = f"# {title}\n\n[Content generation failed]"
    
    # Determine extension
    extensions = {"markdown": ".md", "text": ".txt", "html": ".html"}
    ext = extensions.get(doc_type, ".md")
    
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:50]
    doc_path = RESEARCH_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_{safe_title}{ext}"
    
    try:
        doc_path.write_text(content, encoding="utf-8")
    except Exception as e:
        pass
    
    return {
        "title": title,
        "path": str(doc_path),
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }


def search_free_software(category: str = "general") -> Dict[str, Any]:
    """Search for latest free/open-source software in a category."""
    prompt = f"""List the top 5 FREE and open-source software tools for: {category}

For each tool include:
- Name and what it does
- Why it's useful
- GitHub or website link if known
- Any recent updates or features

Focus on actively maintained projects with good community support."""

    try:
        results = providers.generate_text(prompt, max_output_tokens=500)
    except Exception as e:
        results = "Search failed - try again later"
    
    return {
        "category": category,
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }


def get_recent_suggestions(count: int = 5) -> List[Dict[str, Any]]:
    """Get recent proactive suggestions."""
    if not SUGGESTIONS_LOG.exists():
        return []
    
    suggestions = []
    try:
        with open(SUGGESTIONS_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        suggestions.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        pass
    
    return suggestions[-count:]


# Global monitor instance
_monitor: Optional[ProactiveMonitor] = None


def start_monitoring(interval_minutes: int = 15) -> ProactiveMonitor:
    """Start the proactive monitoring system."""
    global _monitor
    if _monitor:
        _monitor.stop()
    _monitor = ProactiveMonitor(interval_minutes)
    _monitor.start()
    
    # Start autonomous learner in background
    autonomous_learner.start_autonomous_learner()
    
    return _monitor


def stop_monitoring() -> None:
    """Stop the proactive monitoring system."""
    global _monitor
    if _monitor:
        _monitor.stop()
        _monitor = None

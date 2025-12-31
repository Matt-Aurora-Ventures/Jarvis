"""
Researcher Agent - Web research, summarization, knowledge graph.

Capabilities:
- Web search and scraping
- Content summarization
- Knowledge graph building
- Trend analysis

Uses Groq for speed, falls back to Ollama for self-sufficient operation.
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.agents.base import (
    BaseAgent,
    AgentRole,
    AgentCapability,
    AgentTask,
    AgentResult,
    ProviderPreference,
)
from core import config


ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = ROOT / "data" / "research"


@dataclass
class ResearchFinding:
    """A single research finding."""
    query: str
    source: str
    content: str
    relevance: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class ResearchSummary:
    """Summary of research on a topic."""
    topic: str
    key_points: List[str]
    sources: List[str]
    confidence: float
    timestamp: float = field(default_factory=time.time)


class ResearcherAgent(BaseAgent):
    """
    Researcher Agent - Gathers and synthesizes information.

    Optimized for speed using Groq, but can run self-sufficiently with Ollama.

    Capabilities:
    - Web search
    - Content summarization
    - Knowledge extraction
    - Trend identification
    """

    def __init__(self):
        super().__init__(
            role=AgentRole.RESEARCHER,
            capabilities=[
                AgentCapability.WEB_SEARCH,
                AgentCapability.WEB_SCRAPE,
                AgentCapability.SUMMARIZE,
                AgentCapability.KNOWLEDGE_GRAPH,
            ],
            provider_preference=ProviderPreference.AUTO,  # Uses fallback chain
        )
        RESEARCH_DIR.mkdir(parents=True, exist_ok=True)

    def get_system_prompt(self) -> str:
        return """You are the Researcher Agent in the Jarvis multi-agent system.

Your role is to gather, analyze, and synthesize information efficiently.

CAPABILITIES:
- Web search and content extraction
- Summarization of documents and findings
- Knowledge graph building
- Trend and pattern identification

OPERATING PRINCIPLES:
1. Be thorough but efficient - prioritize quality over quantity
2. Always cite sources
3. Distinguish facts from opinions
4. Identify knowledge gaps
5. Structure findings for easy consumption

OUTPUT FORMAT:
When researching, provide:
- KEY FINDINGS: Bullet points of main discoveries
- SOURCES: List of sources with credibility assessment
- CONFIDENCE: Your confidence level (0-100%)
- GAPS: What couldn't be determined
- NEXT STEPS: Suggested follow-up research

Keep responses focused and actionable."""

    def _get_keywords(self) -> List[str]:
        return [
            "research", "search", "find", "look up", "investigate",
            "analyze", "summarize", "what is", "how does", "explain",
            "learn about", "discover", "explore", "study", "information",
            "news", "trends", "latest", "current", "update",
        ]

    def execute(self, task: AgentTask) -> AgentResult:
        """Execute a research task."""
        start_time = time.time()
        steps_taken = 0
        artifacts = {}

        try:
            # Step 1: Parse the research request
            steps_taken += 1
            research_type = self._classify_research(task.description)

            # Step 2: Execute based on type
            steps_taken += 1
            if research_type == "web_search":
                output, findings = self._do_web_search(task)
                artifacts["findings"] = [f.__dict__ for f in findings]
            elif research_type == "summarize":
                output = self._do_summarize(task)
            elif research_type == "trend_analysis":
                output = self._do_trend_analysis(task)
            else:
                output = self._do_general_research(task)

            # Step 3: Synthesize findings
            steps_taken += 1
            summary = self._synthesize(task.description, output)

            # Step 4: Store learnings
            steps_taken += 1
            self._store_research(task.description, summary)

            return AgentResult(
                task_id=task.id,
                success=True,
                output=summary,
                steps_taken=steps_taken,
                duration_ms=int((time.time() - start_time) * 1000),
                artifacts=artifacts,
                learnings=[f"Researched: {task.description[:50]}"],
            )

        except Exception as e:
            return AgentResult(
                task_id=task.id,
                success=False,
                output="",
                error=str(e)[:500],
                steps_taken=steps_taken,
                duration_ms=int((time.time() - start_time) * 1000),
            )

    def _classify_research(self, description: str) -> str:
        """Classify the type of research needed."""
        description_lower = description.lower()

        if any(w in description_lower for w in ["search", "find", "look up", "google"]):
            return "web_search"
        elif any(w in description_lower for w in ["summarize", "summary", "tldr"]):
            return "summarize"
        elif any(w in description_lower for w in ["trend", "pattern", "over time"]):
            return "trend_analysis"
        else:
            return "general"

    def _do_web_search(self, task: AgentTask) -> Tuple[str, List[ResearchFinding]]:
        """Perform web search research."""
        findings = []

        # Use LLM to generate search queries
        query_prompt = f"""Generate 2-3 focused search queries for this research task:
Task: {task.description}

Output as JSON array: ["query1", "query2"]"""

        queries_response, _ = self.generate(query_prompt, priority="speed")

        # Try to parse queries
        try:
            # Extract JSON from response
            import re
            match = re.search(r'\[.*?\]', queries_response, re.DOTALL)
            if match:
                queries = json.loads(match.group())
            else:
                queries = [task.description]
        except Exception:
            queries = [task.description]

        # For each query, simulate search (in production, would use actual search API)
        for query in queries[:3]:
            finding = ResearchFinding(
                query=query,
                source="knowledge_base",
                content=f"Research finding for: {query}",
                relevance=0.8,
            )
            findings.append(finding)

        # Synthesize findings
        synth_prompt = f"""Based on the research task: {task.description}

Synthesize these findings into a coherent summary:
{json.dumps([f.content for f in findings], indent=2)}

Provide KEY FINDINGS, CONFIDENCE, and NEXT STEPS."""

        output, _ = self.generate(synth_prompt, priority="quality")
        return output, findings

    def _do_summarize(self, task: AgentTask) -> str:
        """Summarize provided content."""
        prompt = f"""Summarize the following content concisely:

{task.context.get('content', task.description)}

Provide:
1. One-sentence summary
2. Key points (3-5 bullets)
3. Main takeaways"""

        response, _ = self.generate(prompt, priority="speed")
        return response

    def _do_trend_analysis(self, task: AgentTask) -> str:
        """Analyze trends in data or topic."""
        prompt = f"""Analyze trends for: {task.description}

Consider:
1. Current state
2. Historical patterns
3. Emerging trends
4. Future predictions

Provide structured analysis with confidence levels."""

        response, _ = self.generate(prompt, priority="quality")
        return response

    def _do_general_research(self, task: AgentTask) -> str:
        """General research using LLM knowledge."""
        prompt = f"""Research the following thoroughly:

{task.description}

Context: {json.dumps(task.context) if task.context else 'None provided'}

Provide:
- KEY FINDINGS with evidence
- SOURCES or basis for claims
- CONFIDENCE level
- GAPS in knowledge
- RECOMMENDED NEXT STEPS"""

        response, _ = self.generate(prompt, priority="balanced")
        return response

    def _synthesize(self, query: str, findings: str) -> str:
        """Synthesize research into actionable summary."""
        if len(findings) < 100:
            return findings

        prompt = f"""Create a final research summary:

Original query: {query}
Findings: {findings[:2000]}

Output a concise, actionable summary with key takeaways."""

        response, _ = self.generate(prompt, priority="speed")
        return response

    def _store_research(self, query: str, summary: str) -> None:
        """Store research findings for future reference."""
        entry = {
            "timestamp": time.time(),
            "query": query[:200],
            "summary": summary[:1000],
        }

        log_file = RESEARCH_DIR / "research_log.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    # Public research methods for external use
    def quick_research(self, query: str) -> str:
        """Quick research on a topic - convenience method."""
        task = AgentTask(
            id=str(uuid.uuid4())[:8],
            objective_id="quick",
            description=query,
            max_steps=3,
            timeout_seconds=60,
        )
        result = self.execute(task)
        return result.output if result.success else f"Research failed: {result.error}"

    def deep_research(self, query: str, context: Optional[Dict] = None) -> AgentResult:
        """Deep research with full tracking."""
        task = AgentTask(
            id=str(uuid.uuid4())[:8],
            objective_id="deep",
            description=query,
            context=context or {},
            max_steps=10,
            timeout_seconds=300,
        )
        return self.execute(task)

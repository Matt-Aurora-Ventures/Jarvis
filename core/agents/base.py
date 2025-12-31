"""
Base Agent class for the multi-agent system.

All specialized agents inherit from BaseAgent which provides:
- Consistent interface for the orchestrator
- LLM provider routing (Groq vs Claude)
- Execution tracking and metrics
- Tool access control
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import config, memory, safety, providers
from core.economics.costs import get_cost_tracker, Provider as CostProvider


class AgentRole(str, Enum):
    """Agent roles in the internal org."""
    RESEARCHER = "researcher"   # Web research, summarization
    OPERATOR = "operator"       # Task execution, automation
    TRADER = "trader"           # Crypto strategy, backtesting
    ARCHITECT = "architect"     # Self-improvement, quality gates


class AgentCapability(str, Enum):
    """Capabilities an agent can have."""
    WEB_SEARCH = "web_search"
    WEB_SCRAPE = "web_scrape"
    SUMMARIZE = "summarize"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    UI_AUTOMATION = "ui_automation"
    FILE_OPS = "file_ops"
    EMAIL = "email"
    CALENDAR = "calendar"
    CRYPTO_DATA = "crypto_data"
    BACKTEST = "backtest"
    PAPER_TRADE = "paper_trade"
    LIVE_TRADE = "live_trade"
    CODE_ANALYSIS = "code_analysis"
    CODE_GENERATION = "code_generation"
    QUALITY_GATES = "quality_gates"


class ProviderPreference(str, Enum):
    """Which LLM provider to prefer."""
    GROQ = "groq"           # Fast, cheap - for Researcher/Operator
    CLAUDE = "claude"       # Quality - for Trader/Architect (Anthropic)
    OPENAI = "openai"       # Quality - GPT-4/5 (OpenAI)
    OLLAMA = "ollama"       # Local, free - self-sufficient
    GEMINI = "gemini"       # Google - good balance
    AUTO = "auto"           # Smart routing based on task
    SELF_SUFFICIENT = "self_sufficient"  # Prioritize local, no external deps


# Map provider names to cost tracker providers
PROVIDER_TO_COST_PROVIDER = {
    "groq": CostProvider.GROQ,
    "claude": CostProvider.CLAUDE,
    "openai": CostProvider.OPENAI,
    "gemini": CostProvider.GEMINI,
    "ollama": CostProvider.OLLAMA,
}


# Provider fallback chains for different priorities
PROVIDER_CHAINS = {
    # Quality-first: Claude -> GPT -> Gemini -> Groq -> Ollama
    "quality": ["claude", "openai", "gemini", "groq", "ollama"],

    # Speed-first: Groq -> Ollama -> Gemini -> Claude
    "speed": ["groq", "ollama", "gemini", "claude", "openai"],

    # Cost-first: Ollama -> Groq -> Gemini -> Claude
    "cost": ["ollama", "groq", "gemini", "openai", "claude"],

    # Self-sufficient: Local only, then cloud fallback
    "self_sufficient": ["ollama", "groq", "gemini", "openai", "claude"],

    # Default balanced chain
    "balanced": ["groq", "gemini", "claude", "openai", "ollama"],
}


@dataclass
class AgentTask:
    """A task assigned to an agent."""
    id: str
    objective_id: str
    description: str
    context: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    expected_output: str = ""
    max_steps: int = 10
    timeout_seconds: int = 300


@dataclass
class AgentResult:
    """Result from an agent execution."""
    task_id: str
    success: bool
    output: Any
    steps_taken: int = 0
    duration_ms: int = 0
    tokens_used: int = 0
    cost_estimate: float = 0.0
    error: str = ""
    artifacts: Dict[str, Any] = field(default_factory=dict)
    learnings: List[str] = field(default_factory=list)


@dataclass
class AgentMetrics:
    """Metrics for an agent's performance."""
    role: AgentRole
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_duration_ms: float = 0.0
    success_rate: float = 0.0


ROOT = Path(__file__).resolve().parents[2]
AGENT_LOGS = ROOT / "data" / "agents"


class BaseAgent(ABC):
    """
    Base class for all specialized agents.

    Subclasses must implement:
    - execute(task) -> AgentResult
    - get_system_prompt() -> str
    """

    def __init__(
        self,
        role: AgentRole,
        capabilities: List[AgentCapability],
        provider_preference: ProviderPreference = ProviderPreference.AUTO,
    ):
        self.role = role
        self.capabilities = capabilities
        self.provider_preference = provider_preference
        self._metrics = AgentMetrics(role=role)
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        log_dir = AGENT_LOGS / self.role.value
        log_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def execute(self, task: AgentTask) -> AgentResult:
        """Execute a task and return the result."""
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        pass

    def can_handle(self, task_description: str) -> float:
        """
        Score how well this agent can handle a task (0-1).

        Used by the orchestrator to route tasks to the right agent.
        """
        # Default implementation - subclasses should override
        keywords = self._get_keywords()
        description_lower = task_description.lower()

        matches = sum(1 for kw in keywords if kw in description_lower)
        return min(1.0, matches / max(1, len(keywords) / 2))

    @abstractmethod
    def _get_keywords(self) -> List[str]:
        """Get keywords this agent responds to."""
        pass

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        priority: str = "balanced",  # quality, speed, cost, self_sufficient, balanced
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate a response using intelligent provider routing with fallback.

        The system tries providers in order based on priority:
        - quality: Claude -> GPT -> Gemini -> Groq -> Ollama
        - speed: Groq -> Ollama -> Gemini -> Claude
        - cost: Ollama -> Groq -> Gemini -> Claude
        - self_sufficient: Ollama first, cloud as fallback

        Returns: (response_text, metadata)
        """
        if system_prompt is None:
            system_prompt = self.get_system_prompt()

        full_prompt = f"{system_prompt}\n\n{prompt}"

        # Determine provider chain
        if self.provider_preference == ProviderPreference.AUTO:
            chain = PROVIDER_CHAINS.get(priority, PROVIDER_CHAINS["balanced"])
        elif self.provider_preference == ProviderPreference.SELF_SUFFICIENT:
            chain = PROVIDER_CHAINS["self_sufficient"]
        else:
            # Start with preferred, then fall back through chain
            preferred = self.provider_preference.value
            chain = [preferred] + [p for p in PROVIDER_CHAINS["balanced"] if p != preferred]

        # Try each provider in the chain
        last_error = ""
        used_provider = "none"

        for provider_name in chain:
            try:
                response = self._call_provider(
                    provider_name, full_prompt, temperature, max_tokens
                )
                if response and not response.startswith("Error:"):
                    used_provider = provider_name
                    break
                last_error = response
            except Exception as e:
                last_error = str(e)
                continue
        else:
            # All providers failed
            response = f"All providers failed. Last error: {last_error}"

        # Estimate tokens (rough approximation)
        input_tokens = len(full_prompt.split()) * 1.3
        output_tokens = len(response.split()) * 1.3

        # Log cost to economics tracker
        if used_provider != "none":
            try:
                cost_provider = PROVIDER_TO_COST_PROVIDER.get(used_provider, CostProvider.LOCAL)
                cost_tracker = get_cost_tracker()
                cost_tracker.log_api_call(
                    provider=cost_provider,
                    input_tokens=int(input_tokens),
                    output_tokens=int(output_tokens),
                    model=self._get_model_name(used_provider),
                    purpose=f"agent_{self.role.value}",
                    agent=self.role.value,
                )
            except Exception:
                pass  # Don't let cost tracking failure break execution

        # Extract metadata
        metadata = {
            "provider": used_provider,
            "preference": self.provider_preference.value,
            "priority": priority,
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "tokens": int(input_tokens + output_tokens),
            "fallback_used": used_provider != chain[0] if chain else False,
        }

        return response, metadata

    def _get_model_name(self, provider: str) -> str:
        """Get the model name for a provider."""
        model_names = {
            "groq": "llama-3.3-70b-versatile",
            "claude": "claude-3-5-sonnet",
            "openai": "gpt-4o",
            "gemini": "gemini-2.0-flash-exp",
            "ollama": "local",
        }
        return model_names.get(provider, "unknown")

    def _call_provider(
        self,
        provider: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call a specific provider by name."""
        provider_methods = {
            "groq": self._call_groq,
            "claude": self._call_claude,
            "openai": self._call_openai,
            "gemini": self._call_gemini,
            "ollama": self._call_ollama,
        }

        method = provider_methods.get(provider)
        if method:
            return method(prompt, temperature, max_tokens)
        else:
            return providers.generate_text(prompt)

    def _call_groq(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """Call Groq API - fast and cheap."""
        try:
            from core import secrets
            import requests

            api_key = secrets.get_groq_key() if hasattr(secrets, 'get_groq_key') else None
            if not api_key:
                return "Error: No Groq API key"

            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=30,
            )

            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            return f"Error: Groq returned {response.status_code}"

        except Exception as e:
            return f"Error: {str(e)}"

    def _call_claude(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """Call Claude API - quality transformer (optional booster)."""
        try:
            from core import secrets
            import requests

            api_key = secrets.get_anthropic_key() if hasattr(secrets, 'get_anthropic_key') else None
            if not api_key:
                return "Error: No Anthropic API key"

            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",  # Latest Sonnet
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("content", [{}])[0].get("text", "")
            return f"Error: Claude returned {response.status_code}"

        except Exception as e:
            return f"Error: {str(e)}"

    def _call_openai(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """Call OpenAI API - GPT-4/5 transformer (optional booster)."""
        try:
            from core import secrets
            import requests

            api_key = secrets.get_openai_key() if hasattr(secrets, 'get_openai_key') else None
            if not api_key:
                return "Error: No OpenAI API key"

            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o",  # Latest GPT-4, upgrade to 5 when available
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=60,
            )

            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            return f"Error: OpenAI returned {response.status_code}"

        except Exception as e:
            return f"Error: {str(e)}"

    def _call_gemini(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """Call Gemini API - Google's model."""
        try:
            # Use existing Gemini infrastructure from providers
            from core import secrets
            key = secrets.get_gemini_key() if hasattr(secrets, 'get_gemini_key') else None
            if not key:
                return "Error: No Gemini API key"

            import google.generativeai as genai
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-2.0-flash-exp")
            response = model.generate_content(prompt)
            return response.text

        except Exception as e:
            return f"Error: {str(e)}"

    def _call_ollama(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """
        Call local Ollama - BASELINE self-sufficient provider.

        This is the core that keeps Jarvis running even without cloud APIs.
        Uses whatever local model is available.
        """
        try:
            import requests

            # Check Ollama health first
            try:
                health = requests.get("http://localhost:11434/api/tags", timeout=2)
                if health.status_code != 200:
                    return "Error: Ollama not running"
                models = health.json().get("models", [])
                if not models:
                    return "Error: No Ollama models installed"
                # Use first available model
                model_name = models[0].get("name", "llama3.2")
            except Exception:
                model_name = "llama3.2"  # Default

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
                timeout=120,  # Local models can be slow
            )

            if response.status_code == 200:
                return response.json().get("response", "")
            return f"Error: Ollama returned {response.status_code}"

        except Exception as e:
            return f"Error: {str(e)}"

    def check_provider_availability(self) -> Dict[str, bool]:
        """Check which providers are available."""
        from core import secrets

        availability = {
            "ollama": False,
            "groq": False,
            "gemini": False,
            "claude": False,
            "openai": False,
        }

        # Check Ollama (local)
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            availability["ollama"] = r.status_code == 200
        except Exception:
            pass

        # Check API keys
        if hasattr(secrets, 'get_groq_key') and secrets.get_groq_key():
            availability["groq"] = True
        if hasattr(secrets, 'get_gemini_key') and secrets.get_gemini_key():
            availability["gemini"] = True
        if hasattr(secrets, 'get_anthropic_key') and secrets.get_anthropic_key():
            availability["claude"] = True
        if hasattr(secrets, 'get_openai_key') and secrets.get_openai_key():
            availability["openai"] = True

        return availability

    def get_best_available_chain(self, priority: str = "balanced") -> List[str]:
        """Get provider chain filtered to only available providers."""
        available = self.check_provider_availability()
        chain = PROVIDER_CHAINS.get(priority, PROVIDER_CHAINS["balanced"])
        return [p for p in chain if available.get(p, False)]

    def _log_execution(self, task: AgentTask, result: AgentResult) -> None:
        """Log task execution for analysis."""
        log_file = AGENT_LOGS / self.role.value / "executions.jsonl"

        entry = {
            "timestamp": time.time(),
            "task_id": task.id,
            "objective_id": task.objective_id,
            "description": task.description[:200],
            "success": result.success,
            "duration_ms": result.duration_ms,
            "steps": result.steps_taken,
            "error": result.error[:200] if result.error else "",
        }

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _update_metrics(self, result: AgentResult) -> None:
        """Update agent metrics after execution."""
        self._metrics.total_tasks += 1

        if result.success:
            self._metrics.successful_tasks += 1
        else:
            self._metrics.failed_tasks += 1

        self._metrics.total_tokens += result.tokens_used
        self._metrics.total_cost += result.cost_estimate

        # Update averages
        total = self._metrics.total_tasks
        prev_avg = self._metrics.avg_duration_ms
        self._metrics.avg_duration_ms = (prev_avg * (total - 1) + result.duration_ms) / total
        self._metrics.success_rate = self._metrics.successful_tasks / total

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics for this agent."""
        return asdict(self._metrics)

    def store_learning(self, learning: str) -> None:
        """Store a learning in memory."""
        ctx = safety.SafetyContext(apply=True, dry_run=False)
        memory.append_entry(
            text=f"[{self.role.value.upper()}] {learning}",
            source=f"agent_{self.role.value}",
            context=ctx,
        )

"""
Kaizen Self-Improvement Loop for ClawdBots.

Four autonomous improvement loops:
1. Correction Loop - Real-time memory updates on errors/successes
2. Strategy Loop - Weekly synthesis of learnings (Matt runs Sunday 08:00)
3. Capability Loop - Skill acquisition tracking
4. Cohesion Loop - Peer hardening via shared observations
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("CLAWDBOT_DATA_DIR", "/root/clawdbots/data"))
KAIZEN_FILE = DATA_DIR / "kaizen_log.json"
SKILLS_FILE = DATA_DIR / "skills_registry.json"


class CorrectionLoop:
    """Real-time learning from errors and successes."""

    def __init__(self, supermemory=None):
        self.supermemory = supermemory

    def on_error(self, bot_name: str, action: str, error: str, context: str = ""):
        """Record an error and store lesson in SuperMemory."""
        entry = {
            "type": "error",
            "bot": bot_name,
            "action": action,
            "error": error,
            "context": context,
            "ts": datetime.utcnow().isoformat(),
        }
        self._append_log(entry)

        if self.supermemory:
            self.supermemory.remember(
                key=f"error:{bot_name}:{action}",
                value=f"Error in {action}: {error}. Context: {context}",
                source=bot_name,
                tags=["ops_logs", "technical_stack"],
            )
        logger.info(f"Correction recorded: {bot_name}/{action}")

    def on_success(self, bot_name: str, action: str, outcome: str = ""):
        """Record a success for pattern reinforcement."""
        entry = {
            "type": "success",
            "bot": bot_name,
            "action": action,
            "outcome": outcome,
            "ts": datetime.utcnow().isoformat(),
        }
        self._append_log(entry)

    def get_error_patterns(self, bot_name: Optional[str] = None, days: int = 7) -> Dict[str, int]:
        """Find recurring error patterns."""
        entries = self._read_log()
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        counts: Dict[str, int] = {}
        for e in entries:
            if e["type"] != "error":
                continue
            if e.get("ts", "") < cutoff:
                continue
            if bot_name and e.get("bot") != bot_name:
                continue
            key = f"{e.get('bot')}:{e.get('action')}"
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def _append_log(self, entry: dict):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        entries = self._read_log()
        entries.append(entry)
        # Keep last 1000 entries
        if len(entries) > 1000:
            entries = entries[-1000:]
        KAIZEN_FILE.write_text(json.dumps(entries, indent=2))

    def _read_log(self) -> list:
        if KAIZEN_FILE.exists():
            try:
                return json.loads(KAIZEN_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return []


class StrategyLoop:
    """Weekly synthesis of learnings into actionable strategies."""

    def __init__(self, supermemory=None):
        self.supermemory = supermemory
        self.correction = CorrectionLoop(supermemory)

    def generate_weekly_synthesis(self) -> str:
        """Generate weekly strategy report from kaizen data."""
        sections = []
        now = datetime.utcnow()
        sections.append(f"WEEKLY KAIZEN SYNTHESIS - {now.strftime('%Y-%m-%d')}\n")

        # Error patterns
        patterns = self.correction.get_error_patterns(days=7)
        sections.append("TOP ERROR PATTERNS (7d):")
        if patterns:
            for action, count in list(patterns.items())[:5]:
                sections.append(f"  [{count}x] {action}")
        else:
            sections.append("  No errors recorded")

        # Success rate
        entries = self.correction._read_log()
        cutoff = (now - timedelta(days=7)).isoformat()
        week_entries = [e for e in entries if e.get("ts", "") >= cutoff]
        errors = sum(1 for e in week_entries if e["type"] == "error")
        successes = sum(1 for e in week_entries if e["type"] == "success")
        total = errors + successes
        if total > 0:
            rate = (successes / total) * 100
            sections.append(f"\nSUCCESS RATE: {rate:.0f}% ({successes}/{total})")
        else:
            sections.append("\nNo actions recorded this week")

        # Skills status
        skills = self._load_skills()
        sections.append(f"\nSKILLS TRACKED: {len(skills)}")
        recent = [s for s in skills if s.get("acquired", "") >= cutoff]
        if recent:
            sections.append("  New this week:")
            for s in recent:
                sections.append(f"    + {s['name']}")

        # Recommendations
        sections.append("\nRECOMMENDATIONS:")
        if patterns:
            top_error = list(patterns.keys())[0]
            sections.append(f"  - Investigate recurring: {top_error}")
        if total > 0 and rate < 80:
            sections.append("  - Success rate below 80% - review error handling")
        sections.append("  - Review pending handoffs")

        return "\n".join(sections)

    def _load_skills(self) -> list:
        if SKILLS_FILE.exists():
            try:
                return json.loads(SKILLS_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return []


class CapabilityLoop:
    """Track and acquire new skills/capabilities."""

    def register_skill(self, name: str, bot_name: str, description: str = ""):
        """Register a new capability acquired by a bot."""
        skills = self._load_skills()
        # Check for duplicate
        for s in skills:
            if s["name"] == name and s["bot"] == bot_name:
                s["last_used"] = datetime.utcnow().isoformat()
                self._save_skills(skills)
                return
        skills.append({
            "name": name,
            "bot": bot_name,
            "description": description,
            "acquired": datetime.utcnow().isoformat(),
            "last_used": datetime.utcnow().isoformat(),
            "use_count": 0,
        })
        self._save_skills(skills)
        logger.info(f"Skill registered: {name} for {bot_name}")

    def record_skill_use(self, name: str, bot_name: str):
        """Record usage of a skill."""
        skills = self._load_skills()
        for s in skills:
            if s["name"] == name and s["bot"] == bot_name:
                s["use_count"] = s.get("use_count", 0) + 1
                s["last_used"] = datetime.utcnow().isoformat()
                break
        self._save_skills(skills)

    def get_skills(self, bot_name: Optional[str] = None) -> List[dict]:
        """Get all registered skills, optionally filtered by bot."""
        skills = self._load_skills()
        if bot_name:
            return [s for s in skills if s["bot"] == bot_name]
        return skills

    def _load_skills(self) -> list:
        if SKILLS_FILE.exists():
            try:
                return json.loads(SKILLS_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def _save_skills(self, skills: list):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SKILLS_FILE.write_text(json.dumps(skills, indent=2))


class CohesionLoop:
    """Cross-bot observation sharing for peer hardening."""

    def __init__(self, supermemory=None):
        self.supermemory = supermemory

    def share_observation(self, from_bot: str, observation: str, tags: Optional[List[str]] = None):
        """Share an observation with all bots via SuperMemory."""
        if not self.supermemory:
            logger.warning("No SuperMemory - observation not shared")
            return
        key = f"obs:{from_bot}:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        mem_tags = tags or ["ops_logs"]
        self.supermemory.remember(
            key=key,
            value=observation,
            source=from_bot,
            tags=mem_tags,
        )
        logger.info(f"Observation shared by {from_bot}: {observation[:60]}")

    def get_peer_observations(self, bot_name: str, hours: int = 24) -> List[dict]:
        """Get observations from other bots."""
        if not self.supermemory:
            return []
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        results = self.supermemory.recall(query="obs:", source=bot_name, limit=20)
        # Filter to recent and from other bots
        return [r for r in results if r.get("ts", "") >= cutoff and r.get("source") != bot_name]


class Kaizen:
    """Unified Kaizen engine combining all four loops."""

    def __init__(self, supermemory=None):
        self.correction = CorrectionLoop(supermemory)
        self.strategy = StrategyLoop(supermemory)
        self.capability = CapabilityLoop()
        self.cohesion = CohesionLoop(supermemory)

    def on_error(self, bot_name: str, action: str, error: str, context: str = ""):
        self.correction.on_error(bot_name, action, error, context)

    def on_success(self, bot_name: str, action: str, outcome: str = ""):
        self.correction.on_success(bot_name, action, outcome)

    def weekly_report(self) -> str:
        return self.strategy.generate_weekly_synthesis()

    def register_skill(self, name: str, bot_name: str, description: str = ""):
        self.capability.register_skill(name, bot_name, description)

    def share(self, from_bot: str, observation: str, tags: Optional[List[str]] = None):
        self.cohesion.share_observation(from_bot, observation, tags)


# ---------------------------------------------------------------------------
# KaizenEngine: Per-bot self-improvement loop (spec v2)
# ---------------------------------------------------------------------------

@dataclass
class KaizenMetric:
    """A single performance metric data point."""
    name: str
    value: float
    timestamp: str
    bot: str
    context: str = ""


@dataclass
class KaizenInsight:
    """An improvement insight generated from analysis."""
    category: str  # "error_pattern", "performance", "user_feedback", "resource_usage"
    finding: str
    recommendation: str
    priority: str  # "low", "medium", "high"
    auto_applicable: bool = False
    applied: bool = False


class KaizenEngine:
    """
    Per-bot self-improvement engine.

    Collects metrics, analyzes patterns, generates insights, and applies
    improvements autonomously. Data stored in JSON files per bot.

    Cycle (weekly):
    1. Collect metrics (response quality, error rate, task completion)
    2. Analyze patterns (what's working, what's failing)
    3. Generate insights (concrete improvements)
    4. Apply improvements (update preferences, flag for human review)
    5. Log the cycle (track improvement over time)
    """

    _PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

    def __init__(self, bot_name: str, data_dir: str = "/root/clawdbots"):
        self.bot_name = bot_name
        self.data_dir = Path(data_dir)
        self.metrics_file = self.data_dir / f"kaizen_{bot_name}_metrics.json"
        self.insights_file = self.data_dir / f"kaizen_{bot_name}_insights.json"
        self.cycle_log = self.data_dir / f"kaizen_{bot_name}_cycles.json"
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # File helpers (thread-safe)
    # ------------------------------------------------------------------

    def _read_json(self, path: Path) -> list:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def _write_json(self, path: Path, data: list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _append_json(self, path: Path, entry: dict) -> None:
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            entries = self._read_json(path)
            entries.append(entry)
            path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Metric collection
    # ------------------------------------------------------------------

    def record_metric(self, name: str, value: float, context: str = "") -> None:
        """Record a performance metric."""
        entry = {
            "name": name,
            "value": value,
            "timestamp": self._now_iso(),
            "bot": self.bot_name,
            "context": context,
        }
        self._append_json(self.metrics_file, entry)

    def record_error(self, error_type: str, details: str = "") -> None:
        """Shorthand for recording error metrics."""
        ctx = f"{error_type}: {details}" if details else error_type
        self.record_metric("error", 1.0, context=ctx)

    def record_response_quality(self, quality_score: float, message_type: str = "") -> None:
        """Record user satisfaction / response quality."""
        ctx = f"type={message_type}" if message_type else ""
        self.record_metric("response_quality", quality_score, context=ctx)

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def _metrics_in_period(self, days: int = 7) -> List[dict]:
        """Return metrics within the given period."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        metrics = self._read_json(self.metrics_file)
        return [m for m in metrics if m.get("timestamp", "") >= cutoff]

    def analyze_period(self, days: int = 7) -> Dict:
        """Analyze metrics over a period. Returns pattern analysis."""
        metrics = self._metrics_in_period(days)

        error_counts: Dict[str, int] = {}
        quality_values: List[float] = []

        for m in metrics:
            if m["name"] == "error":
                key = m.get("context", "unknown")
                error_counts[key] = error_counts.get(key, 0) + 1
            elif m["name"] == "response_quality":
                quality_values.append(m["value"])

        quality_avg = (sum(quality_values) / len(quality_values)) if quality_values else 0.0

        return {
            "total_metrics": len(metrics),
            "error_counts": dict(sorted(error_counts.items(), key=lambda x: -x[1])),
            "error_total": sum(error_counts.values()),
            "quality_avg": quality_avg,
            "quality_samples": len(quality_values),
            "period_days": days,
            "bot": self.bot_name,
        }

    def detect_error_patterns(self, days: int = 7) -> List[dict]:
        """Find recurring error patterns."""
        metrics = self._metrics_in_period(days)
        counts: Dict[str, int] = {}
        for m in metrics:
            if m["name"] == "error":
                key = m.get("context", "unknown")
                counts[key] = counts.get(key, 0) + 1
        # Only return patterns with 2+ occurrences, sorted by frequency
        patterns = [
            {"error_type": k, "count": v}
            for k, v in sorted(counts.items(), key=lambda x: -x[1])
            if v >= 2
        ]
        return patterns

    def detect_performance_trends(self, days: int = 7) -> List[dict]:
        """Detect improvement or degradation trends in response quality."""
        metrics = self._metrics_in_period(days)
        quality = [m for m in metrics if m["name"] == "response_quality"]
        if len(quality) < 3:
            return []

        # Sort by timestamp
        quality.sort(key=lambda m: m["timestamp"])

        # Split into first half / second half
        mid = len(quality) // 2
        first_avg = sum(m["value"] for m in quality[:mid]) / mid
        second_avg = sum(m["value"] for m in quality[mid:]) / (len(quality) - mid)

        diff = second_avg - first_avg
        trends = []
        if abs(diff) > 0.02:  # threshold for significance
            direction = "improving" if diff > 0 else "declining"
            trends.append({
                "metric": "response_quality",
                "direction": direction,
                "first_half_avg": round(first_avg, 3),
                "second_half_avg": round(second_avg, 3),
                "change": round(diff, 3),
            })
        return trends

    # ------------------------------------------------------------------
    # Insight generation
    # ------------------------------------------------------------------

    def generate_insights(self, analysis: dict = None) -> List[KaizenInsight]:
        """Generate improvement insights from analysis."""
        if analysis is None:
            analysis = self.analyze_period()

        insights: List[KaizenInsight] = []

        # Insight from error patterns
        for err_type, count in analysis.get("error_counts", {}).items():
            if count >= 3:
                insights.append(KaizenInsight(
                    category="error_pattern",
                    finding=f"Recurring error: {err_type} ({count}x in period)",
                    recommendation=f"Investigate root cause of '{err_type}' and add retry/fallback",
                    priority="high" if count >= 5 else "medium",
                    auto_applicable=False,
                ))
            elif count >= 2:
                insights.append(KaizenInsight(
                    category="error_pattern",
                    finding=f"Repeated error: {err_type} ({count}x)",
                    recommendation=f"Monitor '{err_type}' for escalation",
                    priority="low",
                    auto_applicable=True,
                ))

        # Insight from quality
        if analysis.get("quality_samples", 0) >= 3:
            avg = analysis["quality_avg"]
            if avg < 0.5:
                insights.append(KaizenInsight(
                    category="performance",
                    finding=f"Low response quality average: {avg:.2f}",
                    recommendation="Review response generation pipeline, consider prompt tuning",
                    priority="high",
                ))
            elif avg < 0.7:
                insights.append(KaizenInsight(
                    category="performance",
                    finding=f"Below-target response quality: {avg:.2f}",
                    recommendation="Analyze low-scoring responses for common issues",
                    priority="medium",
                ))

        # Insight from trends
        trends = self.detect_performance_trends()
        for t in trends:
            if t["direction"] == "declining":
                insights.append(KaizenInsight(
                    category="performance",
                    finding=f"{t['metric']} declining: {t['first_half_avg']:.2f} -> {t['second_half_avg']:.2f}",
                    recommendation="Investigate recent changes causing quality regression",
                    priority="high",
                ))

        return insights

    def prioritize_insights(self, insights: List[KaizenInsight]) -> List[KaizenInsight]:
        """Sort insights by priority (high first)."""
        return sorted(insights, key=lambda i: self._PRIORITY_ORDER.get(i.priority, 9))

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    def apply_auto_insights(self, insights: List[KaizenInsight]) -> List[KaizenInsight]:
        """Apply insights that don't need human review. Returns applied list."""
        applied = []
        for insight in insights:
            if insight.auto_applicable and not insight.applied:
                insight.applied = True
                applied.append(insight)
                logger.info(f"[Kaizen:{self.bot_name}] Auto-applied: {insight.finding}")
        # Persist applied insights
        if applied:
            stored = self._read_json(self.insights_file)
            for a in applied:
                stored.append({
                    "category": a.category,
                    "finding": a.finding,
                    "recommendation": a.recommendation,
                    "priority": a.priority,
                    "applied": True,
                    "timestamp": self._now_iso(),
                })
            self._write_json(self.insights_file, stored)
        return applied

    def format_review_report(self, insights: List[KaizenInsight]) -> str:
        """Format insights needing human review as a report."""
        if not insights:
            return f"Kaizen Report ({self.bot_name}): No insights requiring review."

        lines = [
            f"KAIZEN REPORT - {self.bot_name}",
            f"Generated: {self._now_iso()}",
            f"Insights requiring review: {len(insights)}",
            "",
        ]
        for i, insight in enumerate(insights, 1):
            lines.append(f"{i}. [{insight.priority.upper()}] {insight.category}")
            lines.append(f"   Finding: {insight.finding}")
            lines.append(f"   Action: {insight.recommendation}")
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Full cycle
    # ------------------------------------------------------------------

    def run_cycle(self) -> str:
        """Run a full Kaizen cycle. Returns summary report."""
        analysis = self.analyze_period()
        insights = self.generate_insights(analysis)
        insights = self.prioritize_insights(insights)
        applied = self.apply_auto_insights(insights)
        needs_review = [i for i in insights if not i.applied]
        report = self.format_review_report(needs_review)
        self._log_cycle(analysis, insights)
        return report

    def _log_cycle(self, analysis: dict, insights: List[KaizenInsight]) -> None:
        """Log the cycle for historical tracking."""
        entry = {
            "timestamp": self._now_iso(),
            "bot": self.bot_name,
            "analysis_summary": {
                "total_metrics": analysis.get("total_metrics", 0),
                "error_total": analysis.get("error_total", 0),
                "quality_avg": analysis.get("quality_avg", 0),
            },
            "insights_count": len(insights),
            "auto_applied": sum(1 for i in insights if i.applied),
            "needs_review": sum(1 for i in insights if not i.applied),
        }
        self._append_json(self.cycle_log, entry)

    def get_improvement_history(self, cycles: int = 10) -> List[dict]:
        """Get history of Kaizen cycles to show improvement over time."""
        all_cycles = self._read_json(self.cycle_log)
        return all_cycles[-cycles:] if all_cycles else []

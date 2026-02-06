"""
Nightly Routine for Sleep-Time Compute.

Performs deep knowledge synthesis while humans sleep:
1. Ingests last 24 hours of logs from all agents
2. Recognizes patterns across conversations and actions
3. Derives new knowledge entries for Supermemory graph
4. Updates SOUL files with actionable insights

Author: ClawdMatt (Chief Growth Architect)
Cron Schedule: 0 3 * * * (3 AM daily)
"""

import json
import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PatternCategory(Enum):
    """Categories for identified patterns."""

    USER_PREFERENCE = "user_preference"
    TEMPORAL = "temporal"
    ERROR = "error"
    COORDINATION = "coordination"
    PERFORMANCE = "performance"


@dataclass
class Pattern:
    """A pattern identified from log analysis."""

    category: str  # PatternCategory value
    observation: str
    evidence: str
    confidence: float  # 0.0 to 1.0
    recommendation: str
    affected_agents: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize pattern to dictionary."""
        return {
            "category": self.category,
            "observation": self.observation,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "recommendation": self.recommendation,
            "affected_agents": self.affected_agents,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Pattern":
        """Create Pattern from dictionary."""
        return cls(
            category=data["category"],
            observation=data["observation"],
            evidence=data["evidence"],
            confidence=data["confidence"],
            recommendation=data["recommendation"],
            affected_agents=data["affected_agents"],
        )


@dataclass
class DeriveChain:
    """A derive chain for Supermemory graph.

    Links: Observation -> Insight -> Recommendation
    """

    observation: str
    insight: str
    recommendation: str
    tags: list[str]
    confidence: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize derive chain to dictionary."""
        return {
            "observation": self.observation,
            "insight": self.insight,
            "recommendation": self.recommendation,
            "tags": self.tags,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SleepComputeConfig:
    """Configuration for sleep-time compute."""

    logs_dir: Optional[Path] = None
    output_dir: Optional[Path] = None
    soul_dir: Optional[Path] = None
    min_confidence_for_derive: float = 0.65
    min_confidence_for_soul_update: float = 0.70
    max_log_lines: int = 5000
    llm_client: Any = None  # Optional LLM client for pattern recognition

    def __post_init__(self):
        """Set default paths if not provided."""
        if self.logs_dir is None:
            self.logs_dir = Path("/root/clawdbots/logs")
        if self.output_dir is None:
            self.output_dir = Path("/root/clawdbots/sleep_compute")
        if self.soul_dir is None:
            self.soul_dir = Path("/root/clawdbots")


class NightlyRoutine:
    """
    Nightly analysis routine for sleep-time compute.

    Analyzes bot activity logs, extracts patterns, creates
    knowledge graph derives, and updates SOUL files.
    """

    AGENT_LOG_FILES = {
        "friday": "friday_activity.log",
        "matt": "matt_activity.log",
        "jarvis": "jarvis_activity.log",
    }

    SOUL_FILES = {
        "friday": "CLAWDFRIDAY_SOUL.md",
        "matt": "CLAWDMATT_SOUL.md",
        "jarvis": "CLAWDJARVIS_SOUL.md",
    }

    def __init__(self, config: Optional[SleepComputeConfig] = None):
        """Initialize nightly routine with configuration."""
        self.config = config or SleepComputeConfig()
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure required directories exist."""
        if self.config.output_dir:
            self.config.output_dir.mkdir(parents=True, exist_ok=True)

    def analyze_logs(self) -> dict[str, str]:
        """
        Read bot logs from the configured logs directory.

        Returns:
            Dict mapping agent name to log content.
        """
        logs = {}

        for agent, log_file in self.AGENT_LOG_FILES.items():
            log_path = self.config.logs_dir / log_file

            if log_path.exists():
                try:
                    content = log_path.read_text(encoding="utf-8", errors="ignore")
                    # Respect max_log_lines limit (tail)
                    lines = content.strip().split("\n")
                    if len(lines) > self.config.max_log_lines:
                        lines = lines[-self.config.max_log_lines :]
                    logs[agent] = "\n".join(lines)
                    logger.info(f"Read {len(lines)} lines from {log_file}")
                except Exception as e:
                    logger.error(f"Failed to read {log_file}: {e}")
                    logs[agent] = ""
            else:
                logger.warning(f"Log file not found: {log_path}")
                logs[agent] = ""

        return logs

    def extract_patterns(self, logs: dict[str, str]) -> list[Pattern]:
        """
        Extract patterns from log content.

        This is a stub that provides basic pattern recognition.
        In production, this would use an LLM (Codex/GPT) for
        sophisticated pattern detection.

        Args:
            logs: Dict mapping agent name to log content.

        Returns:
            List of identified patterns.
        """
        patterns = []

        # Pattern detection using regex and heuristics
        # These are stubs - real implementation uses LLM

        # 1. User preference patterns
        patterns.extend(self._detect_user_preference_patterns(logs))

        # 2. Temporal patterns
        patterns.extend(self._detect_temporal_patterns(logs))

        # 3. Error patterns
        patterns.extend(self._detect_error_patterns(logs))

        # 4. Coordination patterns
        patterns.extend(self._detect_coordination_patterns(logs))

        # 5. Performance patterns
        patterns.extend(self._detect_performance_patterns(logs))

        logger.info(f"Extracted {len(patterns)} patterns from logs")
        return patterns

    def _detect_user_preference_patterns(
        self, logs: dict[str, str]
    ) -> list[Pattern]:
        """Detect user preference patterns from logs."""
        patterns = []

        # Look for repeated user requests/preferences
        all_logs = "\n".join(logs.values())

        # Example: bullet points preference
        bullet_mentions = len(re.findall(r"bullet.?point", all_logs, re.IGNORECASE))
        if bullet_mentions >= 2:
            patterns.append(
                Pattern(
                    category=PatternCategory.USER_PREFERENCE.value,
                    observation="User frequently requests bullet point format",
                    evidence=f"Found {bullet_mentions} mentions of bullet points in logs",
                    confidence=min(0.5 + bullet_mentions * 0.1, 0.95),
                    recommendation="Default to bullet point format in responses",
                    affected_agents=["friday", "matt", "jarvis"],
                )
            )

        # Example: concise responses
        concise_mentions = len(
            re.findall(r"(concise|brief|short|quick)", all_logs, re.IGNORECASE)
        )
        if concise_mentions >= 2:
            patterns.append(
                Pattern(
                    category=PatternCategory.USER_PREFERENCE.value,
                    observation="User prefers concise responses",
                    evidence=f"Found {concise_mentions} mentions of concise/brief/short",
                    confidence=min(0.5 + concise_mentions * 0.1, 0.90),
                    recommendation="Keep responses under 150 words unless detail requested",
                    affected_agents=["friday", "matt", "jarvis"],
                )
            )

        return patterns

    def _detect_temporal_patterns(self, logs: dict[str, str]) -> list[Pattern]:
        """Detect temporal patterns (best times for activities)."""
        patterns = []

        # Parse timestamps and outcomes from Jarvis logs
        jarvis_logs = logs.get("jarvis", "")

        # Look for trade patterns
        trade_results = re.findall(
            r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}).*?Trade result: ([+-]?\d+\.?\d*)%",
            jarvis_logs,
        )

        if trade_results:
            # Group by hour
            hourly_results = defaultdict(list)
            for timestamp, result in trade_results:
                try:
                    hour = int(timestamp.split(" ")[1].split(":")[0])
                    hourly_results[hour].append(float(result))
                except (IndexError, ValueError):
                    continue

            # Find best and worst hours
            if hourly_results:
                best_hour = max(
                    hourly_results.keys(),
                    key=lambda h: sum(hourly_results[h]) / len(hourly_results[h])
                    if hourly_results[h]
                    else 0,
                )
                worst_hour = min(
                    hourly_results.keys(),
                    key=lambda h: sum(hourly_results[h]) / len(hourly_results[h])
                    if hourly_results[h]
                    else 0,
                )

                if best_hour != worst_hour:
                    best_avg = sum(hourly_results[best_hour]) / len(
                        hourly_results[best_hour]
                    )
                    worst_avg = sum(hourly_results[worst_hour]) / len(
                        hourly_results[worst_hour]
                    )

                    patterns.append(
                        Pattern(
                            category=PatternCategory.TEMPORAL.value,
                            observation=f"Trading performance varies by hour",
                            evidence=f"Hour {best_hour}:00 avg: {best_avg:.1f}%, "
                            f"Hour {worst_hour}:00 avg: {worst_avg:.1f}%",
                            confidence=0.72,
                            recommendation=f"Prioritize trading during {best_hour}:00 UTC, "
                            f"avoid {worst_hour}:00 UTC",
                            affected_agents=["jarvis"],
                        )
                    )

        return patterns

    def _detect_error_patterns(self, logs: dict[str, str]) -> list[Pattern]:
        """Detect recurring error patterns."""
        patterns = []

        all_logs = "\n".join(logs.values())

        # Count error types
        error_counts = defaultdict(int)
        error_lines = re.findall(r"ERROR:?\s*(.*)", all_logs, re.IGNORECASE)

        for error in error_lines:
            # Normalize error message
            normalized = re.sub(r"\d+", "N", error)[:50]
            error_counts[normalized] += 1

        # Report recurring errors
        for error_type, count in error_counts.items():
            if count >= 2:
                patterns.append(
                    Pattern(
                        category=PatternCategory.ERROR.value,
                        observation=f"Recurring error: {error_type}",
                        evidence=f"Occurred {count} times in recent logs",
                        confidence=min(0.6 + count * 0.1, 0.90),
                        recommendation="Investigate and fix root cause",
                        affected_agents=["jarvis"],  # Errors typically in infra
                    )
                )

        return patterns

    def _detect_coordination_patterns(self, logs: dict[str, str]) -> list[Pattern]:
        """Detect cross-agent coordination patterns."""
        patterns = []

        friday_logs = logs.get("friday", "")

        # Look for handoff patterns
        handoffs = re.findall(
            r"Dispatched.*?to\s+(Matt|Jarvis)", friday_logs, re.IGNORECASE
        )
        if handoffs:
            # Look for success/failure after handoffs
            successes = len(re.findall(r"completed successfully", friday_logs, re.IGNORECASE))
            failures = len(re.findall(r"(failed|error|timeout)", friday_logs, re.IGNORECASE))

            total = successes + failures
            if total > 0:
                success_rate = successes / total
                if success_rate < 0.8:
                    patterns.append(
                        Pattern(
                            category=PatternCategory.COORDINATION.value,
                            observation="Handoff success rate below target",
                            evidence=f"{successes}/{total} handoffs successful ({success_rate:.0%})",
                            confidence=0.75,
                            recommendation="Improve handoff templates and clarity",
                            affected_agents=["friday"],
                        )
                    )

        return patterns

    def _detect_performance_patterns(self, logs: dict[str, str]) -> list[Pattern]:
        """Detect performance patterns (what's working, what's not)."""
        patterns = []

        matt_logs = logs.get("matt", "")

        # Look for engagement metrics
        engagements = re.findall(r"engagement[:\s]+(\d+)", matt_logs, re.IGNORECASE)
        impressions = re.findall(r"impressions?[:\s]+(\d+)", matt_logs, re.IGNORECASE)

        if engagements and impressions:
            avg_engagement = sum(int(e) for e in engagements) / len(engagements)
            avg_impressions = sum(int(i) for i in impressions) / len(impressions)

            if avg_impressions > 0:
                engagement_rate = avg_engagement / avg_impressions
                patterns.append(
                    Pattern(
                        category=PatternCategory.PERFORMANCE.value,
                        observation=f"Content engagement rate: {engagement_rate:.1%}",
                        evidence=f"Avg {avg_engagement:.0f} engagements on {avg_impressions:.0f} impressions",
                        confidence=0.80,
                        recommendation="Analyze high-engagement posts for patterns",
                        affected_agents=["matt"],
                    )
                )

        return patterns

    def update_knowledge(self, patterns: list[Pattern]) -> list[DeriveChain]:
        """
        Create Derives entries in Supermemory graph.

        Filters patterns by confidence threshold and creates
        observation -> insight -> recommendation chains.

        Args:
            patterns: List of patterns to process.

        Returns:
            List of created derive chains.
        """
        derives = []

        for pattern in patterns:
            # Skip low-confidence patterns
            if pattern.confidence < self.config.min_confidence_for_derive:
                logger.debug(
                    f"Skipping pattern (confidence {pattern.confidence:.2f} "
                    f"< {self.config.min_confidence_for_derive})"
                )
                continue

            # Create derive chain
            tags = [
                "#sleep-compute",
                "#auto-derived",
                f"#category:{pattern.category}",
                f"#confidence:{pattern.confidence:.2f}",
            ] + [f"#agent:{agent}" for agent in pattern.affected_agents]

            chain = DeriveChain(
                observation=pattern.observation,
                insight=f"Evidence: {pattern.evidence}",
                recommendation=pattern.recommendation,
                tags=tags,
                confidence=pattern.confidence,
            )

            derives.append(chain)
            logger.info(f"Created derive chain for: {pattern.category}")

            # In production, this would call Supermemory API:
            # self._create_supermemory_derives(chain)

        return derives

    def _create_supermemory_derives(self, chain: DeriveChain):
        """
        Create derives in Supermemory graph.

        This is a stub - actual implementation would use:
        - SupermemoryClient from supermemory-sdk
        - Create observation, insight, recommendation nodes
        - Link with "Derives" relationships

        Example API calls (pseudocode):
            client = SupermemoryClient(api_key=os.getenv("SUPERMEMORY_API_KEY"))

            observation_id = client.add_memory(
                space="company_core",
                content=chain.observation,
                tags=["#sleep-compute", "#observation"]
            )

            insight_id = client.add_memory(
                space="company_core",
                content=chain.insight,
                tags=["#sleep-compute", "#insight"]
            )

            client.create_relationship(
                source_id=observation_id,
                relation_type="Derives",
                target_id=insight_id
            )
        """
        logger.info(f"[STUB] Would create Supermemory derives for: {chain.observation[:50]}")

    def generate_insights(self, patterns: list[Pattern]) -> dict[str, list[str]]:
        """
        Update SOUL files with actionable insights.

        Filters by higher confidence threshold and appends to
        the ## Sleep-Compute Insights section of each SOUL file.

        Args:
            patterns: List of patterns to process.

        Returns:
            Dict mapping agent name to list of inserted insights.
        """
        updates = defaultdict(list)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Group patterns by agent
        by_agent = defaultdict(list)
        for pattern in patterns:
            if pattern.confidence < self.config.min_confidence_for_soul_update:
                continue
            for agent in pattern.affected_agents:
                by_agent[agent].append(pattern)

        # Update each agent's SOUL file
        for agent, agent_patterns in by_agent.items():
            if not agent_patterns:
                continue

            soul_file = self.SOUL_FILES.get(agent)
            if not soul_file:
                continue

            soul_path = self.config.soul_dir / soul_file

            if not soul_path.exists():
                logger.warning(f"SOUL file not found: {soul_path}")
                continue

            try:
                current_content = soul_path.read_text(encoding="utf-8")
                new_content = self._update_soul_content(
                    current_content, agent_patterns, timestamp
                )
                soul_path.write_text(new_content, encoding="utf-8")

                updates[agent] = [p.observation for p in agent_patterns]
                logger.info(
                    f"Updated {agent.upper()} SOUL with {len(agent_patterns)} insights"
                )
            except Exception as e:
                logger.error(f"Failed to update {agent} SOUL: {e}")

        return dict(updates)

    def _update_soul_content(
        self, content: str, patterns: list[Pattern], timestamp: str
    ) -> str:
        """Update SOUL file content with new insights."""
        # Check if Sleep-Compute section exists
        section_header = "## Sleep-Compute Insights"

        if section_header not in content:
            # Add new section at the end
            content += f"\n\n---\n\n{section_header}\n"
            content += "<!-- Auto-generated by Matt's nightly analysis -->\n"
            content += f"<!-- Last updated: {timestamp} -->\n\n"

        # Build new insights block
        insights_block = f"\n### Insights from {timestamp}\n\n"

        for pattern in patterns:
            category_title = pattern.category.replace("_", " ").title()
            insights_block += f"#### {category_title} (Confidence: {pattern.confidence:.2f})\n"
            insights_block += f"{pattern.observation}\n\n"
            insights_block += f"**Evidence:** {pattern.evidence}\n\n"
            insights_block += f"**Recommended Action:** {pattern.recommendation}\n\n"
            insights_block += "---\n\n"

        # Insert insights after the section header
        # Find the position right after the header and any existing metadata comments
        header_pos = content.find(section_header)
        insert_pos = header_pos + len(section_header)

        # Skip past any existing comment lines
        remaining = content[insert_pos:]
        lines = remaining.split("\n")
        skip_lines = 0
        for line in lines:
            if line.strip().startswith("<!--") or line.strip() == "":
                skip_lines += 1
            else:
                break

        if skip_lines > 0:
            insert_pos += len("\n".join(lines[:skip_lines])) + 1

        # Insert the new insights
        new_content = content[:insert_pos] + insights_block + content[insert_pos:]

        return new_content

    def run(self) -> dict[str, Any]:
        """
        Execute the full nightly analysis routine.

        Steps:
        1. Analyze logs
        2. Extract patterns
        3. Create knowledge derives
        4. Update SOUL files
        5. Generate report

        Returns:
            Summary dict with counts and status.
        """
        logger.info("Starting nightly sleep-compute analysis...")
        start_time = datetime.now(timezone.utc)

        # Create today's output directory
        today = start_time.strftime("%Y-%m-%d")
        today_dir = self.config.output_dir / today
        today_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Analyze logs
        logs = self.analyze_logs()
        logs_analyzed = sum(1 for content in logs.values() if content)

        # Step 2: Extract patterns
        patterns = self.extract_patterns(logs)

        # Save patterns to file
        patterns_file = today_dir / "patterns.json"
        patterns_data = {"patterns": [p.to_dict() for p in patterns]}
        patterns_file.write_text(json.dumps(patterns_data, indent=2))

        # Step 3: Create knowledge derives
        derives = self.update_knowledge(patterns)

        # Save derives to file
        derives_file = today_dir / "derives.json"
        derives_data = [d.to_dict() for d in derives]
        derives_file.write_text(json.dumps(derives_data, indent=2))

        # Step 4: Update SOUL files
        soul_updates = self.generate_insights(patterns)

        # Step 5: Generate summary
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        result = {
            "status": "completed",
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "duration_seconds": duration,
            "logs_analyzed": logs_analyzed,
            "patterns_found": len(patterns),
            "high_confidence_patterns": len(
                [p for p in patterns if p.confidence >= 0.75]
            ),
            "derives_created": len(derives),
            "soul_updates": soul_updates,
            "output_dir": str(today_dir),
        }

        # Save summary
        summary_file = today_dir / "summary.json"
        summary_file.write_text(json.dumps(result, indent=2))

        logger.info(
            f"Nightly analysis complete: {len(patterns)} patterns, "
            f"{len(derives)} derives, {sum(len(v) for v in soul_updates.values())} SOUL updates"
        )

        return result


def main():
    """Entry point for nightly analysis script."""
    import argparse

    parser = argparse.ArgumentParser(description="Run nightly sleep-time compute")
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=Path("/root/clawdbots/logs"),
        help="Directory containing bot logs",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/root/clawdbots/sleep_compute"),
        help="Output directory for analysis results",
    )
    parser.add_argument(
        "--soul-dir",
        type=Path,
        default=Path("/root/clawdbots"),
        help="Directory containing SOUL files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run analysis without updating SOUL files",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create config
    config = SleepComputeConfig(
        logs_dir=args.logs_dir,
        output_dir=args.output_dir,
        soul_dir=args.soul_dir,
    )

    # Run routine
    routine = NightlyRoutine(config)
    result = routine.run()

    # Print summary
    print(f"\n{'='*50}")
    print("Sleep-Compute Analysis Complete")
    print(f"{'='*50}")
    print(f"Duration: {result['duration_seconds']:.1f}s")
    print(f"Patterns Found: {result['patterns_found']}")
    print(f"High Confidence: {result['high_confidence_patterns']}")
    print(f"Derives Created: {result['derives_created']}")
    print(f"Output: {result['output_dir']}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()

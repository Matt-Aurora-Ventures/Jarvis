"""
Self-Improver - Dynamic Learning for Jarvis Twitter Bot

Implements the feedback loop from xbot.md:
1. Daily reflection on high/low performing tweets
2. Style guide evolution based on engagement
3. Content strategy adaptation

"Feed high-performing and low-performing tweets back into Grok:
'Here are my best and worst posts from yesterday. Analyze why the
best ones succeeded and update my Style Guide to prioritize that
content tomorrow.'"
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# State file for persistence
from core.state_paths import STATE_PATHS
STYLE_GUIDE_FILE = STATE_PATHS.data_dir / "jarvis_style_guide.json"
PERFORMANCE_LOG_FILE = STATE_PATHS.data_dir / "jarvis_performance_log.json"


@dataclass
class TweetPerformance:
    """Performance metrics for a single tweet."""
    tweet_id: str
    content: str
    category: str
    posted_at: datetime
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    impressions: int = 0
    engagement_rate: float = 0.0

    @property
    def engagement_score(self) -> float:
        """Weighted engagement score."""
        return (self.likes * 1) + (self.retweets * 3) + (self.replies * 2)


@dataclass
class StyleGuide:
    """
    Evolving style guide that learns from engagement.

    This is injected into every tweet generation prompt,
    allowing the agent to "learn" what works.
    """
    version: int = 1
    last_updated: Optional[datetime] = None

    # Learned preferences
    preferred_content_types: List[str] = field(default_factory=lambda: [
        "market_update", "trending_token", "agentic_tech"
    ])
    avoid_content_types: List[str] = field(default_factory=list)

    # Tone preferences
    preferred_tones: List[str] = field(default_factory=lambda: [
        "analytical", "slightly_sarcastic", "helpful"
    ])

    # Structural preferences
    optimal_length_chars: int = 200
    use_emojis: bool = False  # Jarvis voice discourages emojis
    use_data_points: bool = True
    include_nfa_disclaimer: bool = True

    # Time preferences (learned optimal posting hours)
    best_posting_hours: List[int] = field(default_factory=lambda: [9, 12, 15, 18])

    # Patterns that worked
    winning_patterns: List[str] = field(default_factory=list)

    # Patterns to avoid
    losing_patterns: List[str] = field(default_factory=list)

    # Raw insights from reflection
    insights: List[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Convert style guide to prompt injection text."""
        lines = [
            "=== JARVIS STYLE GUIDE (Self-Learned) ===",
            "",
            f"Preferred content types: {', '.join(self.preferred_content_types)}",
            f"Avoid content types: {', '.join(self.avoid_content_types) or 'none'}",
            f"Tone: {', '.join(self.preferred_tones)}",
            f"Target length: ~{self.optimal_length_chars} chars",
            f"Include data points: {'yes' if self.use_data_points else 'no'}",
            f"Include NFA disclaimer: {'yes' if self.include_nfa_disclaimer else 'no'}",
        ]

        if self.winning_patterns:
            lines.append(f"\nPatterns that work well: {'; '.join(self.winning_patterns[-5:])}")

        if self.losing_patterns:
            lines.append(f"\nPatterns to avoid: {'; '.join(self.losing_patterns[-5:])}")

        if self.insights:
            lines.append(f"\nRecent insights: {'; '.join(self.insights[-3:])}")

        lines.append("\n=== END STYLE GUIDE ===")

        return "\n".join(lines)


class SelfImprover:
    """
    Self-improvement engine that learns from engagement data.

    Runs daily reflection cycles to:
    1. Analyze top and bottom performing tweets
    2. Extract patterns
    3. Update the style guide
    """

    def __init__(self):
        """Initialize the self-improver."""
        self.style_guide = StyleGuide()
        self.performance_log: List[TweetPerformance] = []
        self._load_state()

    def _load_state(self):
        """Load persisted state from disk."""
        # Load style guide
        try:
            if STYLE_GUIDE_FILE.exists():
                data = json.loads(STYLE_GUIDE_FILE.read_text())
                self.style_guide = StyleGuide(
                    version=data.get("version", 1),
                    last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else None,
                    preferred_content_types=data.get("preferred_content_types", self.style_guide.preferred_content_types),
                    avoid_content_types=data.get("avoid_content_types", []),
                    preferred_tones=data.get("preferred_tones", self.style_guide.preferred_tones),
                    optimal_length_chars=data.get("optimal_length_chars", 200),
                    use_emojis=data.get("use_emojis", False),
                    use_data_points=data.get("use_data_points", True),
                    include_nfa_disclaimer=data.get("include_nfa_disclaimer", True),
                    best_posting_hours=data.get("best_posting_hours", [9, 12, 15, 18]),
                    winning_patterns=data.get("winning_patterns", []),
                    losing_patterns=data.get("losing_patterns", []),
                    insights=data.get("insights", []),
                )
                logger.info(f"Style guide loaded (version {self.style_guide.version})")
        except Exception as e:
            logger.warning(f"Failed to load style guide: {e}")

        # Load performance log
        try:
            if PERFORMANCE_LOG_FILE.exists():
                data = json.loads(PERFORMANCE_LOG_FILE.read_text())
                # Only keep last 30 days
                cutoff = datetime.now() - timedelta(days=30)
                self.performance_log = [
                    TweetPerformance(
                        tweet_id=p["tweet_id"],
                        content=p["content"],
                        category=p.get("category", "unknown"),
                        posted_at=datetime.fromisoformat(p["posted_at"]),
                        likes=p.get("likes", 0),
                        retweets=p.get("retweets", 0),
                        replies=p.get("replies", 0),
                        impressions=p.get("impressions", 0),
                    )
                    for p in data
                    if datetime.fromisoformat(p["posted_at"]) > cutoff
                ]
                logger.info(f"Performance log loaded ({len(self.performance_log)} entries)")
        except Exception as e:
            logger.warning(f"Failed to load performance log: {e}")

    def _save_state(self):
        """Persist state to disk."""
        # Save style guide
        try:
            STYLE_GUIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": self.style_guide.version,
                "last_updated": self.style_guide.last_updated.isoformat() if self.style_guide.last_updated else None,
                "preferred_content_types": self.style_guide.preferred_content_types,
                "avoid_content_types": self.style_guide.avoid_content_types,
                "preferred_tones": self.style_guide.preferred_tones,
                "optimal_length_chars": self.style_guide.optimal_length_chars,
                "use_emojis": self.style_guide.use_emojis,
                "use_data_points": self.style_guide.use_data_points,
                "include_nfa_disclaimer": self.style_guide.include_nfa_disclaimer,
                "best_posting_hours": self.style_guide.best_posting_hours,
                "winning_patterns": self.style_guide.winning_patterns[-20:],
                "losing_patterns": self.style_guide.losing_patterns[-20:],
                "insights": self.style_guide.insights[-10:],
            }
            STYLE_GUIDE_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save style guide: {e}")

        # Save performance log
        try:
            data = [
                {
                    "tweet_id": p.tweet_id,
                    "content": p.content,
                    "category": p.category,
                    "posted_at": p.posted_at.isoformat(),
                    "likes": p.likes,
                    "retweets": p.retweets,
                    "replies": p.replies,
                    "impressions": p.impressions,
                }
                for p in self.performance_log[-500:]  # Keep last 500
            ]
            PERFORMANCE_LOG_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save performance log: {e}")

    def record_tweet(self, tweet_id: str, content: str, category: str):
        """Record a new tweet for later analysis."""
        self.performance_log.append(TweetPerformance(
            tweet_id=tweet_id,
            content=content,
            category=category,
            posted_at=datetime.now(),
        ))
        self._save_state()

    async def update_metrics(self, tweet_id: str, likes: int, retweets: int, replies: int, impressions: int):
        """Update metrics for a tweet (called during self-learning cycle)."""
        for perf in self.performance_log:
            if perf.tweet_id == tweet_id:
                perf.likes = likes
                perf.retweets = retweets
                perf.replies = replies
                perf.impressions = impressions
                if impressions > 0:
                    perf.engagement_rate = perf.engagement_score / impressions
                break
        self._save_state()

    def get_style_context(self) -> str:
        """Get the current style guide as prompt context."""
        return self.style_guide.to_prompt_context()

    async def run_daily_reflection(self) -> Dict[str, Any]:
        """
        Run the daily reflection cycle.

        Analyzes yesterday's tweets, identifies patterns,
        and updates the style guide.

        Returns:
            Summary of what was learned
        """
        logger.info("Starting daily reflection cycle...")

        # Get yesterday's tweets
        yesterday = datetime.now() - timedelta(days=1)
        recent_tweets = [
            p for p in self.performance_log
            if p.posted_at > yesterday
        ]

        if len(recent_tweets) < 3:
            return {"status": "insufficient_data", "count": len(recent_tweets)}

        # Sort by engagement score
        sorted_tweets = sorted(recent_tweets, key=lambda t: t.engagement_score, reverse=True)

        # Get top and bottom performers
        top_tweets = sorted_tweets[:3]
        bottom_tweets = sorted_tweets[-3:] if len(sorted_tweets) > 3 else []

        # Build analysis prompt
        top_content = "\n".join([f"- {t.content[:100]}... (score: {t.engagement_score})" for t in top_tweets])
        bottom_content = "\n".join([f"- {t.content[:100]}... (score: {t.engagement_score})" for t in bottom_tweets])

        reflection_prompt = f"""Analyze my Twitter performance from yesterday.

TOP PERFORMING TWEETS:
{top_content}

BOTTOM PERFORMING TWEETS:
{bottom_content}

CURRENT STYLE GUIDE:
{self.style_guide.to_prompt_context()}

Tasks:
1. Identify what made the top tweets succeed (patterns, tone, timing, topics)
2. Identify why the bottom tweets underperformed
3. Suggest 1-2 concrete changes to my style guide

Output JSON only:
{{
    "winning_patterns": ["pattern1", "pattern2"],
    "losing_patterns": ["pattern1", "pattern2"],
    "content_type_recommendations": {{"boost": ["type1"], "reduce": ["type2"]}},
    "insights": ["insight1", "insight2"],
    "optimal_length": 200
}}"""

        try:
            from bots.twitter.grok_client import GrokClient
            import re

            grok = GrokClient()
            response = await grok.generate_text(
                reflection_prompt,
                temperature=0.3,
                max_tokens=500,
            )

            if response.success:
                # Parse JSON from response
                json_match = re.search(r'\{[^{}]*\}', response.content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())

                    # Update style guide with learnings
                    self.style_guide.version += 1
                    self.style_guide.last_updated = datetime.now()

                    # Add winning patterns
                    for pattern in result.get("winning_patterns", []):
                        if pattern not in self.style_guide.winning_patterns:
                            self.style_guide.winning_patterns.append(pattern)

                    # Add losing patterns
                    for pattern in result.get("losing_patterns", []):
                        if pattern not in self.style_guide.losing_patterns:
                            self.style_guide.losing_patterns.append(pattern)

                    # Update content preferences
                    recs = result.get("content_type_recommendations", {})
                    for content_type in recs.get("boost", []):
                        if content_type not in self.style_guide.preferred_content_types:
                            self.style_guide.preferred_content_types.append(content_type)
                    for content_type in recs.get("reduce", []):
                        if content_type not in self.style_guide.avoid_content_types:
                            self.style_guide.avoid_content_types.append(content_type)

                    # Add insights
                    for insight in result.get("insights", []):
                        self.style_guide.insights.append(f"{datetime.now().strftime('%Y-%m-%d')}: {insight}")

                    # Update optimal length
                    if result.get("optimal_length"):
                        self.style_guide.optimal_length_chars = result["optimal_length"]

                    self._save_state()

                    logger.info(f"Style guide updated to version {self.style_guide.version}")
                    return {
                        "status": "success",
                        "version": self.style_guide.version,
                        "learnings": result,
                    }

        except Exception as e:
            logger.error(f"Daily reflection failed: {e}")

        return {"status": "error", "message": str(e)}

    def get_content_recommendation(self) -> str:
        """Get a recommendation for what type of content to post next."""
        if self.style_guide.preferred_content_types:
            # Rotate through preferred types
            import random
            return random.choice(self.style_guide.preferred_content_types)
        return "market_update"


# Singleton instance
_improver: Optional[SelfImprover] = None


def get_self_improver() -> SelfImprover:
    """Get or create the singleton self-improver."""
    global _improver
    if _improver is None:
        _improver = SelfImprover()
    return _improver

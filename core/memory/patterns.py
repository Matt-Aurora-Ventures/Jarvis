"""Weekly pattern analysis and contradiction detection for memory consolidation."""
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

import anthropic

from .database import get_db
from .config import get_config

logger = logging.getLogger(__name__)


def generate_weekly_summary() -> Dict[str, Any]:
    """
    Generate weekly pattern summary with actionable insights.

    Analyzes the last complete week (Monday-Sunday) of memory data:
    - Trade outcomes (win rate, profit/loss patterns)
    - Top performing tokens
    - Strategy effectiveness
    - Activity patterns by source

    Uses Claude to synthesize 3-5 actionable insights from aggregate statistics.
    Writes markdown summary to ~/.lifeos/memory/bank/weekly_summaries/{year}-W{week}.md

    Returns:
        Dict with:
        - week: ISO week string (e.g., "2026-W04")
        - summary_path: Path to generated markdown file
        - stats: Dict of aggregate statistics
        - insights: LLM-synthesized insights text

    Example:
        result = generate_weekly_summary()
        # {
        #     "week": "2026-W04",
        #     "summary_path": "/home/user/.lifeos/memory/bank/weekly_summaries/2026-W04.md",
        #     "stats": {"total_trades": 42, "win_rate": 0.71, ...},
        #     "insights": "## Key Insights\n1. High-sentiment tokens..."
        # }
    """
    logger.info("Starting weekly summary generation...")

    # Calculate last complete week boundaries (Monday-Sunday)
    today = datetime.utcnow().date()
    days_since_monday = today.weekday()  # 0=Monday, 6=Sunday

    # If today is Monday (0), last complete week ended yesterday
    # Otherwise, go back to last Sunday
    if days_since_monday == 0:
        # Today is Monday, last week ended yesterday (Sunday)
        week_end = today - timedelta(days=1)
    else:
        # Go back to most recent Sunday
        week_end = today - timedelta(days=days_since_monday + 1)

    week_start = week_end - timedelta(days=6)  # 7 days total (Monday to Sunday)

    # Convert to datetime for SQL queries
    start_dt = datetime.combine(week_start, datetime.min.time())
    end_dt = datetime.combine(week_end, datetime.max.time())

    logger.info(f"Analyzing week from {week_start} to {week_end}")

    # Get ISO week number
    iso_calendar = week_start.isocalendar()
    year, week_num = iso_calendar[0], iso_calendar[1]
    week_str = f"{year}-W{week_num:02d}"

    # Query aggregate statistics
    db = get_db()
    stats = {}

    with db.get_cursor() as cursor:
        # Trade outcomes
        cursor.execute(
            """
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN content LIKE '%+%' OR content LIKE '%profit%' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN content LIKE '%-%' OR content LIKE '%loss%' THEN 1 ELSE 0 END) as losses
            FROM facts
            WHERE source = 'treasury'
            AND context LIKE '%trade_outcome%'
            AND timestamp >= ? AND timestamp <= ?
            """,
            (start_dt, end_dt)
        )
        row = cursor.fetchone()
        if row:
            total = row["total_trades"] if hasattr(row, "keys") else row[0]
            wins = row["wins"] if hasattr(row, "keys") else row[1]
            losses = row["losses"] if hasattr(row, "keys") else row[2]

            stats["total_trades"] = total
            stats["wins"] = wins
            stats["losses"] = losses
            stats["win_rate"] = round(wins / total, 2) if total > 0 else 0.0

        # Top performing tokens
        cursor.execute(
            """
            SELECT
                em.entity_name,
                COUNT(*) as mention_count,
                SUM(CASE WHEN f.content LIKE '%+%' OR f.content LIKE '%profit%' THEN 1 ELSE 0 END) as wins
            FROM entity_mentions em
            JOIN facts f ON em.fact_id = f.id
            WHERE em.entity_type = 'token'
            AND f.timestamp >= ? AND f.timestamp <= ?
            GROUP BY em.entity_name
            ORDER BY wins DESC
            LIMIT 10
            """,
            (start_dt, end_dt)
        )
        top_tokens = []
        for row in cursor.fetchall():
            entity_name = row["entity_name"] if hasattr(row, "keys") else row[0]
            mention_count = row["mention_count"] if hasattr(row, "keys") else row[1]
            token_wins = row["wins"] if hasattr(row, "keys") else row[2]

            top_tokens.append({
                "name": entity_name,
                "mentions": mention_count,
                "wins": token_wins
            })
        stats["top_tokens"] = top_tokens

        # Strategy performance
        cursor.execute(
            """
            SELECT
                em.entity_name as strategy,
                COUNT(*) as trades,
                SUM(CASE WHEN f.content LIKE '%+%' THEN 1 ELSE 0 END) as wins
            FROM entity_mentions em
            JOIN facts f ON em.fact_id = f.id
            WHERE em.entity_type = 'strategy'
            AND f.source = 'treasury'
            AND f.timestamp >= ? AND f.timestamp <= ?
            GROUP BY em.entity_name
            ORDER BY wins DESC
            """,
            (start_dt, end_dt)
        )
        strategies = []
        for row in cursor.fetchall():
            strategy = row["strategy"] if hasattr(row, "keys") else row[0]
            trades = row["trades"] if hasattr(row, "keys") else row[1]
            strategy_wins = row["wins"] if hasattr(row, "keys") else row[2]

            strategies.append({
                "name": strategy,
                "trades": trades,
                "wins": strategy_wins,
                "win_rate": round(strategy_wins / trades, 2) if trades > 0 else 0.0
            })
        stats["strategies"] = strategies

        # Activity by source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM facts
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY source
            ORDER BY count DESC
            """,
            (start_dt, end_dt)
        )
        activity = []
        for row in cursor.fetchall():
            source = row["source"] if hasattr(row, "keys") else row[0]
            count = row["count"] if hasattr(row, "keys") else row[1]
            activity.append({"source": source or "unknown", "count": count})
        stats["activity_by_source"] = activity

    # Build stats text for LLM
    stats_lines = []
    stats_lines.append(f"**Period:** {week_start} to {week_end} ({week_str})\n")

    stats_lines.append("**Trade Performance:**")
    stats_lines.append(f"- Total trades: {stats.get('total_trades', 0)}")
    stats_lines.append(f"- Wins: {stats.get('wins', 0)}")
    stats_lines.append(f"- Losses: {stats.get('losses', 0)}")
    stats_lines.append(f"- Win rate: {stats.get('win_rate', 0.0) * 100:.1f}%\n")

    if stats.get("top_tokens"):
        stats_lines.append("**Top Tokens (by wins):**")
        for token in stats["top_tokens"][:5]:
            stats_lines.append(f"- {token['name']}: {token['wins']} wins, {token['mentions']} mentions")
        stats_lines.append("")

    if stats.get("strategies"):
        stats_lines.append("**Strategy Performance:**")
        for strat in stats["strategies"]:
            stats_lines.append(
                f"- {strat['name']}: {strat['wins']}/{strat['trades']} trades "
                f"({strat['win_rate'] * 100:.1f}% win rate)"
            )
        stats_lines.append("")

    if stats.get("activity_by_source"):
        stats_lines.append("**Activity by Source:**")
        for activity_item in stats["activity_by_source"]:
            stats_lines.append(f"- {activity_item['source']}: {activity_item['count']} facts")

    stats_text = "\n".join(stats_lines)

    # Synthesize insights with Claude
    insights = _synthesize_pattern_insights(stats_text)

    # Write markdown summary
    config = get_config()
    summaries_dir = config.bank_dir / "weekly_summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)

    summary_path = summaries_dir / f"{week_str}.md"

    markdown_content = f"""# Weekly Summary: Week {week_num}, {year}

**Period:** {week_start} to {week_end}

## Statistics

{stats_text}

## Pattern Insights

{insights}

_Generated: {datetime.utcnow().isoformat()}_
"""

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    logger.info(f"Weekly summary written to {summary_path}")

    return {
        "week": week_str,
        "summary_path": str(summary_path),
        "stats": stats,
        "insights": insights,
    }


def _synthesize_pattern_insights(stats_text: str) -> str:
    """
    Use Claude to synthesize actionable insights from weekly statistics.

    Args:
        stats_text: Formatted statistics text

    Returns:
        Markdown-formatted insights
    """
    try:
        client = anthropic.Anthropic()

        prompt = f"""Analyze this week's trading and activity data and extract 3-5 actionable insights:

{stats_text}

Focus on:
1. What worked: High win rate tokens/strategies
2. What failed: Underperformers to avoid
3. Emerging patterns: (e.g., "tokens with dev Twitter succeed 70%")
4. Recommendations for next week

Be specific with percentages and examples. Format as a numbered list.
If data is minimal, provide general observations and suggest what to track next week.
"""

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        insights = message.content[0].text
        return insights

    except Exception as e:
        logger.warning(f"Failed to synthesize insights with Claude: {e}")
        return "_(Insight synthesis unavailable - Claude API error)_"


def detect_contradictions() -> List[Dict[str, Any]]:
    """
    Detect contradictions in the memory database.

    Finds:
    1. Conflicting preferences (same user, key, different values)
    2. Entity type conflicts (same name, different types)

    Returns:
        List of contradiction dicts with:
        - type: "preference_conflict" | "entity_type_conflict"
        - id1, id2: IDs of conflicting records
        - reason: Human-readable explanation
        - detected_at: ISO timestamp

    Example:
        contradictions = detect_contradictions()
        # [
        #     {
        #         "type": "preference_conflict",
        #         "id1": 1, "id2": 2,
        #         "reason": "User lucid has conflicting preferences for risk_level: 'high' vs 'low'",
        #         "detected_at": "2026-01-25T19:15:00Z"
        #     }
        # ]
    """
    logger.info("Starting contradiction detection...")
    contradictions = []
    db = get_db()

    with db.get_cursor() as cursor:
        # Detect conflicting preferences
        cursor.execute(
            """
            SELECT
                p1.id as id1, p2.id as id2,
                p1.user_id,
                p1.category,
                p1.preference_key as key,
                p1.preference_value as value1,
                p2.preference_value as value2,
                p1.confidence as conf1,
                p2.confidence as conf2
            FROM preferences p1
            JOIN preferences p2 ON p1.user_id = p2.user_id
                AND p1.category = p2.category
                AND p1.preference_key = p2.preference_key
            WHERE p1.id < p2.id
            AND p1.preference_value != p2.preference_value
            AND p1.confidence > 0.4 AND p2.confidence > 0.4
            """
        )

        for row in cursor.fetchall():
            id1 = row["id1"] if hasattr(row, "keys") else row[0]
            id2 = row["id2"] if hasattr(row, "keys") else row[1]
            user_id = row["user_id"] if hasattr(row, "keys") else row[2]
            category = row["category"] if hasattr(row, "keys") else row[3]
            key = row["key"] if hasattr(row, "keys") else row[4]
            value1 = row["value1"] if hasattr(row, "keys") else row[5]
            value2 = row["value2"] if hasattr(row, "keys") else row[6]
            conf1 = row["conf1"] if hasattr(row, "keys") else row[7]
            conf2 = row["conf2"] if hasattr(row, "keys") else row[8]

            contradictions.append({
                "type": "preference_conflict",
                "id1": id1,
                "id2": id2,
                "user_id": user_id,
                "category": category,
                "key": key,
                "reason": (
                    f"User {user_id} has conflicting preferences for {category}.{key}: "
                    f"'{value1}' (conf: {conf1:.2f}) vs '{value2}' (conf: {conf2:.2f})"
                ),
                "detected_at": datetime.utcnow().isoformat()
            })

        # Detect entity type conflicts
        cursor.execute(
            """
            SELECT
                e1.id as id1, e2.id as id2,
                e1.name,
                e1.type as type1,
                e2.type as type2
            FROM entities e1
            JOIN entities e2 ON LOWER(e1.name) = LOWER(e2.name)
            WHERE e1.id < e2.id
            AND e1.type != e2.type
            """
        )

        for row in cursor.fetchall():
            id1 = row["id1"] if hasattr(row, "keys") else row[0]
            id2 = row["id2"] if hasattr(row, "keys") else row[1]
            name = row["name"] if hasattr(row, "keys") else row[2]
            type1 = row["type1"] if hasattr(row, "keys") else row[3]
            type2 = row["type2"] if hasattr(row, "keys") else row[4]

            contradictions.append({
                "type": "entity_type_conflict",
                "id1": id1,
                "id2": id2,
                "entity_name": name,
                "reason": f"Entity '{name}' has conflicting types: '{type1}' vs '{type2}'",
                "detected_at": datetime.utcnow().isoformat()
            })

    if contradictions:
        logger.warning(f"Detected {len(contradictions)} contradictions")
        for c in contradictions:
            logger.warning(f"  - {c['reason']}")
    else:
        logger.info("No contradictions detected")

    return contradictions

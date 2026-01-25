"""Memory workspace initialization and path utilities."""
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import get_config, MemoryConfig

# Convenience export
MEMORY_ROOT: Optional[Path] = None


def init_workspace(config: Optional[MemoryConfig] = None) -> Path:
    """
    Initialize the memory workspace directory structure.

    Creates all required directories and placeholder files.
    Safe to call multiple times (idempotent).

    Args:
        config: Optional config override. Uses get_config() if not provided.

    Returns:
        Path to the memory root directory.
    """
    global MEMORY_ROOT

    if config is None:
        config = get_config()

    root = config.memory_root
    MEMORY_ROOT = root

    # Create directory structure
    directories = [
        root,
        root / "memory",
        root / "memory" / "archives",
        root / "bank",
        root / "bank" / "entities",
        root / "bank" / "entities" / "tokens",
        root / "bank" / "entities" / "users",
        root / "bank" / "entities" / "strategies",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    # Create placeholder Markdown files if they don't exist
    placeholder_files = {
        root / "memory.md": _create_memory_md_content(),
        root / "bank" / "world.md": _create_world_md_content(),
        root / "bank" / "experience.md": _create_experience_md_content(),
        root / "bank" / "opinions.md": _create_opinions_md_content(),
        root / "SOUL.md": _create_soul_md_content(),
        root / "AGENTS.md": _create_agents_md_content(),
        root / "USER.md": _create_user_md_content(),
    }

    for filepath, content in placeholder_files.items():
        if not filepath.exists():
            filepath.write_text(content, encoding="utf-8")

    return root


def get_memory_path(relative_path: str) -> Path:
    """
    Get absolute path within the memory workspace.

    Args:
        relative_path: Path relative to memory root (e.g., "memory/2026-01-25.md")

    Returns:
        Absolute Path object.
    """
    config = get_config()
    return config.memory_root / relative_path


def get_daily_log_path(date: Optional[datetime] = None) -> Path:
    """
    Get path to daily log file for given date.

    Args:
        date: Date for log file. Defaults to today.

    Returns:
        Path to daily log Markdown file.
    """
    if date is None:
        date = datetime.utcnow()

    config = get_config()
    filename = date.strftime("%Y-%m-%d.md")
    return config.daily_logs_dir / filename


def _create_memory_md_content() -> str:
    """Template for core memory.md file."""
    return f"""# Jarvis Memory

Core durable facts synthesized from daily experiences.

*Last updated: {datetime.utcnow().strftime("%Y-%m-%d")}*

---

## Key Facts

*Facts will be added here during daily reflect operations.*

---

## Patterns

*Recurring patterns will be documented here.*
"""


def _create_world_md_content() -> str:
    """Template for bank/world.md."""
    return """# World Knowledge

Objective facts about the trading world.

---

## Market Facts

*Market knowledge will be stored here.*

## Token Facts

*Token-specific knowledge will be stored here.*
"""


def _create_experience_md_content() -> str:
    """Template for bank/experience.md."""
    return """# Trading Experience

Lessons learned from trade outcomes.

---

## Successful Patterns

*Patterns that led to profitable trades.*

## Failed Patterns

*Patterns to avoid based on losses.*
"""


def _create_opinions_md_content() -> str:
    """Template for bank/opinions.md."""
    return """# Opinions & Preferences

Confidence-weighted beliefs that evolve with evidence.

---

## Trading Preferences

| Preference | Value | Confidence | Evidence Count |
|------------|-------|------------|----------------|
| *Preferences will be added here* | | | |

## Market Opinions

*Evolving market opinions will be stored here.*
"""


def _create_soul_md_content() -> str:
    """Template for SOUL.md (Jarvis identity)."""
    return """# Jarvis Identity

## Core Purpose

Autonomous LifeOS trading and AI assistant running on Solana.

## Personality

- Analytical and data-driven
- Risk-aware but opportunity-seeking
- Evolves intelligence based on evidence
- Remembers everything relevant

## Values

- Protect user capital above all
- Learn from every trade outcome
- Provide honest analysis, even when bearish
- Maintain confidence levels on all opinions
"""


def _create_agents_md_content() -> str:
    """Template for AGENTS.md (operating instructions)."""
    return """# Operating Instructions

## Memory Operations

### Retain
Store every significant event:
- Trade outcomes (buy/sell with context)
- User preferences expressed
- Token intel discovered
- Post performance metrics

### Recall
Query memory before decisions:
- Similar past trades before entering position
- User preferences before responding
- Token history before scoring

### Reflect
Daily synthesis:
- Update core memory.md
- Evolve confidence scores
- Archive old logs
"""


def _create_user_md_content() -> str:
    """Template for USER.md (primary user profile)."""
    return """# User Profile: lucid

## Identity

- Primary Jarvis administrator
- Telegram: @lucid
- X/Twitter: @lucid (if linked)

## Preferences

*Preferences will be populated from stored data.*

## Trading Style

*Trading style will be inferred from behavior.*
"""

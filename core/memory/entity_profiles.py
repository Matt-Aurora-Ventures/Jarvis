"""Entity profile management for markdown-based entity knowledge."""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import get_config
from .database import get_db


def _sanitize_entity_name(name: str) -> str:
    """
    Sanitize entity name for filesystem usage.

    Removes special characters like @, $, and replaces spaces/slashes.

    Args:
        name: Raw entity name (e.g., '@KR8TIV', 'user@telegram')

    Returns:
        Sanitized filename-safe name (e.g., 'KR8TIV', 'user_telegram')
    """
    # Remove leading @ or $
    sanitized = name.lstrip("@$")

    # Replace unsafe filesystem characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', sanitized)

    # Replace spaces with underscores
    sanitized = sanitized.replace(' ', '_')

    return sanitized


def get_entity_type_dir(entity_type: str) -> Path:
    """
    Get directory for entity type (tokens, users, strategies, other).

    Args:
        entity_type: Type of entity ('token', 'user', 'strategy', 'other')

    Returns:
        Path to entity type directory
    """
    config = get_config()
    type_dirs = {
        "token": config.entities_dir / "tokens",
        "user": config.entities_dir / "users",
        "strategy": config.entities_dir / "strategies",
        "other": config.entities_dir,
    }
    return type_dirs.get(entity_type, config.entities_dir)


def create_entity_profile(
    entity_name: str,
    entity_type: str,
    summary: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Create a new entity profile with markdown file and database entry.

    Args:
        entity_name: Entity name (e.g., '@KR8TIV', 'lucid')
        entity_type: Type ('token', 'user', 'strategy', 'other')
        summary: Brief summary of entity
        metadata: Optional metadata dict

    Returns:
        True if created successfully, False if already exists or error
    """
    db = get_db()

    try:
        # Check if entity already exists
        with db.get_cursor() as cursor:
            existing = cursor.execute(
                "SELECT id FROM entities WHERE name = ? AND type = ?",
                (entity_name, entity_type)
            ).fetchone()

            if existing:
                return False  # Already exists

            # Insert into database
            cursor.execute(
                """
                INSERT INTO entities (name, type, summary, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entity_name,
                    entity_type,
                    summary,
                    json.dumps(metadata) if metadata else None,
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                )
            )

        # Create markdown file
        entity_dir = get_entity_type_dir(entity_type)
        entity_dir.mkdir(parents=True, exist_ok=True)

        sanitized_name = _sanitize_entity_name(entity_name)
        profile_path = entity_dir / f"{sanitized_name}.md"

        # Don't overwrite existing file
        if profile_path.exists():
            return False

        # Create markdown template
        created_date = datetime.utcnow().strftime("%Y-%m-%d")

        markdown_content = f"""# {entity_name}

**Type:** {entity_type}
**Created:** {created_date}

## Summary
{summary if summary else '(No summary yet)'}

## Facts
<!-- Facts are appended here by update_entity_profile -->

## Metadata
"""

        # Add metadata as YAML-like format
        if metadata:
            markdown_content += "```yaml\n"
            for key, value in metadata.items():
                markdown_content += f"{key}: {value}\n"
            markdown_content += "```\n"
        else:
            markdown_content += "(No metadata)\n"

        # Write file atomically
        profile_path.write_text(markdown_content, encoding='utf-8')

        return True

    except Exception as e:
        print(f"Error creating entity profile for {entity_name}: {e}")
        return False


def get_entity_profile(entity_name: str) -> Optional[Dict[str, Any]]:
    """
    Get entity profile from markdown file and database.

    Args:
        entity_name: Entity name to look up

    Returns:
        Dict with keys: name, type, summary, metadata, profile_content, facts_count
        None if entity doesn't exist
    """
    db = get_db()

    try:
        # First get entity from database
        with db.get_cursor() as cursor:
            row = cursor.execute(
                """
                SELECT id, name, type, summary, metadata, created_at, updated_at
                FROM entities
                WHERE name = ?
                """,
                (entity_name,)
            ).fetchone()

            if not row:
                return None

            entity_id = row["id"] if hasattr(row, "keys") else row[0]
            entity_type = row["type"] if hasattr(row, "keys") else row[2]
            summary = row["summary"] if hasattr(row, "keys") else row[3]
            metadata_json = row["metadata"] if hasattr(row, "keys") else row[4]

            # Count facts mentioning this entity
            facts_count = cursor.execute(
                "SELECT COUNT(*) FROM entity_mentions WHERE entity_id = ?",
                (entity_id,)
            ).fetchone()[0]

        # Parse metadata if present
        metadata = None
        if metadata_json:
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                metadata = None

        # Read markdown file
        entity_dir = get_entity_type_dir(entity_type)
        sanitized_name = _sanitize_entity_name(entity_name)
        profile_path = entity_dir / f"{sanitized_name}.md"

        profile_content = None
        if profile_path.exists():
            profile_content = profile_path.read_text(encoding='utf-8')

        return {
            "name": entity_name,
            "type": entity_type,
            "summary": summary,
            "metadata": metadata,
            "profile_content": profile_content,
            "facts_count": facts_count,
        }

    except Exception as e:
        print(f"Error getting entity profile for {entity_name}: {e}")
        return None


def update_entity_profile(
    entity_name: str,
    new_fact: str,
    update_summary: bool = False,
    new_summary: Optional[str] = None,
) -> bool:
    """
    Update entity profile by appending a fact and optionally updating summary.

    Args:
        entity_name: Entity name to update
        new_fact: New fact to append to profile
        update_summary: Whether to update the summary
        new_summary: New summary text (if update_summary=True)

    Returns:
        True if updated successfully, False otherwise
    """
    db = get_db()

    try:
        # Get entity type from database
        with db.get_cursor() as cursor:
            row = cursor.execute(
                "SELECT type FROM entities WHERE name = ?",
                (entity_name,)
            ).fetchone()

            if not row:
                return False  # Entity doesn't exist

            entity_type = row["type"] if hasattr(row, "keys") else row[0]

            # Update database summary if requested
            if update_summary and new_summary:
                cursor.execute(
                    "UPDATE entities SET summary = ?, updated_at = ? WHERE name = ?",
                    (new_summary, datetime.utcnow().isoformat(), entity_name)
                )

        # Update markdown file
        entity_dir = get_entity_type_dir(entity_type)
        sanitized_name = _sanitize_entity_name(entity_name)
        profile_path = entity_dir / f"{sanitized_name}.md"

        if not profile_path.exists():
            return False  # Profile file doesn't exist

        # Read existing content
        content = profile_path.read_text(encoding='utf-8')

        # Find ## Facts section and append new fact
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        new_fact_line = f"- [{timestamp}] {new_fact}\n"

        # Look for ## Facts section
        facts_match = re.search(r'## Facts\s*\n', content)

        if facts_match:
            # Insert after ## Facts header
            insert_pos = facts_match.end()

            # Check if there's already a comment line, skip past it
            comment_match = re.match(r'<!--.*?-->\s*\n', content[insert_pos:])
            if comment_match:
                insert_pos += comment_match.end()

            # Insert the new fact
            updated_content = (
                content[:insert_pos] +
                new_fact_line +
                content[insert_pos:]
            )
        else:
            # No Facts section found, append at end
            updated_content = content + f"\n## Facts\n{new_fact_line}"

        # Update summary section if requested
        if update_summary and new_summary:
            summary_match = re.search(r'## Summary\s*\n(.*?)\n\n', updated_content, re.DOTALL)
            if summary_match:
                updated_content = (
                    updated_content[:summary_match.start(1)] +
                    new_summary +
                    updated_content[summary_match.end(1):]
                )

        # Write updated content atomically
        profile_path.write_text(updated_content, encoding='utf-8')

        return True

    except Exception as e:
        print(f"Error updating entity profile for {entity_name}: {e}")
        return False


def get_entity_summary(entity_name: str) -> Optional[str]:
    """
    Get just the summary string for an entity (fast lookup).

    Args:
        entity_name: Entity name to look up

    Returns:
        Summary string or None if entity doesn't exist
    """
    db = get_db()

    try:
        with db.get_cursor() as cursor:
            row = cursor.execute(
                "SELECT summary FROM entities WHERE name = ?",
                (entity_name,)
            ).fetchone()

            if not row:
                return None

            return row["summary"] if hasattr(row, "keys") else row[0]

    except Exception as e:
        print(f"Error getting entity summary for {entity_name}: {e}")
        return None


def list_entities(
    entity_type: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    List all known entities, optionally filtered by type.

    Args:
        entity_type: Optional filter by type ('token', 'user', 'strategy', 'other')
        limit: Maximum number of entities to return

    Returns:
        List of dicts with keys: name, type, summary, facts_count
    """
    db = get_db()

    try:
        with db.get_cursor() as cursor:
            if entity_type:
                rows = cursor.execute(
                    """
                    SELECT e.id, e.name, e.type, e.summary,
                           (SELECT COUNT(*) FROM entity_mentions em WHERE em.entity_id = e.id) as facts_count
                    FROM entities e
                    WHERE e.type = ?
                    ORDER BY e.updated_at DESC
                    LIMIT ?
                    """,
                    (entity_type, limit)
                ).fetchall()
            else:
                rows = cursor.execute(
                    """
                    SELECT e.id, e.name, e.type, e.summary,
                           (SELECT COUNT(*) FROM entity_mentions em WHERE em.entity_id = e.id) as facts_count
                    FROM entities e
                    ORDER BY e.updated_at DESC
                    LIMIT ?
                    """,
                    (limit,)
                ).fetchall()

        results = []
        for row in rows:
            results.append({
                "name": row["name"] if hasattr(row, "keys") else row[1],
                "type": row["type"] if hasattr(row, "keys") else row[2],
                "summary": row["summary"] if hasattr(row, "keys") else row[3],
                "facts_count": row["facts_count"] if hasattr(row, "keys") else row[4],
            })

        return results

    except Exception as e:
        print(f"Error listing entities: {e}")
        return []


def get_entity_facts(
    entity_name: str,
    k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Get facts mentioning this entity from entity_mentions table.

    Args:
        entity_name: Entity name to look up
        k: Number of facts to return

    Returns:
        List of dicts with keys: fact_id, content, timestamp, source
    """
    db = get_db()

    try:
        with db.get_cursor() as cursor:
            # First get entity ID
            entity_row = cursor.execute(
                "SELECT id FROM entities WHERE name = ?",
                (entity_name,)
            ).fetchone()

            if not entity_row:
                return []

            entity_id = entity_row["id"] if hasattr(entity_row, "keys") else entity_row[0]

            # Get facts mentioning this entity
            rows = cursor.execute(
                """
                SELECT f.id, f.content, f.timestamp, f.source
                FROM facts f
                INNER JOIN entity_mentions em ON em.fact_id = f.id
                WHERE em.entity_id = ? AND f.is_active = 1
                ORDER BY f.timestamp DESC
                LIMIT ?
                """,
                (entity_id, k)
            ).fetchall()

        results = []
        for row in rows:
            results.append({
                "fact_id": row["id"] if hasattr(row, "keys") else row[0],
                "content": row["content"] if hasattr(row, "keys") else row[1],
                "timestamp": row["timestamp"] if hasattr(row, "keys") else row[2],
                "source": row["source"] if hasattr(row, "keys") else row[3],
            })

        return results

    except Exception as e:
        print(f"Error getting entity facts for {entity_name}: {e}")
        return []


def on_fact_stored(fact_id: int, content: str, entities: List[str]) -> None:
    """
    Hook called after retain_fact() to update entity profiles.

    This function is called by retain.py after a fact is stored to automatically
    update entity profiles with the new fact.

    Args:
        fact_id: ID of stored fact
        content: Fact content
        entities: List of entity names mentioned in fact
    """
    for entity in entities:
        # Only update profile if entity already exists
        profile = get_entity_profile(entity)
        if profile:
            update_entity_profile(entity, content)

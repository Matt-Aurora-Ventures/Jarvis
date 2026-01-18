#!/usr/bin/env python3
"""
Changelog Generator for JARVIS

Automatically generates CHANGELOG.md from git commit history.

Features:
- Parses conventional commits (feat, fix, docs, etc.)
- Groups by category
- Links to commits
- Supports version tagging

Usage:
    python scripts/generate_changelog.py [--since <tag>] [--output <file>]

Examples:
    python scripts/generate_changelog.py
    python scripts/generate_changelog.py --since v1.0.0
    python scripts/generate_changelog.py --output docs/CHANGELOG.md
"""

import argparse
import re
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Conventional commit categories
COMMIT_CATEGORIES = {
    "feat": ("Features", "New features and capabilities"),
    "fix": ("Bug Fixes", "Bug fixes and corrections"),
    "docs": ("Documentation", "Documentation updates"),
    "perf": ("Performance", "Performance improvements"),
    "security": ("Security", "Security fixes and improvements"),
    "refactor": ("Refactoring", "Code refactoring"),
    "test": ("Testing", "Test additions and improvements"),
    "chore": ("Chores", "Maintenance and tooling"),
    "build": ("Build", "Build system changes"),
    "ci": ("CI/CD", "Continuous integration updates"),
    "style": ("Style", "Code style changes"),
    "deps": ("Dependencies", "Dependency updates"),
}

# Emoji mapping for categories
CATEGORY_EMOJI = {
    "feat": "",
    "fix": "",
    "docs": "",
    "perf": "",
    "security": "",
    "refactor": "",
    "test": "",
    "chore": "",
    "build": "",
    "ci": "",
    "style": "",
    "deps": "",
}


def run_git_command(cmd: List[str]) -> str:
    """Run a git command and return output."""
    result = subprocess.run(
        ["git"] + cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1]
    )
    return result.stdout.strip()


def get_commits_since(since: Optional[str] = None) -> List[Dict]:
    """
    Get commits since a specific tag/commit or all commits.

    Returns list of dicts with:
    - hash: commit hash
    - short_hash: abbreviated hash
    - author: author name
    - date: commit date
    - message: commit message
    """
    # Build git log command
    format_str = "%H|%h|%an|%ad|%s"
    cmd = ["log", f"--pretty=format:{format_str}", "--date=short"]

    if since:
        cmd.append(f"{since}..HEAD")

    output = run_git_command(cmd)

    if not output:
        return []

    commits = []
    for line in output.split("\n"):
        if "|" not in line:
            continue

        parts = line.split("|")
        if len(parts) >= 5:
            commits.append({
                "hash": parts[0],
                "short_hash": parts[1],
                "author": parts[2],
                "date": parts[3],
                "message": parts[4],
            })

    return commits


def parse_conventional_commit(message: str) -> Tuple[str, str, str, bool]:
    """
    Parse a conventional commit message.

    Returns:
    - type: commit type (feat, fix, etc.)
    - scope: optional scope
    - description: commit description
    - breaking: whether it's a breaking change
    """
    # Pattern: type(scope)!: description
    pattern = r"^(\w+)(?:\(([^)]+)\))?(!)?:\s*(.+)$"
    match = re.match(pattern, message)

    if match:
        commit_type = match.group(1).lower()
        scope = match.group(2) or ""
        breaking = match.group(3) == "!"
        description = match.group(4)
        return commit_type, scope, description, breaking

    # Fallback for non-conventional commits
    return "other", "", message, False


def categorize_commits(commits: List[Dict]) -> Dict[str, List[Dict]]:
    """Categorize commits by type."""
    categorized = defaultdict(list)

    for commit in commits:
        commit_type, scope, description, breaking = parse_conventional_commit(commit["message"])

        # Add parsed info to commit
        commit["type"] = commit_type
        commit["scope"] = scope
        commit["description"] = description
        commit["breaking"] = breaking

        # Map to category
        if commit_type in COMMIT_CATEGORIES:
            categorized[commit_type].append(commit)
        else:
            categorized["other"].append(commit)

    return dict(categorized)


def get_latest_tag() -> Optional[str]:
    """Get the most recent git tag."""
    output = run_git_command(["describe", "--tags", "--abbrev=0"])
    return output if output else None


def get_repo_url() -> Optional[str]:
    """Get the repository URL from git remote."""
    output = run_git_command(["remote", "get-url", "origin"])

    if not output:
        return None

    # Convert SSH URL to HTTPS
    if output.startswith("git@"):
        output = output.replace(":", "/").replace("git@", "https://")

    # Remove .git suffix
    if output.endswith(".git"):
        output = output[:-4]

    return output


def generate_changelog(
    commits: List[Dict],
    version: str = "Unreleased",
    repo_url: Optional[str] = None
) -> str:
    """Generate changelog markdown."""
    categorized = categorize_commits(commits)

    lines = []

    # Header
    date = datetime.now().strftime("%Y-%m-%d")
    lines.append(f"## [{version}] - {date}")
    lines.append("")

    # Breaking changes first
    breaking_commits = [c for c in commits if c.get("breaking")]
    if breaking_commits:
        lines.append("### BREAKING CHANGES")
        lines.append("")
        for commit in breaking_commits:
            scope = f"**{commit['scope']}**: " if commit['scope'] else ""
            commit_link = f"[{commit['short_hash']}]({repo_url}/commit/{commit['hash']})" if repo_url else commit['short_hash']
            lines.append(f"- {scope}{commit['description']} ({commit_link})")
        lines.append("")

    # Other categories
    for commit_type, (category_name, _) in COMMIT_CATEGORIES.items():
        if commit_type not in categorized:
            continue

        type_commits = categorized[commit_type]
        emoji = CATEGORY_EMOJI.get(commit_type, "")

        lines.append(f"### {emoji} {category_name}")
        lines.append("")

        for commit in type_commits:
            scope = f"**{commit['scope']}**: " if commit['scope'] else ""
            if repo_url:
                commit_link = f"[{commit['short_hash']}]({repo_url}/commit/{commit['hash']})"
            else:
                commit_link = commit['short_hash']
            lines.append(f"- {scope}{commit['description']} ({commit_link})")

        lines.append("")

    # Other commits
    if "other" in categorized:
        lines.append("### Other")
        lines.append("")
        for commit in categorized["other"]:
            if repo_url:
                commit_link = f"[{commit['short_hash']}]({repo_url}/commit/{commit['hash']})"
            else:
                commit_link = commit['short_hash']
            lines.append(f"- {commit['message']} ({commit_link})")
        lines.append("")

    return "\n".join(lines)


def generate_full_changelog(since: Optional[str] = None, version: str = "Unreleased") -> str:
    """Generate complete changelog document."""
    repo_url = get_repo_url()
    commits = get_commits_since(since)

    if not commits:
        return "# Changelog\n\nNo changes recorded.\n"

    # Header
    lines = [
        "# Changelog",
        "",
        "All notable changes to JARVIS will be documented in this file.",
        "",
        "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),",
        "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).",
        "",
    ]

    # Changelog content
    changelog_content = generate_changelog(commits, version, repo_url)
    lines.append(changelog_content)

    # Footer
    lines.extend([
        "---",
        "",
        f"*Generated automatically on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC*",
    ])

    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate changelog from git commits")
    parser.add_argument(
        "--since",
        help="Generate changelog since this tag/commit (default: all commits)"
    )
    parser.add_argument(
        "--version",
        default="Unreleased",
        help="Version string for this release (default: Unreleased)"
    )
    parser.add_argument(
        "--output",
        default="CHANGELOG.md",
        help="Output file path (default: CHANGELOG.md)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print changelog without writing to file"
    )

    args = parser.parse_args()

    # Determine since tag
    since = args.since
    if since is None:
        since = get_latest_tag()
        if since:
            print(f"Generating changelog since {since}")
        else:
            print("Generating changelog for all commits")

    # Generate changelog
    changelog = generate_full_changelog(since, args.version)

    if args.dry_run:
        print(changelog)
    else:
        output_path = Path(__file__).resolve().parents[1] / args.output
        output_path.write_text(changelog, encoding="utf-8")
        print(f"Changelog written to {output_path}")

        # Count commits
        commits = get_commits_since(since)
        print(f"Included {len(commits)} commits")


if __name__ == "__main__":
    main()

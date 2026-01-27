#!/usr/bin/env python3
"""Auto-skill discovery helper for skills.sh.

Usage:
  python scripts/skill_autodiscovery.py "task description" --install
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from typing import List, Tuple

SKILLS_FIND_CMD = ["npx", "-y", "skills@latest", "find"]
SKILLS_ADD_CMD = ["npx", "-y", "skills@latest", "add"]


def run_find(query: str) -> Tuple[List[Tuple[str, str]], str]:
    cmd = SKILLS_FIND_CMD + [query]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = (result.stdout or "") + "\n" + (result.stderr or "")

    # Prefer parsing skills.sh URLs (normalized, hyphenated skill names)
    url_pattern = re.compile(r"https?://skills\.sh/([^/]+)/([^/]+)/([^\s]+)")
    matches = []
    for owner, repo, skill in url_pattern.findall(output):
        matches.append((f"{owner}/{repo}", skill))

    # De-dup while preserving order
    seen = set()
    deduped = []
    for repo, skill in matches:
        key = (repo, skill)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(key)

    return deduped, output


def install_skills(skills: List[Tuple[str, str]]) -> None:
    for repo, skill in skills:
        cmd = SKILLS_ADD_CMD + [repo, "--skill", skill, "-g", "-y"]
        subprocess.run(cmd, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-discover skills for a task")
    parser.add_argument("query", nargs="*", help="Task description or keywords")
    parser.add_argument("--install", action="store_true", help="Auto-install suggested skills")
    parser.add_argument("--limit", type=int, default=5, help="Max number of skills to return/install")
    args = parser.parse_args()

    query = " ".join(args.query).strip() or os.getenv("TASK", "").strip()
    if not query:
        print("No query provided.")
        return 1

    matches, raw = run_find(query)
    if not matches:
        print("No skills found.")
        return 0

    matches = matches[: max(args.limit, 1)]
    for repo, skill in matches:
        print(f"{repo}@{skill}")

    if args.install or os.getenv("SKILL_AUTODISCOVERY_INSTALL", "").lower() in ("1", "true", "yes", "on"):
        install_skills(matches)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
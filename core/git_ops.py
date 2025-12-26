"""
Git operations helper for Jarvis.

Provides safe wrappers for inspecting repository state, staging filtered files,
committing with mission-aware messages, and pushing changes. Designed so the
daemon/missions can keep the working tree tidy without touching secrets or
volatile paths.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from core import state

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_THROTTLE_SECONDS = 60 * 60 * 3  # 3 hours

EXCLUDE_PREFIXES = (
    "venv/",
    "secrets/",
    ".git/",
    "lifeos/logs/",
    "lifeos/memory/",
    "lifeos/reports/",
    "data/notes/raw/",
    "data/missions/",
)


def _run_git(args: List[str], capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command within the repo root."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        capture_output=capture,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


@dataclass
class GitStatus:
    branch: str = "unknown"
    upstream: Optional[str] = None
    ahead: int = 0
    behind: int = 0
    staged: List[str] = field(default_factory=list)
    unstaged: List[str] = field(default_factory=list)
    untracked: List[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not (self.staged or self.unstaged or self.untracked)


def _parse_branch_status(summary_line: str) -> Dict[str, str]:
    """Parse the first line of `git status -sb` for branch/upstream info."""
    # Example: ## main...origin/main [ahead 1, behind 2]
    data: Dict[str, str] = {}
    if not summary_line.startswith("##"):
        return data
    parts = summary_line[2:].strip().split()
    if parts:
        branch_info = parts[0]
        if "..." in branch_info:
            branch, upstream = branch_info.split("...", 1)
            data["branch"] = branch
            data["upstream"] = upstream
        else:
            data["branch"] = branch_info
    if "[" in summary_line and "]" in summary_line:
        bracket = summary_line[summary_line.index("[") + 1 : summary_line.index("]")]
        for item in bracket.split(","):
            item = item.strip()
            if item.startswith("ahead"):
                data["ahead"] = item.split()[1]
            if item.startswith("behind"):
                data["behind"] = item.split()[1]
    return data


def get_status() -> GitStatus:
    """Return a parsed status snapshot."""
    status = GitStatus()
    summary = _run_git(["status", "-sb"]).stdout.splitlines()
    if summary:
        branch_data = _parse_branch_status(summary[0])
        status.branch = branch_data.get("branch", status.branch)
        status.upstream = branch_data.get("upstream")
        status.ahead = int(branch_data.get("ahead", status.ahead or 0))
        status.behind = int(branch_data.get("behind", status.behind or 0))

    details_output = _run_git(["status", "--porcelain"]).stdout.splitlines()
    for line in details_output:
        if not line:
            continue
        code = line[:2]
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip()
        if code.startswith("??"):
            status.untracked.append(path)
            continue
        if code[0] != " ":
            status.staged.append(path)
        if code[1] != " ":
            status.unstaged.append(path)
    return status


def _filter_paths(paths: Iterable[str]) -> List[str]:
    filtered = []
    for path in paths:
        normalized = path.replace("\\", "/")
        if any(normalized.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
            continue
        filtered.append(path)
    return filtered


def stage_paths(paths: Iterable[str]) -> bool:
    paths = list(paths)
    if not paths:
        return False
    _run_git(["add", "--"] + paths)
    return True


def stage_all_filtered() -> List[str]:
    status = get_status()
    candidates = set(status.staged + status.unstaged + status.untracked)
    allowed = _filter_paths(candidates)
    if not allowed:
        return []
    stage_paths(sorted(allowed))
    return allowed


def commit(message: str, allow_empty: bool = False) -> Optional[str]:
    args = ["commit", "-m", message]
    if allow_empty:
        args.append("--allow-empty")
    result = _run_git(args, capture=True, check=False)
    if result.returncode != 0:
        if "nothing to commit" in result.stdout.lower() or "nothing to commit" in result.stderr.lower():
            return None
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return get_last_commit_hash()


def get_last_commit_hash(short: bool = True) -> Optional[str]:
    args = ["rev-parse", "HEAD"]
    if short:
        args.insert(1, "--short")
    result = _run_git(args, capture=True, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def push(remote: str = "origin", branch: Optional[str] = None) -> bool:
    if not branch:
        branch = get_current_branch()
    result = _run_git(["push", remote, branch], capture=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return True


def get_current_branch() -> str:
    result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    return result.stdout.strip()


def auto_commit(task_name: str, summary: str = "", push_after: bool = True, dry_run: bool = False) -> Dict[str, str]:
    """
    Stage filtered files, commit with a generated message, optionally push.

    Returns a dict describing the action taken.
    """
    status = get_status()
    if status.is_clean:
        return {"status": "clean"}

    staged_files = stage_all_filtered()
    if not staged_files:
        return {"status": "skipped", "reason": "No eligible files to stage"}

    if dry_run:
        return {"status": "dry_run", "files": staged_files}

    timestamp = time.strftime("%Y-%m-%d %H:%M")
    summary_part = summary or f"{len(staged_files)} file(s)"
    message = f"auto({task_name}): {summary_part} [{timestamp}]"
    commit_hash = commit(message)
    if not commit_hash:
        return {"status": "skipped", "reason": "Nothing to commit after staging"}

    result: Dict[str, str] = {"status": "committed", "commit": commit_hash, "files": ", ".join(staged_files)}
    if push_after:
        push()
        result["pushed"] = "true"
    return result


def revert_last_commit(keep_changes: bool = True) -> None:
    args = ["reset", "--soft" if keep_changes else "--hard", "HEAD~1"]
    _run_git(args)


def auto_commit_with_state(
    task_name: str,
    summary: str = "",
    push_after: bool = True,
    dry_run: bool = False,
    throttle_seconds: int = DEFAULT_THROTTLE_SECONDS,
) -> Dict[str, str]:
    """
    Wrapper around auto_commit that respects a throttle stored in state.json.
    """
    now = time.time()
    repo_state = state.read_state()
    last_ts = float(repo_state.get("git_last_auto_commit_ts", 0))
    if not dry_run and (now - last_ts) < throttle_seconds:
        return {
            "status": "throttled",
            "seconds_remaining": int(throttle_seconds - (now - last_ts)),
        }

    result = auto_commit(task_name, summary=summary, push_after=push_after, dry_run=dry_run)
    if not dry_run and result.get("status") == "committed":
        state.update_state(
            git_last_auto_commit_ts=now,
            git_last_auto_commit={
                "task": task_name,
                "summary": summary,
                "commit": result.get("commit"),
            },
        )
    return result


__all__ = [
    "GitStatus",
    "get_status",
    "stage_paths",
    "stage_all_filtered",
    "commit",
    "push",
    "auto_commit",
    "auto_commit_with_state",
    "revert_last_commit",
    "get_current_branch",
    "get_last_commit_hash",
]

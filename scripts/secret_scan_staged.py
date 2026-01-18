#!/usr/bin/env python3
"""Block pushes that include staged secrets."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


SECRET_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"), "Private Key"),
    (re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}"), "AWS Access Key"),
    (re.compile(r"aws_secret_access_key\s*[:=]\s*['\"][A-Za-z0-9/+=]{40}['\"]", re.IGNORECASE), "AWS Secret Key"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "GitHub Token"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{22,}"), "GitHub Token"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "Slack Token"),
    (re.compile(r"sk_(?:live|test)_[A-Za-z0-9]{16,}"), "Stripe Secret"),
    (re.compile(r"sk-(?:live|test|proj|ant|or|sso)-[A-Za-z0-9-]{16,}"), "API Key"),
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "API Key"),
    (re.compile(r"SK[0-9a-fA-F]{32}"), "Twilio Secret"),
    (re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{35}\b"), "Telegram Bot Token"),
    (re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*['\"][A-Za-z0-9/+=]{20,}['\"]"), "Generic Secret"),
]

IGNORE_MARKERS = ("secret-scan:ignore", "gitleaks:allow")
PLACEHOLDER_HINTS = (
    "example",
    "placeholder",
    "changeme",
    "replace",
    "redacted",
    "dummy",
    "fake",
    "your_",
    "your-",
    "<redacted>",
    "replaceme",
)

BLOCKED_EXTENSIONS = {".pem", ".key", ".p12", ".pfx", ".crt", ".csr", ".der"}
BLOCKED_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
    ".env.test",
    "id_rsa",
    "id_ed25519",
}
ALLOWED_ENV_SUFFIXES = (".example", ".sample", ".template")

ALLOWLIST_PATHS = {
    "tests/test_vibe_coding.py",
    "tests/security_pentest.py",
}

SKIP_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".tgz",
    ".bz2",
    ".7z",
}


def run_git(args: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def get_repo_root() -> Path:
    result = run_git(["rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        print("ERROR: Not a git repository.", file=sys.stderr)
        sys.exit(2)
    return Path(result.stdout.strip())


def get_staged_files() -> List[str]:
    result = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMRT"])
    if result.returncode != 0:
        print("ERROR: Unable to read staged files.", file=sys.stderr)
        sys.exit(2)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_blocked_env_file(path: Path) -> bool:
    name = path.name.lower()
    if name == ".env":
        return True
    if name.startswith(".env."):
        return not name.endswith(ALLOWED_ENV_SUFFIXES)
    return False


def is_blocked_path(path: Path) -> bool:
    lower_parts = {part.lower() for part in path.parts}
    if {"secrets", ".secrets", "credentials"} & lower_parts:
        return True
    if path.name.lower() in BLOCKED_FILENAMES:
        return True
    if is_blocked_env_file(path):
        return True
    if path.suffix.lower() in BLOCKED_EXTENSIONS:
        return True
    return False


def should_skip_file(path: Path) -> bool:
    return path.suffix.lower() in SKIP_EXTENSIONS


def has_ignore_marker(line: str) -> bool:
    line_lower = line.lower()
    return any(marker in line_lower for marker in IGNORE_MARKERS)


def is_placeholder_line(line: str) -> bool:
    line_lower = line.lower()
    return any(hint in line_lower for hint in PLACEHOLDER_HINTS)


def is_probably_regex_line(line: str) -> bool:
    if "re.compile" in line or "regex" in line:
        return True
    stripped = line.lstrip()
    return stripped.startswith("r'") or stripped.startswith('r"') or " r'" in line or ' r"' in line


def get_staged_content(path: str) -> str | None:
    result = run_git(["show", f":{path}"])
    if result.returncode != 0:
        return None
    if "\x00" in result.stdout:
        return None
    return result.stdout


def scan_content(path: str, content: str) -> List[Tuple[str, int, str]]:
    findings = []
    for line_num, line in enumerate(content.splitlines(), start=1):
        if has_ignore_marker(line):
            continue
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(line):
                if is_placeholder_line(line) or is_probably_regex_line(line):
                    break
                findings.append((path, line_num, label))
                break
    return findings


def main() -> int:
    repo_root = get_repo_root()
    os.chdir(repo_root)

    staged_files = get_staged_files()
    if not staged_files:
        return 0

    blocked = []
    findings: List[Tuple[str, int, str]] = []

    allowlist_paths = {Path(p).as_posix() for p in ALLOWLIST_PATHS}
    allowlist_env = os.getenv("SECRET_SCAN_ALLOWLIST", "")
    if allowlist_env:
        allowlist_paths.update(p.strip() for p in allowlist_env.split(",") if p.strip())

    for path_str in staged_files:
        path = Path(path_str)
        path_posix = path.as_posix()

        if is_blocked_path(path):
            blocked.append(path_posix)
            continue

        if path_posix in allowlist_paths:
            continue

        if should_skip_file(path):
            continue

        content = get_staged_content(path_posix)
        if content is None:
            continue
        findings.extend(scan_content(path_posix, content))

    if blocked or findings:
        print("\nERROR: Potential secrets detected in staged changes.\n", file=sys.stderr)
        if blocked:
            print("Blocked sensitive files:", file=sys.stderr)
            for path in blocked:
                print(f"  - {path}", file=sys.stderr)
        if findings:
            print("\nSecret pattern matches:", file=sys.stderr)
            for path, line_num, label in findings:
                print(f"  - {path}:{line_num} ({label})", file=sys.stderr)
        print(
            "\nFix the issues before pushing. For false positives, add "
            "'secret-scan:ignore' on the line or set SECRET_SCAN_ALLOWLIST.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Git Push Notifications for Jarvis.

Sends notifications to Telegram and X when code is pushed to GitHub.
Can be called manually or integrated with git hooks.

Usage:
    from core.notifications import git_notify

    # After a git push
    await git_notify.notify_push(
        branch="main",
        commit_hash="abc123",
        message="fix: Improved error handling",
        files_changed=5
    )

    # Or use the CLI
    python -m core.notifications.git_notify --branch main --hash abc123
"""

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Paths
ROOT = Path(__file__).resolve().parents[2]
SECRETS_FILE = ROOT / "secrets" / "keys.json"


@dataclass
class GitCommitInfo:
    """Information about a git commit."""

    hash: str
    short_hash: str
    message: str
    author: str
    branch: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    repo_url: str = ""

    @classmethod
    def from_git(cls, repo_path: str = ".") -> Optional["GitCommitInfo"]:
        """Extract commit info from current git state."""
        try:
            # Get last commit info
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=format:%H|%h|%s|%an"],
                capture_output=True,
                text=True,
                cwd=repo_path,
            )
            if result.returncode != 0:
                return None

            parts = result.stdout.strip().split("|")
            if len(parts) < 4:
                return None

            full_hash, short_hash, message, author = parts[0], parts[1], parts[2], parts[3]

            # Get branch name
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=repo_path,
            )
            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"

            # Get stats
            stats_result = subprocess.run(
                ["git", "diff", "--shortstat", "HEAD~1", "HEAD"],
                capture_output=True,
                text=True,
                cwd=repo_path,
            )
            stats = stats_result.stdout.strip()

            files_changed = 0
            insertions = 0
            deletions = 0

            if stats:
                # Parse: "5 files changed, 100 insertions(+), 20 deletions(-)"
                import re
                files_match = re.search(r"(\d+) files? changed", stats)
                insert_match = re.search(r"(\d+) insertions?\(\+\)", stats)
                delete_match = re.search(r"(\d+) deletions?\(-\)", stats)

                if files_match:
                    files_changed = int(files_match.group(1))
                if insert_match:
                    insertions = int(insert_match.group(1))
                if delete_match:
                    deletions = int(delete_match.group(1))

            # Get remote URL
            remote_result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                capture_output=True,
                text=True,
                cwd=repo_path,
            )
            repo_url = ""
            if remote_result.returncode == 0:
                url = remote_result.stdout.strip()
                # Convert SSH to HTTPS if needed
                if url.startswith("git@github.com:"):
                    url = url.replace("git@github.com:", "https://github.com/")
                if url.endswith(".git"):
                    url = url[:-4]
                repo_url = url

            return cls(
                hash=full_hash,
                short_hash=short_hash,
                message=message,
                author=author,
                branch=branch,
                files_changed=files_changed,
                insertions=insertions,
                deletions=deletions,
                repo_url=repo_url,
            )

        except Exception as e:
            logger.error(f"Failed to get git info: {e}")
            return None


class GitNotifier:
    """Sends git push notifications to Telegram and X."""

    def __init__(self):
        self.telegram_token = self._load_telegram_token()
        self.telegram_chat_ids = self._load_telegram_chats()
        self.x_enabled = False  # Will enable when X integration is ready

    def _load_telegram_token(self) -> Optional[str]:
        """Load Telegram bot token."""
        # Environment first
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if token:
            return token

        # Secrets file
        if SECRETS_FILE.exists():
            try:
                with open(SECRETS_FILE) as f:
                    secrets = json.load(f)
                    return secrets.get("TELEGRAM_BOT_TOKEN")
            except Exception:
                pass

        return None

    def _load_telegram_chats(self) -> List[int]:
        """Load Telegram chat IDs to notify."""
        # Environment
        chat_ids_str = os.environ.get("TELEGRAM_CHAT_IDS", "")
        if chat_ids_str:
            try:
                return [int(x.strip()) for x in chat_ids_str.split(",") if x.strip()]
            except ValueError:
                pass

        # Config file
        config_file = ROOT / "lifeos" / "config" / "telegram_bot.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
                    return config.get("chat_ids", [])
            except Exception:
                pass

        return []

    def format_telegram_message(self, commit: GitCommitInfo) -> str:
        """Format commit info for Telegram."""
        lines = [
            "🚀 *New Push to GitHub*",
            "",
            f"📝 `{commit.message}`",
            f"🔗 Branch: `{commit.branch}`",
            f"👤 Author: {commit.author}",
            f"📊 {commit.files_changed} files (+{commit.insertions}/-{commit.deletions})",
        ]

        if commit.repo_url:
            commit_url = f"{commit.repo_url}/commit/{commit.hash}"
            lines.append(f"🔍 [View Commit]({commit_url})")

        lines.append(f"\n⏰ {commit.timestamp.strftime('%Y-%m-%d %H:%M')}")

        return "\n".join(lines)

    def format_x_message(self, commit: GitCommitInfo) -> str:
        """Format commit info for X/Twitter (280 char limit)."""
        # Keep it concise for X
        emoji = "🚀"
        if "fix" in commit.message.lower():
            emoji = "🔧"
        elif "feat" in commit.message.lower() or "add" in commit.message.lower():
            emoji = "✨"
        elif "docs" in commit.message.lower():
            emoji = "📚"

        msg = f"{emoji} {commit.message}"

        # Add branch if not main
        if commit.branch not in ("main", "master"):
            msg += f" [{commit.branch}]"

        # Add stats
        msg += f"\n📊 {commit.files_changed} files | +{commit.insertions}/-{commit.deletions}"

        # Add link if room
        if commit.repo_url and len(msg) < 220:
            short_url = commit.repo_url.replace("https://github.com/", "")
            msg += f"\n🔗 {short_url}"

        # Truncate if too long
        if len(msg) > 280:
            msg = msg[:277] + "..."

        return msg

    async def send_telegram(self, commit: GitCommitInfo) -> bool:
        """Send notification to Telegram."""
        if not self.telegram_token:
            logger.warning("No Telegram token configured")
            return False

        if not self.telegram_chat_ids:
            logger.warning("No Telegram chat IDs configured")
            return False

        message = self.format_telegram_message(commit)
        success = True

        for chat_id in self.telegram_chat_ids:
            try:
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False,
                }

                response = requests.post(url, json=payload, timeout=10)

                if response.status_code == 200:
                    logger.info(f"Sent git notification to Telegram chat {chat_id}")
                else:
                    logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                    success = False

            except Exception as e:
                logger.error(f"Failed to send Telegram notification: {e}")
                success = False

        return success

    async def send_x(self, commit: GitCommitInfo) -> bool:
        """Send notification to X/Twitter."""
        if not self.x_enabled:
            logger.debug("X notifications not enabled")
            return False

        # TODO: Implement X posting when ready
        # Will use the X integration module
        try:
            from core.integrations.x_integration import post_tweet
            message = self.format_x_message(commit)
            return await post_tweet(message)
        except ImportError:
            logger.debug("X integration not available")
            return False
        except Exception as e:
            logger.error(f"Failed to send X notification: {e}")
            return False

    async def notify_push(
        self,
        commit: Optional[GitCommitInfo] = None,
        send_telegram: bool = True,
        send_x: bool = False,
    ) -> Dict[str, bool]:
        """
        Send push notifications to configured channels.

        Args:
            commit: Commit info (auto-detected if None)
            send_telegram: Send to Telegram
            send_x: Send to X/Twitter

        Returns:
            Dict of channel -> success status
        """
        if commit is None:
            commit = GitCommitInfo.from_git(str(ROOT))
            if commit is None:
                logger.error("Could not get git commit info")
                return {"telegram": False, "x": False}

        results = {}

        if send_telegram:
            results["telegram"] = await self.send_telegram(commit)

        if send_x:
            results["x"] = await self.send_x(commit)

        return results


# Singleton instance
_notifier: Optional[GitNotifier] = None


def get_notifier() -> GitNotifier:
    """Get or create the global GitNotifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = GitNotifier()
    return _notifier


async def notify_push(
    branch: Optional[str] = None,
    commit_hash: Optional[str] = None,
    message: Optional[str] = None,
    send_telegram: bool = True,
    send_x: bool = False,
) -> Dict[str, bool]:
    """
    Send push notification (convenience function).

    Can either auto-detect from git or use provided values.
    """
    notifier = get_notifier()

    if all([branch, commit_hash, message]):
        # Manual commit info
        commit = GitCommitInfo(
            hash=commit_hash,
            short_hash=commit_hash[:7] if commit_hash else "",
            message=message,
            author="Jarvis",
            branch=branch,
        )
    else:
        # Auto-detect from git
        commit = GitCommitInfo.from_git(str(ROOT))

    if commit is None:
        return {"telegram": False, "x": False}

    return await notifier.notify_push(commit, send_telegram, send_x)


def notify_push_sync(
    send_telegram: bool = True,
    send_x: bool = False,
) -> Dict[str, bool]:
    """Synchronous wrapper for notify_push."""
    return asyncio.run(notify_push(send_telegram=send_telegram, send_x=send_x))


# CLI support
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Send git push notifications")
    parser.add_argument("--telegram", action="store_true", default=True, help="Send to Telegram")
    parser.add_argument("--x", action="store_true", default=False, help="Send to X/Twitter")
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram")

    args = parser.parse_args()

    send_tg = args.telegram and not args.no_telegram

    print(f"Sending git push notification (Telegram: {send_tg}, X: {args.x})...")
    results = notify_push_sync(send_telegram=send_tg, send_x=args.x)
    print(f"Results: {results}")

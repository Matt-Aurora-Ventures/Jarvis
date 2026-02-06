"""
Handoff Protocol for ClawdBot Team
Matt triages and routes tasks to Jarvis or Friday.
"""
import json
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

HANDOFF_DIR = Path('/root/clawdbots/handoffs')
try:
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass  # Will fail on non-VPS environments; paths overridden at runtime

# Task routing rules
ROUTING_RULES = {
    'jarvis': [
        'infrastructure', 'server', 'deploy', 'code', 'fix', 'bug',
        'trading', 'solana', 'wallet', 'treasury', 'api', 'database',
        'automation', 'script', 'ssh', 'vps', 'docker', 'systemd',
        'monitor', 'health', 'log', 'error', 'debug', 'performance'
    ],
    'friday': [
        'content', 'marketing', 'brand', 'copy', 'social', 'tweet',
        'post', 'campaign', 'email', 'newsletter', 'design', 'creative',
        'announcement', 'pr', 'community', 'audience', 'engagement',
        'linkedin', 'twitter', 'blog', 'write', 'edit', 'review'
    ]
}


class HandoffProtocol:
    def __init__(self, bot_name: str):
        self.bot_name = bot_name
        self.pending_file = HANDOFF_DIR / 'pending.json'
        self.history_file = HANDOFF_DIR / 'history.json'

    def route_task(self, task_description: str, from_user: str = 'human') -> dict:
        """Matt routes a task to the appropriate bot."""
        task_lower = task_description.lower()

        jarvis_score = sum(1 for kw in ROUTING_RULES['jarvis'] if kw in task_lower)
        friday_score = sum(1 for kw in ROUTING_RULES['friday'] if kw in task_lower)

        if jarvis_score > friday_score:
            target = 'jarvis'
        elif friday_score > jarvis_score:
            target = 'friday'
        else:
            target = 'jarvis'  # default to Jarvis for ambiguous tasks

        handoff = {
            'id': datetime.now().strftime('%Y%m%d_%H%M%S'),
            'from': self.bot_name,
            'to': target,
            'task': task_description,
            'requested_by': from_user,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'completed_at': None,
            'result': None
        }

        self._save_handoff(handoff)
        return handoff

    def check_incoming(self) -> list:
        """Check for tasks assigned to this bot."""
        pending = self._load_pending()
        return [h for h in pending if h['to'] == self.bot_name and h['status'] == 'pending']

    def complete_handoff(self, handoff_id: str, result: str):
        """Mark a handoff as complete."""
        pending = self._load_pending()
        for h in pending:
            if h['id'] == handoff_id:
                h['status'] = 'completed'
                h['completed_at'] = datetime.now().isoformat()
                h['result'] = result
                self._archive(h)
                break
        remaining = [h for h in pending if h['id'] != handoff_id]
        self._save_all_pending(remaining)

    def filter_input(self, raw_input: str) -> str:
        """Strip logs, tool outputs, and noise from handoff input."""
        lines = raw_input.split('\n')
        filtered = []
        skip_patterns = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'Traceback',
                        '>>>>', '<<<<', '====', '----', 'tool_result']
        for line in lines:
            if not any(p in line for p in skip_patterns):
                filtered.append(line)
        return '\n'.join(filtered).strip()

    def _save_handoff(self, handoff: dict):
        pending = self._load_pending()
        pending.append(handoff)
        self._save_all_pending(pending)

    def _load_pending(self) -> list:
        if self.pending_file.exists():
            try:
                return json.loads(self.pending_file.read_text())
            except json.JSONDecodeError:
                return []
        return []

    def _save_all_pending(self, pending: list):
        self.pending_file.write_text(json.dumps(pending, indent=2))

    def _archive(self, handoff: dict):
        history = []
        if self.history_file.exists():
            try:
                history = json.loads(self.history_file.read_text())
            except json.JSONDecodeError:
                pass
        history.append(handoff)
        # Keep last 100
        if len(history) > 100:
            history = history[-100:]
        self.history_file.write_text(json.dumps(history, indent=2))


class FridayInterjection:
    """Friday can interject on high-risk commands before execution."""

    HIGH_RISK_PATTERNS = [
        'delete', 'drop', 'rm -rf', 'format', 'wipe',
        'transfer', 'send sol', 'withdraw',
        'publish', 'post public', 'go live',
        'shutdown', 'reboot', 'kill'
    ]

    @staticmethod
    def should_interject(command: str) -> bool:
        cmd_lower = command.lower()
        return any(pattern in cmd_lower for pattern in FridayInterjection.HIGH_RISK_PATTERNS)

    @staticmethod
    def create_review_request(command: str, requester: str) -> dict:
        return {
            'type': 'interjection',
            'command': command,
            'requester': requester,
            'reason': 'High-risk action detected - requires review',
            'timestamp': datetime.now().isoformat()
        }

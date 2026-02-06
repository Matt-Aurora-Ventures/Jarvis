"""
Action Confirmation System for ClawdBots
High-risk actions require human approval via Telegram before execution.
"""
import json
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)

CONFIRMATIONS_DIR = Path('/root/clawdbots/handoffs/confirmations')
CONFIRMATIONS_DIR.mkdir(parents=True, exist_ok=True)


class RiskLevel(Enum):
    LOW = 'low'           # Auto-execute
    MEDIUM = 'medium'     # Log and execute
    HIGH = 'high'         # Require approval
    CRITICAL = 'critical' # Require approval + cooldown


# Action risk matrix
RISK_MATRIX = {
    # Trading actions
    'buy_token': RiskLevel.HIGH,
    'sell_token': RiskLevel.HIGH,
    'transfer_sol': RiskLevel.CRITICAL,
    'withdraw': RiskLevel.CRITICAL,

    # Infrastructure
    'restart_service': RiskLevel.MEDIUM,
    'deploy_code': RiskLevel.HIGH,
    'delete_file': RiskLevel.HIGH,
    'modify_config': RiskLevel.MEDIUM,

    # Content
    'publish_tweet': RiskLevel.MEDIUM,
    'send_email': RiskLevel.HIGH,
    'post_public': RiskLevel.HIGH,

    # System
    'reboot_server': RiskLevel.CRITICAL,
    'update_packages': RiskLevel.MEDIUM,
    'change_permissions': RiskLevel.HIGH,
}


class ActionConfirmation:
    def __init__(self, bot_name: str, telegram_bot=None, admin_chat_id: str = None):
        self.bot_name = bot_name
        self.telegram_bot = telegram_bot
        self.admin_chat_id = admin_chat_id
        self.pending_file = CONFIRMATIONS_DIR / 'pending.json'
        self.history_file = CONFIRMATIONS_DIR / 'history.json'

    def get_risk_level(self, action: str) -> RiskLevel:
        """Determine risk level for an action."""
        # Exact match
        if action in RISK_MATRIX:
            return RISK_MATRIX[action]

        # Keyword matching
        action_lower = action.lower()
        for key, level in RISK_MATRIX.items():
            if key.replace('_', ' ') in action_lower or key in action_lower:
                return level

        return RiskLevel.LOW

    async def request_confirmation(self, action: str, details: str = '',
                                    timeout_minutes: int = 30) -> dict:
        """Request confirmation for a high-risk action."""
        risk = self.get_risk_level(action)

        confirmation = {
            'id': datetime.now().strftime('%Y%m%d_%H%M%S_%f'),
            'bot': self.bot_name,
            'action': action,
            'details': details,
            'risk_level': risk.value,
            'status': 'auto_approved' if risk in (RiskLevel.LOW, RiskLevel.MEDIUM) else 'pending',
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(minutes=timeout_minutes)).isoformat(),
            'approved_by': None,
            'approved_at': None
        }

        if risk in (RiskLevel.LOW, RiskLevel.MEDIUM):
            # Auto-approve low/medium risk
            confirmation['approved_by'] = 'auto'
            confirmation['approved_at'] = datetime.now().isoformat()
            self._archive(confirmation)
            return confirmation

        # HIGH/CRITICAL: Save as pending and notify
        self._save_pending(confirmation)

        if self.telegram_bot and self.admin_chat_id:
            risk_emoji = '🟡' if risk == RiskLevel.HIGH else '🔴'
            msg = (
                f"{risk_emoji} **ACTION REQUIRES APPROVAL**\n\n"
                f"Bot: {self.bot_name}\n"
                f"Action: `{action}`\n"
                f"Risk: {risk.value.upper()}\n"
                f"Details: {details}\n\n"
                f"Reply `/approve {confirmation['id']}` or `/deny {confirmation['id']}`\n"
                f"Expires in {timeout_minutes} minutes"
            )
            try:
                await self.telegram_bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=msg, parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to send confirmation request: {e}")

        return confirmation

    def approve(self, confirmation_id: str, approved_by: str = 'human') -> bool:
        """Approve a pending action."""
        pending = self._load_pending()
        for c in pending:
            if c['id'] == confirmation_id:
                c['status'] = 'approved'
                c['approved_by'] = approved_by
                c['approved_at'] = datetime.now().isoformat()
                self._archive(c)
                remaining = [x for x in pending if x['id'] != confirmation_id]
                self._save_all_pending(remaining)
                return True
        return False

    def deny(self, confirmation_id: str, denied_by: str = 'human') -> bool:
        """Deny a pending action."""
        pending = self._load_pending()
        for c in pending:
            if c['id'] == confirmation_id:
                c['status'] = 'denied'
                c['approved_by'] = denied_by
                c['approved_at'] = datetime.now().isoformat()
                self._archive(c)
                remaining = [x for x in pending if x['id'] != confirmation_id]
                self._save_all_pending(remaining)
                return True
        return False

    def is_approved(self, confirmation_id: str) -> bool:
        """Check if a confirmation has been approved."""
        pending = self._load_pending()
        for c in pending:
            if c['id'] == confirmation_id:
                if c['status'] == 'approved':
                    return True
                # Check expiry
                if datetime.fromisoformat(c['expires_at']) < datetime.now():
                    c['status'] = 'expired'
                    self._archive(c)
                    remaining = [x for x in pending if x['id'] != confirmation_id]
                    self._save_all_pending(remaining)
                return False
        return False

    def get_pending(self) -> list:
        """Get all pending confirmations."""
        return [c for c in self._load_pending() if c['status'] == 'pending']

    def _save_pending(self, confirmation: dict):
        pending = self._load_pending()
        pending.append(confirmation)
        self._save_all_pending(pending)

    def _load_pending(self) -> list:
        if self.pending_file.exists():
            try:
                return json.loads(self.pending_file.read_text())
            except (json.JSONDecodeError, FileNotFoundError):
                return []
        return []

    def _save_all_pending(self, pending: list):
        self.pending_file.write_text(json.dumps(pending, indent=2))

    def _archive(self, confirmation: dict):
        history = []
        if self.history_file.exists():
            try:
                history = json.loads(self.history_file.read_text())
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        history.append(confirmation)
        if len(history) > 200:
            history = history[-200:]
        self.history_file.write_text(json.dumps(history, indent=2))

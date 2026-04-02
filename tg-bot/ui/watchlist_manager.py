"""
Watchlist Manager for Telegram UI.

Provides functionality for:
- Add/remove tokens to custom watchlists
- View watchlist with current prices
- Persistent storage (JSON)
- Price alert monitoring
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WatchlistToken:
    """A token in the watchlist."""
    address: str
    symbol: str
    added_at: str
    note: Optional[str] = None
    alert_price: Optional[float] = None
    alert_direction: Optional[str] = None  # "above" or "below"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "WatchlistToken":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class UserWatchlist:
    """A user's complete watchlist."""
    tokens: List[WatchlistToken]

    def to_dict(self) -> dict:
        return {"tokens": [t.to_dict() for t in self.tokens]}

    @classmethod
    def from_dict(cls, data: dict) -> "UserWatchlist":
        tokens = [WatchlistToken.from_dict(t) for t in data.get("tokens", [])]
        return cls(tokens=tokens)


class WatchlistManager:
    """
    Manages user watchlists with persistent storage.

    Features:
    - Add/remove tokens per user
    - Price alerts
    - JSON persistence
    """

    DEFAULT_STORAGE_PATH = Path.home() / ".lifeos" / "trading" / "watchlists.json"
    DEFAULT_MAX_ITEMS = 50

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        max_items: int = DEFAULT_MAX_ITEMS,
    ):
        """
        Initialize WatchlistManager.

        Args:
            storage_path: Path to JSON storage file
            max_items: Maximum tokens per user watchlist
        """
        self.storage_path = storage_path or self.DEFAULT_STORAGE_PATH
        self.max_items = max_items
        self._watchlists: Dict[int, UserWatchlist] = {}
        self._load()

    def _load(self) -> None:
        """Load watchlists from storage."""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)

            for user_id_str, wl_data in data.items():
                try:
                    user_id = int(user_id_str)
                    self._watchlists[user_id] = UserWatchlist.from_dict(wl_data)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to load watchlist for user {user_id_str}: {e}")

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse watchlists file: {e}")
        except OSError as e:
            logger.warning(f"Failed to read watchlists file: {e}")

    def save(self) -> None:
        """Save watchlists to storage."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                str(user_id): wl.to_dict()
                for user_id, wl in self._watchlists.items()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except OSError as e:
            logger.error(f"Failed to save watchlists: {e}")

    def _get_or_create_watchlist(self, user_id: int) -> UserWatchlist:
        """Get user's watchlist or create empty one."""
        if user_id not in self._watchlists:
            self._watchlists[user_id] = UserWatchlist(tokens=[])
        return self._watchlists[user_id]

    def add_token(
        self,
        user_id: int,
        token_address: str,
        token_symbol: str,
        note: Optional[str] = None,
    ) -> bool:
        """
        Add a token to user's watchlist.

        Args:
            user_id: Telegram user ID
            token_address: Token contract address
            token_symbol: Token symbol
            note: Optional note

        Returns:
            True if added, False if at limit
        """
        wl = self._get_or_create_watchlist(user_id)

        # Check if already exists - update note if so
        for token in wl.tokens:
            if token.address == token_address:
                token.note = note
                token.symbol = token_symbol
                self.save()
                return True

        # Check limit
        if len(wl.tokens) >= self.max_items:
            # Remove oldest to make room
            wl.tokens = wl.tokens[-(self.max_items - 1):]

        # Add new token
        token = WatchlistToken(
            address=token_address,
            symbol=token_symbol,
            added_at=datetime.utcnow().isoformat(),
            note=note,
        )
        wl.tokens.append(token)
        self.save()
        return True

    def remove_token(self, user_id: int, token_address: str) -> bool:
        """
        Remove a token from user's watchlist.

        Args:
            user_id: Telegram user ID
            token_address: Token contract address

        Returns:
            True if removed, False if not found
        """
        if user_id not in self._watchlists:
            return False

        wl = self._watchlists[user_id]
        original_len = len(wl.tokens)
        wl.tokens = [t for t in wl.tokens if t.address != token_address]

        if len(wl.tokens) < original_len:
            self.save()
            return True
        return False

    def clear_watchlist(self, user_id: int) -> bool:
        """
        Clear all tokens from user's watchlist.

        Args:
            user_id: Telegram user ID

        Returns:
            True if cleared
        """
        if user_id in self._watchlists:
            self._watchlists[user_id].tokens = []
            self.save()
        return True

    def get_watchlist(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get user's watchlist as list of dicts.

        Args:
            user_id: Telegram user ID

        Returns:
            List of token dicts
        """
        if user_id not in self._watchlists:
            return []
        return [t.to_dict() for t in self._watchlists[user_id].tokens]

    def set_price_alert(
        self,
        user_id: int,
        token_address: str,
        target_price: float,
        direction: str = "above",
    ) -> bool:
        """
        Set a price alert for a token.

        Args:
            user_id: Telegram user ID
            token_address: Token contract address
            target_price: Target price for alert
            direction: "above" or "below"

        Returns:
            True if set, False if token not in watchlist
        """
        if user_id not in self._watchlists:
            return False

        wl = self._watchlists[user_id]
        for token in wl.tokens:
            if token.address == token_address:
                token.alert_price = target_price
                token.alert_direction = direction
                self.save()
                return True
        return False

    def remove_alert(self, user_id: int, token_address: str) -> bool:
        """
        Remove a price alert for a token.

        Args:
            user_id: Telegram user ID
            token_address: Token contract address

        Returns:
            True if removed, False if not found
        """
        if user_id not in self._watchlists:
            return False

        wl = self._watchlists[user_id]
        for token in wl.tokens:
            if token.address == token_address:
                token.alert_price = None
                token.alert_direction = None
                self.save()
                return True
        return False

    def get_alerts(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all active alerts for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            List of alert dicts
        """
        if user_id not in self._watchlists:
            return []

        alerts = []
        for token in self._watchlists[user_id].tokens:
            if token.alert_price is not None:
                alerts.append({
                    "token_address": token.address,
                    "symbol": token.symbol,
                    "target_price": token.alert_price,
                    "direction": token.alert_direction,
                })
        return alerts

    def check_alerts(
        self,
        user_id: int,
        current_prices: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """
        Check which alerts have been triggered.

        Args:
            user_id: Telegram user ID
            current_prices: Dict of address -> current price

        Returns:
            List of triggered alert dicts
        """
        if user_id not in self._watchlists:
            return []

        triggered = []
        for token in self._watchlists[user_id].tokens:
            if token.alert_price is None:
                continue

            current = current_prices.get(token.address)
            if current is None:
                continue

            if token.alert_direction == "above" and current >= token.alert_price:
                triggered.append({
                    "token_address": token.address,
                    "symbol": token.symbol,
                    "target_price": token.alert_price,
                    "current_price": current,
                    "direction": "above",
                })
            elif token.alert_direction == "below" and current <= token.alert_price:
                triggered.append({
                    "token_address": token.address,
                    "symbol": token.symbol,
                    "target_price": token.alert_price,
                    "current_price": current,
                    "direction": "below",
                })

        return triggered

    def format_watchlist(self, user_id: int) -> str:
        """
        Format watchlist as display text.

        Args:
            user_id: Telegram user ID

        Returns:
            Formatted watchlist text
        """
        tokens = self.get_watchlist(user_id)

        if not tokens:
            return "*watchlist*\n\n_empty - add tokens with /watch <address>_"

        lines = ["*watchlist*", ""]

        for i, token in enumerate(tokens, 1):
            symbol = token.get("symbol", "???")
            address = token.get("address", "")
            short_addr = f"{address[:6]}...{address[-4:]}" if len(address) > 10 else address

            line = f"{i}. *{symbol}* `{short_addr}`"

            if token.get("note"):
                line += f"\n   _{token['note']}_"

            if token.get("alert_price"):
                direction = token.get("alert_direction", "?")
                price = token["alert_price"]
                line += f"\n   Alert: {direction} ${price:.6f}"

            lines.append(line)

        return "\n".join(lines)

    async def format_watchlist_with_prices(
        self,
        user_id: int,
        price_fetcher: Callable[[str], Any],
    ) -> str:
        """
        Format watchlist with current prices.

        Args:
            user_id: Telegram user ID
            price_fetcher: Async function to fetch price for address

        Returns:
            Formatted watchlist with prices
        """
        tokens = self.get_watchlist(user_id)

        if not tokens:
            return "*watchlist*\n\n_empty - add tokens with /watch <address>_"

        lines = ["*watchlist*", ""]

        for i, token in enumerate(tokens, 1):
            symbol = token.get("symbol", "???")
            address = token.get("address", "")

            # Fetch price
            try:
                price_data = await price_fetcher(address)
                price = price_data.get("price_usd", 0)
                change = price_data.get("change_24h", 0)

                change_emoji = "" if change >= 0 else ""
                price_str = f"${price:.6f}" if price < 1 else f"${price:.2f}"
                change_str = f"{change_emoji} {change:+.1f}%"

                line = f"{i}. *{symbol}* {price_str} {change_str}"
            except Exception as e:
                logger.debug(f"Failed to fetch price for {address}: {e}")
                line = f"{i}. *{symbol}* _price unavailable_"

            lines.append(line)

        return "\n".join(lines)


# =============================================================================
# Singleton Instance
# =============================================================================

_watchlist_manager: Optional[WatchlistManager] = None


def get_watchlist_manager() -> WatchlistManager:
    """Get the global WatchlistManager instance."""
    global _watchlist_manager
    if _watchlist_manager is None:
        _watchlist_manager = WatchlistManager()
    return _watchlist_manager


__all__ = [
    "WatchlistManager",
    "WatchlistToken",
    "UserWatchlist",
    "get_watchlist_manager",
]

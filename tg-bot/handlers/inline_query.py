"""
Telegram Inline Query Handler.

Provides inline query functionality for:
- Token search by symbol or name
- Token lookup by address
- Price queries
- Trending tokens
- Command suggestions

Components:
- InlineQueryParser: Parse raw query text into structured intent
- InlineResultGenerator: Generate InlineQueryResult objects
- InlineQueryCache: Cache results with TTL
- InlineQueryPaginator: Handle offset-based pagination
- InlineAnswerFormatter: Format final answer structure
- InlineQueryHandler: Main handler class
"""

import logging
import re
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from telegram import (
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes, InlineQueryHandler as TelegramInlineQueryHandler

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Solana address regex (base58, 32-44 chars)
SOLANA_ADDRESS_PATTERN = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')

# Telegram limits
MAX_QUERY_LENGTH = 256
MAX_RESULTS = 50
MAX_DESCRIPTION_LENGTH = 256

# Default popular tokens for suggestions
DEFAULT_TOKENS = [
    {"symbol": "SOL", "name": "Solana", "address": "So11111111111111111111111111111111111111112"},
    {"symbol": "BONK", "name": "Bonk", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
    {"symbol": "JUP", "name": "Jupiter", "address": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"},
    {"symbol": "WIF", "name": "dogwifhat", "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"},
    {"symbol": "RAY", "name": "Raydium", "address": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"},
]


# =============================================================================
# InlineQueryParser
# =============================================================================


class InlineQueryParser:
    """
    Parse inline query text into structured intent.

    Detects:
    - Token symbols (e.g., SOL, BONK)
    - Solana addresses
    - Command prefixes
    - Special queries (price, trending)
    """

    def parse(self, query: str) -> Dict[str, Any]:
        """
        Parse query string into structured intent.

        Args:
            query: Raw query text from user

        Returns:
            Dict with type, query, and additional fields
        """
        # Sanitize and normalize
        query = self._sanitize(query)

        if not query:
            return {"type": "empty", "query": ""}

        # Check for command prefix
        if query.startswith("/"):
            return self._parse_command(query)

        # Check for special keywords
        query_lower = query.lower()

        if query_lower == "trending":
            return {"type": "trending", "query": query}

        if query_lower.startswith("price "):
            return {"type": "price_lookup", "query": query[6:].strip()}

        # Check for Solana address
        if SOLANA_ADDRESS_PATTERN.match(query):
            return {"type": "token_address", "query": query}

        # Check for short partial match (less than 3 chars)
        if len(query) < 3:
            return {"type": "partial_search", "query": query}

        # Default to token symbol search
        return {"type": "token_symbol", "query": query}

    def _sanitize(self, query: str) -> str:
        """Sanitize and normalize query string."""
        if not query:
            return ""

        # Strip whitespace
        query = query.strip()

        # Truncate to max length
        if len(query) > MAX_QUERY_LENGTH:
            query = query[:MAX_QUERY_LENGTH]

        # Remove potentially dangerous characters
        query = re.sub(r'<[^>]*>', '', query)  # Remove HTML tags

        return query

    def _parse_command(self, query: str) -> Dict[str, Any]:
        """Parse command-style query."""
        parts = query[1:].split(maxsplit=1)
        command = parts[0] if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        return {
            "type": "command",
            "command": command,
            "args": args,
            "query": query,
        }


# =============================================================================
# InlineResultGenerator
# =============================================================================


class InlineResultGenerator:
    """
    Generate InlineQueryResult objects for Telegram.
    """

    def __init__(self):
        self._counter = 0

    def generate_token_result(
        self,
        token_symbol: str,
        token_name: str,
        token_address: str,
        price: float,
        change_24h: float = 0.0,
        include_buttons: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate article result for a token.

        Args:
            token_symbol: Token symbol (e.g., SOL)
            token_name: Token name (e.g., Solana)
            token_address: Token contract address
            price: Current price in USD
            change_24h: 24h price change percentage
            include_buttons: Include inline keyboard

        Returns:
            Dict representing InlineQueryResultArticle
        """
        # Generate unique ID
        result_id = self._generate_id(f"{token_symbol}_{token_address}_{price}")

        # Format price change emoji
        if change_24h >= 0:
            change_emoji = "+" if change_24h > 0 else ""
            trend = "up" if change_24h > 0 else "neutral"
        else:
            change_emoji = ""
            trend = "down"

        # Build title with emoji
        title = f"{token_symbol} - ${price:,.6f}" if price < 1 else f"{token_symbol} - ${price:,.2f}"

        # Build description
        description = f"{token_name} | {change_emoji}{change_24h:.1f}%"
        if len(description) > MAX_DESCRIPTION_LENGTH:
            description = description[:MAX_DESCRIPTION_LENGTH-3] + "..."

        # Build message content
        message_content = self.format_token_message(
            token_symbol, token_name, price, change_24h, token_address
        )

        result = {
            "type": "article",
            "id": result_id,
            "title": title,
            "description": description,
            "input_message_content": message_content,
        }

        if include_buttons:
            result["reply_markup"] = self._build_token_buttons(token_address, token_symbol)

        return result

    def generate_price_result(
        self,
        token_symbol: str,
        price: float,
    ) -> Dict[str, Any]:
        """Generate compact price-only result."""
        result_id = self._generate_id(f"price_{token_symbol}_{price}")

        price_str = f"${price:,.6f}" if price < 1 else f"${price:,.2f}"

        return {
            "type": "article",
            "id": result_id,
            "title": f"{token_symbol}: {price_str}",
            "description": f"Current price of {token_symbol}",
            "input_message_content": self.format_price_message(token_symbol, price),
        }

    def generate_trending_results(
        self,
        tokens: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Generate results for trending tokens."""
        results = []
        for token in tokens:
            result_id = self._generate_id(f"trending_{token.get('symbol', '')}")
            results.append({
                "type": "article",
                "id": result_id,
                "title": f"{token.get('symbol', 'Unknown')} - Trending",
                "description": f"{token.get('name', '')} | {token.get('change_24h', 0):.1f}%",
                "input_message_content": {
                    "message_text": f"Trending: {token.get('symbol', 'Unknown')} ({token.get('name', '')})",
                },
            })
        return results

    def generate_error_result(self, message: str) -> Dict[str, Any]:
        """Generate error result."""
        return {
            "type": "article",
            "id": self._generate_id(f"error_{message}"),
            "title": "Error - Not Found",
            "description": message[:MAX_DESCRIPTION_LENGTH],
            "input_message_content": {
                "message_text": f"Error: {message}",
            },
        }

    def generate_no_results(self, query: str) -> Dict[str, Any]:
        """Generate no results message."""
        return {
            "type": "article",
            "id": self._generate_id(f"no_results_{query}"),
            "title": "No Results Found",
            "description": f"No tokens found matching '{query}'",
            "input_message_content": {
                "message_text": f"No tokens found matching '{query}'. Try:\n- Token symbol (SOL, BONK)\n- Contract address\n- /analyze <token>",
            },
        }

    def format_token_message(
        self,
        symbol: str,
        name: str,
        price: float,
        change_24h: float,
        address: str,
    ) -> Dict[str, Any]:
        """Format token info as message content."""
        price_str = f"${price:,.6f}" if price < 1 else f"${price:,.2f}"
        change_emoji = "+" if change_24h >= 0 else ""

        message = (
            f"**{symbol}** - {name}\n\n"
            f"Price: {price_str}\n"
            f"24h: {change_emoji}{change_24h:.1f}%\n\n"
            f"Address: `{address[:8]}...{address[-6:]}`"
        )

        return {
            "message_text": message,
            "parse_mode": "Markdown",
        }

    def format_price_message(
        self,
        symbol: str,
        price: float,
    ) -> Dict[str, Any]:
        """Format price-only message."""
        price_str = f"${price:,.6f}" if price < 1 else f"${price:,.2f}"

        return {
            "message_text": f"{symbol}: {price_str}",
        }

    def format_trending_message(
        self,
        tokens: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Format trending tokens message."""
        lines = ["**Trending Tokens**\n"]

        for i, token in enumerate(tokens[:10], 1):
            symbol = token.get("symbol", "???")
            change = token.get("change_24h", 0)
            emoji = "+" if change >= 0 else ""
            lines.append(f"{i}. {symbol} ({emoji}{change:.1f}%)")

        return {
            "message_text": "\n".join(lines),
            "parse_mode": "Markdown",
        }

    def _generate_id(self, seed: str) -> str:
        """Generate unique result ID."""
        self._counter += 1
        combined = f"{seed}_{self._counter}_{time.time()}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]

    def _build_token_buttons(
        self,
        address: str,
        symbol: str,
    ) -> Dict[str, Any]:
        """Build inline keyboard for token result."""
        return {
            "inline_keyboard": [
                [
                    {"text": "Analyze", "callback_data": f"analyze_{address}"},
                    {"text": "Watch", "callback_data": f"watch_add:{address}"},
                ]
            ]
        }


# =============================================================================
# InlineQueryCache
# =============================================================================


class InlineQueryCache:
    """
    Cache inline query results with TTL support.
    """

    # Default TTLs by query type
    TTL_CONFIG = {
        "price_lookup": 30,     # 30 seconds for prices
        "token_search": 120,    # 2 minutes for searches
        "trending": 300,        # 5 minutes for trending
        "default": 60,          # 1 minute default
    }

    def __init__(
        self,
        ttl_seconds: float = 60,
        max_size: int = 1000,
    ):
        self._cache: Dict[str, Tuple[List, float]] = {}
        self._default_ttl = ttl_seconds
        self._max_size = max_size

    def get(
        self,
        query: str,
        user_id: Optional[int] = None,
    ) -> Optional[List]:
        """
        Get cached results if not expired.

        Args:
            query: Cache key (query string)
            user_id: Optional user ID for user-specific caching

        Returns:
            Cached results or None
        """
        key = self._make_key(query, user_id)

        if key not in self._cache:
            return None

        results, expiry = self._cache[key]

        if time.time() > expiry:
            del self._cache[key]
            return None

        return results

    def set(
        self,
        query: str,
        results: List,
        user_id: Optional[int] = None,
        ttl: Optional[float] = None,
    ) -> None:
        """
        Cache results with TTL.

        Args:
            query: Cache key (query string)
            results: Results to cache
            user_id: Optional user ID for user-specific caching
            ttl: Time to live in seconds (uses default if not specified)
        """
        # Evict if over max size
        if len(self._cache) >= self._max_size:
            self._evict_oldest()

        key = self._make_key(query, user_id)
        ttl = ttl if ttl is not None else self._default_ttl
        expiry = time.time() + ttl

        self._cache[key] = (results, expiry)

    def delete(self, query: str, user_id: Optional[int] = None) -> None:
        """Delete cached entry."""
        key = self._make_key(query, user_id)
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)

    def get_ttl_for_query_type(self, query_type: str) -> int:
        """Get appropriate TTL for query type."""
        return self.TTL_CONFIG.get(query_type, self.TTL_CONFIG["default"])

    def _make_key(self, query: str, user_id: Optional[int]) -> str:
        """Generate cache key."""
        normalized = query.lower().strip()
        if user_id:
            return f"{user_id}:{normalized}"
        return normalized

    def _evict_oldest(self) -> None:
        """Evict oldest entries to make room."""
        if not self._cache:
            return

        # Find and remove oldest entries (by expiry)
        sorted_keys = sorted(
            self._cache.keys(),
            key=lambda k: self._cache[k][1]
        )

        # Remove oldest 10%
        to_remove = max(1, len(sorted_keys) // 10)
        for key in sorted_keys[:to_remove]:
            del self._cache[key]


# =============================================================================
# InlineQueryPaginator
# =============================================================================


class InlineQueryPaginator:
    """
    Handle offset-based pagination for inline query results.
    """

    def __init__(self, page_size: int = 20):
        # Enforce Telegram max
        self._page_size = min(page_size, MAX_RESULTS)

    def paginate(
        self,
        results: List[Dict],
        offset: str,
    ) -> Tuple[List[Dict], str]:
        """
        Get page of results based on offset.

        Args:
            results: All results
            offset: Offset string (empty for first page)

        Returns:
            Tuple of (page_results, next_offset)
        """
        # Parse offset
        try:
            start = int(offset) if offset else 0
        except ValueError:
            start = 0

        if start < 0:
            start = 0

        if start >= len(results):
            return [], ""

        # Get page
        end = start + self._page_size
        page = results[start:end]

        # Determine next offset
        if end < len(results):
            next_offset = str(end)
        else:
            next_offset = ""

        return page, next_offset


# =============================================================================
# InlineAnswerFormatter
# =============================================================================


class InlineAnswerFormatter:
    """
    Format final inline query answers for Telegram.
    """

    def format_answer(
        self,
        inline_query_id: str,
        results: List[Dict],
        cache_time: int = 60,
        next_offset: str = "",
        is_personal: bool = False,
        switch_pm_text: Optional[str] = None,
        switch_pm_parameter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Format answer for Telegram answerInlineQuery.

        Args:
            inline_query_id: Query ID from Telegram
            results: List of result dicts
            cache_time: How long to cache (seconds)
            next_offset: Offset for next page
            is_personal: Whether results are personal
            switch_pm_text: Text for PM switch button
            switch_pm_parameter: Parameter for PM switch

        Returns:
            Dict with all answer parameters
        """
        answer = {
            "inline_query_id": inline_query_id,
            "results": results,
            "cache_time": cache_time,
            "is_personal": is_personal,
        }

        if next_offset:
            answer["next_offset"] = next_offset

        if switch_pm_text:
            answer["switch_pm_text"] = switch_pm_text
            if switch_pm_parameter:
                answer["switch_pm_parameter"] = switch_pm_parameter

        return answer

    def to_telegram_result(self, result_dict: Dict[str, Any]) -> InlineQueryResultArticle:
        """
        Convert result dict to Telegram type.

        Args:
            result_dict: Result as dict

        Returns:
            InlineQueryResultArticle
        """
        input_content = result_dict.get("input_message_content", {})

        content = InputTextMessageContent(
            message_text=input_content.get("message_text", ""),
            parse_mode=input_content.get("parse_mode"),
        )

        return InlineQueryResultArticle(
            id=result_dict["id"],
            title=result_dict["title"],
            description=result_dict.get("description"),
            input_message_content=content,
        )


# =============================================================================
# InlineQueryRateLimiter
# =============================================================================


class InlineQueryRateLimiter:
    """
    Rate limiting for inline queries per user.
    """

    def __init__(
        self,
        max_requests: int = 30,
        window_seconds: int = 60,
    ):
        self._max_requests = max_requests
        self._window = window_seconds
        self._requests: Dict[int, List[float]] = {}

    def check(self, user_id: int) -> bool:
        """
        Check if user can make a request.

        Args:
            user_id: Telegram user ID

        Returns:
            True if allowed, False if rate limited
        """
        now = time.time()

        # Clean old requests
        if user_id in self._requests:
            self._requests[user_id] = [
                t for t in self._requests[user_id]
                if now - t < self._window
            ]
        else:
            self._requests[user_id] = []

        # Check limit
        if len(self._requests[user_id]) >= self._max_requests:
            return False

        # Record request
        self._requests[user_id].append(now)
        return True


# =============================================================================
# InlineQueryHandler
# =============================================================================


class InlineQueryHandler:
    """
    Main handler for inline queries.
    """

    def __init__(self):
        self.parser = InlineQueryParser()
        self.generator = InlineResultGenerator()
        self.cache = InlineQueryCache()
        self.paginator = InlineQueryPaginator()
        self.formatter = InlineAnswerFormatter()
        self.rate_limiter = InlineQueryRateLimiter()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        Handle incoming inline query.

        Args:
            update: Telegram Update object
            context: Telegram context
        """
        query = update.inline_query
        if not query:
            return

        user_id = query.from_user.id if query.from_user else 0
        query_text = query.query
        offset = query.offset or ""

        try:
            # Check rate limit
            if not self.rate_limiter.check(user_id):
                await self._answer_rate_limited(query)
                return

            # Check cache
            cached = self.cache.get(query_text, user_id)
            if cached:
                page, next_offset = self.paginator.paginate(cached, offset)
                await self._answer(query, page, next_offset)
                return

            # Parse query
            intent = self.parser.parse(query_text)

            # Get results based on intent
            results = await self._get_results(intent)

            # Cache results
            ttl = self.cache.get_ttl_for_query_type(intent["type"])
            self.cache.set(query_text, results, user_id, ttl)

            # Paginate
            page, next_offset = self.paginator.paginate(results, offset)

            # Answer
            await self._answer(query, page, next_offset)

        except Exception as e:
            logger.error(f"Inline query error: {e}")
            error_result = self.generator.generate_error_result(str(e)[:100])
            await self._answer(query, [error_result], "")

    async def _get_results(self, intent: Dict[str, Any]) -> List[Dict]:
        """Get results based on parsed intent."""
        query_type = intent["type"]
        query = intent.get("query", "")

        if query_type == "empty":
            return self.get_default_suggestions()

        if query_type == "trending":
            return self._get_trending_results()

        if query_type == "token_address":
            token = await self._get_token_by_address(query)
            if token:
                return [self.generator.generate_token_result(
                    token_symbol=token.get("symbol", "???"),
                    token_name=token.get("name", "Unknown"),
                    token_address=query,
                    price=token.get("price", 0),
                    change_24h=token.get("change_24h", 0),
                )]
            return [self.generator.generate_no_results(query)]

        if query_type == "price_lookup":
            return await self._get_price_results(query)

        if query_type in ("token_symbol", "partial_search"):
            tokens = await self._search_tokens(query)
            if tokens:
                results = []
                for token in tokens:
                    results.append(self.generator.generate_token_result(
                        token_symbol=token.get("symbol", "???"),
                        token_name=token.get("name", "Unknown"),
                        token_address=token.get("address", ""),
                        price=token.get("price", 0),
                        change_24h=token.get("change_24h", 0),
                    ))
                return results
            return [self.generator.generate_no_results(query)]

        if query_type == "command":
            return self.get_command_suggestions()

        return self.get_default_suggestions()

    async def _search_tokens(self, query: str) -> List[Dict]:
        """Search for tokens matching query."""
        try:
            from tg_bot.handlers.commands.search_command import search_tokens
            results = search_tokens(query, limit=10)

            # Enrich with prices
            enriched = []
            for token in results:
                enriched.append(await self._enrich_with_price(token))
            return enriched

        except ImportError:
            # Fallback to local search
            return self._search_local(query)

    def _search_local(self, query: str) -> List[Dict]:
        """Local search in default tokens."""
        query_lower = query.lower()
        results = []

        for token in DEFAULT_TOKENS:
            if (query_lower in token["symbol"].lower() or
                query_lower in token["name"].lower()):
                results.append({**token, "price": 0, "change_24h": 0})

        return results

    async def _get_token_by_address(self, address: str) -> Optional[Dict]:
        """Fetch token info by address."""
        try:
            from tg_bot.services.signal_service import get_signal_service
            service = get_signal_service()
            signal = await service.get_comprehensive_signal(address)

            if signal:
                return {
                    "symbol": signal.symbol or "???",
                    "name": signal.name or "Unknown",
                    "price": signal.price or 0,
                    "change_24h": signal.change_24h or 0,
                }
        except Exception as e:
            logger.warning(f"Failed to fetch token {address}: {e}")

        return None

    async def _enrich_with_price(self, token: Dict) -> Dict:
        """Add price data to token dict."""
        try:
            price = await self._get_token_price(token.get("address", ""))
            return {**token, "price": price or 0}
        except Exception:
            return {**token, "price": 0}

    async def _get_token_price(self, address: str) -> Optional[float]:
        """Fetch current token price."""
        try:
            from tg_bot.services.signal_service import get_signal_service
            service = get_signal_service()
            signal = await service.get_comprehensive_signal(address, include_sentiment=False)
            return signal.price if signal else None
        except Exception:
            return None

    async def _get_price_results(self, query: str) -> List[Dict]:
        """Get price lookup results."""
        tokens = await self._search_tokens(query)
        if tokens:
            return [
                self.generator.generate_price_result(t["symbol"], t.get("price", 0))
                for t in tokens
            ]
        return [self.generator.generate_no_results(query)]

    def _get_trending_results(self) -> List[Dict]:
        """Get trending tokens results."""
        # For now, return default tokens as trending
        return self.generator.generate_trending_results(DEFAULT_TOKENS)

    def get_default_suggestions(self) -> List[Dict]:
        """Get default suggestions for empty query."""
        results = []
        for token in DEFAULT_TOKENS:
            results.append(self.generator.generate_token_result(
                token_symbol=token["symbol"],
                token_name=token["name"],
                token_address=token["address"],
                price=0,
                change_24h=0,
            ))
        return results

    def get_suggestions_for_partial(self, partial: str) -> List[Dict]:
        """Get suggestions for partial query."""
        return self._search_local(partial)

    def get_command_suggestions(self) -> List[Dict]:
        """Get command suggestions."""
        commands = [
            {"name": "analyze", "desc": "Analyze a token"},
            {"name": "price", "desc": "Get token price"},
            {"name": "trending", "desc": "See trending tokens"},
        ]

        results = []
        for cmd in commands:
            results.append({
                "type": "article",
                "id": self.generator._generate_id(f"cmd_{cmd['name']}"),
                "title": f"/{cmd['name']}",
                "description": cmd["desc"],
                "input_message_content": {
                    "message_text": f"/{cmd['name']}",
                },
            })
        return results

    async def _answer(
        self,
        query,
        results: List[Dict],
        next_offset: str,
    ) -> None:
        """Send answer to inline query."""
        # Convert to Telegram types
        telegram_results = []
        for r in results[:MAX_RESULTS]:
            telegram_results.append(self.formatter.to_telegram_result(r))

        await query.answer(
            results=telegram_results,
            cache_time=60,
            next_offset=next_offset,
        )

    async def _answer_rate_limited(self, query) -> None:
        """Send rate limit message."""
        result = InlineQueryResultArticle(
            id="rate_limited",
            title="Slow down!",
            description="Please wait before making more queries",
            input_message_content=InputTextMessageContent(
                message_text="Rate limited. Please wait a moment before searching again."
            ),
        )
        await query.answer(results=[result], cache_time=5)


# =============================================================================
# Handler Entry Point
# =============================================================================

# Global handler instance
_handler_instance: Optional[InlineQueryHandler] = None


def _get_handler() -> InlineQueryHandler:
    """Get or create handler instance."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = InlineQueryHandler()
    return _handler_instance


async def inline_query_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Handle inline query - entry point function.

    Args:
        update: Telegram Update
        context: Telegram context
    """
    if not update.inline_query:
        return

    handler = _get_handler()
    await handler.handle(update, context)


def get_inline_query_handler() -> TelegramInlineQueryHandler:
    """
    Get handler for registration with Telegram Application.

    Returns:
        TelegramInlineQueryHandler instance
    """
    return TelegramInlineQueryHandler(inline_query_handler)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    "InlineQueryParser",
    "InlineResultGenerator",
    "InlineQueryCache",
    "InlineQueryPaginator",
    "InlineAnswerFormatter",
    "InlineQueryHandler",
    "InlineQueryRateLimiter",
    "inline_query_handler",
    "get_inline_query_handler",
]

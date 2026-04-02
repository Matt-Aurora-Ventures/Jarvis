"""
/search Command Handler.

Provides token search functionality with partial matching.
"""

import logging
from typing import List, Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import error_handler

logger = logging.getLogger(__name__)


# Popular token database for quick search
POPULAR_TOKENS = {
    # Major tokens
    "SOL": {"address": "So11111111111111111111111111111111111111112", "name": "Solana"},
    "USDC": {"address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "name": "USD Coin"},
    "USDT": {"address": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", "name": "Tether"},

    # Popular memes
    "BONK": {"address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "name": "Bonk"},
    "WIF": {"address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "name": "dogwifhat"},
    "POPCAT": {"address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", "name": "Popcat"},
    "MEW": {"address": "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5", "name": "cat in a dogs world"},
    "BOME": {"address": "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82", "name": "Book of Meme"},
    "SLERF": {"address": "7BgBvyjrZX1YKz4oh9mjb8ZScatkkwb8DzFx7LoiVkM3", "name": "Slerf"},

    # DeFi
    "JUP": {"address": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN", "name": "Jupiter"},
    "RAY": {"address": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", "name": "Raydium"},
    "ORCA": {"address": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE", "name": "Orca"},
    "PYTH": {"address": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3", "name": "Pyth Network"},
    "JITO": {"address": "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn", "name": "Jito"},
    "MARINADE": {"address": "MNDEFzGvMt87ueuHvVU9VcTqsAP5b3fTGPsHuuPA5ey", "name": "Marinade"},

    # Gaming/NFT
    "DUST": {"address": "DUSTawucrTsGU8hcqRdHDCbuYhCPADMLM2VcCb8VnFnQ", "name": "DUST Protocol"},
    "GMT": {"address": "7i5KKsX2weiTkry7jA4ZwSuXGhs5eJBEjY8vVxR4pfRx", "name": "GMT"},
    "SAMO": {"address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU", "name": "Samoyedcoin"},

    # AI tokens
    "RENDER": {"address": "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof", "name": "Render"},
    "AI16Z": {"address": "HeLp6NuQkmYB4pYWo2zYs22mESHXPQYzXbB8n4V98jwC", "name": "ai16z"},
}


def search_tokens(query: str, limit: int = 5) -> List[Dict]:
    """
    Search for tokens matching the query.

    Args:
        query: Search query (partial symbol or name)
        limit: Maximum results to return

    Returns:
        List of matching token dictionaries
    """
    query_lower = query.lower().strip()
    results = []

    # Exact symbol match first
    query_upper = query.upper()
    if query_upper in POPULAR_TOKENS:
        token = POPULAR_TOKENS[query_upper]
        results.append({
            "symbol": query_upper,
            "name": token["name"],
            "address": token["address"],
            "match_type": "exact",
        })

    # Partial matches
    for symbol, token in POPULAR_TOKENS.items():
        if symbol == query_upper:
            continue  # Already added

        # Match by symbol prefix
        if symbol.lower().startswith(query_lower):
            results.append({
                "symbol": symbol,
                "name": token["name"],
                "address": token["address"],
                "match_type": "symbol",
            })
            continue

        # Match by name
        if query_lower in token["name"].lower():
            results.append({
                "symbol": symbol,
                "name": token["name"],
                "address": token["address"],
                "match_type": "name",
            })

    # Sort: exact > symbol > name
    priority = {"exact": 0, "symbol": 1, "name": 2}
    results.sort(key=lambda x: priority.get(x["match_type"], 3))

    return results[:limit]


async def fetch_token_price(address: str) -> Optional[float]:
    """
    Fetch current price for a token.

    Args:
        address: Token contract address

    Returns:
        Price in USD or None if unavailable
    """
    try:
        from tg_bot.services.signal_service import get_signal_service
        service = get_signal_service()

        signal = await service.get_comprehensive_signal(address, include_sentiment=False)
        return signal.price if signal else None

    except Exception as e:
        logger.warning(f"Failed to fetch price for {address}: {e}")
        return None


@error_handler
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /search command - search for tokens.

    Usage: /search bitcoin
    """
    if not context.args:
        await update.message.reply_text(
            "\U0001f50d *Token Search*\n\n"
            "*Usage:* `/search <query>`\n\n"
            "*Examples:*\n"
            "`/search jup` - Search by symbol\n"
            "`/search bonk` - Search meme tokens\n"
            "`/search jupiter` - Search by name\n\n"
            "_Supports partial matching._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    query = " ".join(context.args)

    # Search tokens
    results = search_tokens(query, limit=5)

    if not results:
        await update.message.reply_text(
            f"\U0001f50d *No Results*\n\n"
            f"_Couldn't find tokens matching \"{query}\"_\n\n"
            "*Try:*\n"
            "  - Use token symbol (e.g., SOL, BONK)\n"
            "  - Paste contract address for new tokens\n"
            "  - Check spelling",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Build results message
    lines = [
        f"\U0001f50d *Search: {query}*",
        "",
        f"_Found {len(results)} result(s):_",
        "",
    ]

    keyboard = []

    for i, token in enumerate(results, 1):
        symbol = token["symbol"]
        name = token["name"]
        address = token["address"]

        lines.append(f"*{i}. {symbol}* - {name}")
        lines.append(f"   `{address[:8]}...{address[-6:]}`")

        # Add analyze button for each result
        keyboard.append([
            InlineKeyboardButton(
                f"\U0001f4ca {symbol}",
                callback_data=f"analyze_{address}"
            ),
            InlineKeyboardButton(
                "\u2b50 Watch",
                callback_data=f"watch_add:{address}"
            ),
        ])

    # Add close button
    keyboard.append([
        InlineKeyboardButton("\u2716\ufe0f Close", callback_data="ui_close")
    ])

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


@error_handler
async def search_with_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /searchp command - search tokens with live prices.

    Usage: /searchp bonk
    """
    if not context.args:
        await update.message.reply_text(
            "\U0001f50d *Token Search (with prices)*\n\n"
            "*Usage:* `/searchp <query>`\n\n"
            "_Same as /search but includes live prices._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    query = " ".join(context.args)

    # Send loading message
    loading = await update.message.reply_text(
        f"_Searching for {query}..._",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Search tokens
    results = search_tokens(query, limit=5)

    if not results:
        await loading.edit_text(
            f"\U0001f50d *No Results*\n\n_Couldn't find tokens matching \"{query}\"_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Fetch prices for each result
    for token in results:
        price = await fetch_token_price(token["address"])
        token["price"] = price

    # Build results message
    lines = [
        f"\U0001f50d *Search: {query}*",
        "",
    ]

    keyboard = []

    for i, token in enumerate(results, 1):
        symbol = token["symbol"]
        name = token["name"]
        address = token["address"]
        price = token.get("price")

        price_str = f"${price:,.6f}" if price else "N/A"

        lines.append(f"*{i}. {symbol}* - {name}")
        lines.append(f"   \U0001f4b0 {price_str}")

        keyboard.append([
            InlineKeyboardButton(
                f"\U0001f4ca {symbol}",
                callback_data=f"analyze_{address}"
            ),
        ])

    keyboard.append([
        InlineKeyboardButton("\u2716\ufe0f Close", callback_data="ui_close")
    ])

    await loading.edit_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


__all__ = [
    "search_command",
    "search_with_prices",
    "search_tokens",
    "POPULAR_TOKENS",
]

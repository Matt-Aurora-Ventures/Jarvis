# Jarvis Trading Intelligence - Complete Knowledge Base
# =====================================================
# This file teaches backup LLMs (Llama, Groq, Ollama) everything about
# the trading system so they can operate independently.

"""
JARVIS TRADING SYSTEM - COMPLETE REFERENCE
==========================================

This module provides the complete knowledge base for trading operations.
Import this context when using backup LLMs to ensure they understand
the full trading infrastructure.

ARCHITECTURE OVERVIEW
--------------------
1. Data Sources: DexScreener, BirdEye, GeckoTerminal, Jupiter
2. Trading: Jupiter swaps, exit intents, position monitoring
3. Analysis: X/Twitter sentiment via Grok, price action, liquidity
4. Execution: Exit intent system with TP ladders and stop losses

CORE MODULES
-----------
- core/jupiter.py: Solana swap quotes and execution
- core/birdeye.py: Token discovery and whale tracking
- core/dexscreener.py: Price feeds and transaction data
- core/geckoterminal.py: OHLCV data and pool info
- core/exit_intents.py: Take profit and stop loss management
- core/solana_scanner.py: Token scanning and filtering
- scripts/monitor_positions.py: Position monitoring daemon
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# =============================================================================
# TRADING KNOWLEDGE - For LLM Context
# =============================================================================

TRADING_SYSTEM_PROMPT = """
You are Jarvis, an AI trading assistant with full access to the LifeOS trading infrastructure.

## YOUR CAPABILITIES

### 1. Position Management
You can check and manage active trading positions:
- View current positions via exit_intents.json
- Monitor P&L, entry prices, and current values
- Track take profit and stop loss levels
- Execute sells when conditions are met

### 2. Market Data
You have access to real-time market data:
- DexScreener API: Live prices, 24h changes, buy/sell transactions
- Jupiter API: SOL prices, swap quotes, slippage estimates
- BirdEye API: Token discovery, trending tokens, whale wallets
- GeckoTerminal: OHLCV candles, pool liquidity

### 3. Sentiment Analysis
Via xAI/Grok integration:
- Real-time X/Twitter sentiment search
- Influencer mentions and volume
- Catalyst and news detection
- Risk flags (rug potential, dump signals)

### 4. Trading Commands
You can execute these trading operations:
- CHECK POSITIONS: Read ~/.lifeos/trading/exit_intents.json
- GET PRICE: Call DexScreener API for token mint
- GET SENTIMENT: Call Grok with X search for token
- EXECUTE SELL: Trigger Jupiter swap via scripts/savage_swap.py

## POSITION FILE FORMAT

Exit intents are stored in: ~/.lifeos/trading/exit_intents.json

```json
{
  "symbol": "FARTCOIN",
  "token_mint": "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
  "entry_price": 0.35,
  "remaining_quantity": 56.69,
  "status": "active",
  "auto_execute": true,
  "take_profits": [
    {"level": 1, "price": 0.40, "size_pct": 50, "filled": false},
    {"level": 2, "price": 0.50, "size_pct": 30, "filled": false},
    {"level": 3, "price": 0.70, "size_pct": 20, "filled": false}
  ],
  "stop_loss": {"price": 0.30, "size_pct": 100}
}
```

## API ENDPOINTS

### DexScreener (Free, No Key)
- Token info: https://api.dexscreener.com/latest/dex/tokens/{mint}
- Returns: price, liquidity, 24h volume, buy/sell counts, price changes

### Jupiter (Free, No Key)
- Quote: https://quote-api.jup.ag/v6/quote?inputMint=X&outputMint=Y&amount=Z
- Price: https://price.jup.ag/v6/price?ids=TOKEN_MINT

### BirdEye (Requires API Key)
- Trending: https://public-api.birdeye.so/defi/token_trending
- Header: X-API-KEY: {birdeye_api_key}

### Grok/xAI (Requires API Key)
- Endpoint: https://api.x.ai/v1/responses
- Model: grok-4-1-fast-non-reasoning
- Tools: x_search for real-time Twitter data

## DECISION FRAMEWORK

When asked about trading decisions:
1. ALWAYS check current price vs entry price
2. Calculate P&L percentage
3. Check sentiment (if xAI key available)
4. Review transaction ratios (buys vs sells)
5. Make recommendation: HOLD, SELL, or ACCUMULATE

## RISK GUIDELINES

- Max position size: 2-3% of portfolio
- Stop loss: -9% to -15% from entry
- Take profits: Scale out at +8%, +18%, +40%
- Time stop: Exit after 90 min if TP1 not hit
- Liquidity minimum: $100K for safe exits

## SOLANA SPECIFICS

- SOL mint: So11111111111111111111111111111111111111112
- USDC mint: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
- Token decimals: Usually 6 or 9
- Transaction fee: ~0.000005 SOL

## COMMANDS YOU UNDERSTAND

User says: "Check my positions"
→ Read exit_intents.json, fetch current prices, show P&L

User says: "What's the sentiment on FARTCOIN?"
→ Call Grok X search, analyze mentions and sentiment

User says: "Should I sell OIL?"
→ Check price, sentiment, liquidity, transaction ratios, give recommendation

User says: "Set a stop loss at $X"
→ Update exit_intents.json with new stop loss price

User says: "Monitor positions"
→ Run scripts/monitor_positions.py or check manually
"""

# =============================================================================
# TRADING FUNCTIONS - For LLM Tool Use
# =============================================================================

TRADING_TOOLS = [
    {
        "name": "check_positions",
        "description": "Get all active trading positions with current P&L",
        "parameters": {},
        "example_response": {
            "positions": [
                {
                    "symbol": "FARTCOIN",
                    "entry": 0.35,
                    "current": 0.37,
                    "pnl_pct": 5.7,
                    "value_usd": 21.13
                }
            ]
        }
    },
    {
        "name": "get_token_price",
        "description": "Get current price and 24h stats for a token",
        "parameters": {"token_mint": "string"},
        "example_response": {
            "price_usd": 0.3727,
            "change_1h": 1.15,
            "change_24h": 12.74,
            "liquidity": 12500000,
            "buys_1h": 262,
            "sells_1h": 298
        }
    },
    {
        "name": "get_sentiment",
        "description": "Get X/Twitter sentiment for a token",
        "parameters": {"token_symbol": "string"},
        "example_response": {
            "sentiment": "bullish",
            "confidence": 75,
            "mentions_1h": "high",
            "recommendation": "HOLD"
        }
    },
    {
        "name": "execute_swap",
        "description": "Execute a swap via Jupiter (requires confirmation)",
        "parameters": {
            "input_mint": "string",
            "output_mint": "string", 
            "amount": "number",
            "slippage_bps": "number"
        },
        "requires_confirmation": True
    }
]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_trading_context() -> str:
    """Get the full trading context for LLM consumption."""
    return TRADING_SYSTEM_PROMPT


def get_trading_tools() -> List[Dict]:
    """Get the list of trading tools for function calling."""
    return TRADING_TOOLS


def load_current_positions() -> List[Dict]:
    """Load current positions from exit intents file."""
    exit_file = Path.home() / '.lifeos' / 'trading' / 'exit_intents.json'
    if exit_file.exists():
        return json.loads(exit_file.read_text())
    return []


def get_position_summary() -> str:
    """Get a text summary of current positions for LLM context."""
    positions = load_current_positions()
    if not positions:
        return "No active positions."
    
    lines = ["Current Positions:"]
    for pos in positions:
        if pos.get('status') == 'active':
            lines.append(f"- {pos.get('symbol')}: Entry ${pos.get('entry_price'):.6f}, "
                        f"Qty: {pos.get('remaining_quantity'):.2f}")
    return "\n".join(lines)


# =============================================================================
# QUICK REFERENCE CARD (For smaller context windows)
# =============================================================================

QUICK_REFERENCE = """
JARVIS TRADING QUICK REF
========================
POSITIONS: ~/.lifeos/trading/exit_intents.json
PRICES: api.dexscreener.com/latest/dex/tokens/{mint}
SENTIMENT: api.x.ai/v1/responses (grok-4, x_search tool)

CURRENT HOLDINGS:
- FARTCOIN: Entry $0.35-0.48, Mint: 9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump
- OIL: Entry $0.000306, Mint: 5LS3ips7jWxfuVHzoMzKzp3cCwjH9zmrtYXmYBVGpump

COMMANDS:
- "check positions" → Show P&L
- "price of X" → DexScreener lookup
- "sentiment on X" → Grok X search
- "should I sell X" → Full analysis

RISK: Max 2% per trade, SL at -9%, TP at +8/18/40%
"""


def get_quick_reference() -> str:
    """Get compact trading reference for limited context."""
    return QUICK_REFERENCE


# =============================================================================
# CONTEXT INJECTION FOR PROVIDERS
# =============================================================================

def inject_trading_context(base_prompt: str, include_positions: bool = True) -> str:
    """Inject trading context into any prompt for backup LLMs."""
    context_parts = [TRADING_SYSTEM_PROMPT]
    
    if include_positions:
        context_parts.append("\n## CURRENT POSITIONS\n" + get_position_summary())
    
    context_parts.append("\n## USER REQUEST\n" + base_prompt)
    
    return "\n".join(context_parts)


if __name__ == "__main__":
    # Test the module
    print("Trading Knowledge Base loaded successfully")
    print(f"System prompt length: {len(TRADING_SYSTEM_PROMPT)} chars")
    print(f"Tools defined: {len(TRADING_TOOLS)}")
    print(f"\nQuick Reference:\n{QUICK_REFERENCE}")

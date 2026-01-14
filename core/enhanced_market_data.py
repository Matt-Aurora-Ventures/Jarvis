"""
Enhanced Market Data for Sentiment Reports.

Features:
- Top 10 trending Solana tokens from DexScreener
- Backed.fi xStocks with indexes
- Grok conviction scoring for top picks
- Multi-purchase support data structures
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import requests

logger = logging.getLogger(__name__)

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TrendingToken:
    """Trending Solana token from DexScreener."""
    symbol: str
    name: str
    contract: str
    price_usd: float
    price_change_24h: float
    volume_24h: float
    liquidity_usd: float
    mcap: float
    tx_count_24h: int
    rank: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "contract": self.contract,
            "price_usd": self.price_usd,
            "price_change_24h": self.price_change_24h,
            "volume_24h": self.volume_24h,
            "liquidity_usd": self.liquidity_usd,
            "mcap": self.mcap,
            "tx_count_24h": self.tx_count_24h,
            "rank": self.rank,
        }


@dataclass
class BackedAsset:
    """Tokenized asset from backed.fi."""
    symbol: str
    name: str
    mint_address: str
    asset_type: str  # "stock", "etf", "index"
    underlying: str
    price_usd: float
    change_1y: float
    issuer: str = "backed"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "mint_address": self.mint_address,
            "asset_type": self.asset_type,
            "underlying": self.underlying,
            "price_usd": self.price_usd,
            "change_1y": self.change_1y,
            "issuer": self.issuer,
        }


@dataclass
class ConvictionPick:
    """Grok conviction pick with score."""
    symbol: str
    name: str
    asset_class: str  # "token", "stock", "index", "commodity"
    contract: str
    conviction_score: int  # 1-100
    reasoning: str
    entry_price: float
    target_price: float
    stop_loss: float
    timeframe: str  # "short", "medium", "long"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "asset_class": self.asset_class,
            "contract": self.contract,
            "conviction_score": self.conviction_score,
            "reasoning": self.reasoning,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "timeframe": self.timeframe,
        }


# =============================================================================
# BACKED.FI ASSETS - HARDCODED REGISTRY
# =============================================================================

# Complete xStocks registry with verified Solana mint addresses from xstocks.fi
BACKED_XSTOCKS = {
    # STOCKS - Tech Giants
    "AAPLx": {"name": "Apple xStock", "mint": "XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp", "type": "stock", "underlying": "AAPL"},
    "MSFTx": {"name": "Microsoft xStock", "mint": "XspzcW1PRtgf6Wj92HCiZdjzKCyFekVD8P5Ueh3dRMX", "type": "stock", "underlying": "MSFT"},
    "GOOGLx": {"name": "Alphabet xStock", "mint": "XsCPL9dNWBMvFtTmwcCA5v3xWPSMEBCszbQdiLLq6aN", "type": "stock", "underlying": "GOOGL"},
    "AMZNx": {"name": "Amazon xStock", "mint": "Xs3eBt7uRfJX8QUs4suhyU8p2M6DoUDrJyWBa8LLZsg", "type": "stock", "underlying": "AMZN"},
    "METAx": {"name": "Meta xStock", "mint": "Xsa62P5mvPszXL1krVUnU5ar38bBSVcWAB6fmPCo5Zu", "type": "stock", "underlying": "META"},
    "NVDAx": {"name": "NVIDIA xStock", "mint": "Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh", "type": "stock", "underlying": "NVDA"},
    "TSLAx": {"name": "Tesla xStock", "mint": "XsDoVfqeBukxuZHWhdvWHBhgEHjGNst4MLodqsJHzoB", "type": "stock", "underlying": "TSLA"},
    "AVGOx": {"name": "Broadcom xStock", "mint": "XsgSaSvNSqLTtFuyWPBhK9196Xb9Bbdyjj4fH3cPJGo", "type": "stock", "underlying": "AVGO"},
    "ORCLx": {"name": "Oracle xStock", "mint": "XsjFwUPiLofddX5cWFHW35GCbXcSu1BCUGfxoQAQjeL", "type": "stock", "underlying": "ORCL"},
    "CRMx": {"name": "Salesforce xStock", "mint": "XsczbcQ3zfcgAEt9qHQES8pxKAVG5rujPSHQEXi4kaN", "type": "stock", "underlying": "CRM"},
    "CSCOx": {"name": "Cisco xStock", "mint": "Xsr3pdLQyXvDJBFgpR5nexCEZwXvigb8wbPYp4YoNFf", "type": "stock", "underlying": "CSCO"},
    "INTCx": {"name": "Intel xStock", "mint": "XshPgPdXFRWB8tP1j82rebb2Q9rPgGX37RuqzohmArM", "type": "stock", "underlying": "INTC"},
    "IBMx": {"name": "IBM xStock", "mint": "XspwhyYPdWVM8XBHZnpS9hgyag9MKjLRyE3tVfmCbSr", "type": "stock", "underlying": "IBM"},
    "ACNx": {"name": "Accenture xStock", "mint": "Xs5UJzmCRQ8DWZjskExdSQDnbE6iLkRu2jjrRAB1JSU", "type": "stock", "underlying": "ACN"},
    "APPx": {"name": "AppLovin xStock", "mint": "XsPdAVBi8Zc1xvv53k4JcMrQaEDTgkGqKYeh7AYgPHV", "type": "stock", "underlying": "APP"},
    "CRWDx": {"name": "CrowdStrike xStock", "mint": "Xs7xXqkcK7K8urEqGg52SECi79dRp2cEKKuYjUePYDw", "type": "stock", "underlying": "CRWD"},
    "PLTRx": {"name": "Palantir xStock", "mint": "XsoBhf2ufR8fTyNSjqfU71DYGaE6Z3SUGAidpzriAA4", "type": "stock", "underlying": "PLTR"},
    "MRVLx": {"name": "Marvell xStock", "mint": "XsuxRGDzbLjnJ72v74b7p9VY6N66uYgTCyfwwRjVCJA", "type": "stock", "underlying": "MRVL"},

    # STOCKS - Crypto/Fintech
    "COINx": {"name": "Coinbase xStock", "mint": "Xs7ZdzSHLU9ftNJsii5fCeJhoRWSC32SQGzGQtePxNu", "type": "stock", "underlying": "COIN"},
    "MSTRx": {"name": "MicroStrategy xStock", "mint": "XsP7xzNPvEHS1m6qfanPUGjNmdnmsLKEoNAnHjdxxyZ", "type": "stock", "underlying": "MSTR"},
    "HOODx": {"name": "Robinhood xStock", "mint": "XsvNBAYkrDRNhA7wPHQfX3ZUXZyZLdnCQDfHZ56bzpg", "type": "stock", "underlying": "HOOD"},
    "CRCLx": {"name": "Circle xStock", "mint": "XsueG8BtpquVJX9LVLLEGuViXUungE6WmK5YZ3p3bd1", "type": "stock", "underlying": "CRCL"},

    # STOCKS - Finance
    "JPMx": {"name": "JPMorgan Chase xStock", "mint": "XsMAqkcKsUewDrzVkait4e5u4y8REgtyS7jWgCpLV2C", "type": "stock", "underlying": "JPM"},
    "GSx": {"name": "Goldman Sachs xStock", "mint": "XsgaUyp4jd1fNBCxgtTKkW64xnnhQcvgaxzsbAq5ZD1", "type": "stock", "underlying": "GS"},
    "BACx": {"name": "Bank of America xStock", "mint": "XswsQk4duEQmCbGzfqUUWYmi7pV7xpJ9eEmLHXCaEQP", "type": "stock", "underlying": "BAC"},
    "MAx": {"name": "Mastercard xStock", "mint": "XsApJFV9MAktqnAc6jqzsHVujxkGm9xcSUffaBoYLKC", "type": "stock", "underlying": "MA"},
    "Vx": {"name": "Visa xStock", "mint": "XsqgsbXwWogGJsNcVZ3TyVouy2MbTkfCFhCGGGcQZ2p", "type": "stock", "underlying": "V"},
    "BRK.Bx": {"name": "Berkshire Hathaway xStock", "mint": "Xs6B6zawENwAbWVi7w92rjazLuAr5Az59qgWKcNb45x", "type": "stock", "underlying": "BRK.B"},

    # STOCKS - Healthcare
    "JNJx": {"name": "Johnson & Johnson xStock", "mint": "XsGVi5eo1Dh2zUpic4qACcjuWGjNv8GCt3dm5XcX6Dn", "type": "stock", "underlying": "JNJ"},
    "UNHx": {"name": "UnitedHealth xStock", "mint": "XszvaiXGPwvk2nwb3o9C1CX4K6zH8sez11E6uyup6fe", "type": "stock", "underlying": "UNH"},
    "LLYx": {"name": "Eli Lilly xStock", "mint": "Xsnuv4omNoHozR6EEW5mXkw8Nrny5rB3jVfLqi6gKMH", "type": "stock", "underlying": "LLY"},
    "PFEx": {"name": "Pfizer xStock", "mint": "XsAtbqkAP1HJxy7hFDeq7ok6yM43DQ9mQ1Rh861X8rw", "type": "stock", "underlying": "PFE"},
    "MRKx": {"name": "Merck xStock", "mint": "XsnQnU7AdbRZYe2akqqpibDdXjkieGFfSkbkjX1Sd1X", "type": "stock", "underlying": "MRK"},
    "ABTx": {"name": "Abbott xStock", "mint": "XsHtf5RpxsQ7jeJ9ivNewouZKJHbPxhPoEy6yYvULr7", "type": "stock", "underlying": "ABT"},
    "ABBVx": {"name": "AbbVie xStock", "mint": "XswbinNKyPmzTa5CskMbCPvMW6G5CMnZXZEeQSSQoie", "type": "stock", "underlying": "ABBV"},
    "TMOx": {"name": "Thermo Fisher xStock", "mint": "Xs8drBWy3Sd5QY3aifG9kt9KFs2K3PGZmx7jWrsrk57", "type": "stock", "underlying": "TMO"},
    "DHRx": {"name": "Danaher xStock", "mint": "Xseo8tgCZfkHxWS9xbFYeKFyMSbWEvZGFV1Gh53GtCV", "type": "stock", "underlying": "DHR"},
    "MDTx": {"name": "Medtronic xStock", "mint": "XsDgw22qRLTv5Uwuzn6T63cW69exG41T6gwQhEK22u2", "type": "stock", "underlying": "MDT"},
    "AZNx": {"name": "AstraZeneca xStock", "mint": "Xs3ZFkPYT2BN7qBMqf1j1bfTeTm1rFzEFSsQ1z3wAKU", "type": "stock", "underlying": "AZN"},
    "NVOx": {"name": "Novo Nordisk xStock", "mint": "XsfAzPzYrYjd4Dpa9BU3cusBsvWfVB9gBcyGC87S57n", "type": "stock", "underlying": "NVO"},

    # STOCKS - Consumer
    "WMTx": {"name": "Walmart xStock", "mint": "Xs151QeqTCiuKtinzfRATnUESM2xTU6V9Wy8Vy538ci", "type": "stock", "underlying": "WMT"},
    "PGx": {"name": "Procter & Gamble xStock", "mint": "XsYdjDjNUygZ7yGKfQaB6TxLh2gC6RRjzLtLAGJrhzV", "type": "stock", "underlying": "PG"},
    "KOx": {"name": "Coca-Cola xStock", "mint": "XsaBXg8dU5cPM6ehmVctMkVqoiRG2ZjMo1cyBJ3AykQ", "type": "stock", "underlying": "KO"},
    "PEPx": {"name": "PepsiCo xStock", "mint": "Xsv99frTRUeornyvCfvhnDesQDWuvns1M852Pez91vF", "type": "stock", "underlying": "PEP"},
    "MCDx": {"name": "McDonald's xStock", "mint": "XsqE9cRRpzxcGKDXj1BJ7Xmg4GRhZoyY1KpmGSxAWT2", "type": "stock", "underlying": "MCD"},
    "HDx": {"name": "Home Depot xStock", "mint": "XszjVtyhowGjSC5odCqBpW1CtXXwXjYokymrk7fGKD3", "type": "stock", "underlying": "HD"},

    # STOCKS - Energy
    "XOMx": {"name": "Exxon Mobil xStock", "mint": "XsaHND8sHyfMfsWPj6kSdd5VwvCayZvjYgKmmcNL5qh", "type": "stock", "underlying": "XOM"},
    "CVXx": {"name": "Chevron xStock", "mint": "XsNNMt7WTNA2sV3jrb1NNfNgapxRF5i4i6GcnTRRHts", "type": "stock", "underlying": "CVX"},

    # STOCKS - Industrial
    "HONx": {"name": "Honeywell xStock", "mint": "XsRbLZthfABAPAfumWNEJhPyiKDW6TvDVeAeW7oKqA2", "type": "stock", "underlying": "HON"},
    "LINx": {"name": "Linde xStock", "mint": "XsSr8anD1hkvNMu8XQiVcmiaTP7XGvYu7Q58LdmtE8Z", "type": "stock", "underlying": "LIN"},

    # STOCKS - Media/Entertainment
    "NFLXx": {"name": "Netflix xStock", "mint": "XsEH7wWfJJu2ZT3UCFeVfALnVA6CP5ur7Ee11KmzVpL", "type": "stock", "underlying": "NFLX"},
    "CMCSAx": {"name": "Comcast xStock", "mint": "XsvKCaNsxg2GN8jjUmq71qukMJr7Q1c5R2Mk9P8kcS8", "type": "stock", "underlying": "CMCSA"},

    # STOCKS - Telecom
    "PMx": {"name": "Philip Morris xStock", "mint": "Xsba6tUnSjDae2VcopDB6FGGDaxRrewFCDa5hKn5vT3", "type": "stock", "underlying": "PM"},

    # STOCKS - Meme/Speculative
    "GMEx": {"name": "Gamestop xStock", "mint": "Xsf9mBktVB9BSU5kf4nHxPq5hCBJ2j2ui3ecFGxPRGc", "type": "stock", "underlying": "GME"},
    "AMBRx": {"name": "Amber xStock", "mint": "XsaQTCgebC2KPbf27KUhdv5JFvHhQ4GDAPURwrEhAzb", "type": "stock", "underlying": "AMBR"},

    # STOCKS - Other
    "OPENx": {"name": "OPEN xStock", "mint": "XsGtpmjhmC8kyjVSWL4VicGu36ceq9u55PTgF8bhGv6", "type": "stock", "underlying": "OPEN"},
    "DFDVx": {"name": "DFDV xStock", "mint": "Xs2yquAgsHByNzx68WJC55WHjHBvG9JsMB7CWjTLyPy", "type": "stock", "underlying": "DFDV"},
    "STRCx": {"name": "Strategy PP Variable xStock", "mint": "Xs78JED6PFZxWc2wCEPspZW9kL3Se5J7L5TChKgsidH", "type": "stock", "underlying": "STRC"},
    "TONXx": {"name": "TON xStock", "mint": "XscE4GUcsYhcyZu5ATiGUMmhxYa1D5fwbpJw4K6K4dp", "type": "stock", "underlying": "TONX"},

    # INDEXES/ETFs
    "SPYx": {"name": "S&P 500 xStock", "mint": "XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W", "type": "index", "underlying": "SPY"},
    "QQQx": {"name": "NASDAQ 100 xStock", "mint": "Xs8S1uUs1zvS2p7iwtsG3b6fkhpvmwz4GYU3gWAmWHZ", "type": "index", "underlying": "QQQ"},
    "VTIx": {"name": "Vanguard Total Market xStock", "mint": "XsssYEQjzxBCFgvYFFNuhJFBeHNdLWYeUSP8F45cDr9", "type": "index", "underlying": "VTI"},
    "TQQQx": {"name": "TQQQ 3x Leveraged NASDAQ xStock", "mint": "XsjQP3iMAaQ3kQScQKthQpx9ALRbjKAjQtHg6TFomoc", "type": "index", "underlying": "TQQQ"},

    # COMMODITIES
    "GLDx": {"name": "Gold xStock", "mint": "Xsv9hRk1z5ystj9MhnA7Lq4vjSsLwzL2nxrwmwtD3re", "type": "commodity", "underlying": "GLD"},

    # BONDS/TREASURIES
    "TBLLx": {"name": "Treasury Bill xStock", "mint": "XsqBC5tcVQLYt8wqGCHRnAUUecbRYXoJCReD6w7QEKp", "type": "bond", "underlying": "TBLL"},
}


# =============================================================================
# HIGH-LIQUIDITY SOLANA TOKENS (>$200M MCAP, >1 YEAR HISTORY)
# =============================================================================

# Established Solana ecosystem tokens for sentiment analysis
# These are blue-chip tokens with proven liquidity and history
HIGH_LIQUIDITY_SOLANA_TOKENS = {
    # Native Solana
    "SOL": {
        "name": "Solana",
        "mint": "So11111111111111111111111111111111111111112",
        "category": "L1",
        "description": "Native Solana token - foundation of the ecosystem",
    },
    # DeFi Giants
    "JUP": {
        "name": "Jupiter",
        "mint": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
        "category": "DeFi",
        "description": "Leading Solana DEX aggregator",
    },
    "RAY": {
        "name": "Raydium",
        "mint": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
        "category": "DeFi",
        "description": "Premier Solana AMM and liquidity provider",
    },
    "ORCA": {
        "name": "Orca",
        "mint": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
        "category": "DeFi",
        "description": "User-friendly Solana DEX",
    },
    "JTO": {
        "name": "Jito",
        "mint": "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",
        "category": "DeFi",
        "description": "MEV infrastructure and liquid staking",
    },
    # Infrastructure
    "PYTH": {
        "name": "Pyth Network",
        "mint": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
        "category": "Infrastructure",
        "description": "Leading oracle network for DeFi",
    },
    "RENDER": {
        "name": "Render",
        "mint": "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",
        "category": "Infrastructure",
        "description": "Decentralized GPU rendering network",
    },
    "HNT": {
        "name": "Helium",
        "mint": "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux",
        "category": "Infrastructure",
        "description": "Decentralized wireless network",
    },
    # Meme Blue Chips (established, high volume)
    "BONK": {
        "name": "Bonk",
        "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "category": "Meme",
        "description": "Solana's original community dog coin",
    },
    "WIF": {
        "name": "dogwifhat",
        "mint": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        "category": "Meme",
        "description": "Iconic Solana meme token",
    },
}


async def fetch_high_liquidity_tokens() -> Tuple[List[TrendingToken], List[str]]:
    """
    Fetch live data for established high-liquidity Solana tokens.

    These are blue-chip tokens with >$200M market cap and >1 year history.
    Used as stable alternatives to trending tokens for sentiment analysis.

    Returns:
        (tokens, warnings)
    """
    warnings = []
    tokens = []

    try:
        async with aiohttp.ClientSession() as session:
            for symbol, info in HIGH_LIQUIDITY_SOLANA_TOKENS.items():
                try:
                    url = f"https://api.dexscreener.com/latest/dex/tokens/{info['mint']}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            pairs = data.get("pairs") or []
                            if pairs:
                                # Get the highest liquidity pair
                                best_pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                                tokens.append(TrendingToken(
                                    symbol=symbol,
                                    name=info["name"],
                                    contract=info["mint"],
                                    price_usd=float(best_pair.get("priceUsd") or 0),
                                    price_change_24h=float(best_pair.get("priceChange", {}).get("h24") or 0),
                                    volume_24h=float(best_pair.get("volume", {}).get("h24") or 0),
                                    liquidity_usd=float(best_pair.get("liquidity", {}).get("usd") or 0),
                                    mcap=float(best_pair.get("marketCap") or best_pair.get("fdv") or 0),
                                    tx_count_24h=int(best_pair.get("txns", {}).get("h24", {}).get("buys", 0) or 0) +
                                                int(best_pair.get("txns", {}).get("h24", {}).get("sells", 0) or 0),
                                    rank=len(tokens) + 1,
                                ))
                        else:
                            warnings.append(f"DexScreener returned {resp.status} for {symbol}")
                except Exception as e:
                    warnings.append(f"Failed to fetch {symbol}: {e}")

                # Rate limit: small delay between requests
                await asyncio.sleep(0.2)

    except Exception as e:
        warnings.append(f"High liquidity fetch failed: {e}")

    # Sort by market cap descending
    tokens.sort(key=lambda t: t.mcap, reverse=True)

    # Update ranks
    for i, token in enumerate(tokens):
        token.rank = i + 1

    return tokens, warnings


# =============================================================================
# TRENDING TOKENS FETCHER
# =============================================================================

async def fetch_trending_solana_tokens(limit: int = 10) -> Tuple[List[TrendingToken], List[str]]:
    """
    Fetch top trending Solana tokens from DexScreener.

    Returns:
        (tokens, warnings)
    """
    warnings = []
    tokens = []

    try:
        async with aiohttp.ClientSession() as session:
            # Use DexScreener's Solana token profiles (trending)
            url = "https://api.dexscreener.com/token-profiles/latest/v1"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    warnings.append(f"DexScreener profiles returned {resp.status}")
                else:
                    data = await resp.json()
                    solana_profiles = [
                        p for p in (data or [])
                        if isinstance(p, dict) and p.get("chainId") == "solana"
                    ][:limit * 2]  # Get more to filter

                    for profile in solana_profiles[:limit]:
                        token_addr = profile.get("tokenAddress", "")
                        if not token_addr:
                            continue

                        # Fetch detailed token data
                        detail_url = f"https://api.dexscreener.com/latest/dex/tokens/{token_addr}"
                        try:
                            async with session.get(detail_url, timeout=aiohttp.ClientTimeout(total=10)) as detail_resp:
                                if detail_resp.status == 200:
                                    detail_data = await detail_resp.json()
                                    pairs = detail_data.get("pairs") or []
                                    if pairs:
                                        best_pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                                        tokens.append(TrendingToken(
                                            symbol=best_pair.get("baseToken", {}).get("symbol", "???"),
                                            name=best_pair.get("baseToken", {}).get("name", "Unknown"),
                                            contract=token_addr,
                                            price_usd=float(best_pair.get("priceUsd") or 0),
                                            price_change_24h=float(best_pair.get("priceChange", {}).get("h24") or 0),
                                            volume_24h=float(best_pair.get("volume", {}).get("h24") or 0),
                                            liquidity_usd=float(best_pair.get("liquidity", {}).get("usd") or 0),
                                            mcap=float(best_pair.get("marketCap") or best_pair.get("fdv") or 0),
                                            tx_count_24h=int(best_pair.get("txns", {}).get("h24", {}).get("buys", 0) or 0) +
                                                        int(best_pair.get("txns", {}).get("h24", {}).get("sells", 0) or 0),
                                            rank=len(tokens) + 1,
                                        ))
                        except Exception as e:
                            warnings.append(f"Failed to get details for {token_addr[:8]}: {e}")

            # Fallback: use Solana boosted tokens if not enough
            if len(tokens) < limit:
                boost_url = "https://api.dexscreener.com/token-boosts/top/v1"
                try:
                    async with session.get(boost_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for item in (data or []):
                                if len(tokens) >= limit:
                                    break
                                if item.get("chainId") != "solana":
                                    continue
                                token_addr = item.get("tokenAddress", "")
                                if any(t.contract == token_addr for t in tokens):
                                    continue

                                # Fetch details
                                detail_url = f"https://api.dexscreener.com/latest/dex/tokens/{token_addr}"
                                try:
                                    async with session.get(detail_url, timeout=aiohttp.ClientTimeout(total=10)) as detail_resp:
                                        if detail_resp.status == 200:
                                            detail_data = await detail_resp.json()
                                            pairs = detail_data.get("pairs") or []
                                            if pairs:
                                                best_pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                                                tokens.append(TrendingToken(
                                                    symbol=best_pair.get("baseToken", {}).get("symbol", "???"),
                                                    name=best_pair.get("baseToken", {}).get("name", "Unknown"),
                                                    contract=token_addr,
                                                    price_usd=float(best_pair.get("priceUsd") or 0),
                                                    price_change_24h=float(best_pair.get("priceChange", {}).get("h24") or 0),
                                                    volume_24h=float(best_pair.get("volume", {}).get("h24") or 0),
                                                    liquidity_usd=float(best_pair.get("liquidity", {}).get("usd") or 0),
                                                    mcap=float(best_pair.get("marketCap") or best_pair.get("fdv") or 0),
                                                    tx_count_24h=int(best_pair.get("txns", {}).get("h24", {}).get("buys", 0) or 0) +
                                                                int(best_pair.get("txns", {}).get("h24", {}).get("sells", 0) or 0),
                                                    rank=len(tokens) + 1,
                                                ))
                                except:
                                    pass
                except Exception as e:
                    warnings.append(f"Boost fallback failed: {e}")

    except Exception as e:
        warnings.append(f"Trending fetch failed: {e}")

    # Update ranks
    for i, token in enumerate(tokens):
        token.rank = i + 1

    return tokens[:limit], warnings


def fetch_trending_solana_tokens_sync(limit: int = 10) -> Tuple[List[TrendingToken], List[str]]:
    """Synchronous wrapper for trending tokens."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(fetch_trending_solana_tokens(limit))


# =============================================================================
# BACKED.FI ASSETS FETCHER
# =============================================================================

def fetch_backed_assets() -> Tuple[List[BackedAsset], List[str]]:
    """
    Fetch backed.fi xStocks assets.
    Uses hardcoded registry + live price data.

    Returns:
        (assets, warnings)
    """
    warnings = []
    assets = []

    for symbol, info in BACKED_XSTOCKS.items():
        try:
            # Get live price from DexScreener
            price_usd = 0.0
            change_1y = 0.0

            try:
                resp = requests.get(
                    f"https://api.dexscreener.com/latest/dex/tokens/{info['mint']}",
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    pairs = data.get("pairs") or []
                    if pairs:
                        best = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                        price_usd = float(best.get("priceUsd") or 0)
            except Exception as e:
                warnings.append(f"Price fetch failed for {symbol}: {e}")

            assets.append(BackedAsset(
                symbol=symbol,
                name=info["name"],
                mint_address=info["mint"],
                asset_type=info["type"],
                underlying=info["underlying"],
                price_usd=price_usd,
                change_1y=change_1y,
            ))
        except Exception as e:
            warnings.append(f"Failed to process {symbol}: {e}")

    return assets, warnings


def fetch_backed_stocks() -> Tuple[List[BackedAsset], List[str]]:
    """Get only stocks from backed.fi."""
    assets, warnings = fetch_backed_assets()
    return [a for a in assets if a.asset_type == "stock"], warnings


def fetch_backed_indexes() -> Tuple[List[BackedAsset], List[str]]:
    """Get only indexes/ETFs from backed.fi."""
    assets, warnings = fetch_backed_assets()
    return [a for a in assets if a.asset_type == "index"], warnings


# =============================================================================
# GROK CONVICTION ANALYSIS
# =============================================================================

async def get_grok_conviction_picks(
    tokens: List[TrendingToken],
    stocks: List[BackedAsset],
    indexes: List[BackedAsset],
    grok_client: Any,
    top_n: int = 10,
) -> Tuple[List[ConvictionPick], List[str]]:
    """
    Use Grok to analyze all assets and provide conviction scores.

    Args:
        tokens: Trending Solana tokens
        stocks: xStocks from backed.fi
        indexes: Index ETFs from backed.fi
        grok_client: Grok API client
        top_n: Number of top picks to return

    Returns:
        (conviction_picks, warnings)
    """
    warnings = []
    picks = []

    if not grok_client:
        warnings.append("Grok client not available")
        return picks, warnings

    try:
        # Build asset summary for Grok
        asset_summary = "ASSETS TO ANALYZE:\n\n"

        asset_summary += "TRENDING SOLANA TOKENS:\n"
        for t in tokens[:10]:
            asset_summary += f"- {t.symbol}: ${t.price_usd:.8f}, 24h: {t.price_change_24h:+.1f}%, Vol: ${t.volume_24h:,.0f}, MCap: ${t.mcap:,.0f}\n"

        asset_summary += "\nTOKENIZED STOCKS (xStocks):\n"
        for s in stocks[:10]:
            asset_summary += f"- {s.symbol} ({s.underlying}): ${s.price_usd:.2f}\n"

        asset_summary += "\nINDEXES/ETFs:\n"
        for i in indexes[:5]:
            asset_summary += f"- {i.symbol} ({i.underlying}): ${i.price_usd:.2f}\n"

        prompt = f"""Analyze these assets and provide your TOP {top_n} conviction picks.

{asset_summary}

For each pick, provide:
1. SYMBOL - The asset symbol
2. ASSET_CLASS - token/stock/index
3. CONVICTION - Score from 1-100 (100 = highest conviction)
4. REASONING - Brief 1-2 sentence explanation
5. TARGET - Target price (approximate % gain)
6. STOP - Stop loss (approximate % loss)
7. TIMEFRAME - short (1-7 days), medium (1-4 weeks), long (1-3 months)

Format EXACTLY as:
PICK|SYMBOL|ASSET_CLASS|CONVICTION|REASONING|TARGET_PCT|STOP_PCT|TIMEFRAME

Example:
PICK|NVDA|stock|85|Strong AI demand and upcoming earnings catalyst|+15%|-5%|medium

Provide your {top_n} best picks with conviction scores. Be selective - only include assets you have genuine conviction in."""

        response = await grok_client.chat_async(prompt, max_tokens=1500, temperature=0.3)

        # Parse response
        lines = response.strip().split("\n")
        for line in lines:
            if not line.startswith("PICK|"):
                continue
            parts = line.split("|")
            if len(parts) < 8:
                continue

            try:
                symbol = parts[1].strip().upper()
                asset_class = parts[2].strip().lower()
                conviction = int(parts[3].strip())
                reasoning = parts[4].strip()
                target_pct = float(parts[5].strip().replace("%", "").replace("+", ""))
                stop_pct = float(parts[6].strip().replace("%", "").replace("-", ""))
                timeframe = parts[7].strip().lower()

                # Find the asset to get entry price and contract
                entry_price = 0.0
                contract = ""

                if asset_class == "token":
                    for t in tokens:
                        if t.symbol.upper() == symbol:
                            entry_price = t.price_usd
                            contract = t.contract
                            break
                elif asset_class == "stock":
                    for s in stocks:
                        if s.symbol.upper() == symbol or s.underlying.upper() == symbol:
                            entry_price = s.price_usd
                            contract = s.mint_address
                            break
                elif asset_class == "index":
                    for i in indexes:
                        if i.symbol.upper() == symbol or i.underlying.upper() == symbol:
                            entry_price = i.price_usd
                            contract = i.mint_address
                            break

                picks.append(ConvictionPick(
                    symbol=symbol,
                    name=symbol,
                    asset_class=asset_class,
                    contract=contract,
                    conviction_score=min(100, max(1, conviction)),
                    reasoning=reasoning,
                    entry_price=entry_price,
                    target_price=entry_price * (1 + target_pct / 100) if entry_price > 0 else 0,
                    stop_loss=entry_price * (1 - stop_pct / 100) if entry_price > 0 else 0,
                    timeframe=timeframe if timeframe in ("short", "medium", "long") else "medium",
                ))
            except Exception as e:
                warnings.append(f"Failed to parse pick line: {e}")

    except Exception as e:
        warnings.append(f"Grok conviction analysis failed: {e}")

    # Sort by conviction score
    picks.sort(key=lambda p: p.conviction_score, reverse=True)

    return picks[:top_n], warnings


def get_grok_conviction_picks_sync(
    tokens: List[TrendingToken],
    stocks: List[BackedAsset],
    indexes: List[BackedAsset],
    grok_client: Any,
    top_n: int = 10,
) -> Tuple[List[ConvictionPick], List[str]]:
    """Synchronous wrapper for Grok conviction picks."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(
        get_grok_conviction_picks(tokens, stocks, indexes, grok_client, top_n)
    )


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    import asyncio

    async def test():
        print("Testing trending tokens...")
        tokens, warnings = await fetch_trending_solana_tokens(10)
        print(f"Got {len(tokens)} trending tokens")
        for t in tokens:
            print(f"  {t.rank}. {t.symbol}: ${t.price_usd:.8f} ({t.price_change_24h:+.1f}%)")
        if warnings:
            print(f"Warnings: {warnings}")

        print("\nTesting backed.fi assets...")
        stocks, warnings = fetch_backed_stocks()
        print(f"Got {len(stocks)} stocks")
        for s in stocks:
            print(f"  {s.symbol}: ${s.price_usd:.2f}")

        indexes, warnings = fetch_backed_indexes()
        print(f"Got {len(indexes)} indexes")
        for i in indexes:
            print(f"  {i.symbol}: ${i.price_usd:.2f}")

    asyncio.run(test())

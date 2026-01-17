"""Test the enhanced market data module."""
import asyncio
from core.enhanced_market_data import (
    fetch_trending_solana_tokens_sync,
    fetch_backed_stocks,
    fetch_backed_indexes,
    BACKED_XSTOCKS,
)

def main():
    print("Testing enhanced market data module...\n")

    # Test trending tokens
    print("=" * 50)
    print("TRENDING SOLANA TOKENS")
    print("=" * 50)
    tokens, warnings = fetch_trending_solana_tokens_sync(5)
    print(f"Found {len(tokens)} trending tokens")
    for t in tokens:
        price_str = f"${t.price_usd:.8f}" if t.price_usd < 1 else f"${t.price_usd:.4f}"
        print(f"  #{t.rank} {t.symbol}: {price_str} ({t.price_change_24h:+.1f}%)")
    if warnings:
        print(f"Warnings: {warnings[:3]}")

    # Test backed stocks
    print("\n" + "=" * 50)
    print("BACKED XSTOCKS (STOCKS)")
    print("=" * 50)
    stocks, warnings = fetch_backed_stocks()
    print(f"Found {len(stocks)} stocks")
    for s in stocks[:5]:
        print(f"  {s.symbol}: {s.underlying} - {s.name}")

    # Test backed indexes
    print("\n" + "=" * 50)
    print("BACKED XSTOCKS (INDEXES)")
    print("=" * 50)
    indexes, warnings = fetch_backed_indexes()
    print(f"Found {len(indexes)} indexes/commodities/bonds")
    for i in indexes:
        print(f"  {i.symbol}: {i.underlying} ({i.asset_type}) - {i.name}")

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Total xStocks registry: {len(BACKED_XSTOCKS)} tokens")

    # Count by type
    types = {}
    for symbol, info in BACKED_XSTOCKS.items():
        t = info.get("type", "unknown")
        types[t] = types.get(t, 0) + 1

    for t, count in sorted(types.items()):
        print(f"  {t}: {count}")

    print("\nTest complete!")

if __name__ == "__main__":
    main()

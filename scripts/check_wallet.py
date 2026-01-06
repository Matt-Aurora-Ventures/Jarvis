#!/usr/bin/env python3
"""Check wallet status including token balances with price lookup."""

import asyncio
import json
import time
from pathlib import Path

import requests
from solders.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TokenAccountOpts
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey

# Known RPC endpoints (try in order)
RPC_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-mainnet.g.alchemy.com/v2/demo",
]

# Known token symbols for display
KNOWN_TOKENS = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {"symbol": "USDC", "decimals": 6, "price": 1.0},
    "So11111111111111111111111111111111111111112": {"symbol": "WSOL", "decimals": 9},
    "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump": {"symbol": "FARTCOIN", "decimals": 6},
}


def get_sol_price() -> float:
    """Get current SOL price from CoinGecko (free, no key)."""
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("solana", {}).get("usd", 200.0)
    except Exception:
        pass
    return 200.0  # Fallback estimate


def get_token_price_dexscreener(mint: str) -> tuple[float, str]:
    """Get token price from DexScreener (free, no key required)."""
    try:
        resp = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{mint}",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            pairs = data.get("pairs", [])
            if pairs:
                pair = pairs[0]
                symbol = pair.get("baseToken", {}).get("symbol", "???")
                price = float(pair.get("priceUsd", 0) or 0)
                return price, symbol
    except Exception:
        pass
    return 0.0, "???"


async def check_wallet():
    """Main wallet check function."""
    # Load wallet
    wallet_path = Path.home() / ".lifeos" / "wallets" / "phantom_trading_wallet.json"
    if not wallet_path.exists():
        print(f"❌ Wallet not found: {wallet_path}")
        return

    data = json.loads(wallet_path.read_text())
    kp = Keypair.from_bytes(bytes(data))
    pubkey = kp.pubkey()

    print(f"\n{'='*60}")
    print(f"🔐 WALLET: {pubkey}")
    print(f"{'='*60}\n")

    # Get SOL price
    sol_price = get_sol_price()
    print(f"📊 SOL Price: ${sol_price:.2f}\n")

    # Try RPC endpoints
    client = None
    for rpc in RPC_ENDPOINTS:
        try:
            client = AsyncClient(rpc)
            await client.get_balance(pubkey)  # Test connection
            print(f"✅ Connected to RPC: {rpc[:40]}...")
            break
        except Exception:
            continue

    if not client:
        print("❌ Could not connect to any RPC endpoint")
        return

    total_usd = 0.0

    try:
        # Get SOL balance
        balance = await client.get_balance(pubkey)
        sol_balance = balance.value / 1e9
        sol_usd = sol_balance * sol_price
        total_usd += sol_usd

        print(f"💰 SOL Balance: {sol_balance:.6f} SOL (${sol_usd:.2f})")
        print(f"\n📦 Token Holdings:")
        print(f"{'-'*50}")

        # Get token accounts with parsed data
        resp = await client.get_token_accounts_by_owner_json_parsed(
            pubkey,
            TokenAccountOpts(
                program_id=Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
            ),
            Confirmed,
        )

        token_balances = []

        for ta in resp.value:
            info = ta.account.data.parsed["info"]
            mint = info["mint"]
            amount = float(info["tokenAmount"]["uiAmount"] or 0)

            if amount <= 0:
                continue

            # Get token info
            if mint in KNOWN_TOKENS:
                token_info = KNOWN_TOKENS[mint]
                symbol = token_info["symbol"]
                if "price" in token_info:
                    price = token_info["price"]
                else:
                    price, _ = get_token_price_dexscreener(mint)
                    time.sleep(0.3)  # Rate limit
            else:
                price, symbol = get_token_price_dexscreener(mint)
                time.sleep(0.3)  # Rate limit

            usd_value = amount * price
            total_usd += usd_value

            token_balances.append({
                "symbol": symbol,
                "amount": amount,
                "price": price,
                "usd": usd_value,
                "mint": mint,
            })

        # Sort by USD value (highest first)
        token_balances.sort(key=lambda x: x["usd"], reverse=True)

        for tb in token_balances:
            if tb["price"] > 0:
                print(f"  {tb['symbol']:12} {tb['amount']:>15,.4f} @ ${tb['price']:<12.8f} = ${tb['usd']:>10,.2f}")
            else:
                print(f"  {tb['symbol']:12} {tb['amount']:>15,.4f} @ ${'(no price)':<12} = ${'?.??':>10}")

        print(f"{'-'*50}")
        print(f"\n{'='*60}")
        print(f"💵 TOTAL WALLET VALUE: ${total_usd:,.2f}")
        print(f"{'='*60}\n")

        # Summary for sniper
        min_sol_reserve = 0.01  # Keep for tx fees
        available_usd = total_usd - (min_sol_reserve * sol_price)
        print(f"📈 Available for Trading: ${available_usd:,.2f}")
        print(f"   (after {min_sol_reserve} SOL reserve for fees)")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(check_wallet())

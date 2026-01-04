#!/usr/bin/env python3
"""
Savage Swap Executor - Solana DEX Trading Tool
===============================================

Executes Jupiter swaps programmatically using local keypair.
Part of the $20 → $1M Challenge infrastructure.

Security:
- Private key NEVER leaves your machine
- All signing happens locally
- No key exposure to external services

Usage:
    python3 scripts/savage_swap.py --buy FARTCOIN --amount 20
    python3 scripts/savage_swap.py --sell FARTCOIN --percent 50
    python3 scripts/savage_swap.py --status

Requirements:
    pip install solders solana aiohttp base58
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    print("⚠️  aiohttp not installed. Run: pip install aiohttp")

try:
    from solders.keypair import Keypair
    from solders.transaction import VersionedTransaction
    from solana.rpc.async_api import AsyncClient
    HAS_SOLANA = True
except ImportError:
    HAS_SOLANA = False
    print("⚠️  Solana SDK not installed. Run: pip install solders solana base58")


# ============================================================================
# Configuration
# ============================================================================

JUPITER_QUOTE_API = "https://public.jupiterapi.com/quote"
JUPITER_SWAP_API = "https://public.jupiterapi.com/swap"
SOLANA_RPC = "https://api.mainnet-beta.solana.com"

# Token mints
TOKENS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCER3EJmqvQC2Uo9qowWP1h1xFh3Le7YpR1V",
    "FARTCOIN": "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
    "PIPPIN": "Dfh5DzRgSvvCFDoYc2ciTkMrbDfRKybA4SoFbPmApump",
    "TRUMP": "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN",
    "POPCAT": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
    "MOG": "26VfKb7jjtdEdvfovoBijScoZmJbWWasFZkgfUD5w7cy",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
}

# Decimals (pump.fun tokens typically have 6 decimals)
DECIMALS = {
    "SOL": 9,
    "USDC": 6,
    "USDT": 6,
    "FARTCOIN": 6,  # pump.fun token
    "PIPPIN": 6,    # pump.fun token
    "TRUMP": 6,
    "POPCAT": 9,
    "MOG": 9,
    "BONK": 5,
    "WIF": 6,
}


@dataclass
class SwapResult:
    """Result of a swap execution."""
    success: bool
    signature: Optional[str] = None
    input_amount: float = 0.0
    output_amount: float = 0.0
    price_impact: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "signature": self.signature,
            "input_amount": self.input_amount,
            "output_amount": self.output_amount,
            "price_impact": self.price_impact,
            "error": self.error,
        }


# ============================================================================
# Keypair Management
# ============================================================================

def load_keypair(path: Optional[str] = None) -> Optional[Keypair]:
    from core import solana_wallet

    keypair = solana_wallet.load_keypair(path)
    if not keypair:
        print("❌ No keypair found. Options:")
        print("   1. Run: solana-keygen new")
        print("   2. Set SOLANA_PRIVATE_KEY env var")
        print("   3. Add solana_private_key to secrets/keys.json")
    return keypair


# ============================================================================
# Jupiter API
# ============================================================================

async def get_quote(
    input_mint: str,
    output_mint: str,
    amount: int,
    slippage_bps: int = 100,
) -> Optional[Dict[str, Any]]:
    """Get swap quote from Jupiter."""
    if not HAS_AIOHTTP:
        return None
    
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount),
        "slippageBps": slippage_bps,
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(JUPITER_QUOTE_API, params=params) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                print(f"❌ Quote failed: {resp.status}")
                return None


async def get_swap_transaction(
    quote: Dict[str, Any],
    user_public_key: str,
) -> Optional[str]:
    """Get serialized swap transaction from Jupiter."""
    if not HAS_AIOHTTP:
        return None
    
    payload = {
        "quoteResponse": quote,
        "userPublicKey": user_public_key,
        "wrapAndUnwrapSol": True,
        "dynamicComputeUnitLimit": True,
        "prioritizationFeeLamports": "auto",
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(JUPITER_SWAP_API, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("swapTransaction")
            else:
                error = await resp.text()
                print(f"❌ Swap transaction failed: {error}")
                return None


# ============================================================================
# Swap Execution
# ============================================================================

async def execute_swap(
    input_token: str,
    output_token: str,
    amount_usd: float,
    keypair: Keypair,
    slippage_bps: int = 100,
) -> SwapResult:
    """
    Execute a swap via Jupiter.
    
    Args:
        input_token: Token symbol to sell (e.g., "USDC")
        output_token: Token symbol to buy (e.g., "FARTCOIN")
        amount_usd: Amount in USD (for USDC input)
        keypair: Solana keypair for signing
        slippage_bps: Slippage tolerance in basis points
        
    Returns:
        SwapResult with transaction details
    """
    if not HAS_SOLANA or not HAS_AIOHTTP:
        return SwapResult(success=False, error="Missing dependencies")
    
    # Resolve token mints
    input_mint = TOKENS.get(input_token.upper())
    output_mint = TOKENS.get(output_token.upper())
    
    if not input_mint:
        # Assume it's a mint address
        input_mint = input_token
    if not output_mint:
        output_mint = output_token
    
    # Calculate amount in smallest units
    from core import solana_tokens

    input_decimals = DECIMALS.get(input_token.upper())
    if input_decimals is None:
        input_decimals = solana_tokens.get_token_decimals(input_mint, fallback=6)
    amount_lamports = int(amount_usd * (10 ** input_decimals))
    
    print(f"\n🔄 Swapping {amount_usd} {input_token} → {output_token}")
    print(f"   Input mint: {input_mint[:20]}...")
    print(f"   Output mint: {output_mint[:20]}...")
    
    # Get quote
    print("📊 Getting quote...")
    quote = await get_quote(input_mint, output_mint, amount_lamports, slippage_bps)
    
    if not quote:
        return SwapResult(success=False, error="Failed to get quote")
    
    out_amount_raw = int(quote.get("outAmount", 0))
    output_decimals = DECIMALS.get(output_token.upper())
    if output_decimals is None:
        output_decimals = solana_tokens.get_token_decimals(output_mint, fallback=9)
    out_amount = out_amount_raw / (10 ** output_decimals)
    price_impact = float(quote.get("priceImpactPct", 0)) * 100
    
    print(f"   Output: {out_amount:,.4f} {output_token}")
    print(f"   Price impact: {price_impact:.4f}%")
    
    # Get swap transaction
    print("🔧 Building transaction...")
    user_pubkey = str(keypair.pubkey())
    swap_tx_b64 = await get_swap_transaction(quote, user_pubkey)

    if not swap_tx_b64:
        return SwapResult(success=False, error="Failed to get swap transaction")

    # Deserialize, sign, and send via reliable executor
    print("✍️  Signing transaction...")
    try:
        from core import solana_execution

        tx_bytes = base64.b64decode(swap_tx_b64)
        tx = VersionedTransaction.from_bytes(tx_bytes)
        signed_tx = VersionedTransaction(tx.message, [keypair])

        print("📤 Sending to Solana (RPC failover + confirm)...")
        endpoints = solana_execution.load_solana_rpc_endpoints()
        result = await solana_execution.execute_swap_transaction(
            signed_tx,
            endpoints,
            simulate=True,
            commitment="confirmed",
        )

        if result.success and result.signature:
            sig_str = result.signature
            print(f"\n✅ SWAP EXECUTED!")
            print(f"   Signature: {sig_str}")
            print(f"   Explorer: https://solscan.io/tx/{sig_str}")

            return SwapResult(
                success=True,
                signature=sig_str,
                input_amount=amount_usd,
                output_amount=out_amount,
                price_impact=price_impact,
            )
        return SwapResult(success=False, error=result.error or "Execution failed")
    except Exception as e:
        return SwapResult(success=False, error=str(e))


# ============================================================================
# Exit Intent Integration
# ============================================================================

def create_exit_intent(
    position_id: str,
    token: str,
    entry_price: float,
    quantity: float,
):
    """Create exit intent for a new position."""
    from core import exit_intents

    token_mint = TOKENS.get(token.upper(), token)
    return exit_intents.create_spot_intent(
        position_id=position_id,
        token_mint=token_mint,
        symbol=token.upper(),
        entry_price=entry_price,
        quantity=quantity,
        is_paper=False,
    )


def persist_exit_intent(intent) -> bool:
    """Persist exit intent to disk."""
    from core import exit_intents

    try:
        exit_intents.persist_intent(intent)
        print(f"✅ Exit intent saved to {exit_intents.INTENTS_FILE}")
        return True
    except Exception as exc:
        print(f"❌ Failed to save exit intent: {exc}")
        return False


# ============================================================================
# CLI
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="Savage Swap Executor - Solana DEX Trading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Buy $20 of FARTCOIN with USDC
  python3 savage_swap.py --buy FARTCOIN --amount 20
  
  # Buy with SOL instead of USDC
  python3 savage_swap.py --buy FARTCOIN --amount 0.15 --from SOL
  
  # Sell 50% of a position
  python3 savage_swap.py --sell FARTCOIN --percent 50
  
  # Check wallet status
  python3 savage_swap.py --status
        """
    )
    
    parser.add_argument("--buy", type=str, help="Token to buy (e.g., FARTCOIN)")
    parser.add_argument("--sell", type=str, help="Token to sell")
    parser.add_argument("--amount", type=float, help="Amount in USD (or input token)")
    parser.add_argument("--percent", type=float, help="Percent of position to sell")
    parser.add_argument("--from", dest="from_token", type=str, default="USDC", help="Input token (default: USDC)")
    parser.add_argument("--to", dest="to_token", type=str, default="USDC", help="Output token for sells (default: USDC)")
    parser.add_argument("--slippage", type=int, default=100, help="Slippage in bps (default: 100 = 1%)")
    parser.add_argument("--keypair", type=str, help="Path to keypair file")
    parser.add_argument("--status", action="store_true", help="Show wallet status")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without executing")
    
    args = parser.parse_args()
    
    # Check dependencies
    if not HAS_SOLANA or not HAS_AIOHTTP:
        print("\n❌ Missing dependencies. Install with:")
        print("   pip install solders solana aiohttp base58")
        return
    
    # Load keypair
    keypair = load_keypair(args.keypair)
    if not keypair:
        return
    
    pubkey = str(keypair.pubkey())
    print(f"🔑 Wallet: {pubkey[:20]}...{pubkey[-8:]}")
    
    # Status check
    if args.status:
        print("\n📊 Wallet Status")
        print("-" * 40)
        from core import solana_execution
        endpoints = solana_execution.load_solana_rpc_endpoints()
        async with AsyncClient(endpoints[0].url) as client:
            balance = await client.get_balance(keypair.pubkey())
            sol_balance = balance.value / 1e9
            print(f"   SOL: {sol_balance:.4f}")
        return
    
    # Buy flow
    if args.buy:
        if not args.amount:
            print("❌ --amount required for buy")
            return
        
        input_token = args.from_token
        output_token = args.buy
        amount = args.amount
        
        if args.dry_run:
            print(f"\n🔄 [DRY RUN] Would swap {amount} {input_token} → {output_token}")
            quote = await get_quote(
                TOKENS.get(input_token.upper(), input_token),
                TOKENS.get(output_token.upper(), output_token),
                int(amount * (10 ** DECIMALS.get(input_token.upper(), 6))),
                args.slippage,
            )
            if quote:
                out_amount = int(quote.get("outAmount", 0)) / (10 ** DECIMALS.get(output_token.upper(), 9))
                print(f"   Would receive: {out_amount:,.4f} {output_token}")
            return
        
        # Check SOL balance for fees
        from core import solana_execution
        endpoints = solana_execution.load_solana_rpc_endpoints()
        async with AsyncClient(endpoints[0].url) as client:
            balance = await client.get_balance(keypair.pubkey())
            sol_balance = balance.value / 1e9
            if sol_balance <= 0.005:
                print("❌ Insufficient SOL for fees. Top up before trading.")
                return

        # Execute swap
        result = await execute_swap(
            input_token=input_token,
            output_token=output_token,
            amount_usd=amount,
            keypair=keypair,
            slippage_bps=args.slippage,
        )
        
        if result.success:
            # Create and persist exit intent
            position_id = f"savage-{result.signature[:8] if result.signature else 'manual'}"
            
            # Estimate entry price
            if result.output_amount > 0:
                entry_price = amount / result.output_amount
            else:
                entry_price = 0.35  # Fallback for FARTCOIN
            
            intent = create_exit_intent(
                position_id=position_id,
                token=output_token,
                entry_price=entry_price,
                quantity=result.output_amount,
            )
            persist_exit_intent(intent)
            
            print(f"\n🔥 SAVAGE TRADE COMPLETE!")
            print(f"   Position: {position_id}")
        else:
            print(f"\n❌ Trade failed: {result.error}")
    
    # Sell flow
    elif args.sell:
        token = args.sell
        percent = args.percent or 100.0
        if percent <= 0:
            print("❌ --percent must be > 0")
            return

        mint = TOKENS.get(token.upper(), token)
        from core import solana_tokens

        from core import solana_execution
        endpoints = solana_execution.load_solana_rpc_endpoints()
        async with AsyncClient(endpoints[0].url) as client:
            resp = await client.get_token_accounts_by_owner(
                keypair.pubkey(),
                {"mint": mint},
            )
            if not resp.value:
                print(f"❌ No token accounts found for {token}")
                return
            balance = 0.0
            for item in resp.value:
                amount = float(item.account.data.parsed["info"]["tokenAmount"]["uiAmount"] or 0.0)
                balance += amount
            if balance <= 0:
                print(f"❌ Zero balance for {token}")
                return

        sell_amount = balance * (percent / 100.0)
        print(f"\n🔄 Selling {sell_amount:.6f} {token} ({percent:.1f}% of balance)")

        result = await execute_swap(
            input_token=token,
            output_token=args.to_token,
            amount_usd=sell_amount,
            keypair=keypair,
            slippage_bps=args.slippage,
        )

        if result.success:
            print(f"\n✅ SELL COMPLETE! Signature: {result.signature}")
        else:
            print(f"\n❌ Sell failed: {result.error}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())

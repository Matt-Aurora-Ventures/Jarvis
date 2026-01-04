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
import os
import sys
import time
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
    from solders.message import to_bytes_versioned
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.commitment import Confirmed
    import base58
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
    """
    Load Solana keypair from file.
    
    Tries (in order):
    1. Provided path
    2. ~/.config/solana/id.json (Solana CLI default)
    3. secrets/keys.json (LifeOS format)
    4. SOLANA_PRIVATE_KEY env var
    """
    if not HAS_SOLANA:
        print("❌ Solana SDK not installed")
        return None
    
    # Try provided path
    if path:
        return _load_keypair_from_file(Path(path))
    
    # Try Solana CLI default
    solana_default = Path.home() / ".config" / "solana" / "id.json"
    if solana_default.exists():
        kp = _load_keypair_from_file(solana_default)
        if kp:
            print(f"✅ Loaded keypair from {solana_default}")
            return kp
    
    # Try LifeOS wallets directory
    lifeos_wallets = Path.home() / ".lifeos" / "wallets"
    if lifeos_wallets.exists():
        # Try JSON format first
        json_wallet = lifeos_wallets / "phantom_trading_wallet.json"
        if json_wallet.exists():
            kp = _load_keypair_from_file(json_wallet)
            if kp:
                print(f"✅ Loaded keypair from {json_wallet}")
                return kp
        
        # Try base58 format
        base58_wallet = lifeos_wallets / "phantom_trading_wallet.base58"
        if base58_wallet.exists():
            try:
                key_str = base58_wallet.read_text().strip()
                secret_bytes = base58.b58decode(key_str)
                kp = Keypair.from_bytes(secret_bytes)
                print(f"✅ Loaded keypair from {base58_wallet}")
                return kp
            except Exception as e:
                print(f"⚠️  Failed to load from base58 wallet: {e}")
    
    # Try LifeOS secrets
    lifeos_secrets = Path(__file__).parent.parent / "secrets" / "keys.json"
    if lifeos_secrets.exists():
        kp = _load_keypair_from_lifeos_secrets(lifeos_secrets)
        if kp:
            print(f"✅ Loaded keypair from LifeOS secrets")
            return kp
    
    # Try env var
    env_key = os.environ.get("SOLANA_PRIVATE_KEY")
    if env_key:
        try:
            secret_bytes = base58.b58decode(env_key)
            kp = Keypair.from_bytes(secret_bytes)
            print("✅ Loaded keypair from SOLANA_PRIVATE_KEY env var")
            return kp
        except Exception as e:
            print(f"⚠️  Failed to load from env var: {e}")
    
    print("❌ No keypair found. Options:")
    print("   1. Run: solana-keygen new")
    print("   2. Set SOLANA_PRIVATE_KEY env var")
    print("   3. Add solana_private_key to secrets/keys.json")
    return None


def _load_keypair_from_file(path: Path) -> Optional[Keypair]:
    """Load keypair from JSON array file (Solana CLI format)."""
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            secret_bytes = bytes(data)
            return Keypair.from_bytes(secret_bytes)
    except Exception as e:
        print(f"⚠️  Failed to load keypair from {path}: {e}")
    return None


def _load_keypair_from_lifeos_secrets(path: Path) -> Optional[Keypair]:
    """Load keypair from LifeOS secrets format."""
    try:
        data = json.loads(path.read_text())
        
        # Try different key names
        for key_name in ["solana_private_key", "solana_key", "private_key", "wallet_key"]:
            if key_name in data:
                key_value = data[key_name]
                
                # Try base58 decode
                try:
                    secret_bytes = base58.b58decode(key_value)
                    return Keypair.from_bytes(secret_bytes)
                except:
                    pass
                
                # Try JSON array
                try:
                    if isinstance(key_value, list):
                        secret_bytes = bytes(key_value)
                        return Keypair.from_bytes(secret_bytes)
                except:
                    pass
                
    except Exception as e:
        print(f"⚠️  Failed to load from LifeOS secrets: {e}")
    return None


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
    input_decimals = DECIMALS.get(input_token.upper(), 6)
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
    output_decimals = DECIMALS.get(output_token.upper(), 9)
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
    
    # Deserialize, sign, and send
    print("✍️  Signing transaction...")
    try:
        tx_bytes = base64.b64decode(swap_tx_b64)
        
        # Parse the versioned transaction
        from solders.transaction import VersionedTransaction as VTx
        tx = VTx.from_bytes(tx_bytes)
        
        # Create a new signed transaction with our keypair
        # The transaction from Jupiter has a placeholder signature that we replace
        signed_tx = VTx(tx.message, [keypair])
        
        # Send to Solana
        print("📤 Sending to Solana...")
        async with AsyncClient(SOLANA_RPC) as client:
            # Use send_transaction with skip_preflight for faster execution
            from solana.rpc.types import TxOpts
            result = await client.send_transaction(
                signed_tx,
                opts=TxOpts(skip_preflight=True, max_retries=3),
            )
            
            if result.value:
                sig_str = str(result.value)
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
            else:
                return SwapResult(success=False, error="No signature returned")
                
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
) -> Dict[str, Any]:
    """Create exit intent for a new position."""
    now = time.time()
    
    intent = {
        "id": position_id[:8],
        "position_id": position_id,
        "position_type": "spot",
        "token_mint": TOKENS.get(token.upper(), token),
        "symbol": token.upper(),
        "entry_price": entry_price,
        "entry_timestamp": now,
        "original_quantity": quantity,
        "remaining_quantity": quantity,
        "status": "active",
        "take_profits": [
            {"level": 1, "price": entry_price * 1.30, "size_pct": 60, "filled": False},
            {"level": 2, "price": entry_price * 1.60, "size_pct": 25, "filled": False},
            {"level": 3, "price": entry_price * 2.00, "size_pct": 15, "filled": False},
        ],
        "stop_loss": {
            "price": entry_price * 0.88,
            "size_pct": 100.0,
            "adjusted": False,
            "original_price": entry_price * 0.88,
        },
        "time_stop": {
            "deadline_timestamp": now + (90 * 60),
            "action": "exit_fully",
            "triggered": False,
        },
        "trailing_stop": {
            "active": False,
            "trail_pct": 0.20,
            "highest_price": entry_price,
            "current_stop": 0.0,
        },
        "is_paper": False,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    
    return intent


def persist_exit_intent(intent: Dict[str, Any]) -> bool:
    """Persist exit intent to disk."""
    trading_dir = Path.home() / ".lifeos" / "trading"
    trading_dir.mkdir(parents=True, exist_ok=True)
    intents_file = trading_dir / "exit_intents.json"
    
    intents = []
    if intents_file.exists():
        try:
            data = json.loads(intents_file.read_text())
            if isinstance(data, list):
                intents = data
            else:
                intents = [data]
        except:
            intents = []
    
    intents.append(intent)
    intents_file.write_text(json.dumps(intents, indent=2))
    print(f"✅ Exit intent saved to {intents_file}")
    return True


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
        async with AsyncClient(SOLANA_RPC) as client:
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
        print("❌ Sell flow not yet implemented")
        print("   Use Jupiter directly: https://jup.ag")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())

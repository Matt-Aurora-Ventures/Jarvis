#!/usr/bin/env python3
"""
Emergency script to sell all treasury positions and transfer SOL to target wallet.
Target: AXYFBhYPhHt4SzGqdpSfBSMWEQmKdCyQScA1xjRvHzph
"""

import sys
import os
import asyncio
import json
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.system_program import transfer
from solders.message import Message
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts

# Import Jarvis modules
from bots.treasury.jupiter import JupiterClient
from core.security.key_manager import load_treasury_keypair

TARGET_WALLET = "AXYFBhYPhHt4SzGqdpSfBSMWEQmKdCyQScA1xjRvHzph"
POSITIONS_FILE = Path(__file__).parent.parent / "bots" / "treasury" / ".positions.json"
SOL_MINT = "So11111111111111111111111111111111111111112"
# IMPORTANT: Never hardcode RPC API keys in the repo.
HELIUS_RPC = os.getenv("HELIUS_RPC_URL") or os.getenv("SOLANA_RPC_URL") or "https://api.mainnet-beta.solana.com"


class SimpleWalletInfo:
    """Simple wrapper to mimic WalletInfo interface"""
    def __init__(self, keypair: Keypair):
        self.keypair = keypair
        self.address = str(keypair.pubkey())
        self.is_treasury = True


class SimpleWalletWrapper:
    """Simple wrapper to make Keypair work with JupiterClient"""
    def __init__(self, keypair: Keypair):
        self.keypair = keypair
        self._treasury = SimpleWalletInfo(keypair)

    def get_treasury(self) -> SimpleWalletInfo:
        """Return treasury wallet info"""
        return self._treasury

    def sign_transaction(self, address: str, tx_bytes: bytes) -> bytes:
        """Sign transaction bytes with keypair"""
        from solders.transaction import VersionedTransaction

        # Deserialize transaction
        tx = VersionedTransaction.from_bytes(tx_bytes)

        # Sign it
        tx.sign([self.keypair], tx.message.recent_blockhash)

        # Return serialized
        return bytes(tx)


async def sell_all_positions():
    """Sell all non-SOL positions"""
    print("Loading positions...")

    if not POSITIONS_FILE.exists():
        print("ERROR: No positions file found")
        return

    with open(POSITIONS_FILE, 'r') as f:
        positions = json.load(f)

    # Filter out SOL and closed positions
    open_positions = [p for p in positions if p['status'] == 'OPEN' and p['token_symbol'] != 'SOL']

    if not open_positions:
        print("SUCCESS: No open positions to sell")
        return

    print(f"Found {len(open_positions)} positions to sell:")
    for pos in open_positions:
        print(f"  - {pos['token_symbol']}: ${pos['amount_usd']:.2f}")

    # Load wallet
    treasury_keypair = load_treasury_keypair()
    if not treasury_keypair:
        print("ERROR: Could not load treasury keypair")
        return

    # Wrap keypair for Jupiter
    wallet_wrapper = SimpleWalletWrapper(treasury_keypair)

    # Initialize Jupiter
    jupiter = JupiterClient(rpc_url=HELIUS_RPC)

    # Sell each position
    for pos in open_positions:
        token_mint = pos['token_mint']
        amount = pos['amount']
        symbol = pos['token_symbol']

        print(f"\nSelling {symbol} (amount: {amount})...")

        try:
            # Get quote first
            # Amount needs to be in token's smallest unit (usually 1e9 for 9 decimals)
            amount_lamports = int(amount * 1e9)

            print(f"  Getting quote for {amount_lamports} lamports...")
            quote = await jupiter.get_quote(
                input_mint=token_mint,
                output_mint=SOL_MINT,
                amount=amount_lamports,
                slippage_bps=100  # 1% slippage
            )

            if not quote:
                print(f"  ERROR: Could not get quote for {symbol}")
                continue

            print(f"  Quote: {quote.input_amount_ui:.6f} {symbol} -> {quote.output_amount_ui:.6f} SOL")

            # Execute swap
            print(f"  Executing swap...")
            result = await jupiter.execute_swap(
                quote=quote,
                wallet=wallet_wrapper,
                simulate_first=True
            )

            if result.success:
                print(f"  SUCCESS: Sold {symbol}")
                print(f"    Signature: {result.signature}")
                print(f"    https://solscan.io/tx/{result.signature}")
            else:
                print(f"  ERROR: Failed to sell {symbol}: {result.error}")
        except Exception as e:
            print(f"  ERROR selling {symbol}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Small delay between swaps
            await asyncio.sleep(2)

    # Close Jupiter session
    await jupiter.close()

    print("\nAll positions processed")


async def transfer_all_sol():
    """Transfer all SOL to target wallet"""
    print("\nTransferring all SOL...")

    # Load wallet
    treasury_keypair = load_treasury_keypair()
    if not treasury_keypair:
        print("ERROR: Could not load treasury keypair")
        return

    # Get balance
    rpc_client = AsyncClient(HELIUS_RPC)

    try:
        balance_resp = await rpc_client.get_balance(treasury_keypair.pubkey())
        balance_lamports = balance_resp.value
        balance_sol = balance_lamports / 1e9

        print(f"Current balance: {balance_sol:.4f} SOL ({balance_lamports} lamports)")

        if balance_lamports < 10000:  # Less than 0.00001 SOL
            print("Balance too low to transfer (need lamports for fees)")
            return

        # Reserve 5000 lamports for transaction fee
        transfer_amount = balance_lamports - 5000

        if transfer_amount <= 0:
            print("Balance too low after reserving fee")
            return

        print(f"Transferring {transfer_amount / 1e9:.4f} SOL to {TARGET_WALLET}...")

        # Create transfer instruction
        target_pubkey = Pubkey.from_string(TARGET_WALLET)
        transfer_ix = transfer(
            {
                "from_pubkey": treasury_keypair.pubkey(),
                "to_pubkey": target_pubkey,
                "lamports": transfer_amount
            }
        )

        # Get recent blockhash
        blockhash_resp = await rpc_client.get_latest_blockhash()
        recent_blockhash = blockhash_resp.value.blockhash

        # Create and sign transaction
        message = Message.new_with_blockhash(
            [transfer_ix],
            treasury_keypair.pubkey(),
            recent_blockhash
        )

        tx = VersionedTransaction(message, [treasury_keypair])

        # Send transaction
        tx_resp = await rpc_client.send_transaction(
            tx,
            opts=TxOpts(skip_preflight=False, preflight_commitment=Confirmed)
        )

        signature = str(tx_resp.value)
        print(f"SUCCESS: Transfer complete")
        print(f"  Signature: {signature}")
        print(f"  https://solscan.io/tx/{signature}")

    except Exception as e:
        print(f"Transfer failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await rpc_client.close()


async def main():
    print("=" * 60)
    print("EMERGENCY TREASURY SELLALL & TRANSFER")
    print("=" * 60)

    # Step 1: Sell all positions
    await sell_all_positions()

    # Wait a bit for swaps to settle
    print("\nWaiting 10 seconds for swaps to settle...")
    await asyncio.sleep(10)

    # Step 2: Transfer all SOL
    await transfer_all_sol()

    print("\n" + "=" * 60)
    print("OPERATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

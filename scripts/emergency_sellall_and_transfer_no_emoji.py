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

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed

# Import Jarvis modules
from bots.treasury.jupiter import JupiterClient
from core.security.key_manager import KeyManager, load_treasury_keypair

TARGET_WALLET = "AXYFBhYPhHt4SzGqdpSfBSMWEQmKdCyQScA1xjRvHzph"
POSITIONS_FILE = Path(__file__).parent.parent / "bots" / "treasury" / ".positions.json"

async def sell_all_positions():
    """Sell all non-SOL positions"""
    print(" Loading positions...")

    if not POSITIONS_FILE.exists():
        print(" No positions file found")
        return

    with open(POSITIONS_FILE, 'r') as f:
        positions = json.load(f)

    # Filter out SOL and closed positions
    open_positions = [p for p in positions if p['status'] == 'OPEN' and p['token_symbol'] != 'SOL']

    if not open_positions:
        print(" No open positions to sell")
        return

    print(f" Found {len(open_positions)} positions to sell:")
    for pos in open_positions:
        print(f"  - {pos['token_symbol']}: ${pos['amount_usd']:.2f}")

    # Load wallet
    treasury_keypair = load_treasury_keypair()

    # Initialize Jupiter
    jupiter = JupiterClient()

    # Sell each position
    for pos in open_positions:
        token_mint = pos['token_mint']
        amount = pos['amount']
        symbol = pos['token_symbol']

        print(f"\n Selling {symbol} (amount: {amount})...")

        try:
            # Swap to SOL
            result = await jupiter.swap(
                wallet=treasury_keypair,
                input_mint=token_mint,
                output_mint="So11111111111111111111111111111111111111112",  # SOL
                amount=int(amount * 1e9),  # Convert to lamports
                slippage_bps=100  # 1% slippage
            )

            if result.get('success'):
                print(f" Sold {symbol}: {result.get('signature', 'N/A')}")
            else:
                print(f" Failed to sell {symbol}: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f" Error selling {symbol}: {e}")

    print("\n All positions sold")

async def transfer_all_sol():
    """Transfer all SOL to target wallet"""
    print("\n Transferring all SOL...")

    # Load wallet
    treasury_keypair = load_treasury_keypair()

    # Get balance
    rpc_client = AsyncClient("https://api.mainnet-beta.solana.com")

    try:
        balance_resp = await rpc_client.get_balance(treasury_keypair.pubkey())
        balance_lamports = balance_resp.value
        balance_sol = balance_lamports / 1e9

        print(f" Current balance: {balance_sol:.4f} SOL ({balance_lamports} lamports)")

        if balance_lamports < 5000:  # Less than 0.000005 SOL
            print(" Insufficient balance to transfer")
            return

        # Reserve 0.001 SOL for transaction fee
        fee_lamports = 1_000_000  # 0.001 SOL
        transfer_amount = balance_lamports - fee_lamports

        if transfer_amount <= 0:
            print(" Not enough SOL after fee reservation")
            return

        print(f" Transferring {transfer_amount / 1e9:.4f} SOL to {TARGET_WALLET}...")

        # Create transfer instruction
        target_pubkey = Pubkey.from_string(TARGET_WALLET)
        transfer_ix = transfer(
            TransferParams(
                from_pubkey=treasury_keypair.pubkey(),
                to_pubkey=target_pubkey,
                lamports=transfer_amount
            )
        )

        # Get recent blockhash
        blockhash_resp = await rpc_client.get_latest_blockhash()
        recent_blockhash = blockhash_resp.value.blockhash

        # Create and sign transaction
        tx = Transaction(recent_blockhash=recent_blockhash, fee_payer=treasury_keypair.pubkey())
        tx.add(transfer_ix)
        tx.sign(treasury_keypair)

        # Send transaction
        result = await rpc_client.send_transaction(tx)
        signature = str(result.value)

        print(f" Transfer complete!")
        print(f" Signature: {signature}")
        print(f" https://solscan.io/tx/{signature}")

    except Exception as e:
        print(f" Transfer failed: {e}")
    finally:
        await rpc_client.close()

async def main():
    print("=" * 60)
    print(" EMERGENCY TREASURY SELLALL & TRANSFER")
    print("=" * 60)

    # Step 1: Sell all positions
    await sell_all_positions()

    # Wait a bit for swaps to settle
    print("\n Waiting 5 seconds for swaps to settle...")
    await asyncio.sleep(5)

    # Step 2: Transfer all SOL
    await transfer_all_sol()

    print("\n" + "=" * 60)
    print(" OPERATION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

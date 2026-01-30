#!/usr/bin/env python3
"""
Test script for bags.fm real swap execution.

Usage:
    python scripts/test_bags_swap.py [--execute]

Without --execute, it will only get a quote and show what would happen.
With --execute, it will actually perform the swap.
"""

import os
import sys
import json
import asyncio
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "../tg_bot/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
    
    # Load secrets
    secrets_path = "/root/clawd/secrets/keys.json"
    if os.path.exists(secrets_path):
        with open(secrets_path) as f:
            secrets = json.load(f)
            if 'bags_api_key' in secrets:
                os.environ['BAGS_API_KEY'] = secrets['bags_api_key']
            if 'bags_partner_key' in secrets:
                os.environ['BAGS_PARTNER_KEY'] = secrets['bags_partner_key']
            if 'helius' in secrets and 'api_key' in secrets['helius']:
                os.environ['HELIUS_API_KEY'] = secrets['helius']['api_key']

load_env()


async def test_swap(execute: bool = False):
    """Test the bags.fm swap flow."""
    from core.trading.bags_client import BagsAPIClient, SwapStatus
    
    # Constants
    SOL_MINT = "So11111111111111111111111111111111111111112"
    TREASURY_WALLET = "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR"
    
    # Test token - using FARTCOIN as it's active
    TEST_TOKEN = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
    TEST_AMOUNT = 0.01  # 0.01 SOL
    
    print("=" * 60)
    print("BAGS.FM SWAP TEST")
    print("=" * 60)
    print(f"Treasury Wallet: {TREASURY_WALLET}")
    print(f"Token: {TEST_TOKEN}")
    print(f"Amount: {TEST_AMOUNT} SOL")
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN (quote only)'}")
    print("=" * 60)
    
    # Initialize client
    client = BagsAPIClient()
    
    # Step 1: Test keypair loading
    print("\n[1/4] Testing keypair decryption...")
    keypair_path = os.path.join(os.path.dirname(__file__), "../data/treasury_keypair.json")
    keypair = await client._load_keypair(keypair_path)
    
    if not keypair:
        print("✗ Failed to load keypair!")
        print("  Check TREASURY_PASSWORD or JARVIS_WALLET_PASSWORD in .env")
        return False
    
    pubkey = str(keypair.pubkey())
    print(f"✓ Keypair loaded: {pubkey}")
    
    if pubkey != TREASURY_WALLET:
        print(f"⚠ Warning: Keypair pubkey ({pubkey}) doesn't match expected ({TREASURY_WALLET})")
    
    # Step 2: Get quote
    print("\n[2/4] Getting quote from bags.fm...")
    quote = await client.get_quote_raw(
        from_token=SOL_MINT,
        to_token=TEST_TOKEN,
        amount=TEST_AMOUNT,
        slippage_bps=200
    )
    
    if not quote:
        print("✗ Failed to get quote!")
        return False
    
    in_amount = int(quote.get('inAmount', 0)) / 1e9
    out_amount = int(quote.get('outAmount', 0)) / 1e9  # Adjust decimals as needed
    price_impact = quote.get('priceImpactPct', 0)
    
    print(f"✓ Quote received:")
    print(f"  - Input: {in_amount} SOL")
    print(f"  - Output: ~{out_amount:.6f} tokens")
    print(f"  - Price Impact: {price_impact}%")
    print(f"  - Request ID: {quote.get('requestId')}")
    
    if not execute:
        print("\n" + "=" * 60)
        print("DRY RUN COMPLETE")
        print("To execute the swap, run with --execute flag")
        print("=" * 60)
        return True
    
    # Step 3: Execute swap
    print("\n[3/4] Executing swap via bags.fm...")
    result = await client.swap(
        from_token=SOL_MINT,
        to_token=TEST_TOKEN,
        amount=TEST_AMOUNT,
        wallet_address=TREASURY_WALLET,
        slippage_bps=200
    )
    
    if not result.success:
        print(f"✗ Swap failed: {result.error}")
        return False
    
    print(f"✓ Swap successful!")
    print(f"  - TX Hash: {result.tx_hash}")
    print(f"  - Tokens received: {result.to_amount}")
    
    # Step 4: Verify on Solscan
    print("\n[4/4] Transaction details:")
    print(f"  Solscan: https://solscan.io/tx/{result.tx_hash}")
    print(f"  Solana Explorer: https://explorer.solana.com/tx/{result.tx_hash}")
    
    print("\n" + "=" * 60)
    print("SWAP COMPLETE")
    print("=" * 60)
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Test bags.fm swap execution')
    parser.add_argument('--execute', action='store_true', help='Actually execute the swap (default: dry run)')
    args = parser.parse_args()
    
    success = asyncio.run(test_swap(execute=args.execute))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Check wallet status on VPS."""

import asyncio
from pathlib import Path

async def main():
    # Check treasury wallet
    try:
        from bots.treasury.wallet import SecureWallet
        treasury_wallet = SecureWallet(Path("./wallets/treasury.json"))
        treasury = treasury_wallet.get_treasury()
        if treasury:
            print(f"✓ Treasury wallet: {treasury.address}")
        else:
            print("✗ Treasury wallet not initialized")
    except Exception as e:
        print(f"✗ Treasury wallet error: {e}")

    # Check demo wallet
    try:
        demo_wallet = SecureWallet(Path("bots/treasury/.wallets-demo"), profile="demo")
        demo_treasury = demo_wallet.get_treasury()
        if demo_treasury:
            print(f"✓ Demo wallet: {demo_treasury.address}")
        else:
            print("✗ Demo wallet not initialized")
    except Exception as e:
        print(f"✗ Demo wallet error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Setup VPS Wallets for Jarvis Treasury
Creates encrypted wallet files for treasury, active trading, and profit wallets.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bots.treasury.wallet import SecureWallet, WalletInfo


def setup_wallets():
    """Create all required wallets for VPS deployment."""

    # Check for master password
    master_password = os.environ.get('JARVIS_WALLET_PASSWORD')
    if not master_password:
        print("ERROR: JARVIS_WALLET_PASSWORD environment variable not set")
        print("\nSet it with:")
        print("  export JARVIS_WALLET_PASSWORD='your-secure-password'")
        sys.exit(1)

    # Create wallet directory
    wallet_dir = Path("./wallets")
    wallet_dir.mkdir(parents=True, exist_ok=True)

    print("=== Jarvis Wallet Setup ===\n")

    try:
        # Initialize secure wallet manager
        wallet_manager = SecureWallet(master_password=master_password, wallet_dir=wallet_dir)
        print("✓ Wallet manager initialized")

        # Create treasury wallet
        print("\n1. Creating treasury wallet...")
        treasury_info = wallet_manager.create_wallet(label="Treasury", is_treasury=True)
        print(f"   ✓ Treasury: {treasury_info.address}")

        # Create active trading wallet
        print("\n2. Creating active trading wallet...")
        active_info = wallet_manager.create_wallet(label="Active Trading", is_treasury=False)
        print(f"   ✓ Active: {active_info.address}")

        # Create profit wallet
        print("\n3. Creating profit wallet...")
        profit_info = wallet_manager.create_wallet(label="Profit", is_treasury=False)
        print(f"   ✓ Profit: {profit_info.address}")

        # Create legacy file paths for backward compatibility
        legacy_paths = {
            'treasury.json': treasury_info.address,
            'active.json': active_info.address,
            'profit.json': profit_info.address
        }

        for filename, address in legacy_paths.items():
            legacy_path = wallet_dir / filename
            with open(legacy_path, 'w') as f:
                json.dump({
                    'address': address,
                    'note': 'Private keys stored in .wallets/ directory',
                    'created_by': 'setup_vps_wallets.py'
                }, f, indent=2)

        print("\n✓ Legacy compatibility files created")

        # Output summary
        print("\n=== Setup Complete ===")
        print(f"\nWallets created in: {wallet_dir.absolute()}")
        print(f"Treasury: {treasury_info.address}")
        print(f"Active:   {active_info.address}")
        print(f"Profit:   {profit_info.address}")

        print("\n⚠️  IMPORTANT:")
        print("1. Backup the .wallets/ directory securely")
        print("2. Never commit wallet files to git")
        print("3. Keep JARVIS_WALLET_PASSWORD secure")
        print("4. Fund the treasury wallet before trading")

        return True

    except Exception as e:
        print(f"\n✗ Error creating wallets: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = setup_wallets()
    sys.exit(0 if success else 1)

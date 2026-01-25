#!/usr/bin/env python3
"""
Freeze Token Metadata - Make $KR8TIV metadata immutable

This script uses Metaplex to freeze token metadata on Solana.
Once frozen, the metadata (name, symbol, image) can NEVER be changed.

Usage:
    python scripts/freeze_token_metadata.py --mint <MINT_ADDRESS> --keypair <PATH_TO_KEYPAIR>

Requirements:
    - solana-py
    - metaplex-python (or we'll use subprocess to call metaplex CLI)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from solana.rpc.api import Client
from solders.pubkey import Pubkey


class MetadataFreezer:
    """Freeze Metaplex token metadata."""

    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        self.client = Client(rpc_url)

    def get_metadata_pda(self, mint: Pubkey) -> Pubkey:
        """
        Derive the Metaplex metadata PDA for a token mint.

        Metaplex metadata PDA: [metadata_program, 'metadata', mint]
        """
        METADATA_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")

        # Find PDA (Program Derived Address)
        metadata_pda, _ = Pubkey.find_program_address(
            [
                b"metadata",
                bytes(METADATA_PROGRAM_ID),
                bytes(mint),
            ],
            METADATA_PROGRAM_ID,
        )
        return metadata_pda

    def check_metadata_exists(self, mint: str) -> bool:
        """Check if token has Metaplex metadata account."""
        try:
            mint_pubkey = Pubkey.from_string(mint)
            metadata_pda = self.get_metadata_pda(mint_pubkey)

            response = self.client.get_account_info(metadata_pda)

            if response.value is None:
                print(f"❌ No Metaplex metadata found for {mint}")
                print(f"   Metadata PDA: {metadata_pda}")
                return False

            print(f"✅ Metadata account exists at {metadata_pda}")
            return True

        except Exception as e:
            print(f"❌ Error checking metadata: {e}")
            return False

    def get_token_info(self, mint: str) -> Optional[dict]:
        """Get basic token account info."""
        try:
            mint_pubkey = Pubkey.from_string(mint)
            response = self.client.get_account_info(mint_pubkey, encoding="jsonParsed")

            if response.value is None:
                print(f"❌ Token mint not found: {mint}")
                return None

            print(f"✅ Token mint found: {mint}")
            return response.value.data

        except Exception as e:
            print(f"❌ Error fetching token info: {e}")
            return None

    def freeze_with_metaboss(self, mint: str, keypair_path: str, dry_run: bool = True):
        """
        Freeze metadata using metaboss CLI.

        Metaboss is the most reliable tool for Metaplex metadata operations.
        Install: cargo install metaboss
        """
        if dry_run:
            print("\n" + "="*60)
            print("DRY RUN MODE - No changes will be made")
            print("="*60)

        # Check if metaboss is installed
        try:
            result = subprocess.run(
                ["metaboss", "--version"],
                capture_output=True,
                text=True,
            )
            print(f"✅ Metaboss installed: {result.stdout.strip()}")
        except FileNotFoundError:
            print("❌ Metaboss not installed!")
            print("\nInstall with:")
            print("  cargo install metaboss")
            print("\nOr download from: https://github.com/samuelvanderwaal/metaboss")
            return False

        # Prepare command
        cmd = [
            "metaboss",
            "update",
            "immutable",
            "--keypair", keypair_path,
            "--account", mint,
        ]

        print(f"\n📝 Command to freeze metadata:")
        print(f"   {' '.join(cmd)}")

        if dry_run:
            print("\n⚠️  To actually freeze metadata, run with --execute flag")
            return True

        # Execute
        print("\n🚀 Freezing metadata...")
        print("⚠️  This is IRREVERSIBLE - metadata will be permanently locked!")

        confirm = input("\nType 'FREEZE' to confirm: ")
        if confirm != "FREEZE":
            print("❌ Cancelled")
            return False

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            print("✅ SUCCESS! Metadata is now immutable!")
            print(f"\nTransaction signature: {result.stdout}")

            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to freeze metadata:")
            print(f"   {e.stderr}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Freeze Solana token metadata (make immutable)"
    )
    parser.add_argument(
        "--mint",
        required=True,
        help="Token mint address (e.g., 7BLH...23cf)",
    )
    parser.add_argument(
        "--keypair",
        required=True,
        help="Path to update authority keypair JSON file",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually freeze metadata (default is dry-run)",
    )
    parser.add_argument(
        "--rpc",
        default="https://api.mainnet-beta.solana.com",
        help="Solana RPC URL",
    )

    args = parser.parse_args()

    print("="*60)
    print("Token Metadata Freezer")
    print("="*60)
    print(f"Mint: {args.mint}")
    print(f"Keypair: {args.keypair}")
    print(f"RPC: {args.rpc}")
    print("="*60)

    # Validate keypair exists
    if not Path(args.keypair).exists():
        print(f"❌ Keypair file not found: {args.keypair}")
        sys.exit(1)

    # Initialize
    freezer = MetadataFreezer(rpc_url=args.rpc)

    # Check token exists
    print("\n1. Checking token mint...")
    if not freezer.get_token_info(args.mint):
        sys.exit(1)

    # Check metadata exists
    print("\n2. Checking Metaplex metadata...")
    if not freezer.check_metadata_exists(args.mint):
        print("\n⚠️  This token doesn't have Metaplex metadata!")
        print("   It may have been created with bags.fm's custom system.")
        print("   You'll need to use bags.fm API to update it.")
        sys.exit(1)

    # Freeze metadata
    print("\n3. Freezing metadata...")
    success = freezer.freeze_with_metaboss(
        mint=args.mint,
        keypair_path=args.keypair,
        dry_run=not args.execute,
    )

    if not success:
        sys.exit(1)

    print("\n" + "="*60)
    print("✅ COMPLETE!")
    print("="*60)
    print("\nNext steps:")
    print("1. Verify on Solscan:")
    print(f"   https://solscan.io/token/{args.mint}")
    print("2. Check that 'Mutable' shows 'false'")
    print("3. Announce to community (builds trust)")
    print("="*60)


if __name__ == "__main__":
    main()

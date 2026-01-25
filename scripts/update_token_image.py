#!/usr/bin/env python3
"""
Update Token Image - Add/change token logo before freezing metadata

This script helps you update the token image/logo using Metaplex.
Do this BEFORE freezing metadata!

Usage:
    python scripts/update_token_image.py --mint <MINT> --keypair <KEYPAIR> --image <IMAGE_PATH>

Requirements:
    - metaboss CLI (cargo install metaboss)
    - Image file (PNG/JPG recommended)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


class MetadataUpdater:
    """Update token metadata using metaboss."""

    def upload_to_nft_storage(self, image_path: str) -> str:
        """
        Upload image to NFT.Storage (free, permanent IPFS hosting).

        Returns: IPFS URL
        """
        print(f"\n📤 Uploading {image_path} to NFT.Storage...")

        # Check if metaboss can upload
        try:
            result = subprocess.run(
                [
                    "metaboss",
                    "upload",
                    "nft-storage",
                    "--file", image_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            ipfs_url = result.stdout.strip()
            print(f"✅ Uploaded to: {ipfs_url}")
            return ipfs_url

        except subprocess.CalledProcessError as e:
            print(f"❌ Upload failed: {e.stderr}")
            print("\nNote: You need an NFT.Storage API key")
            print("1. Get free key at https://nft.storage")
            print("2. Set env var: export NFT_STORAGE_API_KEY=your_key")
            sys.exit(1)

    def create_metadata_json(
        self,
        name: str,
        symbol: str,
        description: str,
        image_url: str,
        output_path: str = "metadata.json",
    ) -> str:
        """Create Metaplex-compatible metadata JSON."""

        metadata = {
            "name": name,
            "symbol": symbol,
            "description": description,
            "image": image_url,
            "attributes": [],
            "properties": {
                "files": [
                    {
                        "uri": image_url,
                        "type": "image/png",
                    }
                ],
                "category": "image",
            },
        }

        with open(output_path, "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"✅ Created metadata JSON: {output_path}")
        return output_path

    def update_uri(self, mint: str, keypair_path: str, new_uri: str, dry_run: bool = True):
        """Update the token's metadata URI using metaboss."""

        cmd = [
            "metaboss",
            "update",
            "uri",
            "--keypair", keypair_path,
            "--account", mint,
            "--new-uri", new_uri,
        ]

        print(f"\n📝 Command:")
        print(f"   {' '.join(cmd)}")

        if dry_run:
            print("\n⚠️  DRY RUN - To execute, run with --execute flag")
            return True

        print("\n🚀 Updating metadata URI...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            print("✅ SUCCESS! Metadata URI updated!")
            print(f"\nTransaction: {result.stdout}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed: {e.stderr}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Update token image/logo before freezing metadata"
    )
    parser.add_argument("--mint", required=True, help="Token mint address")
    parser.add_argument("--keypair", required=True, help="Update authority keypair path")
    parser.add_argument("--image", help="Path to image file (PNG/JPG)")
    parser.add_argument("--uri", help="Direct URI to metadata JSON (if already uploaded)")
    parser.add_argument("--execute", action="store_true", help="Execute the update")

    # Optional metadata fields
    parser.add_argument("--name", help="Token name (e.g., 'KR8TIV')")
    parser.add_argument("--symbol", help="Token symbol (e.g., 'KR8TIV')")
    parser.add_argument("--description", help="Token description")

    args = parser.parse_args()

    print("="*60)
    print("Token Image Updater")
    print("="*60)

    updater = MetadataUpdater()

    # Path 1: User provides direct URI
    if args.uri:
        print(f"Using provided URI: {args.uri}")
        new_uri = args.uri

    # Path 2: Upload image and create metadata
    elif args.image:
        if not Path(args.image).exists():
            print(f"❌ Image not found: {args.image}")
            sys.exit(1)

        # Upload image
        image_url = updater.upload_to_nft_storage(args.image)

        # Create metadata JSON
        name = args.name or input("Token name: ")
        symbol = args.symbol or input("Token symbol: ")
        description = args.description or input("Token description: ")

        metadata_path = updater.create_metadata_json(
            name=name,
            symbol=symbol,
            description=description,
            image_url=image_url,
        )

        # Upload metadata JSON
        print("\n📤 Uploading metadata JSON...")
        new_uri = updater.upload_to_nft_storage(metadata_path)

    else:
        print("❌ Must provide either --image or --uri")
        parser.print_help()
        sys.exit(1)

    # Update on-chain
    success = updater.update_uri(
        mint=args.mint,
        keypair_path=args.keypair,
        new_uri=new_uri,
        dry_run=not args.execute,
    )

    if success and not args.execute:
        print("\n" + "="*60)
        print("Next steps:")
        print("="*60)
        print("1. Review the metadata JSON")
        print("2. Run again with --execute to update on-chain")
        print("3. After update, run freeze_token_metadata.py")
        print("="*60)


if __name__ == "__main__":
    main()

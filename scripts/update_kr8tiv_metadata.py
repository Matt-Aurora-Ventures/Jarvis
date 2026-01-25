#!/usr/bin/env python3
"""
KR8TIV Token Metadata Updater
Uses NFT.Storage + Solana/Metaplex
"""

import os
import json
import requests
from pathlib import Path

# Config
MINT = "7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf"
LOGO_PATH = Path(__file__).parent.parent / "assets" / "kr8tiv" / "logo.png"
KEYPAIR_PATH = Path(__file__).parent.parent / "keypair.json"
NFT_STORAGE_API_KEY = "08c145c0.2313919737a346fa8ac2d8091d24b34b"

print("\n" + "="*50)
print("        KR8TIV Metadata Update")
print("="*50 + "\n")

def upload_to_nft_storage(file_path, filename="file"):
    """Upload file to NFT.Storage"""
    print(f"Uploading {filename}...")

    url = "https://api.nft.storage/upload"
    headers = {
        "Authorization": f"Bearer {NFT_STORAGE_API_KEY}",
    }

    with open(file_path, 'rb') as f:
        files = {'file': (filename, f)}
        response = requests.post(url, headers=headers, files=files)

    if response.status_code != 200:
        raise Exception(f"Upload failed ({response.status_code}): {response.text}")

    data = response.json()
    if not data.get('ok'):
        raise Exception(f"Upload failed: {data.get('error', {}).get('message', 'Unknown error')}")

    ipfs_url = f"https://ipfs.io/ipfs/{data['value']['cid']}"
    print(f"✓ {filename} uploaded\n  {ipfs_url}\n")
    return ipfs_url

def upload_json(json_data, filename="metadata.json"):
    """Upload JSON to NFT.Storage"""
    print(f"Uploading {filename}...")

    url = "https://api.nft.storage/upload"
    headers = {
        "Authorization": f"Bearer {NFT_STORAGE_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json=json_data)

    if response.status_code != 200:
        raise Exception(f"Upload failed ({response.status_code}): {response.text}")

    data = response.json()
    if not data.get('ok'):
        raise Exception(f"Upload failed: {data.get('error', {}).get('message', 'Unknown error')}")

    ipfs_url = f"https://ipfs.io/ipfs/{data['value']['cid']}"
    print(f"✓ {filename} uploaded\n  {ipfs_url}\n")
    return ipfs_url

def main():
    try:
        # Step 1: Upload logo
        print("[1/3] Uploading logo to IPFS...\n")
        image_url = upload_to_nft_storage(LOGO_PATH, "kr8tiv-logo.png")

        # Step 2: Create and upload metadata
        print("[2/3] Creating and uploading metadata...\n")

        metadata = {
            "name": "KR8TIV",
            "symbol": "KR8TIV",
            "description": "kr8tiv builds Decentralized Open Sourced AI for the masses — powerful, practical, and dangerous (in a good way).",
            "image": image_url,
            "external_url": "https://kr8tiv.ai",
            "attributes": [
                {"trait_type": "Category", "value": "AI"},
                {"trait_type": "Type", "value": "Utility Token"},
                {"trait_type": "Network", "value": "Solana"},
                {"trait_type": "Platform", "value": "Decentralized AI"}
            ],
            "properties": {
                "files": [{"uri": image_url, "type": "image/png"}],
                "category": "image",
                "creators": []
            },
            "links": {
                "website": "https://kr8tiv.ai",
                "jarvis": "https://jarvislife.io",
                "twitter": "https://x.com/kr8tivai",
                "jarvis_twitter": "https://x.com/Jarvis_lifeos"
            }
        }

        metadata_url = upload_json(metadata)

        # Step 3: Show update info
        print("[3/3] Metadata ready for on-chain update\n")
        print("Review:")
        print("="*50)
        print(f"  Mint:     {MINT}")
        print(f"  Image:    {image_url}")
        print(f"  Metadata: {metadata_url}")
        print("="*50 + "\n")

        # Save for manual update
        update_info = {
            "mint": MINT,
            "image_url": image_url,
            "metadata_url": metadata_url,
            "keypair_path": str(KEYPAIR_PATH),
        }

        output_path = Path(__file__).parent.parent / "assets" / "kr8tiv" / "update_info.json"
        with open(output_path, 'w') as f:
            json.dump(update_info, f, indent=2)

        print(f"✓ Update info saved to: {output_path}\n")

        print("="*50)
        print("         IPFS UPLOAD COMPLETE!")
        print("="*50 + "\n")

        print("Next step: Update on-chain with Solana CLI\n")
        print("Run this command:\n")
        print(f"  solana-cli update-metadata \\")
        print(f"    --keypair {KEYPAIR_PATH} \\")
        print(f"    --mint {MINT} \\")
        print(f"    --uri {metadata_url}\n")

        print("Or use metaboss (when installed):\n")
        print(f"  metaboss update uri \\")
        print(f"    --keypair {KEYPAIR_PATH} \\")
        print(f"    --account {MINT} \\")
        print(f"    --new-uri {metadata_url}\n")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    exit(main())

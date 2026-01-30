#!/usr/bin/env python3
"""
Initialize Treasury Keypair for Jarvis
Creates an encrypted treasury_keypair.json for the trading bot.
"""

import os
import sys
import json
import base64
import secrets
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import nacl.secret
    import nacl.pwhash
    from solders.keypair import Keypair
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install pynacl solders")
    sys.exit(1)


def create_encrypted_keypair(password: str, output_path: Path) -> dict:
    """
    Create a new Solana keypair and encrypt it with NaCl.
    
    Returns dict with address and file path.
    """
    # Generate new keypair
    keypair = Keypair()
    private_key_bytes = bytes(keypair)  # 64 bytes: 32 private + 32 public
    
    # Get public key (address)
    address = str(keypair.pubkey())
    
    # Generate salt and nonce
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(24)
    
    # Derive encryption key from password
    key = nacl.pwhash.argon2id.kdf(
        nacl.secret.SecretBox.KEY_SIZE,
        password.encode(),
        salt,
        opslimit=nacl.pwhash.argon2id.OPSLIMIT_MODERATE,
        memlimit=nacl.pwhash.argon2id.MEMLIMIT_MODERATE,
    )
    
    # Encrypt the keypair
    box = nacl.secret.SecretBox(key)
    encrypted = box.encrypt(private_key_bytes, nonce).ciphertext
    
    # Create JSON structure
    keypair_data = {
        "address": address,
        "encrypted_key": base64.b64encode(encrypted).decode(),
        "salt": base64.b64encode(salt).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "encryption": "nacl-argon2id",
        "created_by": "init_treasury_keypair.py"
    }
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(keypair_data, f, indent=2)
    
    return {
        "address": address,
        "path": str(output_path)
    }


def main():
    # Get password from environment
    password = os.environ.get('JARVIS_WALLET_PASSWORD')
    
    if not password:
        print("ERROR: JARVIS_WALLET_PASSWORD environment variable not set")
        print("\nSet it with:")
        print("  export JARVIS_WALLET_PASSWORD='your-secure-password'")
        sys.exit(1)
    
    # Output path
    output_path = Path(__file__).parent.parent / "data" / "treasury_keypair.json"
    
    # Check if already exists
    if output_path.exists():
        print(f"WARNING: {output_path} already exists!")
        response = input("Overwrite? (y/N): ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)
    
    print("=== Treasury Keypair Initialization ===\n")
    
    result = create_encrypted_keypair(password, output_path)
    
    print(f"✓ Treasury keypair created")
    print(f"  Address: {result['address']}")
    print(f"  File: {result['path']}")
    print(f"\n⚠️  IMPORTANT:")
    print(f"  1. Fund this address with SOL before trading")
    print(f"  2. Keep your password safe - needed for decryption")
    print(f"  3. Back up the keypair file securely")


if __name__ == "__main__":
    main()

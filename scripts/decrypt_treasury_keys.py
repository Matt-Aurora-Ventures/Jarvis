#!/usr/bin/env python3
"""
Decrypt Treasury Wallet Private Keys
Extracts private keys from encrypted JSON keypair files
"""

import json
import base64
import sys
from pathlib import Path

def decrypt_nacl_keypair(keypair_path: str, password: str):
    """Decrypt a NaCl-encrypted Solana keypair file."""

    try:
        import nacl.secret
        import nacl.pwhash
    except ImportError:
        print("[ERROR] PyNaCl not installed")
        print("Install with: pip install pynacl")
        return None

    # Load encrypted keypair
    with open(keypair_path) as f:
        data = json.load(f)

    # Extract encryption components
    salt = base64.b64decode(data['salt'])
    nonce = base64.b64decode(data['nonce'])
    encrypted = base64.b64decode(data['encrypted_key'])
    pubkey = data['pubkey']

    # Derive encryption key using Argon2id (same as core/security/key_manager.py)
    key = nacl.pwhash.argon2id.kdf(
        nacl.secret.SecretBox.KEY_SIZE,
        password.encode(),
        salt,
        opslimit=nacl.pwhash.argon2id.OPSLIMIT_MODERATE,
        memlimit=nacl.pwhash.argon2id.MEMLIMIT_MODERATE,
    )

    # Decrypt the private key
    box = nacl.secret.SecretBox(key)
    try:
        private_key_bytes = box.decrypt(encrypted, nonce)
    except nacl.exceptions.CryptoError as e:
        print(f"[ERROR] Decryption failed - wrong password or corrupted file")
        return None

    # Convert to array format (Solana standard)
    private_key_array = list(private_key_bytes)

    return {
        'pubkey': pubkey,
        'private_key_bytes': private_key_array,
        'private_key_b58_array': private_key_array  # Solana CLI format
    }

if __name__ == "__main__":
    print("=" * 60)
    print("TREASURY WALLET KEY DECRYPTION")
    print("=" * 60)
    print()

    # Password from tg_bot/.env line 67
    PASSWORD = "ElonMusk987#"

    # Old treasury keypair (BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR)
    old_treasury_path = Path(__file__).parent.parent / "data" / "treasury_keypair.json"

    print(f"Decrypting OLD treasury account...")
    print(f"File: {old_treasury_path}")
    print()

    if old_treasury_path.exists():
        try:
            result = decrypt_nacl_keypair(str(old_treasury_path), PASSWORD)
            if result:
                print(f"[SUCCESS] Old Treasury Account Decrypted")
                print(f"Public Key: {result['pubkey']}")
                print(f"\nPrivate Key (Solana keypair array format):")
                print(f"{result['private_key_b58_array']}")
                print()
                print("=" * 60)
                print("SAVE THIS PRIVATE KEY:")
                print("=" * 60)
                with open("OLD_TREASURY_PRIVATE_KEY.json", "w") as f:
                    json.dump(result['private_key_b58_array'], f)
                print(f"Saved to: OLD_TREASURY_PRIVATE_KEY.json")
                print()
                print("To import into Solana CLI:")
                print(f"  solana-keygen recover -o old_treasury.key --force")
                print(f"  (Then paste the array when prompted)")
                print()
            else:
                print("[ERROR] Decryption failed")
        except Exception as e:
            print(f"[ERROR] Decryption failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"[ERROR] Keypair file not found at: {old_treasury_path}")

    print("-" * 60)
    print()

    # Search for new treasury account (57w9GUzRwXim3nh13R7WtFbpHzUcyKHTtjcTv8cuFoqN)
    print("Searching for NEW treasury account...")
    print("Address: 57w9GUzRwXim3nh13R7WtFbpHzUcyKHTtjcTv8cuFoqN")
    print()

    # Check common locations
    search_paths = [
        Path(__file__).parent.parent / "data",
        Path(__file__).parent.parent / "bots" / "treasury",
        Path(__file__).parent.parent / "bots" / "treasury" / ".wallets",
        Path.home() / ".config" / "solana",
        Path.home() / ".lifeos" / "wallets",
    ]

    found_new = False
    for search_dir in search_paths:
        if search_dir.exists():
            # Check for JSON files with the address in name or content
            for json_file in search_dir.glob("*.json"):
                if '57w9' in json_file.name.lower():
                    print(f"[FOUND BY NAME] {json_file}")
                    found_new = True
                    try:
                        with open(json_file) as f:
                            data = json.load(f)
                            if isinstance(data, dict) and 'encrypted_key' in data:
                                print("  [ENCRYPTED] Attempting decryption...")
                                result = decrypt_nacl_keypair(str(json_file), PASSWORD)
                                if result:
                                    print(f"  [SUCCESS] Decrypted")
                                    print(f"  Public Key: {result['pubkey']}")
                                    with open("NEW_TREASURY_PRIVATE_KEY.json", "w") as out:
                                        json.dump(result['private_key_b58_array'], out)
                                    print(f"  Saved to: NEW_TREASURY_PRIVATE_KEY.json")
                                else:
                                    print(f"  [ERROR] Decryption failed")
                            elif isinstance(data, list) and len(data) == 64:
                                print(f"  [UNENCRYPTED] Raw keypair found")
                                with open("NEW_TREASURY_PRIVATE_KEY.json", "w") as out:
                                    json.dump(data, out)
                                print(f"  Saved to: NEW_TREASURY_PRIVATE_KEY.json")
                    except Exception as e:
                        print(f"  [ERROR] {e}")

            # Also check files with address in content
            for json_file in search_dir.glob("*.json"):
                if found_new:
                    break
                try:
                    with open(json_file) as f:
                        content = f.read()
                        if '57w9GUzRwXim3nh13R7WtFbpHzUcyKHTtjcTv8cuFoqN' in content:
                            print(f"[FOUND BY CONTENT] {json_file}")
                            found_new = True
                            data = json.loads(content)
                            if isinstance(data, dict) and 'encrypted_key' in data:
                                print("  [ENCRYPTED] Attempting decryption...")
                                result = decrypt_nacl_keypair(str(json_file), PASSWORD)
                                if result:
                                    print(f"  [SUCCESS] Decrypted")
                                    with open("NEW_TREASURY_PRIVATE_KEY.json", "w") as out:
                                        json.dump(result['private_key_b58_array'], out)
                                    print(f"  Saved to: NEW_TREASURY_PRIVATE_KEY.json")
                except:
                    pass

    if not found_new:
        print("[NOT FOUND] New treasury keypair not found in local filesystems")
        print()
        print("Searched directories:")
        for path in search_paths:
            print(f"  - {path} {'(exists)' if path.exists() else '(not found)'}")
        print()
        print("The key may be:")
        print("  1. On the VPS at /home/jarvis/Jarvis/data/")
        print("  2. In WSL filesystem - check with:")
        print("     wsl find ~ -name '*57w9*.json' 2>/dev/null")
        print("     wsl find ~ -name '*treasury*.json' 2>/dev/null")
        print("  3. Generated externally (Phantom wallet, Solflare, etc.)")
        print("  4. In hardware wallet")
        print()
        print("To search VPS:")
        print(f"  ssh root@72.61.7.126 'find /home/jarvis -name \"*treasury*.json\" -o -name \"*57w9*.json\"'")

    print()
    print("=" * 60)

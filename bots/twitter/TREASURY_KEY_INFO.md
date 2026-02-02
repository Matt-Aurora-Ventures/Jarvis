# Treasury Private Key Information

**Extracted**: 2026-01-31 (Ralph Wiggum Loop Session)

## Keypair Location
- **File**: `treasury_keypair.json` (in this directory)
- **Original**: `C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\data\treasury_keypair.json`

## Wallet Details
- **Public Key**: `BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR`
- **Balance**: 0.1 SOL (for live trading)
- **Encryption**: AES-256 encrypted with password

## Decryption Password
**Location**: `tg_bot/.env` line 67
**Variable**: `JARVIS_WALLET_PASSWORD=ElonMusk987#`

## File Format
```json
{
  "salt": "pyceNifHVUNNqdyIM6C6eg==",
  "nonce": "L8Q+4P8La0DEsA0UHlGpGa1g741jXeqi",
  "encrypted_key": "x+o2WIj6/+U8TR7xY2pPNfSe+trCNerNRIBJabHTQ4bDxLnM0ifHmIPQjoDJWPxjXVhE0FuelVnmZVaChMbd5yiSKcgLU1QzBteEyw9tQxE=",
  "pubkey": "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR"
}
```

## Decryption Code
To decrypt the private key for use:

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import json

# Load keypair
with open('treasury_keypair.json') as f:
    data = json.load(f)

# Decrypt
password = "ElonMusk987#"  # From JARVIS_WALLET_PASSWORD
salt = base64.b64decode(data['salt'])
nonce = base64.b64decode(data['nonce'])
encrypted = base64.b64decode(data['encrypted_key'])

# Derive key from password + salt
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

kdf = PBKDF2(
    algorithm=hashes.SHA256(),
    length=32,
    salt=salt,
    iterations=100000,
    backend=default_backend()
)
key = kdf.derive(password.encode())

# Decrypt the private key
cipher = AESGCM(key)
private_key_bytes = cipher.decrypt(nonce, encrypted, None)

# private_key_bytes is now the raw Solana keypair (64 bytes)
```

## Security Notes
- ✅ File is gitignored
- ✅ Encrypted at rest
- ✅ Password stored separately in .env
- ⚠️ NEVER commit to git
- ⚠️ NEVER expose password in logs

## Related Files
- `tg_bot/.env` - Contains decryption password
- `bots/treasury/trading.py` - Uses this keypair for live trading
- `core/treasury_wallet.py` - Wallet management utilities

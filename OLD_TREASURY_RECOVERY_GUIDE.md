# Old Treasury Private Key Recovery

**Wallet Address**: `BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR`
**Balance**: Check on Solscan (had funds transferred out to new treasury on Jan 30)

## Private Key (Array Format)

The private key is saved in: `OLD_TREASURY_PRIVATE_KEY.json`

**Raw keypair array**:
```json
[66, 86, 71, 216, 233, 169, 158, 246, 44, 215, 181, 244, 117, 214, 228, 66, 226, 116, 235, 85, 69, 84, 26, 28, 140, 187, 143, 207, 205, 142, 209, 254, 152, 88, 191, 238, 227, 102, 174, 16, 180, 212, 201, 197, 31, 40, 199, 182, 221, 46, 92, 219, 69, 69, 30, 164, 69, 202, 33, 10, 125, 36, 251, 148]
```

## Import to Phantom Wallet

1. Open Phantom wallet extension
2. Click settings → Add / Connect Wallet
3. Select "Import Private Key"
4. Choose "Keypair Array" format
5. Paste the array above
6. Click Import

## Import to Solana CLI

```bash
# Save to file
echo '[66, 86, 71, 216, 233, 169, 158, 246, 44, 215, 181, 244, 117, 214, 228, 66, 226, 116, 235, 85, 69, 84, 26, 28, 140, 187, 143, 207, 205, 142, 209, 254, 152, 88, 191, 238, 227, 102, 174, 16, 180, 212, 201, 197, 31, 40, 199, 182, 221, 46, 92, 219, 69, 69, 30, 164, 69, 202, 33, 10, 125, 36, 251, 148]' > old-treasury.json

# Import
solana-keygen recover -o old-treasury.key old-treasury.json --force

# Verify
solana-keygen pubkey old-treasury.key
# Should output: BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR
```

## Python Usage

```python
from solders.keypair import Keypair

key_bytes = bytes([66, 86, 71, 216, 233, 169, 158, 246, 44, 215, 181, 244, 117, 214, 228, 66, 226, 116, 235, 85, 69, 84, 26, 28, 140, 187, 143, 207, 205, 142, 209, 254, 152, 88, 191, 238, 227, 102, 174, 16, 180, 212, 201, 197, 31, 40, 199, 182, 221, 46, 92, 219, 69, 69, 30, 164, 69, 202, 33, 10, 125, 36, 251, 148])

keypair = Keypair.from_bytes(key_bytes)
print(f"Address: {keypair.pubkey()}")
```

---

**SECURITY NOTE**: Delete `OLD_TREASURY_PRIVATE_KEY.json` and this file after importing to your secure wallet!

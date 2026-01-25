# KR8TIV Metadata Quick Start

**Your Token**: `7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf`

## 🚀 Quick Commands

### 1. Install metaboss

```bash
# Install Rust first (if needed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install metaboss
cargo install metaboss
```

### 2. Upload Image

```bash
# Get free API key from https://nft.storage
export NFT_STORAGE_API_KEY=your_key_here

# Upload logo
metaboss upload nft-storage --file logo.png
# Returns: https://ipfs.io/ipfs/YOUR_IMAGE_CID
```

### 3. Create metadata.json

```json
{
  "name": "KR8TIV",
  "symbol": "KR8TIV",
  "description": "Autonomous AI trading and sentiment analysis",
  "image": "https://ipfs.io/ipfs/YOUR_IMAGE_CID",
  "external_url": "https://kr8tiv.com",
  "attributes": [],
  "properties": {
    "files": [{"uri": "https://ipfs.io/ipfs/YOUR_IMAGE_CID", "type": "image/png"}],
    "category": "image"
  }
}
```

### 4. Upload Metadata

```bash
metaboss upload nft-storage --file metadata.json
# Returns: https://ipfs.io/ipfs/YOUR_METADATA_CID
```

### 5. Update On-Chain

```bash
metaboss update uri \
  --keypair ./your-keypair.json \
  --account 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf \
  --new-uri https://ipfs.io/ipfs/YOUR_METADATA_CID
```

### 6. Freeze (PERMANENT!)

```bash
metaboss update immutable \
  --keypair ./your-keypair.json \
  --account 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf
```

### 7. Verify

```bash
# Check on Solscan
open https://solscan.io/token/7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf
```

---

## 📦 Automated Option

```bash
# Run the complete setup script
bash scripts/setup_kr8tiv_metadata.sh
```

---

## ⚠️ Important Notes

- **Freezing is PERMANENT** - Can never undo it
- **Upload to permanent storage** - Use IPFS/Arweave, not S3/CDN
- **Verify before freezing** - Check metadata looks correct
- **You need the private key** - Must be the update authority

---

## 🔍 Metadata Fields You Can Update

| Field | What It Is | Example |
|-------|------------|---------|
| `name` | Token name | "KR8TIV" |
| `symbol` | Token ticker | "KR8TIV" |
| `description` | What it does | "AI trading platform" |
| `image` | Logo URL | "https://ipfs.io/..." |
| `external_url` | Website | "https://kr8tiv.com" |
| `attributes` | Custom traits | `[{"trait_type": "Category", "value": "DeFi"}]` |

---

## 📚 Full Documentation

See [TOKEN_METADATA_GUIDE.md](./TOKEN_METADATA_GUIDE.md) for complete details.

---

## 💬 Need Help?

- Metaboss docs: https://metaboss.rs/
- Metaplex docs: https://developers.metaplex.com/
- Jarvis TG: t.me/kr8tiventry

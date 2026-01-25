# Token Metadata Management Guide

Complete guide for updating and freezing $KR8TIV token metadata.

## Your Token Info

- **Mint Address**: `7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf`
- **Contract**: `U1zc8QpnrQ3HBJUBrWFYWbQTLzNsCpPgZNegWXdBAGS`
- **Authority**: You have the private key ✅

---

## What Can You Update?

### Standard Metaplex Metadata Fields

| Field | Description | Can Update Before Freeze? |
|-------|-------------|---------------------------|
| **name** | Token name (e.g., "KR8TIV") | ✅ Yes |
| **symbol** | Token symbol (e.g., "KR8TIV") | ✅ Yes |
| **uri** | Link to off-chain metadata JSON | ✅ Yes |
| **seller_fee_basis_points** | Royalty % (usually 0 for tokens) | ✅ Yes |
| **creators** | List of creator addresses | ✅ Yes |
| **isMutable** | Can metadata be changed? | ✅ Yes (but one-way!) |
| **update_authority** | Who can update metadata | ✅ Yes |

### Off-Chain Metadata (in the JSON file at the URI)

| Field | Description | Examples |
|-------|-------------|----------|
| **image** | Token logo/image URL | IPFS, Arweave URL |
| **description** | Token description | "The official KR8TIV token..." |
| **external_url** | Project website | "https://kr8tiv.com" |
| **attributes** | Custom traits | `[{"trait_type": "Type", "value": "Utility"}]` |
| **properties.files** | Additional files | Images, videos |
| **properties.category** | Asset category | "image", "video", etc. |

### Social Links (in off-chain JSON)

```json
{
  "name": "KR8TIV",
  "symbol": "KR8TIV",
  "description": "Autonomous AI trading and sentiment analysis",
  "image": "https://your-image-url.com/logo.png",
  "external_url": "https://kr8tiv.com",
  "attributes": [
    {
      "trait_type": "Category",
      "value": "DeFi"
    }
  ],
  "properties": {
    "files": [
      {
        "uri": "https://your-image-url.com/logo.png",
        "type": "image/png"
      }
    ],
    "category": "image",
    "creators": []
  },
  "collection": {
    "name": "KR8TIV",
    "family": "LifeOS"
  }
}
```

---

## Update Options

### Option 1: Metaboss CLI (Recommended)

**Best for**: Complete control, reliable, widely used

**Install**:
```bash
cargo install metaboss
```

**Update image**:
```bash
# 1. Upload image to permanent storage
metaboss upload nft-storage --file logo.png

# 2. Create metadata JSON with new image URL
# (use update_token_image.py script)

# 3. Update on-chain URI
metaboss update uri \
  --keypair ./your-keypair.json \
  --account 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf \
  --new-uri https://ipfs.io/ipfs/YOUR_CID

# 4. Freeze metadata (make immutable)
metaboss update immutable \
  --keypair ./your-keypair.json \
  --account 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf
```

**Pros**:
- ✅ Most reliable
- ✅ Works with all Metaplex tokens
- ✅ Actively maintained
- ✅ CLI = easy automation

**Cons**:
- ❌ Requires Rust/Cargo
- ❌ CLI-only (no GUI)

---

### Option 2: Metaplex Sugar CLI

**Best for**: Bundled operations, candy machine users

**Install**:
```bash
bash <(curl -sSf https://sugar.metaplex.com/install.sh)
```

**Usage**:
```bash
sugar update --keypair your-keypair.json --new-uri YOUR_URI
```

**Pros**:
- ✅ Official Metaplex tool
- ✅ Handles uploads + updates together

**Cons**:
- ❌ More complex than metaboss
- ❌ Designed for NFT collections

---

### Option 3: Metaplex Umi SDK (TypeScript)

**Best for**: Custom integration, programmatic control

**Install**:
```bash
npm install @metaplex-foundation/umi @metaplex-foundation/umi-bundle-defaults @metaplex-foundation/mpl-token-metadata
```

**Code**:
```typescript
import { createUmi } from '@metaplex-foundation/umi-bundle-defaults';
import { updateV1, fetchMetadataFromSeeds } from '@metaplex-foundation/mpl-token-metadata';
import { publicKey, keypairIdentity } from '@metaplex-foundation/umi';

const umi = createUmi('https://api.mainnet-beta.solana.com')
  .use(mplTokenMetadata());

// Load keypair
const updateAuthority = umi.eddsa.createKeypairFromSecretKey(yourSecretKey);
umi.use(keypairIdentity(updateAuthority));

// Update metadata
await updateV1(umi, {
  mint: publicKey('7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf'),
  authority: updateAuthority,
  newUpdateAuthority: null,  // Revoke update authority
  isMutable: false,          // Freeze metadata
}).sendAndConfirm(umi);
```

**Pros**:
- ✅ Full programmatic control
- ✅ TypeScript type safety
- ✅ Can integrate into apps

**Cons**:
- ❌ Requires Node.js setup
- ❌ More code to write

---

### Option 4: Solana Explorer UI

**Best for**: Quick manual updates, no CLI

**Steps**:
1. Go to https://explorer.solana.com/
2. Connect wallet with update authority
3. Find your token metadata account
4. Use "Update" button (if available)

**Pros**:
- ✅ No installation
- ✅ Visual interface

**Cons**:
- ❌ Limited functionality
- ❌ May not support all operations
- ❌ Not reliable for freezing

---

### Option 5: Python with our Scripts

**Best for**: Integration with Jarvis codebase

**Usage**:
```bash
# 1. Add image
python scripts/update_token_image.py \
  --mint 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf \
  --keypair ./your-keypair.json \
  --image ./logo.png \
  --name "KR8TIV" \
  --symbol "KR8TIV" \
  --description "Autonomous AI trading platform" \
  --execute

# 2. Freeze metadata
python scripts/freeze_token_metadata.py \
  --mint 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf \
  --keypair ./your-keypair.json \
  --execute
```

**Pros**:
- ✅ Integrated with your Python codebase
- ✅ Uses metaboss under the hood
- ✅ Dry-run mode for safety

**Cons**:
- ❌ Still requires metaboss CLI

---

## Recommended Workflow

### Step 1: Prepare Image

```bash
# Upload to permanent storage (choose one)

# Option A: NFT.Storage (free, IPFS)
metaboss upload nft-storage --file logo.png

# Option B: Arweave (permanent, small fee)
metaboss upload arweave --file logo.png

# Option C: Use existing CDN URL
# Just use the URL directly
```

### Step 2: Create Metadata JSON

```json
{
  "name": "KR8TIV",
  "symbol": "KR8TIV",
  "description": "Autonomous AI trading and sentiment analysis platform",
  "image": "https://arweave.net/YOUR_IMAGE_HASH",
  "external_url": "https://kr8tiv.com",
  "attributes": [
    {
      "trait_type": "Category",
      "value": "DeFi"
    },
    {
      "trait_type": "Type",
      "value": "Utility Token"
    }
  ],
  "properties": {
    "files": [
      {
        "uri": "https://arweave.net/YOUR_IMAGE_HASH",
        "type": "image/png"
      }
    ],
    "category": "image"
  }
}
```

### Step 3: Upload Metadata JSON

```bash
metaboss upload nft-storage --file metadata.json
# Returns: https://ipfs.io/ipfs/YOUR_METADATA_CID
```

### Step 4: Update On-Chain URI

```bash
metaboss update uri \
  --keypair your-keypair.json \
  --account 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf \
  --new-uri https://ipfs.io/ipfs/YOUR_METADATA_CID
```

### Step 5: Verify Changes

```bash
# Check on Solscan
open https://solscan.io/token/7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf

# Or use solana CLI
solana account 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf
```

### Step 6: Freeze Metadata (FINAL STEP!)

```bash
metaboss update immutable \
  --keypair your-keypair.json \
  --account 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf
```

⚠️ **WARNING**: This is **PERMANENT and IRREVERSIBLE**. Once frozen:
- You can NEVER change the name, symbol, or URI again
- The image will be locked forever
- Update authority will be revoked

---

## Storage Options for Images

| Service | Type | Cost | Permanence | Speed |
|---------|------|------|------------|-------|
| **Arweave** | Blockchain storage | ~$0.01/MB one-time | Forever | Medium |
| **IPFS (NFT.Storage)** | Decentralized | Free | Permanent* | Fast |
| **IPFS (Pinata)** | Decentralized | Free tier | While pinned | Fast |
| **AWS S3** | Centralized | ~$0.023/GB/mo | While you pay | Fast |
| **GitHub Raw** | Git hosting | Free | While repo exists | Medium |

**Recommended**: Arweave or NFT.Storage for permanence

---

## Troubleshooting

### "Transaction simulation failed"

**Cause**: You may not be the update authority

**Fix**: Check who has update authority:
```bash
metaboss decode mint -a 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf
```

### "Invalid metadata account"

**Cause**: Token doesn't have Metaplex metadata

**Fix**: This is rare. Your token should have metadata if created via bags.fm. Double-check the mint address.

### "Insufficient funds"

**Cause**: Need SOL for transaction fees

**Fix**: Add ~0.01 SOL to the update authority wallet

---

## FAQ

**Q: Can I update after freezing?**
A: NO. Freezing is permanent. Update everything first.

**Q: What if I don't have the update authority?**
A: You can't update. Only the wallet that created the token can update metadata.

**Q: Does freezing cost SOL?**
A: Yes, ~0.005 SOL for the transaction.

**Q: Will this affect bags.fm?**
A: No. Freezing metadata only affects the Metaplex metadata account, not the token's functionality on bags.fm.

**Q: Can I change the image URL later if it's on IPFS?**
A: The IPFS content itself is immutable, but you can update the URI field... UNTIL you freeze metadata.

---

## Support

- Metaboss docs: https://metaboss.rs/
- Metaplex docs: https://developers.metaplex.com/token-metadata
- Bags.fm docs: https://docs.bags.fm/

Questions? Check the Jarvis Telegram: t.me/kr8tiventry

# KR8TIV Token Metadata Update - Step by Step

**Token Mint**: `7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf`

## What We're Updating

- ✅ Logo: Blue energy wave KR8TIV design
- ✅ Name: KR8TIV
- ✅ Symbol: KR8TIV
- ✅ Description: "kr8tiv builds Decentralized Open Sourced AI for the masses — powerful, practical, and dangerous (in a good way)."
- ✅ Website: https://kr8tiv.ai
- ✅ Twitter: @kr8tivai
- ✅ Additional: jarvislife.io, @Jarvis_lifeos

---

## Prerequisites

### 1. Save the Logo Image

The logo image you provided needs to be saved to disk:

```
📁 Location: assets/kr8tiv/logo.png
```

**Action**: Save the KR8TIV logo image file as `logo.png` in the `assets/kr8tiv/` directory.

### 2. Install Metaboss

```bash
# Option A: If you have Rust installed
cargo install metaboss

# Option B: Install Rust first, then metaboss
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
cargo install metaboss
```

### 3. Get NFT.Storage API Key

1. Go to https://nft.storage
2. Sign up (free)
3. Create API key
4. Save it:

```bash
export NFT_STORAGE_API_KEY="your_api_key_here"
```

Or add to your `.env`:
```bash
echo "NFT_STORAGE_API_KEY=your_api_key_here" >> .env
```

---

## Step-by-Step Execution

### Step 1: Upload Logo to IPFS

```bash
cd assets/kr8tiv

metaboss upload nft-storage --file logo.png
```

**Output**: You'll get an IPFS URL like:
```
https://ipfs.io/ipfs/bafybeig...xyz
```

**✏️ COPY THIS URL** - You'll need it in Step 2.

---

### Step 2: Update metadata.json

Open `assets/kr8tiv/metadata.json` and replace both `PLACEHOLDER_WILL_BE_REPLACED_AFTER_UPLOAD` instances with your IPFS URL from Step 1.

**Before**:
```json
"image": "PLACEHOLDER_WILL_BE_REPLACED_AFTER_UPLOAD",
```

**After**:
```json
"image": "https://ipfs.io/ipfs/bafybeig...xyz",
```

Do this for BOTH locations:
1. The `"image"` field
2. The `"properties.files[0].uri"` field

---

### Step 3: Upload Metadata JSON

```bash
metaboss upload nft-storage --file metadata.json
```

**Output**: You'll get another IPFS URL:
```
https://ipfs.io/ipfs/bafkreic...abc
```

**✏️ COPY THIS URL** - This is your metadata URI.

---

### Step 4: Locate Your Keypair

You mentioned you have the private key for:
```
7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf
```

**Where is your keypair stored?**

Common locations:
- `~/.config/solana/id.json` (default Solana CLI)
- Phantom wallet export (need to export as JSON)
- `./keypair.json` (custom location)

If you exported from Phantom:
1. Open Phantom
2. Settings → Export Private Key
3. Copy the array format: `[123,45,67,...]`
4. Save to `keypair.json`:

```json
[123,45,67,89,...]
```

---

### Step 5: Update On-Chain Metadata (DRY RUN)

**⚠️ First, do a dry run to make sure everything works:**

```bash
metaboss update uri \
  --keypair /path/to/your/keypair.json \
  --account 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf \
  --new-uri https://ipfs.io/ipfs/YOUR_METADATA_CID
```

Replace:
- `/path/to/your/keypair.json` → Your actual keypair path
- `YOUR_METADATA_CID` → The metadata IPFS URL from Step 3

If this succeeds, you'll see:
```
✅ Successfully updated metadata URI
Signature: 5x7y...abc
```

---

### Step 6: Verify Update

Check Solscan to see if metadata updated:

```
https://solscan.io/token/7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf
```

**Look for:**
- ✅ Logo showing the blue energy KR8TIV design
- ✅ Name: KR8TIV
- ✅ Symbol: KR8TIV
- ✅ Description showing
- ✅ Mutable: true (for now)

---

### Step 7: Freeze Metadata (OPTIONAL - PERMANENT!)

**⚠️ THIS IS IRREVERSIBLE - Only do this when you're 100% happy with everything**

Once you've verified the metadata looks perfect:

```bash
metaboss update immutable \
  --keypair /path/to/your/keypair.json \
  --account 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf
```

**Type confirmation when prompted.**

After freezing:
- ✅ Metadata can NEVER be changed
- ✅ Shows "Mutable: false" on Solscan
- ✅ Builds trust with community
- ❌ Can't update logo, name, or anything else ever again

---

## Quick Reference Commands

```bash
# 1. Upload logo
metaboss upload nft-storage --file assets/kr8tiv/logo.png

# 2. Edit metadata.json (add image URL)

# 3. Upload metadata
metaboss upload nft-storage --file assets/kr8tiv/metadata.json

# 4. Update on-chain
metaboss update uri \
  --keypair ~/.config/solana/id.json \
  --account 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf \
  --new-uri <METADATA_IPFS_URL>

# 5. Verify
open https://solscan.io/token/7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf

# 6. Freeze (PERMANENT!)
metaboss update immutable \
  --keypair ~/.config/solana/id.json \
  --account 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf
```

---

## Troubleshooting

### "Transaction simulation failed"

**Cause**: Wrong keypair (not the update authority)

**Fix**: Make sure you're using the keypair that originally created the token.

### "Invalid account"

**Cause**: Metadata account doesn't exist or wrong mint address

**Fix**: Double-check the mint address: `7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf`

### "NFT.Storage upload failed"

**Cause**: API key not set

**Fix**:
```bash
export NFT_STORAGE_API_KEY="your_key"
```

### "Insufficient funds"

**Cause**: Need SOL for transaction

**Fix**: Add ~0.01 SOL to the keypair wallet.

---

## What Happens After Update

1. **Logo shows on all Solana platforms**
   - Solscan
   - Raydium
   - Jupiter
   - Birdeye
   - Any wallet

2. **Metadata is discoverable**
   - DEXs can pull name/symbol/image
   - Explorers show description
   - Social links visible

3. **Builds trust**
   - Professional appearance
   - Shows commitment
   - Prevents metadata rug

---

## Timeline

- **Step 1-3**: 5 minutes (uploads)
- **Step 4**: 1 minute (find keypair)
- **Step 5**: 1 minute (update transaction)
- **Step 6**: 1 minute (verify)
- **Step 7**: 1 minute (freeze - optional)

**Total**: ~10 minutes

---

## Questions?

Check:
- [TOKEN_METADATA_GUIDE.md](./TOKEN_METADATA_GUIDE.md) - Full documentation
- [QUICK_START.md](./QUICK_START.md) - Quick reference

Or reach out:
- Telegram: t.me/kr8tiventry
- Twitter: @kr8tivai

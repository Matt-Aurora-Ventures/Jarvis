# KR8TIV Metadata Update - Manual Method

The NFT.Storage API key needs to be refreshed. Here's how to complete the update manually:

## Option 1: Get Fresh NFT.Storage API Key

1. Go to https://nft.storage
2. Login (or sign up - it's free)
3. Go to "API Keys" section
4. Click "New API Key"
5. Copy the NEW key (should start with `eyJ...`)

Then run:
```bash
export NFT_STORAGE_API_KEY="your_new_key_here"
python scripts/update_kr8tiv_metadata.py
```

---

## Option 2: Use Web3.Storage (Simpler)

Web3.Storage is another free IPFS service:

1. Go to https://web3.storage
2. Sign up (free)
3. Upload logo: `assets/kr8tiv/logo.png`
4. Copy the IPFS CID (e.g., `bafybeig...`)
5. Create metadata JSON:

```json
{
  "name": "KR8TIV",
  "symbol": "KR8TIV",
  "description": "kr8tiv builds Decentralized Open Sourced AI for the masses — powerful, practical, and dangerous (in a good way).",
  "image": "https://ipfs.io/ipfs/YOUR_IMAGE_CID",
  "external_url": "https://kr8tiv.ai",
  "attributes": [
    {"trait_type": "Category", "value": "AI"},
    {"trait_type": "Type", "value": "Utility Token"}
  ],
  "properties": {
    "files": [{"uri": "https://ipfs.io/ipfs/YOUR_IMAGE_CID", "type": "image/png"}],
    "category": "image"
  },
  "links": {
    "website": "https://kr8tiv.ai",
    "twitter": "https://x.com/kr8tivai"
  }
}
```

6. Upload metadata.json to Web3.Storage
7. Copy metadata CID

---

## Option 3: Use Pinata (Popular IPFS Service)

1. Go to https://app.pinata.cloud/
2. Sign up (free tier: 1GB)
3. Click "Upload" → Select `assets/kr8tiv/logo.png`
4. Copy the CID
5. Create metadata.json (replace IMAGE_CID)
6. Upload metadata.json
7. Copy metadata CID

---

## Step 4: Update On-Chain

Once you have the metadata IPFS URL, update on-chain:

### Method A: Using Metaplex Umi SDK (Node.js)

I'll create a simple script that just needs the metadata URL:

```bash
node scripts/update_onchain_only.js <METADATA_IPFS_URL>
```

### Method B: Using Solana CLI (if you have it)

```bash
metaplex update \
  --keypair keypair.json \
  --mint 7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf \
  --uri https://ipfs.io/ipfs/YOUR_METADATA_CID
```

---

## What You Have Ready

✅ Logo: `assets/kr8tiv/logo.png` (1.4MB)
✅ Keypair: `keypair.json`
✅ Metadata template: Ready to fill in
✅ Mint address: `7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf`

## Next Steps

1. Choose IPFS service (NFT.Storage, Web3.Storage, or Pinata)
2. Upload logo → get CID
3. Create metadata.json with logo CID
4. Upload metadata.json → get CID
5. Run update script with metadata CID

Would you like me to:
- Create a script for a specific upload service?
- Walk you through Web3.Storage upload (simplest)?
- Create the on-chain update script only?

Let me know which path you prefer!

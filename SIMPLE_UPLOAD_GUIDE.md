# Simple KR8TIV Metadata Update Guide

The API key issue is blocking automated uploads. Here's the **simplest manual method**:

## 🎯 Quick Steps (5 minutes)

### Step 1: Upload Logo to IPFS (Web Interface)

**Use Web3.Storage** (easiest, no API key needed):

1. Go to https://web3.storage
2. Click "Sign Up" (free, just email)
3. Click "Upload Files"
4. Select: `c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\assets\kr8tiv\logo.png`
5. Wait for upload
6. **Copy the CID** (looks like: `bafybeig...`)

Your logo URL is: `https://ipfs.io/ipfs/YOUR_CID`

---

### Step 2: Create Metadata JSON

Create a file called `metadata.json` with this content (replace `YOUR_IMAGE_CID`):

```json
{
  "name": "KR8TIV",
  "symbol": "KR8TIV",
  "description": "kr8tiv builds Decentralized Open Sourced AI for the masses — powerful, practical, and dangerous (in a good way).",
  "image": "https://ipfs.io/ipfs/YOUR_IMAGE_CID",
  "external_url": "https://kr8tiv.ai",
  "attributes": [
    {
      "trait_type": "Category",
      "value": "AI"
    },
    {
      "trait_type": "Type",
      "value": "Utility Token"
    },
    {
      "trait_type": "Network",
      "value": "Solana"
    },
    {
      "trait_type": "Platform",
      "value": "Decentralized AI"
    }
  ],
  "properties": {
    "files": [
      {
        "uri": "https://ipfs.io/ipfs/YOUR_IMAGE_CID",
        "type": "image/png"
      }
    ],
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
```

---

### Step 3: Upload Metadata to IPFS

1. Go back to https://web3.storage
2. Click "Upload Files"
3. Select your `metadata.json` file
4. Wait for upload
5. **Copy the new CID** (for the metadata)

Your metadata URL is: `https://ipfs.io/ipfs/YOUR_METADATA_CID`

---

### Step 4: Update On-Chain

Run this command (replace `YOUR_METADATA_CID`):

```bash
cd c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis
node scripts/update_onchain.js https://ipfs.io/ipfs/YOUR_METADATA_CID
```

It will ask for confirmation, then update the on-chain metadata!

---

## ✅ What I've Prepared For You

✅ **Logo saved**: `assets/kr8tiv/logo.png`
✅ **Keypair saved**: `keypair.json`
✅ **Metaplex SDK installed**: Ready to use
✅ **Update script created**: `scripts/update_onchain.js`

## 🎯 All You Need To Do

1. Upload logo to web3.storage → Copy CID
2. Create metadata.json with that CID
3. Upload metadata.json → Copy CID
4. Run: `node scripts/update_onchain.js https://ipfs.io/ipfs/CID`

That's it!

---

## 📋 Checklist

- [ ] Go to web3.storage and sign up
- [ ] Upload `assets/kr8tiv/logo.png` → Get CID
- [ ] Create `metadata.json` with image CID
- [ ] Upload `metadata.json` → Get metadata CID
- [ ] Run update script with metadata URL
- [ ] Verify on Solscan

---

## 🆘 Need Help?

Let me know which step you're on and I can guide you through it!

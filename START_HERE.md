# Start Here: Update $KR8TIV Token Metadata

## 🚀 One Command to Do Everything

I've created a **fully automated script** that will:
1. ✅ Check/install all dependencies (Rust, metaboss)
2. ✅ Get your NFT.Storage API key
3. ✅ Find your logo image
4. ✅ Upload to permanent IPFS storage
5. ✅ Update on-chain metadata
6. ✅ (Optional) Freeze metadata

## 📋 Before You Run

You only need TWO things:

### 1. Save the Logo Image
Save the blue energy wave KR8TIV image as:
```
assets/kr8tiv/logo.png
```

### 2. Have Your Keypair Ready
The private key for: `7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf`

Common locations:
- `~/.config/solana/id.json`
- `./keypair.json`
- Or export from Phantom wallet

---

## ▶️ Run The Script

### Option 1: Windows (WSL/Git Bash)

```bash
bash setup_kr8tiv.sh
```

### Option 2: Mac/Linux

```bash
./setup_kr8tiv.sh
```

---

## 🎯 What The Script Does

The script will **automatically**:

1. **Install Rust** (if needed)
2. **Install metaboss** (if needed)
3. **Prompt for NFT.Storage API key** (free from https://nft.storage)
4. **Find your logo** (or ask where it is)
5. **Upload logo to IPFS** (permanent storage)
6. **Create metadata JSON** with all your info:
   - Name: KR8TIV
   - Symbol: KR8TIV
   - Description: "kr8tiv builds Decentralized Open Sourced AI for the masses..."
   - Website: https://kr8tiv.ai
   - Twitter: @kr8tivai, @Jarvis_lifeos
7. **Upload metadata to IPFS**
8. **Update on-chain** with your keypair
9. **Ask if you want to freeze** (optional, permanent)

---

## ⏱️ How Long Does It Take?

- **First time** (installing tools): 10-15 minutes
- **After tools installed**: 2-3 minutes
- **Just the update** (if setup already): 30 seconds

---

## 🎬 Step-by-Step Walkthrough

When you run the script, it will guide you through:

### Step 1: Dependencies
```
[1/8] Checking Rust installation...
✓ Rust already installed

[2/8] Checking metaboss installation...
Installing metaboss (this may take 5-10 minutes)...
✓ metaboss installed!
```

### Step 2: API Key
```
[3/8] NFT.Storage API Key Setup

Steps to get your key:
  1. Open: https://nft.storage
  2. Click 'Sign Up' (free)
  3. Click 'API Keys' → 'New API Key'
  4. Copy the key

Paste your NFT.Storage API key here: _
```

### Step 3: Logo
```
[4/8] Logo Image Setup

✓ Logo found at: assets/kr8tiv/logo.png
```

### Step 4: Keypair
```
[5/8] Keypair Setup

✓ Found keypair: ~/.config/solana/id.json
Use this keypair? (yes/no): _
```

### Step 5: Upload
```
[6/8] Uploading logo to IPFS...

Uploading to NFT.Storage (permanent IPFS)...
✓ Logo uploaded!

  URL: https://ipfs.io/ipfs/bafybeig...xyz
```

### Step 6: Metadata
```
[7/8] Creating metadata...

✓ Metadata JSON created
Uploading metadata to IPFS...
✓ Metadata uploaded!

  URL: https://ipfs.io/ipfs/bafkreic...abc
```

### Step 7: Update
```
[8/8] Updating on-chain metadata...

Review:
═══════════════════════════════════════════
  Mint:        7BLH...23cf
  Name:        KR8TIV
  Symbol:      KR8TIV
  Description: kr8tiv builds Decentralized...
  Website:     https://kr8tiv.ai
  Image URL:   https://ipfs.io/ipfs/...
  Metadata:    https://ipfs.io/ipfs/...
═══════════════════════════════════════════

Update on-chain now? (yes/no): yes

Sending transaction...

✓ ON-CHAIN METADATA UPDATED!
```

### Step 8: Freeze (Optional)
```
════════════════════════════════════════════
         Freeze Metadata? (OPTIONAL)
════════════════════════════════════════════

⚠️  WARNING: Freezing is PERMANENT

After freezing:
  ✓ Metadata can NEVER be changed
  ✓ Shows commitment to holders
  ✓ Prevents rug via metadata change

Freeze metadata now? (yes/no): _
```

---

## ✅ Verification

After the script completes, check:

**Solscan**:
```
https://solscan.io/token/7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf
```

Look for:
- [x] Blue energy wave KR8TIV logo showing
- [x] Name: KR8TIV
- [x] Symbol: KR8TIV
- [x] Description visible
- [x] Website link working
- [x] Mutable: false (if you froze it)

**DEX Platforms**:
- Jupiter: https://jup.ag/
- Raydium: https://raydium.io/
- Birdeye: https://birdeye.so/

---

## 🎉 After Update

### Announce on X
```
🚀 $KR8TIV metadata is live!

✅ Professional logo
✅ Complete token info
✅ Permanently frozen (immutable)

Building decentralized AI for the masses.

Check it out 👇
https://solscan.io/token/7BLH...23cf

#Solana #AI #DeFi
```

### Share in Telegram
Post the Solscan link and explain:
- Logo is now visible everywhere
- Metadata is frozen (can't be changed)
- Shows commitment to community

---

## 🐛 Troubleshooting

### Script fails with "command not found"
**Fix**: You're not in Bash. Use Git Bash or WSL on Windows.

### "NFT.Storage upload failed"
**Fix**: Check your API key is correct. Get a new one from https://nft.storage

### "Transaction simulation failed"
**Fix**: Wrong keypair. Use the one that created the token.

### "Insufficient funds"
**Fix**: Add ~0.01 SOL to your keypair wallet.

---

## 📚 Full Documentation

If you want to understand every detail:
- **Quick Commands**: [scripts/QUICK_START.md](scripts/QUICK_START.md)
- **Complete Guide**: [scripts/TOKEN_METADATA_GUIDE.md](scripts/TOKEN_METADATA_GUIDE.md)
- **Manual Steps**: [assets/kr8tiv/UPDATE_INSTRUCTIONS.md](assets/kr8tiv/UPDATE_INSTRUCTIONS.md)

---

## 💬 Support

- **Telegram**: t.me/kr8tiventry
- **Twitter**: @kr8tivai
- **Website**: https://kr8tiv.ai

---

## 🎯 Ready?

Just run:

```bash
bash setup_kr8tiv.sh
```

The script will do everything for you! 🚀

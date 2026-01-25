# KR8TIV Token Metadata Update

Everything you need to update $KR8TIV token metadata and add the logo.

## 📁 Files in This Directory

- **logo.png** - The KR8TIV blue energy wave logo (SAVE THIS IMAGE HERE FIRST!)
- **metadata.json** - Complete metadata configuration
- **UPDATE_INSTRUCTIONS.md** - Step-by-step manual guide
- **run_update.sh** - Automated update script (Mac/Linux/WSL)
- **README.md** - This file

## 🎯 Your Token Info

- **Mint**: `7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf`
- **Website**: https://kr8tiv.ai
- **Twitter**: @kr8tivai
- **Description**: "kr8tiv builds Decentralized Open Sourced AI for the masses — powerful, practical, and dangerous (in a good way)."

## ⚡ Quick Start (Automated)

### Prerequisites

1. **Save the logo image**:
   - Save the KR8TIV blue energy wave image as `logo.png` in this directory

2. **Install metaboss**:
   ```bash
   cargo install metaboss
   ```

3. **Get NFT.Storage API key**:
   ```bash
   # Sign up at https://nft.storage (free)
   export NFT_STORAGE_API_KEY="your_key_here"
   ```

4. **Prepare keypair**:
   - Have your update authority keypair JSON file ready

### Run The Update

```bash
# Make sure logo.png is saved first!

# Run the automated script
bash assets/kr8tiv/run_update.sh
```

The script will:
1. ✅ Upload logo to IPFS
2. ✅ Create metadata with your info
3. ✅ Upload metadata to IPFS
4. ✅ Update on-chain
5. ✅ (Optional) Freeze metadata

## 📖 Manual Instructions

If you prefer step-by-step control, see [UPDATE_INSTRUCTIONS.md](./UPDATE_INSTRUCTIONS.md)

## 🔍 What Gets Updated

### Logo
The blue energy wave KR8TIV design will show on:
- Solscan
- Jupiter
- Raydium
- Birdeye
- All Solana wallets

### Metadata
```json
{
  "name": "KR8TIV",
  "symbol": "KR8TIV",
  "description": "kr8tiv builds Decentralized Open Sourced AI for the masses — powerful, practical, and dangerous (in a good way).",
  "external_url": "https://kr8tiv.ai",
  "links": {
    "website": "https://kr8tiv.ai",
    "jarvis": "https://jarvislife.io",
    "twitter": "https://x.com/kr8tivai",
    "jarvis_twitter": "https://x.com/Jarvis_lifeos"
  }
}
```

## ⚠️ Important Notes

### Before You Start

1. **Save the logo** as `logo.png` in this directory
2. **Have your keypair** ready (the one that created the token)
3. **Set NFT_STORAGE_API_KEY** environment variable
4. **Have ~0.01 SOL** in the keypair wallet for transaction fees

### About Freezing

**Freezing metadata is OPTIONAL but PERMANENT:**

✅ **Benefits**:
- Shows commitment to community
- Prevents rug pull via metadata changes
- Builds trust ("can't change the logo on us")

❌ **Risks**:
- Can NEVER change name, symbol, or logo again
- Typos are permanent
- Can't update links/description

**Recommendation**: Only freeze after verifying everything looks perfect on Solscan.

## 🐛 Troubleshooting

### "metaboss: command not found"

Install Rust and metaboss:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
cargo install metaboss
```

### "Transaction simulation failed"

**Cause**: Wrong keypair (you're not the update authority)

**Fix**: Make sure you're using the keypair that created the token

### "NFT.Storage upload failed"

**Cause**: API key not set

**Fix**:
```bash
export NFT_STORAGE_API_KEY="your_key"
```

### "logo.png not found"

**Cause**: You need to save the image first

**Fix**: Save the KR8TIV logo image as `assets/kr8tiv/logo.png`

## 📊 Timeline

- **Setup** (install tools, get API key): 5-10 minutes
- **Update** (run script): 2-3 minutes
- **Verify** (check Solscan): 1 minute
- **Freeze** (optional): 1 minute

**Total**: ~10-15 minutes

## ✅ Verification Checklist

After running the update, check:

1. Go to: https://solscan.io/token/7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf

2. Verify:
   - [ ] Logo showing (blue energy wave KR8TIV design)
   - [ ] Name: KR8TIV
   - [ ] Symbol: KR8TIV
   - [ ] Description showing
   - [ ] Links visible
   - [ ] Mutable: true (before freeze) or false (after freeze)

3. Test on DEXs:
   - [ ] Jupiter shows logo
   - [ ] Raydium shows logo
   - [ ] Birdeye shows logo

## 🎉 After Update

1. **Announce on X**:
   ```
   🚀 $KR8TIV metadata updated!

   ✅ Professional logo added
   ✅ Complete token info
   ✅ Metadata frozen (immutable)

   Building decentralized AI for the masses.

   Check it: https://solscan.io/token/7BLH...23cf
   ```

2. **Share in Telegram**:
   - Post the Solscan link
   - Show before/after screenshots
   - Explain the freeze (builds trust)

3. **Update docs**:
   - Add logo to README
   - Update website with Solscan link

## 📚 Additional Resources

- **Full Guide**: [../../scripts/TOKEN_METADATA_GUIDE.md](../../scripts/TOKEN_METADATA_GUIDE.md)
- **Quick Reference**: [../../scripts/QUICK_START.md](../../scripts/QUICK_START.md)
- **Metaboss Docs**: https://metaboss.rs/
- **Metaplex Docs**: https://developers.metaplex.com/

## 💬 Questions?

- **Telegram**: t.me/kr8tiventry
- **Twitter**: @kr8tivai
- **Website**: https://kr8tiv.ai

#!/bin/bash
#
# KR8TIV Token Metadata Complete Setup
# This script does EVERYTHING for you
#

set -e

MINT="7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

clear
echo -e "${CYAN}"
echo "════════════════════════════════════════════════════════════════"
echo "          KR8TIV Token Metadata - Complete Setup"
echo "════════════════════════════════════════════════════════════════"
echo -e "${NC}"
echo ""
echo "This script will:"
echo "  1. Check/install dependencies"
echo "  2. Get your NFT.Storage API key"
echo "  3. Find your logo image"
echo "  4. Upload everything to IPFS"
echo "  5. Update on-chain metadata"
echo "  6. (Optional) Freeze metadata"
echo ""
read -p "Press Enter to continue..."

# ============================================================
# STEP 1: Check Rust/Cargo
# ============================================================

clear
echo -e "${YELLOW}[1/8] Checking Rust installation...${NC}"
echo ""

if ! command -v cargo &> /dev/null; then
    echo -e "${RED}✗ Rust/Cargo not installed${NC}"
    echo ""
    echo "Installing Rust now..."
    echo ""

    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

    # Source cargo
    source "$HOME/.cargo/env"

    echo ""
    echo -e "${GREEN}✓ Rust installed!${NC}"
else
    echo -e "${GREEN}✓ Rust already installed${NC}"
fi

# ============================================================
# STEP 2: Check/Install Metaboss
# ============================================================

echo ""
echo -e "${YELLOW}[2/8] Checking metaboss installation...${NC}"
echo ""

if ! command -v metaboss &> /dev/null; then
    echo -e "${RED}✗ metaboss not installed${NC}"
    echo ""
    echo "Installing metaboss (this may take 5-10 minutes)..."
    echo ""

    cargo install metaboss

    echo ""
    echo -e "${GREEN}✓ metaboss installed!${NC}"
else
    VERSION=$(metaboss --version)
    echo -e "${GREEN}✓ metaboss already installed: $VERSION${NC}"
fi

# ============================================================
# STEP 3: Get NFT.Storage API Key
# ============================================================

clear
echo -e "${YELLOW}[3/8] NFT.Storage API Key Setup${NC}"
echo ""

if [ -n "$NFT_STORAGE_API_KEY" ]; then
    echo -e "${GREEN}✓ NFT_STORAGE_API_KEY already set${NC}"
else
    echo "You need a free API key from NFT.Storage"
    echo ""
    echo -e "${CYAN}Steps to get your key:${NC}"
    echo "  1. Open: https://nft.storage"
    echo "  2. Click 'Sign Up' (free)"
    echo "  3. Verify email"
    echo "  4. Click 'API Keys' → 'New API Key'"
    echo "  5. Copy the key"
    echo ""
    echo -e "${YELLOW}Opening NFT.Storage in your browser...${NC}"

    # Try to open browser
    if command -v xdg-open &> /dev/null; then
        xdg-open "https://nft.storage" 2>/dev/null &
    elif command -v open &> /dev/null; then
        open "https://nft.storage" 2>/dev/null &
    fi

    echo ""
    read -p "Paste your NFT.Storage API key here: " API_KEY
    export NFT_STORAGE_API_KEY="$API_KEY"

    # Save to .env
    echo "NFT_STORAGE_API_KEY=$API_KEY" >> .env

    echo ""
    echo -e "${GREEN}✓ API key saved!${NC}"
fi

# ============================================================
# STEP 4: Find Logo Image
# ============================================================

clear
echo -e "${YELLOW}[4/8] Logo Image Setup${NC}"
echo ""

LOGO_PATH="assets/kr8tiv/logo.png"

if [ -f "$LOGO_PATH" ]; then
    echo -e "${GREEN}✓ Logo found at: $LOGO_PATH${NC}"
else
    echo -e "${RED}✗ Logo not found at: $LOGO_PATH${NC}"
    echo ""
    echo "Please provide the path to your KR8TIV logo image:"
    echo "(The blue energy wave design)"
    echo ""
    read -p "Path to logo image: " USER_LOGO_PATH

    if [ ! -f "$USER_LOGO_PATH" ]; then
        echo -e "${RED}✗ File not found: $USER_LOGO_PATH${NC}"
        echo ""
        echo "Please save the logo image and run this script again."
        exit 1
    fi

    # Create directory and copy
    mkdir -p assets/kr8tiv
    cp "$USER_LOGO_PATH" "$LOGO_PATH"

    echo -e "${GREEN}✓ Logo copied to: $LOGO_PATH${NC}"
fi

# ============================================================
# STEP 5: Get Keypair
# ============================================================

clear
echo -e "${YELLOW}[5/8] Keypair Setup${NC}"
echo ""

# Try common locations
COMMON_KEYPAIRS=(
    "$HOME/.config/solana/id.json"
    "$HOME/.config/solana/devnet.json"
    "./keypair.json"
    "./id.json"
)

FOUND_KEYPAIR=""
for kp in "${COMMON_KEYPAIRS[@]}"; do
    if [ -f "$kp" ]; then
        FOUND_KEYPAIR="$kp"
        break
    fi
done

if [ -n "$FOUND_KEYPAIR" ]; then
    echo -e "${GREEN}✓ Found keypair: $FOUND_KEYPAIR${NC}"
    echo ""
    read -p "Use this keypair? (yes/no): " USE_FOUND

    if [ "$USE_FOUND" == "yes" ]; then
        KEYPAIR_PATH="$FOUND_KEYPAIR"
    else
        read -p "Path to your keypair JSON: " KEYPAIR_PATH
    fi
else
    echo "Common keypair locations checked:"
    for kp in "${COMMON_KEYPAIRS[@]}"; do
        echo "  ✗ $kp"
    done
    echo ""
    read -p "Path to your keypair JSON: " KEYPAIR_PATH
fi

if [ ! -f "$KEYPAIR_PATH" ]; then
    echo -e "${RED}✗ Keypair not found: $KEYPAIR_PATH${NC}"
    echo ""
    echo "Export your keypair from Phantom:"
    echo "  1. Open Phantom wallet"
    echo "  2. Settings → Export Private Key"
    echo "  3. Save as keypair.json in this format:"
    echo "     [123,45,67,...]"
    exit 1
fi

echo -e "${GREEN}✓ Keypair found: $KEYPAIR_PATH${NC}"

# ============================================================
# STEP 6: Upload Logo to IPFS
# ============================================================

clear
echo -e "${YELLOW}[6/8] Uploading logo to IPFS...${NC}"
echo ""

echo "Uploading to NFT.Storage (permanent IPFS)..."
IMAGE_URL=$(metaboss upload nft-storage --file "$LOGO_PATH" 2>&1 | grep -E "^https?://" | tail -1)

if [ -z "$IMAGE_URL" ]; then
    echo -e "${RED}✗ Logo upload failed${NC}"
    echo ""
    echo "Please check:"
    echo "  1. NFT_STORAGE_API_KEY is correct"
    echo "  2. You have internet connection"
    echo "  3. Logo file is valid PNG/JPG"
    exit 1
fi

echo -e "${GREEN}✓ Logo uploaded!${NC}"
echo ""
echo "  URL: $IMAGE_URL"

# ============================================================
# STEP 7: Create and Upload Metadata
# ============================================================

clear
echo -e "${YELLOW}[7/8] Creating metadata...${NC}"
echo ""

METADATA_FILE="assets/kr8tiv/metadata_final.json"

cat > "$METADATA_FILE" <<EOF
{
  "name": "KR8TIV",
  "symbol": "KR8TIV",
  "description": "kr8tiv builds Decentralized Open Sourced AI for the masses — powerful, practical, and dangerous (in a good way).",
  "image": "$IMAGE_URL",
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
        "uri": "$IMAGE_URL",
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
EOF

echo -e "${GREEN}✓ Metadata JSON created${NC}"
echo ""
echo "Uploading metadata to IPFS..."

METADATA_URL=$(metaboss upload nft-storage --file "$METADATA_FILE" 2>&1 | grep -E "^https?://" | tail -1)

if [ -z "$METADATA_URL" ]; then
    echo -e "${RED}✗ Metadata upload failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Metadata uploaded!${NC}"
echo ""
echo "  URL: $METADATA_URL"

# ============================================================
# STEP 8: Update On-Chain
# ============================================================

clear
echo -e "${YELLOW}[8/8] Updating on-chain metadata...${NC}"
echo ""

echo -e "${CYAN}Review:${NC}"
echo "═══════════════════════════════════════════════════════"
echo -e "  ${BLUE}Mint:${NC}        $MINT"
echo -e "  ${BLUE}Name:${NC}        KR8TIV"
echo -e "  ${BLUE}Symbol:${NC}      KR8TIV"
echo -e "  ${BLUE}Description:${NC} kr8tiv builds Decentralized Open Sourced AI..."
echo -e "  ${BLUE}Website:${NC}     https://kr8tiv.ai"
echo -e "  ${BLUE}Image URL:${NC}   $IMAGE_URL"
echo -e "  ${BLUE}Metadata:${NC}    $METADATA_URL"
echo "═══════════════════════════════════════════════════════"
echo ""

read -p "Update on-chain now? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Cancelled${NC}"
    echo ""
    echo "To update later, run:"
    echo "  metaboss update uri \\"
    echo "    --keypair $KEYPAIR_PATH \\"
    echo "    --account $MINT \\"
    echo "    --new-uri $METADATA_URL"
    exit 0
fi

echo ""
echo "Sending transaction..."

TX_SIG=$(metaboss update uri \
    --keypair "$KEYPAIR_PATH" \
    --account "$MINT" \
    --new-uri "$METADATA_URL" 2>&1)

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ ON-CHAIN METADATA UPDATED!${NC}"
    echo ""
    echo "Transaction: $TX_SIG"
else
    echo ""
    echo -e "${RED}✗ Update failed${NC}"
    echo ""
    echo "Error: $TX_SIG"
    echo ""
    echo "Common issues:"
    echo "  - Wrong keypair (not the update authority)"
    echo "  - Insufficient SOL for fees (~0.01 SOL needed)"
    echo "  - Network issues"
    exit 1
fi

# ============================================================
# Verification
# ============================================================

clear
echo -e "${CYAN}"
echo "════════════════════════════════════════════════════════"
echo "                     SUCCESS!"
echo "════════════════════════════════════════════════════════"
echo -e "${NC}"
echo ""
echo -e "${GREEN}✓ Logo uploaded to IPFS${NC}"
echo -e "${GREEN}✓ Metadata created and uploaded${NC}"
echo -e "${GREEN}✓ On-chain metadata updated${NC}"
echo ""
echo "Verify on Solscan:"
echo -e "${CYAN}https://solscan.io/token/$MINT${NC}"
echo ""
echo "Look for:"
echo "  ✓ Blue energy wave KR8TIV logo"
echo "  ✓ Name: KR8TIV"
echo "  ✓ Symbol: KR8TIV"
echo "  ✓ Description showing"
echo "  ✓ Mutable: true (not frozen yet)"
echo ""

# ============================================================
# Optional: Freeze Metadata
# ============================================================

echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}         Freeze Metadata? (OPTIONAL)${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}⚠️  WARNING: Freezing is PERMANENT and IRREVERSIBLE${NC}"
echo ""
echo "After freezing:"
echo "  ${GREEN}✓${NC} Metadata can NEVER be changed"
echo "  ${GREEN}✓${NC} Shows commitment to holders"
echo "  ${GREEN}✓${NC} Prevents rug via metadata change"
echo ""
echo "  ${RED}✗${NC} Can't fix typos"
echo "  ${RED}✗${NC} Can't update logo/name/symbol"
echo "  ${RED}✗${NC} Can't change links"
echo ""
echo -e "${YELLOW}Recommendation:${NC} Verify everything on Solscan first,"
echo "then run freeze separately when ready."
echo ""

read -p "Freeze metadata now? (yes/no): " FREEZE

if [ "$FREEZE" == "yes" ]; then
    echo ""
    echo -e "${RED}⚠⚠⚠ FINAL WARNING ⚠⚠⚠${NC}"
    echo -e "${RED}This CANNOT be undone. Ever.${NC}"
    echo ""
    read -p "Type 'FREEZE' (all caps) to confirm: " FINAL

    if [ "$FINAL" == "FREEZE" ]; then
        echo ""
        echo "Freezing metadata..."

        FREEZE_TX=$(metaboss update immutable \
            --keypair "$KEYPAIR_PATH" \
            --account "$MINT" 2>&1)

        if [ $? -eq 0 ]; then
            clear
            echo -e "${GREEN}"
            echo "════════════════════════════════════════════════════════"
            echo "              METADATA IS NOW IMMUTABLE!"
            echo "════════════════════════════════════════════════════════"
            echo -e "${NC}"
            echo ""
            echo "Transaction: $FREEZE_TX"
            echo ""
            echo "Your metadata is now permanently locked."
            echo "This will show as 'Mutable: false' on Solscan."
        else
            echo -e "${RED}✗ Freeze failed${NC}"
            echo ""
            echo "Error: $FREEZE_TX"
        fi
    else
        echo -e "${YELLOW}Freeze cancelled${NC}"
    fi
else
    echo -e "${YELLOW}Skipped freeze${NC}"
    echo ""
    echo "To freeze later:"
    echo "  metaboss update immutable \\"
    echo "    --keypair $KEYPAIR_PATH \\"
    echo "    --account $MINT"
fi

# ============================================================
# Final Summary
# ============================================================

clear
echo -e "${CYAN}"
echo "════════════════════════════════════════════════════════"
echo "                  SETUP COMPLETE!"
echo "════════════════════════════════════════════════════════"
echo -e "${NC}"
echo ""
echo "What was done:"
echo "  ${GREEN}✓${NC} Logo uploaded to permanent IPFS storage"
echo "  ${GREEN}✓${NC} Metadata created with all your info"
echo "  ${GREEN}✓${NC} On-chain metadata updated"
if [ "$FREEZE" == "yes" ] && [ "$FINAL" == "FREEZE" ]; then
echo "  ${GREEN}✓${NC} Metadata frozen (immutable)"
fi
echo ""
echo "Files created:"
echo "  - $LOGO_PATH"
echo "  - $METADATA_FILE"
echo ""
echo "URLs:"
echo "  - Image:    $IMAGE_URL"
echo "  - Metadata: $METADATA_URL"
echo ""
echo "Verify:"
echo "  https://solscan.io/token/$MINT"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Check Solscan (link above)"
echo "  2. Verify logo and info are correct"
echo "  3. Announce on X/Telegram"
echo "  4. Share updated token with community"
echo ""
echo -e "${CYAN}Thanks for using KR8TIV! 🚀${NC}"
echo ""

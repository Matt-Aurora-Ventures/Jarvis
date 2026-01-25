#!/bin/bash
#
# KR8TIV Metadata Update - Automated Script
#
# This script automates the entire metadata update process.
# Run this after you've:
#   1. Saved the logo as assets/kr8tiv/logo.png
#   2. Set NFT_STORAGE_API_KEY environment variable
#   3. Prepared your keypair.json file
#

set -e  # Exit on error

# Config
MINT="7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf"
LOGO_FILE="assets/kr8tiv/logo.png"
METADATA_FILE="assets/kr8tiv/metadata.json"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "════════════════════════════════════════════════════════"
echo "           KR8TIV Token Metadata Update"
echo "════════════════════════════════════════════════════════"
echo ""

# Check dependencies
echo -e "${YELLOW}[1/7] Checking dependencies...${NC}"

if ! command -v metaboss &> /dev/null; then
    echo -e "${RED}✗ metaboss not installed${NC}"
    echo ""
    echo "Install with:"
    echo "  cargo install metaboss"
    exit 1
fi

echo -e "${GREEN}✓ metaboss installed${NC}"

# Check API key
if [ -z "$NFT_STORAGE_API_KEY" ]; then
    echo -e "${RED}✗ NFT_STORAGE_API_KEY not set${NC}"
    echo ""
    echo "Get a free key from https://nft.storage and run:"
    echo "  export NFT_STORAGE_API_KEY='your_key'"
    exit 1
fi

echo -e "${GREEN}✓ NFT_STORAGE_API_KEY set${NC}"

# Check logo exists
if [ ! -f "$LOGO_FILE" ]; then
    echo -e "${RED}✗ Logo not found: $LOGO_FILE${NC}"
    echo ""
    echo "Please save the KR8TIV logo image as:"
    echo "  $LOGO_FILE"
    exit 1
fi

echo -e "${GREEN}✓ Logo found${NC}"

# Get keypair
echo ""
echo -e "${YELLOW}[2/7] Keypair setup...${NC}"

if [ -f "~/.config/solana/id.json" ]; then
    DEFAULT_KEYPAIR="~/.config/solana/id.json"
else
    DEFAULT_KEYPAIR="./keypair.json"
fi

read -p "Path to keypair JSON [$DEFAULT_KEYPAIR]: " KEYPAIR_PATH
KEYPAIR_PATH=${KEYPAIR_PATH:-$DEFAULT_KEYPAIR}

if [ ! -f "$KEYPAIR_PATH" ]; then
    echo -e "${RED}✗ Keypair not found: $KEYPAIR_PATH${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Keypair found${NC}"

# Upload logo
echo ""
echo -e "${YELLOW}[3/7] Uploading logo to IPFS...${NC}"

IMAGE_URL=$(metaboss upload nft-storage --file "$LOGO_FILE" 2>&1 | tail -1)

if [ -z "$IMAGE_URL" ]; then
    echo -e "${RED}✗ Logo upload failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Logo uploaded: $IMAGE_URL${NC}"

# Update metadata.json with image URL
echo ""
echo -e "${YELLOW}[4/7] Updating metadata.json...${NC}"

# Create updated metadata with actual image URL
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

echo -e "${GREEN}✓ metadata.json updated${NC}"

# Upload metadata
echo ""
echo -e "${YELLOW}[5/7] Uploading metadata to IPFS...${NC}"

METADATA_URL=$(metaboss upload nft-storage --file "$METADATA_FILE" 2>&1 | tail -1)

if [ -z "$METADATA_URL" ]; then
    echo -e "${RED}✗ Metadata upload failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Metadata uploaded: $METADATA_URL${NC}"

# Update on-chain
echo ""
echo -e "${YELLOW}[6/7] Updating on-chain metadata...${NC}"
echo ""
echo "Review:"
echo "  Mint:     $MINT"
echo "  Image:    $IMAGE_URL"
echo "  Metadata: $METADATA_URL"
echo ""

read -p "Update on-chain? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Cancelled${NC}"
    exit 0
fi

echo ""
echo "Sending transaction..."

metaboss update uri \
    --keypair "$KEYPAIR_PATH" \
    --account "$MINT" \
    --new-uri "$METADATA_URL"

echo -e "${GREEN}✓ On-chain metadata updated!${NC}"

# Verify
echo ""
echo -e "${YELLOW}[7/7] Verification...${NC}"
echo ""
echo "Check Solscan:"
echo "  https://solscan.io/token/$MINT"
echo ""
echo "Look for:"
echo "  ✓ Blue energy wave KR8TIV logo"
echo "  ✓ Name: KR8TIV"
echo "  ✓ Description showing"
echo "  ✓ Mutable: true (for now)"
echo ""

# Freeze option
echo "════════════════════════════════════════════════════════"
echo "           Freeze Metadata (Optional)"
echo "════════════════════════════════════════════════════════"
echo ""
echo "⚠️  WARNING: Freezing is PERMANENT and IRREVERSIBLE"
echo ""
echo "After freezing:"
echo "  ✓ Metadata can NEVER be changed again"
echo "  ✓ Shows 'Mutable: false' on Solscan"
echo "  ✓ Builds trust with community"
echo ""

read -p "Freeze metadata now? (yes/no): " FREEZE

if [ "$FREEZE" == "yes" ]; then
    echo ""
    echo -e "${RED}⚠⚠⚠ FINAL WARNING ⚠⚠⚠${NC}"
    echo -e "${RED}This CANNOT be undone${NC}"
    echo ""
    read -p "Type 'FREEZE' to confirm: " FINAL

    if [ "$FINAL" == "FREEZE" ]; then
        echo ""
        echo "Freezing metadata..."

        metaboss update immutable \
            --keypair "$KEYPAIR_PATH" \
            --account "$MINT"

        echo ""
        echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}✓ SUCCESS! Metadata is now IMMUTABLE${NC}"
        echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
    else
        echo -e "${YELLOW}Freeze cancelled${NC}"
    fi
else
    echo -e "${YELLOW}Skipped freeze${NC}"
fi

echo ""
echo "════════════════════════════════════════════════════════"
echo "✓ COMPLETE"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Verify on Solscan (link above)"
echo "  2. Announce to community on X/Telegram"
echo "  3. Share the updated logo"
echo ""

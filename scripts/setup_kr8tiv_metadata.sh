#!/bin/bash
#
# KR8TIV Token Metadata Setup
# Complete workflow: Install tools → Upload image → Update metadata → Freeze
#

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Token info
MINT="7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf"
CONTRACT="U1zc8QpnrQ3HBJUBrWFYWbQTLzNsCpPgZNegWXdBAGS"

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}           KR8TIV Token Metadata Setup${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Mint:     ${GREEN}$MINT${NC}"
echo -e "Contract: ${GREEN}$CONTRACT${NC}"
echo ""

# Step 1: Check/Install metaboss
echo -e "${YELLOW}[1/6] Checking metaboss installation...${NC}"

if ! command -v metaboss &> /dev/null; then
    echo -e "${RED}✗ metaboss not found${NC}"
    echo ""
    echo -e "${YELLOW}Installing metaboss via cargo...${NC}"

    if ! command -v cargo &> /dev/null; then
        echo -e "${RED}✗ Rust/cargo not installed${NC}"
        echo ""
        echo "Install Rust first:"
        echo "  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
        echo ""
        echo "Then run this script again."
        exit 1
    fi

    cargo install metaboss
    echo -e "${GREEN}✓ metaboss installed${NC}"
else
    VERSION=$(metaboss --version)
    echo -e "${GREEN}✓ metaboss found: $VERSION${NC}"
fi

# Step 2: Get keypair path
echo ""
echo -e "${YELLOW}[2/6] Locating update authority keypair...${NC}"

read -p "Path to your keypair JSON file: " KEYPAIR_PATH

if [ ! -f "$KEYPAIR_PATH" ]; then
    echo -e "${RED}✗ Keypair file not found: $KEYPAIR_PATH${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Keypair found${NC}"

# Step 3: Get image
echo ""
echo -e "${YELLOW}[3/6] Preparing token image...${NC}"

read -p "Path to logo image (PNG/JPG): " IMAGE_PATH

if [ ! -f "$IMAGE_PATH" ]; then
    echo -e "${RED}✗ Image file not found: $IMAGE_PATH${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Image found${NC}"

# Step 4: Get metadata details
echo ""
echo -e "${YELLOW}[4/6] Token metadata details...${NC}"

read -p "Token name (default: KR8TIV): " TOKEN_NAME
TOKEN_NAME=${TOKEN_NAME:-KR8TIV}

read -p "Token symbol (default: KR8TIV): " TOKEN_SYMBOL
TOKEN_SYMBOL=${TOKEN_SYMBOL:-KR8TIV}

read -p "Token description: " TOKEN_DESCRIPTION

read -p "Website URL (optional): " WEBSITE_URL

# Step 5: Upload image to NFT.Storage
echo ""
echo -e "${YELLOW}[5/6] Uploading image to permanent storage...${NC}"

# Check if NFT_STORAGE_API_KEY is set
if [ -z "$NFT_STORAGE_API_KEY" ]; then
    echo -e "${YELLOW}⚠ NFT_STORAGE_API_KEY not set${NC}"
    echo ""
    echo "Get a free API key:"
    echo "  1. Visit https://nft.storage"
    echo "  2. Sign up (free)"
    echo "  3. Create API key"
    echo "  4. Export: export NFT_STORAGE_API_KEY=your_key"
    echo ""
    read -p "Enter your NFT.Storage API key now: " API_KEY
    export NFT_STORAGE_API_KEY="$API_KEY"
fi

echo "Uploading image..."
IMAGE_URL=$(metaboss upload nft-storage --file "$IMAGE_PATH" 2>&1 | tail -1)

if [ -z "$IMAGE_URL" ]; then
    echo -e "${RED}✗ Image upload failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Image uploaded: $IMAGE_URL${NC}"

# Create metadata JSON
echo ""
echo "Creating metadata JSON..."

METADATA_FILE="kr8tiv_metadata.json"

cat > "$METADATA_FILE" <<EOF
{
  "name": "$TOKEN_NAME",
  "symbol": "$TOKEN_SYMBOL",
  "description": "$TOKEN_DESCRIPTION",
  "image": "$IMAGE_URL",
  "external_url": "$WEBSITE_URL",
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
        "uri": "$IMAGE_URL",
        "type": "image/png"
      }
    ],
    "category": "image"
  }
}
EOF

echo -e "${GREEN}✓ Metadata JSON created: $METADATA_FILE${NC}"

# Upload metadata JSON
echo "Uploading metadata JSON..."
METADATA_URL=$(metaboss upload nft-storage --file "$METADATA_FILE" 2>&1 | tail -1)

if [ -z "$METADATA_URL" ]; then
    echo -e "${RED}✗ Metadata upload failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Metadata uploaded: $METADATA_URL${NC}"

# Step 6: Update on-chain
echo ""
echo -e "${YELLOW}[6/6] Updating on-chain metadata...${NC}"
echo ""
echo -e "${BLUE}Review:${NC}"
echo -e "  Name:        $TOKEN_NAME"
echo -e "  Symbol:      $TOKEN_SYMBOL"
echo -e "  Description: $TOKEN_DESCRIPTION"
echo -e "  Image:       $IMAGE_URL"
echo -e "  Metadata:    $METADATA_URL"
echo ""

read -p "Update on-chain metadata? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Cancelled${NC}"
    exit 0
fi

echo ""
echo "Updating URI on-chain..."

metaboss update uri \
    --keypair "$KEYPAIR_PATH" \
    --account "$MINT" \
    --new-uri "$METADATA_URL"

echo -e "${GREEN}✓ Metadata updated successfully!${NC}"

# Option to freeze
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}⚠  FREEZE METADATA (OPTIONAL)${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo "Freezing metadata makes it PERMANENTLY IMMUTABLE."
echo "After freezing:"
echo "  - Name, symbol, image can NEVER be changed"
echo "  - Update authority will be revoked"
echo "  - This is IRREVERSIBLE"
echo ""
echo "Benefits:"
echo "  - Shows commitment to community"
echo "  - Prevents rug pull via metadata changes"
echo "  - Builds trust with holders"
echo ""

read -p "Freeze metadata now? (yes/no): " FREEZE_CONFIRM

if [ "$FREEZE_CONFIRM" == "yes" ]; then
    echo ""
    echo -e "${RED}⚠⚠⚠ FINAL WARNING ⚠⚠⚠${NC}"
    echo -e "${RED}This is PERMANENT and CANNOT BE UNDONE${NC}"
    echo ""
    read -p "Type 'FREEZE' to confirm: " FINAL_CONFIRM

    if [ "$FINAL_CONFIRM" == "FREEZE" ]; then
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
    echo -e "${YELLOW}Skipped freeze - you can freeze later${NC}"
    echo ""
    echo "To freeze later, run:"
    echo "  python scripts/freeze_token_metadata.py \\"
    echo "    --mint $MINT \\"
    echo "    --keypair $KEYPAIR_PATH \\"
    echo "    --execute"
fi

# Final verification
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ COMPLETE${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo "Next steps:"
echo "  1. Verify on Solscan:"
echo "     https://solscan.io/token/$MINT"
echo ""
echo "  2. Check metadata displays correctly"
echo ""
echo "  3. Announce to community:"
echo "     - Token metadata updated"
echo "     - Professional logo added"
if [ "$FREEZE_CONFIRM" == "yes" ] && [ "$FINAL_CONFIRM" == "FREEZE" ]; then
echo "     - Metadata frozen (immutable) ✅"
fi
echo ""
echo "Files created:"
echo "  - $METADATA_FILE (metadata JSON)"
echo ""

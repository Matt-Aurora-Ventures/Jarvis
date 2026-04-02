#!/bin/bash
# ClawdBot Solana Wallet Initialization
# Generates or loads a Solana wallet for each bot

set -e

BOT_NAME="${BOT_NAME:-unknown}"
WALLET_DIR="/root/.clawdbot/solana"
WALLET_FILE="$WALLET_DIR/${BOT_NAME}-keypair.json"
LOG_PREFIX="[solana-wallet:$BOT_NAME]"

log() {
    echo "$LOG_PREFIX $(date '+%H:%M:%S') $1"
}

# Ensure solana CLI is available
check_solana_cli() {
    if ! command -v solana &> /dev/null; then
        log "Installing Solana CLI..."
        sh -c "$(curl -sSfL https://release.solana.com/stable/install)" 2>/dev/null || {
            log "Failed to install Solana CLI"
            return 1
        }
        export PATH="/root/.local/share/solana/install/active_release/bin:$PATH"
    fi
    return 0
}

# Generate or load wallet
init_wallet() {
    mkdir -p "$WALLET_DIR"
    chmod 700 "$WALLET_DIR"

    if [ -f "$WALLET_FILE" ]; then
        log "Loading existing wallet..."
        solana config set --keypair "$WALLET_FILE" 2>/dev/null || true
    else
        log "Generating new wallet for $BOT_NAME..."
        solana-keygen new --outfile "$WALLET_FILE" --no-bip39-passphrase --force 2>/dev/null || {
            log "Failed to generate wallet"
            return 1
        }
        chmod 600 "$WALLET_FILE"
        log "New wallet generated"
    fi

    # Set default RPC
    solana config set --url https://api.mainnet-beta.solana.com 2>/dev/null || true

    # Display wallet address (but not the key)
    local address
    address=$(solana-keygen pubkey "$WALLET_FILE" 2>/dev/null) || {
        log "Failed to read wallet address"
        return 1
    }

    log "Wallet address: $address"

    # Save address to a public file for reference
    echo "$address" > "$WALLET_DIR/${BOT_NAME}-address.txt"

    # Create wallet info JSON (without private key)
    cat > "$WALLET_DIR/${BOT_NAME}-info.json" << EOF
{
    "bot": "$BOT_NAME",
    "address": "$address",
    "network": "mainnet-beta",
    "initialized_at": "$(date -Iseconds)"
}
EOF

    return 0
}

# Get wallet balance
get_balance() {
    if [ ! -f "$WALLET_FILE" ]; then
        echo "0"
        return
    fi

    local balance
    balance=$(solana balance "$WALLET_FILE" 2>/dev/null | awk '{print $1}') || echo "0"
    echo "$balance"
}

# Main
case "${1:-init}" in
    init)
        check_solana_cli || exit 1
        init_wallet
        ;;
    address)
        if [ -f "$WALLET_DIR/${BOT_NAME}-address.txt" ]; then
            cat "$WALLET_DIR/${BOT_NAME}-address.txt"
        else
            check_solana_cli || exit 1
            solana-keygen pubkey "$WALLET_FILE" 2>/dev/null || echo "NO_WALLET"
        fi
        ;;
    balance)
        check_solana_cli || exit 1
        get_balance
        ;;
    info)
        if [ -f "$WALLET_DIR/${BOT_NAME}-info.json" ]; then
            cat "$WALLET_DIR/${BOT_NAME}-info.json"
        else
            echo '{"error": "wallet not initialized"}'
        fi
        ;;
    *)
        echo "Usage: $0 {init|address|balance|info}"
        exit 1
        ;;
esac

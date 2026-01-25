#!/usr/bin/env python3
"""
Find ALL tokens in treasury wallet across both token programs.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Treasury wallet address
TREASURY_WALLET = "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
SOL_MINT = "So11111111111111111111111111111111111111112"


async def get_tokens_for_program(rpc_url: str, program_id: str, program_name: str):
    """Get all tokens for a specific token program."""

    async with httpx.AsyncClient() as client:
        rpc_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                TREASURY_WALLET,
                {"programId": program_id},
                {"encoding": "jsonParsed"}
            ]
        }

        resp = await client.post(rpc_url, json=rpc_request, timeout=30.0)
        rpc_result = resp.json()

    if 'error' in rpc_result:
        logger.error(f"{program_name} error: {rpc_result['error']}")
        return []

    token_accounts = rpc_result.get('result', {}).get('value', [])

    tokens = []
    for account in token_accounts:
        try:
            account_data = account.get('account', {}).get('data', {})
            parsed = account_data.get('parsed', {})
            info = parsed.get('info', {})

            mint = info.get('mint', '')
            token_amount = info.get('tokenAmount', {})
            ui_amount = token_amount.get('uiAmount')
            raw_amount = int(token_amount.get('amount', 0))
            decimals = token_amount.get('decimals', 0)

            # Include all tokens even with tiny/zero amounts
            if mint and mint != SOL_MINT:
                tokens.append({
                    "program": program_name,
                    "mint": mint,
                    "ui_amount": ui_amount,
                    "raw_amount": raw_amount,
                    "decimals": decimals,
                    "account": account.get('pubkey', 'Unknown')
                })

        except Exception as e:
            logger.error(f"Error parsing account: {e}")

    return tokens


async def main():
    """Find all tokens."""

    rpc_url = os.getenv("SOLANA_RPC_URL") or os.getenv("HELIUS_RPC_URL") or "https://api.mainnet-beta.solana.com"

    logger.info(f"🔍 Scanning treasury wallet: {TREASURY_WALLET}")
    logger.info(f"Using RPC: {rpc_url[:50]}...")

    # Get tokens from both programs
    logger.info("\n📊 Checking Token Program...")
    token_program_tokens = await get_tokens_for_program(rpc_url, TOKEN_PROGRAM, "Token")

    logger.info("\n📊 Checking Token-2022 Program...")
    token_2022_tokens = await get_tokens_for_program(rpc_url, TOKEN_2022_PROGRAM, "Token-2022")

    # Combine results
    all_tokens = token_program_tokens + token_2022_tokens

    logger.info(f"\n\n🔍 RESULTS:")
    logger.info(f"━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"Token Program: {len(token_program_tokens)} accounts")
    logger.info(f"Token-2022 Program: {len(token_2022_tokens)} accounts")
    logger.info(f"TOTAL: {len(all_tokens)} token accounts")
    logger.info(f"━━━━━━━━━━━━━━━━━━━━━\n")

    if all_tokens:
        logger.info("📋 Token Details:")
        for i, token in enumerate(all_tokens, 1):
            mint_short = f"{token['mint'][:8]}...{token['mint'][-6:]}"
            ui_amt = token['ui_amount'] if token['ui_amount'] is not None else "null"
            logger.info(f"{i}. [{token['program']}] {mint_short}")
            logger.info(f"   UI Amount: {ui_amt}")
            logger.info(f"   Raw Amount: {token['raw_amount']}")
            logger.info(f"   Decimals: {token['decimals']}")
            logger.info(f"   Account: {token['account'][:8]}...\n")
    else:
        logger.info("No tokens found")


if __name__ == "__main__":
    asyncio.run(main())

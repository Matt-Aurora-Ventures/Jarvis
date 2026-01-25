#!/usr/bin/env python3
"""
Check all token balances in treasury wallet using RPC.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from spl.token.instructions import get_associated_token_address
from telegram import Bot
from telegram.constants import ParseMode

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Treasury wallet address from WALLET_FIX_SUCCESS.md
TREASURY_WALLET = "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR"

# Well-known SPL Token Program
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")


async def get_all_token_accounts():
    """Query all SPL token accounts for treasury wallet."""

    # Try to get RPC URL from environment or use public endpoint
    rpc_url = os.getenv("SOLANA_RPC_URL") or os.getenv("HELIUS_RPC_URL") or "https://api.mainnet-beta.solana.com"

    logger.info(f"Using RPC: {rpc_url[:50]}...")

    try:
        async with AsyncClient(rpc_url) as client:
            wallet_pubkey = Pubkey.from_string(TREASURY_WALLET)

            # Get SOL balance
            sol_response = await client.get_balance(wallet_pubkey)
            sol_lamports = sol_response.value
            sol_balance = sol_lamports / 1e9

            logger.info(f"SOL Balance: {sol_balance:.4f} SOL")

            # Get all token accounts owned by the wallet using raw RPC
            import httpx

            async with httpx.AsyncClient() as http_client:
                rpc_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTokenAccountsByOwner",
                    "params": [
                        str(wallet_pubkey),
                        {"programId": str(TOKEN_PROGRAM_ID)},
                        {"encoding": "jsonParsed"}
                    ]
                }

                resp = await http_client.post(rpc_url, json=rpc_request)
                rpc_result = resp.json()

            if 'error' in rpc_result:
                raise Exception(f"RPC error: {rpc_result['error']}")

            token_accounts = rpc_result.get('result', {}).get('value', [])
            response_value = token_accounts

            if not response_value:
                logger.info("No SPL token accounts found")
                return {
                    "sol_balance": sol_balance,
                    "tokens": []
                }

            tokens = []
            logger.info(f"\nFound {len(response_value)} token accounts:")

            for account in response_value:
                try:
                    # Parse account data from RPC response
                    account_data = account.get('account', {}).get('data', {})
                    parsed = account_data.get('parsed', {})
                    info = parsed.get('info', {})

                    mint = info.get('mint', 'Unknown')
                    token_amount = info.get('tokenAmount', {})
                    amount = float(token_amount.get('uiAmount', 0) or 0)
                    decimals = token_amount.get('decimals', 0)

                    if amount > 0:  # Only include non-zero balances
                        token_info = {
                            "account": account.get('pubkey', 'Unknown'),
                            "mint": mint,
                            "balance": amount,
                            "decimals": decimals
                        }
                        tokens.append(token_info)
                        logger.info(f"  {mint[:8]}... = {amount:.4f} tokens")

                except Exception as e:
                    logger.error(f"Error parsing token account: {e}", exc_info=True)

            return {
                "sol_balance": sol_balance,
                "tokens": tokens,
                "token_count": len(tokens)
            }

    except Exception as e:
        logger.error(f"RPC error: {e}", exc_info=True)
        raise


async def main():
    """Main function."""
    logger.info(f"🔍 Checking treasury wallet: {TREASURY_WALLET}")

    result = await get_all_token_accounts()

    tokens_text = ""
    if result.get('tokens'):
        tokens_text = "\n\n*Alt Tokens:*\n"
        for token in result['tokens']:
            mint_short = f"{token['mint'][:8]}...{token['mint'][-6:]}"
            tokens_text += f"├ `{mint_short}`: {token['balance']:.4f}\n"

    message = f"""
🔍 *TREASURY WALLET SCAN*
━━━━━━━━━━━━━━━━━━━━━

*Wallet:* `{TREASURY_WALLET[:8]}...{TREASURY_WALLET[-6:]}`

💰 *SOL Balance:* {result['sol_balance']:.4f} SOL

📊 *SPL Token Accounts:* {result.get('token_count', 0)} total
{tokens_text}
━━━━━━━━━━━━━━━━━━━━━
"""

    logger.info(f"\n{message}")

    # Send to Telegram
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_BROADCAST_CHAT_ID") or os.getenv("TELEGRAM_BUY_BOT_CHAT_ID")

        if bot_token and chat_id:
            bot = Bot(token=bot_token)
            await bot.send_message(
                chat_id=int(chat_id),
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info("✅ Sent to Telegram")
    except Exception as e:
        logger.error(f"Failed to send to Telegram: {e}")

    return result


if __name__ == "__main__":
    asyncio.run(main())

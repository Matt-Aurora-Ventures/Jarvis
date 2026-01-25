#!/usr/bin/env python3
"""
Liquidate all altcoin positions to SOL using Jupiter.
Swaps all SPL tokens in treasury wallet to wrapped SOL.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.treasury.jupiter import JupiterClient
from core.security.key_manager import KeyManager
from telegram import Bot
from telegram.constants import ParseMode
import httpx
from solders.keypair import Keypair
from dataclasses import dataclass

@dataclass
class TreasuryWallet:
    """Simple wrapper to make keypair compatible with Jupiter swap execution."""
    address: str
    keypair: Keypair

class SimpleWalletWrapper:
    """Wrapper to make raw keypair compatible with SecureWallet interface."""
    def __init__(self, keypair: Keypair):
        self.keypair = keypair
        self._treasury = TreasuryWallet(
            address=str(keypair.pubkey()),
            keypair=keypair
        )

    def get_treasury(self):
        """Return treasury wallet info."""
        return self._treasury

    def sign_transaction(self, address: str, tx_bytes: bytes) -> bytes:
        """Sign a transaction (correct method for VersionedTransaction)."""
        from solders.transaction import VersionedTransaction
        from solders.message import to_bytes_versioned

        versioned = VersionedTransaction.from_bytes(tx_bytes)
        # Sign message using to_bytes_versioned (correct way for VersionedTransaction)
        message_bytes = to_bytes_versioned(versioned.message)
        signature = self.keypair.sign_message(message_bytes)
        # Replace placeholder signature
        sigs = list(versioned.signatures)
        sigs[0] = signature
        versioned.signatures = sigs
        return bytes(versioned)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Treasury wallet address
TREASURY_WALLET = "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
SOL_MINT = "So11111111111111111111111111111111111111112"


async def get_token_accounts_for_program(rpc_url: str, program_id: str) -> List[Dict[str, Any]]:
    """Get token accounts for a specific program."""

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
        raise Exception(f"RPC error: {rpc_result['error']}")

    return rpc_result.get('result', {}).get('value', [])


async def get_token_accounts(rpc_url: str) -> List[Dict[str, Any]]:
    """Get all SPL token accounts with balances from both Token and Token-2022 programs."""

    # Get tokens from both programs
    token_accounts = await get_token_accounts_for_program(rpc_url, TOKEN_PROGRAM_ID)
    token_2022_accounts = await get_token_accounts_for_program(rpc_url, TOKEN_2022_PROGRAM_ID)

    # Combine all accounts
    all_accounts = token_accounts + token_2022_accounts
    logger.info(f"Found {len(token_accounts)} Token accounts and {len(token_2022_accounts)} Token-2022 accounts")

    tokens = []
    for account in all_accounts:
        try:
            account_data = account.get('account', {}).get('data', {})
            parsed = account_data.get('parsed', {})
            info = parsed.get('info', {})

            mint = info.get('mint', '')
            token_amount = info.get('tokenAmount', {})
            amount = float(token_amount.get('uiAmount', 0) or 0)
            decimals = token_amount.get('decimals', 0)

            # Include all non-SOL tokens (even with 0 UI amount - check raw amount)
            raw_amount = int(token_amount.get('amount', 0))
            if mint != SOL_MINT and raw_amount > 0:
                tokens.append({
                    "mint": mint,
                    "balance": amount,
                    "decimals": decimals,
                    "raw_amount": raw_amount
                })

        except Exception as e:
            logger.error(f"Error parsing token account: {e}")

    return tokens


async def liquidate_all():
    """Liquidate all altcoins to SOL."""

    logger.info("🔴 Starting full treasury liquidation to SOL...")

    try:
        # Get RPC URL
        rpc_url = os.getenv("SOLANA_RPC_URL") or os.getenv("HELIUS_RPC_URL") or "https://api.mainnet-beta.solana.com"

        # Get treasury keypair and wrap it for Jupiter compatibility
        key_mgr = KeyManager()
        raw_keypair = key_mgr.load_treasury_keypair()
        wallet = SimpleWalletWrapper(raw_keypair)

        # Initialize Jupiter client
        jupiter = JupiterClient(rpc_url=rpc_url)

        # Get all token accounts
        tokens = await get_token_accounts(rpc_url)

        if not tokens:
            logger.info("No altcoin positions to liquidate")
            message = """
🔴 *TREASURY LIQUIDATION*
━━━━━━━━━━━━━━━━━━━━━

*Result:* No altcoin positions found
*Status:* ✅ Already 100% SOL

━━━━━━━━━━━━━━━━━━━━━
"""
            await send_telegram(message)
            return

        logger.info(f"Found {len(tokens)} altcoin positions to liquidate")

        # Track results
        swapped_count = 0
        failed_count = 0
        total_sol_received = 0.0
        results = []

        # Swap each token to SOL
        for token in tokens:
            mint = token['mint']
            balance = token['balance']
            raw_amount = token['raw_amount']

            mint_short = f"{mint[:8]}...{mint[-6:]}"
            logger.info(f"Swapping {balance:.4f} of {mint_short} to SOL...")

            try:
                # Get quote for swap to SOL
                quote = await jupiter.get_quote(
                    input_mint=mint,
                    output_mint=SOL_MINT,
                    amount=raw_amount,
                    slippage_bps=100  # 1% slippage tolerance
                )

                if not quote:
                    failed_count += 1
                    results.append(f"❌ {mint_short}: No route found")
                    logger.error(f"No route found for {mint_short}")
                    continue

                # Get expected SOL output
                output_amount = float(quote.output_amount) / 1e9
                logger.info(f"Expected output: {output_amount:.4f} SOL")

                # Execute swap
                result = await jupiter.execute_swap(quote, wallet)

                if result.success:
                    swapped_count += 1
                    total_sol_received += output_amount
                    results.append(f"✅ {mint_short}: {balance:.4f} → {output_amount:.4f} SOL")
                    logger.info(f"✅ Swapped {mint_short}: TX {result.signature}")
                else:
                    failed_count += 1
                    error_msg = result.error[:50] if result.error else "Swap failed"
                    results.append(f"❌ {mint_short}: {error_msg}")
                    logger.error(f"❌ Swap failed for {mint_short}: {result.error}")

            except Exception as e:
                failed_count += 1
                error_msg = str(e)[:50]
                results.append(f"❌ {mint_short}: {error_msg}")
                logger.error(f"Error swapping {mint_short}: {e}", exc_info=True)

        # Close Jupiter client
        await jupiter.close()

        # Escape markdown in results
        def escape_md(text: str) -> str:
            """Escape markdown special characters."""
            chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in chars:
                text = text.replace(char, f'\\{char}')
            return text

        # Prepare summary message
        escaped_results = [escape_md(r) for r in results[:15]]
        result_lines = "\n".join(escaped_results)
        if len(results) > 15:
            result_lines += f"\n_...and {len(results) - 15} more_"

        message = f"""
🔴 *TREASURY LIQUIDATION COMPLETE*
━━━━━━━━━━━━━━━━━━━━━

*Total Positions:* {len(tokens)}
*Successfully Swapped:* {swapped_count} ✅
*Failed:* {failed_count} ❌

💰 *Total SOL Received:* {total_sol_received:.4f} SOL

*Results:*
{result_lines}

━━━━━━━━━━━━━━━━━━━━━
*Treasury Status:* 100% SOL
"""

        logger.info(f"Liquidation complete: {swapped_count} swapped, {failed_count} failed")
        await send_telegram(message)

    except Exception as e:
        logger.error(f"Fatal error during liquidation: {e}", exc_info=True)

        error_message = f"""
🔴 *TREASURY LIQUIDATION ERROR*
━━━━━━━━━━━━━━━━━━━━━

*Error:* {str(e)[:100]}

Please check logs for details.
"""
        await send_telegram(error_message)
        raise


async def send_telegram(message: str):
    """Send notification to Telegram group."""

    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_BROADCAST_CHAT_ID") or os.getenv("TELEGRAM_BUY_BOT_CHAT_ID")

        if not bot_token or not chat_id:
            logger.error("Telegram credentials not found")
            return

        bot = Bot(token=bot_token)
        await bot.send_message(
            chat_id=int(chat_id),
            text=message,
            parse_mode=ParseMode.MARKDOWN
        )

        logger.info("✅ Telegram notification sent")

    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(liquidate_all())

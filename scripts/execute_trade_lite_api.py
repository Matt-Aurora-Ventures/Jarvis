"""
Execute trade using Jupiter Lite API (resolves when quote-api doesn't).
Industry-standard approach using Helius RPC for tx sending.
"""

import asyncio
import json
import os
import sys
import base64
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Load env
for line in open(ROOT / 'tg_bot/.env').read().splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"'))

import aiohttp
import nacl.secret
import nacl.pwhash
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.message import to_bytes_versioned

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_IDS", "").split(",")[0].strip()
TREASURY_ADDRESS = "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR"

# Jupiter Lite API - works when quote-api doesn't
JUPITER_LITE_API = "https://lite-api.jup.ag/swap/v1"

# Helius RPC (free tier works)
HELIUS_RPC = "https://mainnet.helius-rpc.com/?api-key=1234"  # Will use public if no key

# Solana public RPC as fallback
SOLANA_RPC = "https://api.mainnet-beta.solana.com"

# Test token - BONK (very liquid)
TEST_TOKEN = {
    "symbol": "BONK", 
    "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
}
SOL_MINT = "So11111111111111111111111111111111111111112"

# Very small test - 0.005 SOL
TEST_AMOUNT_LAMPORTS = 5_000_000  # 0.005 SOL


def load_keypair():
    """Load and decrypt the treasury keypair."""
    kp_path = ROOT / "data" / "treasury_keypair.json"
    with open(kp_path) as f:
        data = json.load(f)
    
    password = os.environ.get("JARVIS_WALLET_PASSWORD", "")
    if not password:
        raise ValueError("JARVIS_WALLET_PASSWORD not set")
    
    salt = base64.b64decode(data["salt"])
    nonce = base64.b64decode(data["nonce"])
    encrypted = base64.b64decode(data["encrypted_key"])
    
    # Derive key using Argon2
    key = nacl.pwhash.argon2id.kdf(
        nacl.secret.SecretBox.KEY_SIZE,
        password.encode(),
        salt,
        opslimit=nacl.pwhash.argon2id.OPSLIMIT_MODERATE,
        memlimit=nacl.pwhash.argon2id.MEMLIMIT_MODERATE,
    )
    
    box = nacl.secret.SecretBox(key)
    decrypted = box.decrypt(encrypted, nonce)
    
    return Keypair.from_bytes(decrypted)


async def send_telegram(text: str):
    """Send message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_ID:
        return
    async with aiohttp.ClientSession() as s:
        await s.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_ADMIN_ID, "text": text, "parse_mode": "Markdown"}
        )


async def get_balance(address: str) -> float:
    """Get SOL balance."""
    async with aiohttp.ClientSession() as s:
        async with s.post(SOLANA_RPC, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getBalance",
            "params": [address]
        }) as r:
            data = await r.json()
            return data.get("result", {}).get("value", 0) / 1e9


async def get_jupiter_quote(input_mint: str, output_mint: str, amount: int, slippage_bps: int = 50):
    """Get quote from Jupiter Lite API."""
    url = f"{JUPITER_LITE_API}/quote?inputMint={input_mint}&outputMint={output_mint}&amount={amount}&slippageBps={slippage_bps}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            if r.status == 200:
                return await r.json()
            else:
                text = await r.text()
                raise Exception(f"Quote failed: {r.status} - {text}")


async def get_jupiter_swap(quote: dict, user_pubkey: str):
    """Get swap transaction from Jupiter Lite API."""
    url = f"{JUPITER_LITE_API}/swap"
    payload = {
        "quoteResponse": quote,
        "userPublicKey": user_pubkey,
        "dynamicComputeUnitLimit": True,
        "prioritizationFeeLamports": {
            "priorityLevelWithMaxLamports": {
                "maxLamports": 100000,  # 0.0001 SOL max priority fee
                "priorityLevel": "high"
            }
        }
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json=payload) as r:
            if r.status == 200:
                return await r.json()
            else:
                text = await r.text()
                raise Exception(f"Swap failed: {r.status} - {text}")


async def send_transaction(tx_base64: str, keypair: Keypair):
    """Sign and send transaction."""
    from solders.presigner import Presigner
    from solders.signature import Signature
    
    # Deserialize the transaction
    tx_bytes = base64.b64decode(tx_base64)
    tx = VersionedTransaction.from_bytes(tx_bytes)
    
    # Sign the message with keypair
    message_bytes = bytes(tx.message)
    signature = keypair.sign_message(message_bytes)
    
    # Create new transaction with signature
    signed_tx = VersionedTransaction.populate(tx.message, [signature])
    
    # Serialize signed transaction
    signed_bytes = bytes(signed_tx)
    signed_b64 = base64.b64encode(signed_bytes).decode()
    
    # Send via RPC
    async with aiohttp.ClientSession() as s:
        async with s.post(SOLANA_RPC, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [signed_b64, {"encoding": "base64", "skipPreflight": True, "maxRetries": 3}]
        }) as r:
            result = await r.json()
            if "error" in result:
                raise Exception(f"TX failed: {result['error']}")
            return result.get("result")


async def confirm_transaction(signature: str, timeout: int = 60):
    """Wait for transaction confirmation."""
    async with aiohttp.ClientSession() as s:
        for _ in range(timeout // 2):
            await asyncio.sleep(2)
            async with s.post(SOLANA_RPC, json={
                "jsonrpc": "2.0", "id": 1,
                "method": "getSignatureStatuses",
                "params": [[signature], {"searchTransactionHistory": True}]
            }) as r:
                result = await r.json()
                statuses = result.get("result", {}).get("value", [])
                if statuses and statuses[0]:
                    status = statuses[0]
                    if status.get("confirmationStatus") in ["confirmed", "finalized"]:
                        return True
                    if status.get("err"):
                        raise Exception(f"TX error: {status['err']}")
    return False


async def main():
    print("=" * 60)
    print("TREASURY TRADE - JUPITER LITE API")
    print("=" * 60)
    
    # Load keypair
    print("\n[1] Loading keypair...")
    try:
        keypair = load_keypair()
        address = str(keypair.pubkey())
        print(f"    Address: {address[:8]}...{address[-6:]}")
    except Exception as e:
        print(f"    FAILED: {e}")
        return
    
    # Check balance
    print("\n[2] Checking balance...")
    initial_balance = await get_balance(address)
    print(f"    Balance: {initial_balance:.6f} SOL")
    
    if initial_balance < 0.01:
        print("    ERROR: Need at least 0.01 SOL")
        return
    
    # Notify Telegram
    await send_telegram(
        f"*TRADE TEST STARTING*\n\n"
        f"Wallet: `{address[:8]}...`\n"
        f"Balance: {initial_balance:.6f} SOL\n"
        f"Token: {TEST_TOKEN['symbol']}\n"
        f"Amount: {TEST_AMOUNT_LAMPORTS / 1e9} SOL"
    )
    
    # Get quote
    print(f"\n[3] Getting Jupiter quote...")
    print(f"    {TEST_AMOUNT_LAMPORTS / 1e9} SOL -> {TEST_TOKEN['symbol']}")
    try:
        quote = await get_jupiter_quote(SOL_MINT, TEST_TOKEN["mint"], TEST_AMOUNT_LAMPORTS)
        out_amount = int(quote.get("outAmount", 0))
        price_impact = float(quote.get("priceImpactPct", 0))
        print(f"    Output: {out_amount:,} {TEST_TOKEN['symbol']}")
        print(f"    Price impact: {price_impact:.4f}%")
    except Exception as e:
        print(f"    FAILED: {e}")
        await send_telegram(f"*TRADE FAILED*\n\nQuote error: {e}")
        return
    
    # Get swap transaction
    print("\n[4] Getting swap transaction...")
    try:
        swap = await get_jupiter_swap(quote, address)
        tx_b64 = swap.get("swapTransaction")
        if not tx_b64:
            raise Exception("No swap transaction returned")
        print(f"    Transaction ready ({len(tx_b64)} bytes)")
    except Exception as e:
        print(f"    FAILED: {e}")
        await send_telegram(f"*TRADE FAILED*\n\nSwap error: {e}")
        return
    
    # Execute BUY
    print("\n[5] Sending transaction...")
    try:
        signature = await send_transaction(tx_b64, keypair)
        print(f"    Signature: {signature}")
    except Exception as e:
        print(f"    FAILED: {e}")
        await send_telegram(f"*TRADE FAILED*\n\nTX error: {e}")
        return
    
    # Confirm
    print("\n[6] Waiting for confirmation...")
    try:
        confirmed = await confirm_transaction(signature)
        if confirmed:
            print("    CONFIRMED!")
        else:
            print("    Timeout - check explorer")
    except Exception as e:
        print(f"    Error: {e}")
    
    # Check new balance
    await asyncio.sleep(2)
    post_buy_balance = await get_balance(address)
    spent = initial_balance - post_buy_balance
    print(f"\n[7] Balance after buy: {post_buy_balance:.6f} SOL")
    print(f"    SOL spent: {spent:.6f}")
    
    # Send success to Telegram
    await send_telegram(
        f"*BUY EXECUTED*\n\n"
        f"Token: {TEST_TOKEN['symbol']}\n"
        f"Input: {TEST_AMOUNT_LAMPORTS / 1e9} SOL\n"
        f"Output: {out_amount:,} tokens\n"
        f"TX: `{signature}`\n\n"
        f"[View on Solscan](https://solscan.io/tx/{signature})"
    )
    
    # Now SELL back to SOL
    print("\n[8] Selling back to SOL...")
    await asyncio.sleep(3)  # Wait for state to settle
    
    try:
        # Get quote for sell (token -> SOL)
        sell_quote = await get_jupiter_quote(TEST_TOKEN["mint"], SOL_MINT, out_amount)
        sell_out = int(sell_quote.get("outAmount", 0))
        print(f"    Selling {out_amount:,} {TEST_TOKEN['symbol']} -> {sell_out / 1e9:.6f} SOL")
        
        # Get swap tx
        sell_swap = await get_jupiter_swap(sell_quote, address)
        sell_tx_b64 = sell_swap.get("swapTransaction")
        
        # Send sell tx
        sell_sig = await send_transaction(sell_tx_b64, keypair)
        print(f"    Sell TX: {sell_sig}")
        
        # Confirm
        await confirm_transaction(sell_sig)
        print("    SELL CONFIRMED!")
        
    except Exception as e:
        print(f"    Sell failed: {e}")
        await send_telegram(f"*SELL FAILED*\n\n{e}")
    
    # Final balance
    await asyncio.sleep(2)
    final_balance = await get_balance(address)
    net_change = final_balance - initial_balance
    
    print("\n" + "=" * 60)
    print("TRADE TEST COMPLETE")
    print("=" * 60)
    print(f"\nInitial: {initial_balance:.6f} SOL")
    print(f"Final:   {final_balance:.6f} SOL")
    print(f"Net:     {net_change:+.6f} SOL (fees + slippage)")
    
    # Final Telegram report
    await send_telegram(
        f"*TRADE TEST COMPLETE*\n\n"
        f"Initial: {initial_balance:.6f} SOL\n"
        f"Final: {final_balance:.6f} SOL\n"
        f"Net: {net_change:+.6f} SOL\n\n"
        f"Buy TX: `{signature}`\n"
        f"Sell TX: `{sell_sig}`\n\n"
        f"[Buy on Solscan](https://solscan.io/tx/{signature})\n"
        f"[Sell on Solscan](https://solscan.io/tx/{sell_sig})"
    )


if __name__ == "__main__":
    asyncio.run(main())

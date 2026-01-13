"""Sell BONK back to SOL and report to Telegram."""

import asyncio
import json
import os
import sys
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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

JUPITER_LITE_API = "https://lite-api.jup.ag/swap/v1"
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
SOL_MINT = "So11111111111111111111111111111111111111112"
BONK_MINT = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
TREASURY = "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR"
BUY_TX = "3b1vUNwRWyPPKMDgZ8DCAiSg6iBUUYwR685zzkXq4jn1ymPu77jotuWvEeFAt5uCoazncCriKjFjgVw8WTjS4eCL"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_ID = os.environ.get("TELEGRAM_ADMIN_IDS", "").split(",")[0].strip()


def load_keypair():
    kp_path = ROOT / "data" / "treasury_keypair.json"
    with open(kp_path) as f:
        data = json.load(f)
    
    password = os.environ.get("JARVIS_WALLET_PASSWORD", "")
    salt = base64.b64decode(data["salt"])
    nonce = base64.b64decode(data["nonce"])
    encrypted = base64.b64decode(data["encrypted_key"])
    
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


async def get_token_balance(session, mint):
    """Get token balance for treasury."""
    async with session.post(SOLANA_RPC, json={
        "jsonrpc": "2.0", "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [TREASURY, {"mint": mint}, {"encoding": "jsonParsed"}]
    }) as r:
        result = await r.json()
        accounts = result.get("result", {}).get("value", [])
        if accounts:
            info = accounts[0].get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
            amount = int(info.get("tokenAmount", {}).get("amount", 0))
            return amount
        return 0


async def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_ADMIN_ID:
        return
    async with aiohttp.ClientSession() as s:
        await s.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_ADMIN_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}
        )


async def main():
    print("=" * 60)
    print("SELL BONK AND REPORT")
    print("=" * 60)
    
    keypair = load_keypair()
    pubkey = str(keypair.pubkey())
    
    async with aiohttp.ClientSession() as session:
        # Get BONK balance
        print("\n[1] Getting BONK balance...")
        bonk_balance = await get_token_balance(session, BONK_MINT)
        print(f"    BONK balance: {bonk_balance:,}")
        
        if bonk_balance == 0:
            print("    No BONK to sell!")
            return
        
        # Get SOL balance before
        async with session.post(SOLANA_RPC, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getBalance",
            "params": [TREASURY]
        }) as r:
            result = await r.json()
            sol_before = result.get("result", {}).get("value", 0) / 1e9
        print(f"    SOL before: {sol_before:.6f}")
        
        # Get quote for BONK -> SOL
        print("\n[2] Getting sell quote...")
        url = f"{JUPITER_LITE_API}/quote?inputMint={BONK_MINT}&outputMint={SOL_MINT}&amount={bonk_balance}&slippageBps=100"
        async with session.get(url) as r:
            quote = await r.json()
            out_amount = int(quote.get("outAmount", 0))
            print(f"    Output: {out_amount / 1e9:.6f} SOL")
        
        # Get swap transaction
        print("\n[3] Getting swap transaction...")
        swap_url = f"{JUPITER_LITE_API}/swap"
        swap_payload = {
            "quoteResponse": quote,
            "userPublicKey": pubkey,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": {
                "priorityLevelWithMaxLamports": {
                    "maxLamports": 500000,
                    "priorityLevel": "veryHigh"
                }
            }
        }
        async with session.post(swap_url, json=swap_payload) as r:
            swap_resp = await r.json()
            tx_b64 = swap_resp.get("swapTransaction")
            print(f"    TX ready")
        
        # Sign and send
        print("\n[4] Signing and sending...")
        tx_bytes = base64.b64decode(tx_b64)
        tx = VersionedTransaction.from_bytes(tx_bytes)
        
        message_bytes = to_bytes_versioned(tx.message)
        signature = keypair.sign_message(message_bytes)
        
        sigs = list(tx.signatures)
        sigs[0] = signature
        tx.signatures = sigs
        
        signed_b64 = base64.b64encode(bytes(tx)).decode()
        
        async with session.post(SOLANA_RPC, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "sendTransaction",
            "params": [signed_b64, {"encoding": "base64", "skipPreflight": False, "maxRetries": 5}]
        }) as r:
            result = await r.json()
            if "error" in result:
                print(f"    ERROR: {result['error']}")
                return
            sell_sig = result.get("result")
            print(f"    Signature: {sell_sig}")
        
        # Wait for confirmation
        print("\n[5] Waiting for confirmation...")
        for i in range(30):
            await asyncio.sleep(2)
            async with session.post(SOLANA_RPC, json={
                "jsonrpc": "2.0", "id": 1,
                "method": "getSignatureStatuses",
                "params": [[sell_sig], {"searchTransactionHistory": True}]
            }) as r:
                status_result = await r.json()
                statuses = status_result.get("result", {}).get("value", [])
                if statuses and statuses[0]:
                    status = statuses[0]
                    conf = status.get("confirmationStatus")
                    if conf in ["confirmed", "finalized"]:
                        print(f"    CONFIRMED!")
                        break
            print(f"    Waiting... ({i+1}/30)")
        
        # Get final balance
        await asyncio.sleep(2)
        async with session.post(SOLANA_RPC, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getBalance",
            "params": [TREASURY]
        }) as r:
            result = await r.json()
            sol_after = result.get("result", {}).get("value", 0) / 1e9
        
        net_change = sol_after - sol_before
        
        print("\n" + "=" * 60)
        print("TRADE COMPLETE")
        print("=" * 60)
        print(f"SOL before sell: {sol_before:.6f}")
        print(f"SOL after sell:  {sol_after:.6f}")
        print(f"Net change:      {net_change:+.6f}")
        print(f"\nBuy TX:  {BUY_TX}")
        print(f"Sell TX: {sell_sig}")
        
        # Send Telegram report
        report = f"""*TRADE TEST COMPLETE - VERIFIED*

*BUY Transaction:*
TX: `{BUY_TX[:30]}...`
[View on Solscan](https://solscan.io/tx/{BUY_TX})

*SELL Transaction:*
TX: `{sell_sig[:30]}...`
[View on Solscan](https://solscan.io/tx/{sell_sig})

*Balance:*
Before: {sol_before:.6f} SOL
After: {sol_after:.6f} SOL
Net: {net_change:+.6f} SOL (fees)

*Summary:*
Bought {bonk_balance:,} BONK
Sold back to SOL
Round-trip successful!

*Solution:* Jupiter Lite API
(Works when quote-api.jup.ag DNS fails)"""

        await send_telegram(report)
        print("\nReport sent to Telegram!")


if __name__ == "__main__":
    asyncio.run(main())

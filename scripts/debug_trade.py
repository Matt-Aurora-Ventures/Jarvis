"""Debug trade execution - check signing and transaction structure."""

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
from solders.signature import Signature
from solders.message import to_bytes_versioned

JUPITER_LITE_API = "https://lite-api.jup.ag/swap/v1"
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
SOL_MINT = "So11111111111111111111111111111111111111112"
BONK_MINT = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
TEST_AMOUNT = 5_000_000  # 0.005 SOL


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


async def main():
    print("=" * 60)
    print("DEBUG TRADE EXECUTION")
    print("=" * 60)
    
    # Load keypair
    keypair = load_keypair()
    pubkey = str(keypair.pubkey())
    print(f"\n[1] Keypair loaded: {pubkey}")
    
    async with aiohttp.ClientSession() as session:
        # Get quote
        print("\n[2] Getting quote...")
        url = f"{JUPITER_LITE_API}/quote?inputMint={SOL_MINT}&outputMint={BONK_MINT}&amount={TEST_AMOUNT}&slippageBps=100"
        async with session.get(url) as r:
            quote = await r.json()
            print(f"    Output: {quote.get('outAmount')} BONK")
        
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
            print(f"    TX size: {len(tx_b64)} bytes")
        
        # Decode and inspect transaction
        print("\n[4] Inspecting transaction...")
        tx_bytes = base64.b64decode(tx_b64)
        tx = VersionedTransaction.from_bytes(tx_bytes)
        
        print(f"    Signatures count: {len(tx.signatures)}")
        print(f"    First sig (should be empty): {tx.signatures[0]}")
        
        # Check if the transaction needs our signature
        message = tx.message
        print(f"    Account keys count: {len(message.account_keys)}")
        print(f"    First account (should be signer): {message.account_keys[0]}")
        print(f"    Our pubkey matches: {str(message.account_keys[0]) == pubkey}")
        
        # Sign the message using to_bytes_versioned (correct way)
        print("\n[5] Signing transaction...")
        message_bytes = to_bytes_versioned(message)
        signature = keypair.sign_message(message_bytes)
        print(f"    Signature: {signature}")
        
        # Replace the placeholder signature in place
        sigs = list(tx.signatures)
        sigs[0] = signature
        tx.signatures = sigs
        print(f"    Signed TX signatures: {len(tx.signatures)}")
        
        # Serialize the modified transaction
        signed_bytes = bytes(tx)
        signed_b64 = base64.b64encode(signed_bytes).decode()
        print(f"    Signed TX size: {len(signed_bytes)} bytes")
        
        # Simulate first
        print("\n[6] Simulating transaction...")
        async with session.post(SOLANA_RPC, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "simulateTransaction",
            "params": [signed_b64, {"encoding": "base64", "commitment": "processed"}]
        }) as r:
            sim_result = await r.json()
            sim_value = sim_result.get("result", {}).get("value", {})
            sim_err = sim_value.get("err")
            sim_logs = sim_value.get("logs", [])
            
            if sim_err:
                print(f"    SIMULATION FAILED: {sim_err}")
                for log in sim_logs[-10:]:
                    print(f"    {log}")
                return
            else:
                print("    SIMULATION SUCCESS!")
                print(f"    Units consumed: {sim_value.get('unitsConsumed')}")
        
        # Send for real
        print("\n[7] Sending transaction...")
        async with session.post(SOLANA_RPC, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "sendTransaction",
            "params": [signed_b64, {
                "encoding": "base64",
                "skipPreflight": False,
                "preflightCommitment": "processed",
                "maxRetries": 5
            }]
        }) as r:
            send_result = await r.json()
            print(f"    Result: {json.dumps(send_result, indent=2)}")
            
            if "error" in send_result:
                print(f"    ERROR: {send_result['error']}")
                return
            
            sig = send_result.get("result")
            print(f"    Signature: {sig}")
        
        # Wait for confirmation
        print("\n[8] Waiting for confirmation...")
        for i in range(30):
            await asyncio.sleep(2)
            async with session.post(SOLANA_RPC, json={
                "jsonrpc": "2.0", "id": 1,
                "method": "getSignatureStatuses",
                "params": [[sig], {"searchTransactionHistory": True}]
            }) as r:
                status_result = await r.json()
                statuses = status_result.get("result", {}).get("value", [])
                if statuses and statuses[0]:
                    status = statuses[0]
                    conf = status.get("confirmationStatus")
                    err = status.get("err")
                    print(f"    Status: {conf}, Error: {err}")
                    if conf in ["confirmed", "finalized"]:
                        print("    CONFIRMED!")
                        return sig
                    if err:
                        print(f"    TX FAILED: {err}")
                        return None
            print(f"    Waiting... ({i+1}/30)")
        
        print("    TIMEOUT")
        return None


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Query Treasury Wallet via Helius API
Check transaction history and wallet info for 57w9GUzRwXim3nh13R7WtFbpHzUcyKHTtjcTv8cuFoqN
"""

import json
import requests
import os
from pathlib import Path

# Load environment
env_path = Path(__file__).parent.parent / "tg_bot" / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
NEW_TREASURY = "57w9GUzRwXim3nh13R7WtFbpHzUcyKHTtjcTv8cuFoqN"
OLD_TREASURY = "BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR"

print("=" * 70)
print("TREASURY WALLET BLOCKCHAIN QUERY")
print("=" * 70)
print()

# Get account balance and info
print(f"Querying wallet: {NEW_TREASURY}")
print()

url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# Get balance
balance_req = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getBalance",
    "params": [NEW_TREASURY]
}

resp = requests.post(url, json=balance_req)
balance_data = resp.json()

if "result" in balance_data:
    balance_lamports = balance_data["result"]["value"]
    balance_sol = balance_lamports / 1_000_000_000
    print(f"[BALANCE] {balance_sol:.9f} SOL ({balance_lamports:,} lamports)")
else:
    print(f"[ERROR] Could not fetch balance: {balance_data}")

print()

# Get transaction history
print("Fetching recent transactions...")
print()

# Use getSignaturesForAddress to get recent transactions
sig_req = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getSignaturesForAddress",
    "params": [
        NEW_TREASURY,
        {"limit": 10}
    ]
}

resp = requests.post(url, json=sig_req)
sig_data = resp.json()

if "result" in sig_data and sig_data["result"]:
    signatures = sig_data["result"]
    print(f"Found {len(signatures)} recent transactions:")
    print()

    for i, sig_info in enumerate(signatures, 1):
        signature = sig_info["signature"]
        slot = sig_info["slot"]
        err = sig_info.get("err")
        block_time = sig_info.get("blockTime")

        status = "[FAILED]" if err else "[SUCCESS]"

        from datetime import datetime
        if block_time:
            dt = datetime.fromtimestamp(block_time)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = "Unknown"

        print(f"{i}. {status} | {time_str}")
        print(f"   Signature: {signature}")
        print(f"   Slot: {slot:,}")

        # Get transaction details
        tx_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                signature,
                {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
            ]
        }

        tx_resp = requests.post(url, json=tx_req)
        tx_data = tx_resp.json()

        if "result" in tx_data and tx_data["result"]:
            tx = tx_data["result"]
            meta = tx.get("meta", {})
            message = tx.get("transaction", {}).get("message", {})

            # Get account keys
            account_keys = message.get("accountKeys", [])
            if account_keys:
                accounts_involved = [acc["pubkey"] if isinstance(acc, dict) else acc
                                   for acc in account_keys[:5]]  # First 5 accounts

                # Check if old treasury is involved
                if OLD_TREASURY in accounts_involved:
                    print(f"   [TRANSFER] TRANSFER FROM OLD TREASURY")

                print(f"   Accounts: {', '.join(accounts_involved[:3])}...")

            # Get SOL balance change
            pre_balances = meta.get("preBalances", [])
            post_balances = meta.get("postBalances", [])

            if pre_balances and post_balances:
                # Find the NEW_TREASURY account index
                for idx, acc in enumerate(account_keys):
                    acc_key = acc["pubkey"] if isinstance(acc, dict) else acc
                    if acc_key == NEW_TREASURY:
                        if idx < len(pre_balances) and idx < len(post_balances):
                            pre = pre_balances[idx]
                            post = post_balances[idx]
                            change = (post - pre) / 1_000_000_000
                            if change > 0:
                                print(f"   [+] Received: +{change:.9f} SOL")
                            elif change < 0:
                                print(f"   [-] Sent: {change:.9f} SOL")

        print()

else:
    print("[NO TRANSACTIONS] Wallet has no transaction history")
    print()
    print("This could mean:")
    print("  - Wallet was just created and not yet used")
    print("  - Address might be incorrect")
    print("  - RPC node hasn't indexed this wallet yet")

print()
print("-" * 70)
print()

# Check if old treasury has transactions to new treasury
print(f"Checking if old treasury sent funds to new treasury...")
print()

sig_req_old = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getSignaturesForAddress",
    "params": [
        OLD_TREASURY,
        {"limit": 20}
    ]
}

resp = requests.post(url, json=sig_req_old)
sig_data_old = resp.json()

found_transfer = False

if "result" in sig_data_old and sig_data_old["result"]:
    for sig_info in sig_data_old["result"]:
        signature = sig_info["signature"]

        # Get transaction details
        tx_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                signature,
                {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
            ]
        }

        tx_resp = requests.post(url, json=tx_req)
        tx_data = tx_resp.json()

        if "result" in tx_data and tx_data["result"]:
            tx = tx_data["result"]
            message = tx.get("transaction", {}).get("message", {})
            account_keys = message.get("accountKeys", [])

            # Check if new treasury is in this transaction
            accounts = [acc["pubkey"] if isinstance(acc, dict) else acc for acc in account_keys]
            if NEW_TREASURY in accounts:
                found_transfer = True
                block_time = sig_info.get("blockTime")
                if block_time:
                    from datetime import datetime
                    dt = datetime.fromtimestamp(block_time)
                    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    time_str = "Unknown"

                print(f"[OK] FOUND TRANSFER!")
                print(f"   Signature: {signature}")
                print(f"   Time: {time_str}")
                print(f"   Explorer: https://solscan.io/tx/{signature}")
                print()
                break

if not found_transfer:
    print("[X] No direct transfer found from old to new treasury")
    print()
    print("Possible scenarios:")
    print("  1. Transfer went through an intermediate wallet")
    print("  2. Funds were swapped/traded before sending")
    print("  3. Address is for a different purpose (not treasury)")

print()
print("=" * 70)
print()
print("NEXT STEPS:")
print("  1. Check VPS logs when connection is available")
print("  2. Review Telegram bot commands for wallet generation")
print("  3. Check if you generated this wallet externally (Phantom, etc.)")
print()

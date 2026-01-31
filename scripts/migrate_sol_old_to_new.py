"""Migrate SOL from old treasury keypair backup -> current treasury keypair.

This is used after a rotation if the SOL transfer step failed.

Inputs:
- OLD_KEYPAIR_BACKUP: path to the *encrypted* backup json (NaCl format)
- Uses current data/treasury_keypair.json as the new treasury keypair.

Does NOT print private keys.
"""

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any

import httpx
import nacl.pwhash
import nacl.secret

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.hash import Hash
from solders.message import Message
from solders.transaction import Transaction

ROOT = Path(__file__).resolve().parents[1]
NEW_PATH = ROOT / "data" / "treasury_keypair.json"
OLD_PATH = Path(os.environ.get("OLD_KEYPAIR_BACKUP", "")).expanduser()

SOLANA_RPC = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
FEE_RESERVE_SOL = float(os.getenv("TREASURY_ROTATE_FEE_RESERVE_SOL", "0.01"))


def _load_password() -> str:
    pw = os.getenv("JARVIS_WALLET_PASSWORD") or os.getenv("TREASURY_WALLET_PASSWORD") or os.getenv("WALLET_PASSWORD")
    if not pw:
        raise RuntimeError("Wallet password not found in environment")
    return pw


def load_encrypted_keypair(path: Path) -> Keypair:
    data = json.loads(path.read_text())
    pw = _load_password()

    salt = base64.b64decode(data["salt"])
    nonce = base64.b64decode(data["nonce"])
    encrypted = base64.b64decode(data["encrypted_key"])

    key = nacl.pwhash.argon2id.kdf(
        nacl.secret.SecretBox.KEY_SIZE,
        pw.encode(),
        salt,
        opslimit=nacl.pwhash.argon2id.OPSLIMIT_MODERATE,
        memlimit=nacl.pwhash.argon2id.MEMLIMIT_MODERATE,
    )
    box = nacl.secret.SecretBox(key)
    decrypted = box.decrypt(encrypted, nonce)
    return Keypair.from_bytes(decrypted)


async def rpc(client: httpx.AsyncClient, method: str, params: list) -> Any:
    res = await client.post(SOLANA_RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    out = res.json()
    if "error" in out:
        raise RuntimeError(f"RPC error for {method}: {out['error']}")
    return out.get("result")


async def get_balance_lamports(client: httpx.AsyncClient, addr: str) -> int:
    res = await rpc(client, "getBalance", [addr])
    return int(res.get("value", 0))


async def get_latest_blockhash(client: httpx.AsyncClient) -> Hash:
    res = await rpc(client, "getLatestBlockhash", [])
    bh = res["value"]["blockhash"]
    return Hash.from_string(bh)


async def send_tx(client: httpx.AsyncClient, tx: Transaction) -> str:
    raw = bytes(tx)
    b64 = base64.b64encode(raw).decode()
    res = await rpc(client, "sendTransaction", [b64, {"encoding": "base64", "skipPreflight": False}])
    return str(res)


async def confirm_tx(client: httpx.AsyncClient, sig: str, timeout_s: int = 45) -> bool:
    start = asyncio.get_event_loop().time()
    while True:
        res = await rpc(client, "getSignatureStatuses", [[sig], {"searchTransactionHistory": True}])
        val = (res.get("value") or [None])[0]
        if val and val.get("confirmationStatus") in ("confirmed", "finalized"):
            return True
        if asyncio.get_event_loop().time() - start > timeout_s:
            return False
        await asyncio.sleep(1.5)


async def main() -> None:
    if not OLD_PATH.exists():
        raise SystemExit("Set OLD_KEYPAIR_BACKUP to the backup keypair json path")
    if not NEW_PATH.exists():
        raise SystemExit(f"Missing new keypair file: {NEW_PATH}")

    old_kp = load_encrypted_keypair(OLD_PATH)
    new_kp = load_encrypted_keypair(NEW_PATH)

    old_addr = str(old_kp.pubkey())
    new_addr = str(new_kp.pubkey())

    print(f"Old treasury: {old_addr[:8]}...{old_addr[-6:]}")
    print(f"New treasury: {new_addr[:8]}...{new_addr[-6:]}")

    async with httpx.AsyncClient(timeout=30) as client:
        old_lamports = await get_balance_lamports(client, old_addr)
        reserve = int(FEE_RESERVE_SOL * 1_000_000_000)
        send_lamports = max(0, old_lamports - reserve)

        print(f"Old SOL balance: {old_lamports/1e9:.6f}")
        print(f"To transfer: {send_lamports/1e9:.6f} (reserve {reserve/1e9:.6f})")

        if send_lamports <= 0:
            print("No SOL to transfer.")
            return

        bh = await get_latest_blockhash(client)
        ix = transfer(
            TransferParams(
                from_pubkey=Pubkey.from_string(old_addr),
                to_pubkey=Pubkey.from_string(new_addr),
                lamports=send_lamports,
            )
        )

        msg = Message.new_with_blockhash([ix], Pubkey.from_string(old_addr), bh)
        tx = Transaction.new_unsigned(msg)
        tx.sign([old_kp], bh)

        sig = await send_tx(client, tx)
        ok = await confirm_tx(client, sig)
        print(f"SOL transfer submitted: {sig}")
        print(f"Confirmed: {'yes' if ok else 'no (check manually)'}")


if __name__ == "__main__":
    asyncio.run(main())

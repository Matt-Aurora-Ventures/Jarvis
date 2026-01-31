"""Rotate the Jarvis treasury keypair and migrate SOL balance.

SAFETY:
- Does NOT print or expose any private key material.
- Backs up existing encrypted keypair file before replacing.
- Leaves a small SOL reserve in the old wallet for fees/rent.

This script:
1) Loads current treasury keypair from data/treasury_keypair.json (NaCl encrypted)
2) Generates a new Keypair
3) Encrypts + writes it to data/treasury_keypair.json (after making a timestamped backup)
4) Transfers SOL from old -> new (minus fee reserve)

NOTE: SPL token migration is NOT performed here (we only enumerate token accounts).
"""

import asyncio
import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
KEYPAIR_PATH = ROOT / "data" / "treasury_keypair.json"

SOLANA_RPC = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

# Leave some SOL behind so the old wallet can pay fees if needed.
FEE_RESERVE_SOL = float(os.getenv("TREASURY_ROTATE_FEE_RESERVE_SOL", "0.01"))


def _load_password() -> str:
    pw = os.getenv("JARVIS_WALLET_PASSWORD") or os.getenv("TREASURY_WALLET_PASSWORD") or os.getenv("WALLET_PASSWORD")
    if not pw:
        raise RuntimeError("Wallet password not found in environment (JARVIS_WALLET_PASSWORD / TREASURY_WALLET_PASSWORD)")
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


def encrypt_keypair_bytes(raw: bytes) -> Dict[str, str]:
    pw = _load_password()

    salt = os.urandom(16)
    nonce = os.urandom(nacl.secret.SecretBox.NONCE_SIZE)

    key = nacl.pwhash.argon2id.kdf(
        nacl.secret.SecretBox.KEY_SIZE,
        pw.encode(),
        salt,
        opslimit=nacl.pwhash.argon2id.OPSLIMIT_MODERATE,
        memlimit=nacl.pwhash.argon2id.MEMLIMIT_MODERATE,
    )

    box = nacl.secret.SecretBox(key)
    encrypted = box.encrypt(raw, nonce).ciphertext

    return {
        "salt": base64.b64encode(salt).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "encrypted_key": base64.b64encode(encrypted).decode(),
    }


async def rpc(client: httpx.AsyncClient, method: str, params: list) -> Any:
    res = await client.post(SOLANA_RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    out = res.json()
    if "error" in out:
        raise RuntimeError(f"RPC error for {method}: {out['error']}")
    return out.get("result")


async def get_balance_lamports(client: httpx.AsyncClient, addr: str) -> int:
    res = await rpc(client, "getBalance", [addr])
    return int(res.get("value", 0))


async def list_token_accounts(client: httpx.AsyncClient, owner: str) -> List[Tuple[str, int]]:
    # Returns list of (mint, amount_raw)
    res = await rpc(
        session,
        "getTokenAccountsByOwner",
        [owner, {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"}, {"encoding": "jsonParsed"}],
    )
    vals = res.get("value", []) if isinstance(res, dict) else []
    out: List[Tuple[str, int]] = []
    for v in vals:
        try:
            info = v["account"]["data"]["parsed"]["info"]
            mint = info.get("mint")
            amt = int(info.get("tokenAmount", {}).get("amount", 0))
            if mint and amt > 0:
                out.append((mint, amt))
        except Exception:
            continue
    return out


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
    if not KEYPAIR_PATH.exists():
        raise SystemExit(f"Missing keypair file: {KEYPAIR_PATH}")

    # 1) Load old keypair
    old_kp = load_encrypted_keypair(KEYPAIR_PATH)
    old_addr = str(old_kp.pubkey())

    # 2) Generate new keypair
    new_kp = Keypair()
    new_addr = str(new_kp.pubkey())

    # 3) Backup and write new encrypted keypair (do this BEFORE sending funds so the system switches)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = KEYPAIR_PATH.with_suffix(f".json.bak.{ts}")
    backup_path.write_bytes(KEYPAIR_PATH.read_bytes())

    enc = encrypt_keypair_bytes(bytes(new_kp))
    KEYPAIR_PATH.write_text(json.dumps(enc, indent=2))

    print(f"Rotated treasury keypair file ✅")
    print(f"Old treasury: {old_addr[:8]}...{old_addr[-6:]}")
    print(f"New treasury: {new_addr[:8]}...{new_addr[-6:]}")
    print(f"Backup: {backup_path}")

    async with httpx.AsyncClient(timeout=30) as client:
        # 4) Migrate SOL
        old_lamports = await get_balance_lamports(client, old_addr)
        reserve = int(FEE_RESERVE_SOL * 1_000_000_000)
        send_lamports = max(0, old_lamports - reserve)

        print(f"Old SOL balance: {old_lamports/1e9:.6f}")
        print(f"Fee reserve: {reserve/1e9:.6f}")
        print(f"To transfer: {send_lamports/1e9:.6f}")

        if send_lamports <= 0:
            print("No SOL to transfer (balance <= reserve).")
        else:
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

        # 5) Enumerate SPL token accounts remaining on old wallet
        toks = await list_token_accounts(client, old_addr)
        if toks:
            print(f"WARNING: Old treasury still holds {len(toks)} SPL token balances (not migrated by this script).")
            # Print only mint prefixes (safe)
            for mint, amt in toks[:20]:
                print(f" - {mint[:8]}...{mint[-6:]} : {amt}")
        else:
            print("No SPL token balances detected on old treasury.")


if __name__ == "__main__":
    asyncio.run(main())

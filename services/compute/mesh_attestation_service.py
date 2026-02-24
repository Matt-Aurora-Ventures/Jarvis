"""
On-chain mesh attestation service for Jarvis mesh state hashes.

Supports:
- commit_state_hash() writes
- verify_context() checks
- callback wiring for mesh sync receive path
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_PROGRAM_ID = "Jarv1sMesh111111111111111111111111111111111"


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


class MeshAttestationService:
    def __init__(
        self,
        *,
        enabled: Optional[bool] = None,
        program_id: Optional[str] = None,
        rpc_url: Optional[str] = None,
        keypair_path: Optional[str] = None,
        wallet_password: Optional[str] = None,
        node_endpoint: Optional[str] = None,
        node_stake_lamports: Optional[int] = None,
        commit_on_receive: Optional[bool] = None,
        auto_register_node: Optional[bool] = None,
        executor: Optional[Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
    ):
        self.enabled = (
            _env_flag("JARVIS_USE_MESH_ATTEST", _env_flag("JARVIS_MESH_ATTESTATION_ENABLED", False))
            if enabled is None
            else enabled
        )
        self.program_id = str(program_id or os.environ.get("JARVIS_MESH_PROGRAM_ID", "")).strip() or DEFAULT_PROGRAM_ID
        self.rpc_url = str(rpc_url or os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")).strip()
        self.keypair_path = str(
            keypair_path or os.environ.get("JARVIS_MESH_KEYPAIR_PATH", "") or os.environ.get("TREASURY_WALLET_PATH", "")
        ).strip()
        self.wallet_password = wallet_password if wallet_password is not None else os.environ.get("JARVIS_WALLET_PASSWORD", "")
        self.node_endpoint = str(node_endpoint or os.environ.get("JARVIS_MESH_NODE_ENDPOINT", "")).strip()
        self.node_stake_lamports = int(
            node_stake_lamports
            if node_stake_lamports is not None
            else os.environ.get("JARVIS_MESH_NODE_STAKE_LAMPORTS", "0")
        )
        self.commit_on_receive = (
            _env_flag("JARVIS_MESH_COMMIT_ON_RECEIVE", True) if commit_on_receive is None else commit_on_receive
        )
        self.auto_register_node = (
            _env_flag("JARVIS_MESH_AUTO_REGISTER_NODE", False) if auto_register_node is None else auto_register_node
        )
        self._executor = executor or self._rpc_executor
        self._custom_executor = executor is not None
        self._last_error: Optional[str] = None
        self._last_result: Dict[str, Any] = {}
        self._metrics = {
            "commit_success": 0,
            "commit_failure": 0,
            "verify_success": 0,
            "verify_failure": 0,
            "register_success": 0,
            "register_failure": 0,
            "callback_invocations": 0,
        }

    def _is_configured(self) -> bool:
        if not self.program_id:
            return False
        if self._custom_executor:
            return True
        return bool(self.keypair_path)

    @staticmethod
    def _hex32_to_bytes(hash_hex: str) -> bytes:
        raw = bytes.fromhex(str(hash_hex).strip())
        if len(raw) != 32:
            raise ValueError("state hash must be 32 bytes (64 hex chars)")
        return raw

    @staticmethod
    def _anchor_discriminator(method_name: str) -> bytes:
        return hashlib.sha256(f"global:{method_name}".encode("utf-8")).digest()[:8]

    @staticmethod
    def _decode_keypair_json(path: Path, password: str) -> bytes:
        def _pad_base64(data: str) -> str:
            return data + "=" * (4 - len(data) % 4) if len(data) % 4 else data

        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return bytes(payload)

        if isinstance(payload, dict):
            if "secret_key" in payload and isinstance(payload["secret_key"], list):
                return bytes(payload["secret_key"])
            if "private_key" in payload and isinstance(payload["private_key"], list):
                return bytes(payload["private_key"])

            if {"encrypted_key", "salt", "nonce"}.issubset(payload):
                if not password:
                    raise ValueError("wallet password required for encrypted keypair")
                import nacl.pwhash
                import nacl.secret

                salt = base64.b64decode(_pad_base64(str(payload["salt"])))
                nonce = base64.b64decode(_pad_base64(str(payload["nonce"])))
                encrypted_key = base64.b64decode(_pad_base64(str(payload["encrypted_key"])))

                key = nacl.pwhash.argon2id.kdf(
                    nacl.secret.SecretBox.KEY_SIZE,
                    password.encode(),
                    salt,
                    opslimit=nacl.pwhash.argon2id.OPSLIMIT_MODERATE,
                    memlimit=nacl.pwhash.argon2id.MEMLIMIT_MODERATE,
                )
                box = nacl.secret.SecretBox(key)
                return box.decrypt(encrypted_key, nonce)

        raise ValueError("unsupported keypair format")

    async def _rpc_executor(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from solana.rpc.async_api import AsyncClient
            from solana.rpc.commitment import Confirmed
            from solana.rpc.types import TxOpts
            from solders.hash import Hash
            from solders.instruction import AccountMeta, Instruction
            from solders.keypair import Keypair
            from solders.message import MessageV0
            from solders.pubkey import Pubkey
            from solders.signature import Signature
            from solders.system_program import ID as SYSTEM_PROGRAM_ID
            from solders.transaction import VersionedTransaction
        except Exception as exc:
            return {"ok": False, "error": f"solana_dependencies_missing:{exc}"}

        if not self.keypair_path:
            return {"ok": False, "error": "mesh_keypair_path_missing"}

        path = Path(self.keypair_path)
        if not path.exists():
            return {"ok": False, "error": "mesh_keypair_file_missing"}

        try:
            secret_bytes = self._decode_keypair_json(path, self.wallet_password or "")
            signer = Keypair.from_bytes(secret_bytes)
        except Exception as exc:
            return {"ok": False, "error": f"keypair_load_failed:{exc}"}

        try:
            program_id = Pubkey.from_string(self.program_id)
            authority = signer.pubkey()
            node_registry, _ = Pubkey.find_program_address([b"node", bytes(authority)], program_id)
            state_commitment, _ = Pubkey.find_program_address([b"commitment", bytes(node_registry)], program_id)

            if action == "commit_state_hash":
                state_hash_bytes = payload.get("state_hash_bytes")
                if not isinstance(state_hash_bytes, (bytes, bytearray)) or len(state_hash_bytes) != 32:
                    return {"ok": False, "error": "invalid_state_hash_bytes"}
                keys = [
                    AccountMeta(pubkey=authority, is_signer=True, is_writable=True),
                    AccountMeta(pubkey=node_registry, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=state_commitment, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
                ]
                data = self._anchor_discriminator("commit_state_hash") + bytes(state_hash_bytes)
            elif action == "verify_context":
                state_hash_bytes = payload.get("state_hash_bytes")
                if not isinstance(state_hash_bytes, (bytes, bytearray)) or len(state_hash_bytes) != 32:
                    return {"ok": False, "error": "invalid_state_hash_bytes"}
                keys = [
                    AccountMeta(pubkey=node_registry, is_signer=False, is_writable=False),
                    AccountMeta(pubkey=state_commitment, is_signer=False, is_writable=False),
                ]
                data = self._anchor_discriminator("verify_context") + bytes(state_hash_bytes)
            elif action == "register_node":
                endpoint = str(payload.get("endpoint") or "").strip()
                if not endpoint:
                    return {"ok": False, "error": "node_endpoint_missing"}
                if len(endpoint.encode("utf-8")) > 256:
                    return {"ok": False, "error": "node_endpoint_too_long"}
                stake_lamports = int(payload.get("stake_lamports", 0))
                keys = [
                    AccountMeta(pubkey=authority, is_signer=True, is_writable=True),
                    AccountMeta(pubkey=node_registry, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
                ]
                endpoint_bytes = endpoint.encode("utf-8")
                data = (
                    self._anchor_discriminator("register_node")
                    + len(endpoint_bytes).to_bytes(4, "little")
                    + endpoint_bytes
                    + int(stake_lamports).to_bytes(8, "little", signed=False)
                )
            else:
                return {"ok": False, "error": f"unsupported_action:{action}"}

            ix = Instruction(program_id, data, keys)
            async with AsyncClient(self.rpc_url, commitment=Confirmed) as client:
                latest = await client.get_latest_blockhash(commitment=Confirmed)
                recent_blockhash = latest.value.blockhash if latest.value else Hash.default()
                msg = MessageV0.try_compile(
                    payer=authority,
                    instructions=[ix],
                    address_lookup_table_accounts=[],
                    recent_blockhash=recent_blockhash,
                )
                tx = VersionedTransaction(msg, [signer])
                send_result = await client.send_raw_transaction(
                    bytes(tx),
                    opts=TxOpts(skip_preflight=False, preflight_commitment=Confirmed, max_retries=3),
                )
                signature = str(send_result.value)
                sig_obj = Signature.from_string(signature)

                slot = None
                deadline = time.monotonic() + 60.0
                while time.monotonic() < deadline:
                    statuses = await client.get_signature_statuses([sig_obj], search_transaction_history=True)
                    status = statuses.value[0] if statuses.value else None
                    if status is not None:
                        if status.err is not None:
                            return {"ok": False, "error": f"transaction_failed:{status.err}"}
                        slot = int(status.slot)
                        confirmation_status = str(status.confirmation_status or "").lower()
                        if confirmation_status in {"confirmed", "finalized"}:
                            return {"ok": True, "signature": signature, "slot": slot}
                    await asyncio.sleep(1.0)

                return {"ok": False, "error": "confirmation_timeout", "signature": signature, "slot": slot}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = self._executor(action, payload)
        if inspect.isawaitable(result):
            result = await result
        return result if isinstance(result, dict) else {"ok": False, "error": "invalid_executor_result"}

    async def commit_state_hash(
        self,
        state_hash_hex: str,
        *,
        event_id: Optional[str] = None,
        node_pubkey: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "reason": "mesh_attestation_disabled"}
        if not self._is_configured():
            return {"status": "unconfigured", "reason": "mesh_attestation_config_missing"}

        try:
            state_hash_bytes = self._hex32_to_bytes(state_hash_hex)
        except Exception as exc:
            self._metrics["commit_failure"] += 1
            self._last_error = str(exc)
            return {"status": "failed", "reason": "invalid_hash", "error": str(exc)}

        result = await self._execute(
            "commit_state_hash",
            {
                "state_hash": state_hash_hex,
                "state_hash_bytes": state_hash_bytes,
                "program_id": self.program_id,
                "rpc_url": self.rpc_url,
            },
        )
        if result.get("ok"):
            self._metrics["commit_success"] += 1
            response = {
                "status": "committed",
                "state_hash": state_hash_hex,
                "signature": result.get("signature"),
                "slot": result.get("slot"),
                "event_id": event_id,
                "node_pubkey": node_pubkey,
                "metadata": dict(metadata or {}),
            }
            self._last_result = response
            return response

        self._metrics["commit_failure"] += 1
        self._last_error = str(result.get("error", "unknown_error"))
        response = {
            "status": "failed",
            "reason": "commit_failed",
            "state_hash": state_hash_hex,
            "error": self._last_error,
            "event_id": event_id,
            "node_pubkey": node_pubkey,
            "metadata": dict(metadata or {}),
        }
        self._last_result = response
        return response

    async def verify_context(self, expected_hash_hex: str) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "reason": "mesh_attestation_disabled"}
        if not self._is_configured():
            return {"status": "unconfigured", "reason": "mesh_attestation_config_missing"}

        try:
            state_hash_bytes = self._hex32_to_bytes(expected_hash_hex)
        except Exception as exc:
            self._metrics["verify_failure"] += 1
            self._last_error = str(exc)
            return {"status": "failed", "reason": "invalid_hash", "error": str(exc)}

        result = await self._execute(
            "verify_context",
            {
                "state_hash": expected_hash_hex,
                "state_hash_bytes": state_hash_bytes,
                "program_id": self.program_id,
                "rpc_url": self.rpc_url,
            },
        )
        if result.get("ok"):
            self._metrics["verify_success"] += 1
            response = {
                "status": "verified",
                "state_hash": expected_hash_hex,
                "signature": result.get("signature"),
                "slot": result.get("slot"),
            }
            self._last_result = response
            return response

        self._metrics["verify_failure"] += 1
        self._last_error = str(result.get("error", "unknown_error"))
        response = {
            "status": "failed",
            "reason": "verify_failed",
            "state_hash": expected_hash_hex,
            "error": self._last_error,
        }
        self._last_result = response
        return response

    async def register_node(
        self,
        *,
        endpoint: Optional[str] = None,
        stake_lamports: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "reason": "mesh_attestation_disabled"}
        if not self._is_configured():
            return {"status": "unconfigured", "reason": "mesh_attestation_config_missing"}

        target_endpoint = str(endpoint or self.node_endpoint).strip()
        target_stake = int(self.node_stake_lamports if stake_lamports is None else stake_lamports)
        if not target_endpoint:
            self._metrics["register_failure"] += 1
            return {"status": "failed", "reason": "node_endpoint_missing"}

        result = await self._execute(
            "register_node",
            {
                "endpoint": target_endpoint,
                "stake_lamports": target_stake,
                "program_id": self.program_id,
                "rpc_url": self.rpc_url,
            },
        )
        if result.get("ok"):
            self._metrics["register_success"] += 1
            response = {
                "status": "registered",
                "endpoint": target_endpoint,
                "stake_lamports": target_stake,
                "signature": result.get("signature"),
                "slot": result.get("slot"),
            }
            self._last_result = response
            return response

        self._metrics["register_failure"] += 1
        self._last_error = str(result.get("error", "unknown_error"))
        response = {
            "status": "failed",
            "reason": "register_failed",
            "endpoint": target_endpoint,
            "error": self._last_error,
        }
        self._last_result = response
        return response

    async def on_mesh_hash(
        self,
        state_hash: str,
        envelope: Dict[str, Any],
        validation: Dict[str, Any],
    ) -> Dict[str, Any]:
        self._metrics["callback_invocations"] += 1
        if not self.commit_on_receive:
            return {"status": "skipped", "reason": "commit_on_receive_disabled", "state_hash": state_hash}

        result = await self.commit_state_hash(state_hash)
        if result.get("status") == "failed" and self.auto_register_node:
            await self.register_node()
            result = await self.commit_state_hash(state_hash)
        result["message_id"] = envelope.get("message_id")
        result["validation_reason"] = validation.get("reason")
        return result

    def get_status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "configured": self._is_configured(),
            "program_id": self.program_id,
            "rpc_url": self.rpc_url,
            "keypair_path": self.keypair_path,
            "commit_on_receive": self.commit_on_receive,
            "auto_register_node": self.auto_register_node,
            "last_error": self._last_error,
            "last_result": dict(self._last_result),
            "metrics": dict(self._metrics),
        }


_mesh_attestation_service: Optional[MeshAttestationService] = None


def get_mesh_attestation_service() -> MeshAttestationService:
    global _mesh_attestation_service
    if _mesh_attestation_service is None:
        _mesh_attestation_service = MeshAttestationService()
    return _mesh_attestation_service


__all__ = ["MeshAttestationService", "get_mesh_attestation_service"]

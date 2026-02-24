"""
Nosana decentralized compute client.

Focus:
- Select the cheapest market that meets model VRAM constraints
- Build Ollama-compatible job payloads from templates
- Submit and track jobs on the Nosana API
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional

import requests
from nacl.secret import SecretBox
from nacl.utils import random as nacl_random

logger = logging.getLogger(__name__)

MESH_SYNC_PROTOCOL_VERSION = "1.0"
DEFAULT_SYNC_TTL_SECONDS = 300
MAX_CLOCK_SKEW_SECONDS = 30


class NosanaClient:
    """Thin API client for Nosana job execution."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = "https://api.nosana.io",
        timeout_seconds: int = 20,
    ):
        self.api_key = api_key or os.getenv("NOSANA_API_KEY", "").strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._seen_message_ids: Dict[str, float] = {}
        self._last_job_summary: Dict[str, Any] = {}
        self._last_mesh_event: Dict[str, Any] = {}
        self._last_mesh_validation: Dict[str, Any] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def list_markets(self) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            response = requests.get(
                f"{self.base_url}/v1/market/list",
                headers=self._auth_headers(),
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            markets = payload.get("data", payload if isinstance(payload, list) else [])
            if isinstance(markets, list):
                return [m for m in markets if isinstance(m, dict)]
            return []
        except Exception as exc:
            logger.warning("Nosana market list failed: %s", exc)
            return []

    def select_market(
        self,
        markets: List[Mapping[str, Any]],
        *,
        required_vram_gb: int,
    ) -> Dict[str, Any]:
        """
        Choose the cheapest GPU market that satisfies required_vram_gb.
        """
        eligible = []
        for market in markets:
            vram = float(market.get("gpu_vram_gb", market.get("vram", 0)) or 0)
            if vram < required_vram_gb:
                continue
            price = float(market.get("price_per_hour", market.get("price", 1e9)) or 1e9)
            eligible.append((price, dict(market)))
        if not eligible:
            raise ValueError("No Nosana market satisfies required VRAM")
        eligible.sort(key=lambda item: item[0])
        return eligible[0][1]

    def build_job_payload(
        self,
        *,
        template_path: Path,
        model: str,
        prompt: str,
        extra_input: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Load a JSON template and inject runtime prompt/model values.
        """
        template = json.loads(template_path.read_text(encoding="utf-8"))
        if "input" not in template or not isinstance(template["input"], dict):
            template["input"] = {}

        payload = dict(template)
        payload_input = dict(payload["input"])
        payload_input["model"] = model
        payload_input["prompt"] = prompt
        if extra_input:
            payload_input.update(extra_input)
        payload["input"] = payload_input
        return payload

    def submit_job(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Submit a job payload to Nosana.
        """
        if not self.is_configured:
            raise RuntimeError("NOSANA_API_KEY is not configured")
        response = requests.post(
            f"{self.base_url}/v1/jobs",
            json=dict(payload),
            headers=self._auth_headers(),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"status": "unknown", "raw": data}

    @staticmethod
    def _estimate_required_vram_gb(model: str) -> int:
        lowered = model.lower()
        if "70b" in lowered or "72b" in lowered:
            return 48
        if "34b" in lowered or "32b" in lowered:
            return 32
        if "14b" in lowered or "13b" in lowered:
            return 24
        if "7b" in lowered or "8b" in lowered:
            return 12
        return 8

    def submit_ollama_job(
        self,
        *,
        template_path: Path,
        model: str,
        prompt: str,
        market_id: Optional[str] = None,
        extra_input: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Submit an Ollama workload to Nosana and choose a market automatically.
        """
        selected_market: Optional[Dict[str, Any]] = None
        selected_market_id = market_id
        if not selected_market_id:
            markets = self.list_markets()
            selected_market = self.select_market(
                markets,
                required_vram_gb=self._estimate_required_vram_gb(model),
            )
            selected_market_id = str(
                selected_market.get("id")
                or selected_market.get("market")
                or selected_market.get("market_id")
                or ""
            )

        payload = self.build_job_payload(
            template_path=template_path,
            model=model,
            prompt=prompt,
            extra_input=extra_input,
        )
        if selected_market_id:
            payload["market"] = selected_market_id

        result = self.submit_job(payload)
        result.setdefault("provider", "nosana")
        result["selected_market"] = selected_market
        result["market_id"] = selected_market_id
        self._last_job_summary = {
            "status": result.get("status", "unknown"),
            "job_id": result.get("id") or result.get("job_id"),
            "market_id": selected_market_id,
            "model": model,
            "prompt_preview": str(prompt)[:200],
            "submitted_at": self._utc_now().isoformat(),
        }
        return result

    @staticmethod
    def _decode_sync_key(shared_key_hex: str) -> bytes:
        key = bytes.fromhex(shared_key_hex)
        if len(key) != SecretBox.KEY_SIZE:
            raise ValueError("Sync key must be 32 bytes (64 hex chars)")
        return key

    def encrypt_sync_payload(self, payload: Mapping[str, Any], *, shared_key_hex: str) -> Dict[str, str]:
        """
        Encrypt mesh sync payloads before transport over NATS.
        """
        key = self._decode_sync_key(shared_key_hex)
        box = SecretBox(key)
        nonce = nacl_random(SecretBox.NONCE_SIZE)
        plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        encrypted = box.encrypt(plaintext, nonce)
        return {
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(encrypted.ciphertext).decode("ascii"),
        }

    def decrypt_sync_payload(self, envelope: Mapping[str, str], *, shared_key_hex: str) -> Dict[str, Any]:
        """
        Decrypt mesh sync payload received from NATS.
        """
        key = self._decode_sync_key(shared_key_hex)
        box = SecretBox(key)
        nonce = base64.b64decode(str(envelope["nonce_b64"]))
        ciphertext = base64.b64decode(str(envelope["ciphertext_b64"]))
        plaintext = box.decrypt(ciphertext, nonce)
        decoded = json.loads(plaintext.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("Decoded sync payload must be an object")
        return decoded

    @staticmethod
    def _canonicalize_payload(payload: Any) -> Any:
        """
        Canonicalize payload deterministically for hashing and attestation.
        """
        if isinstance(payload, Mapping):
            return {str(k): NosanaClient._canonicalize_payload(payload[k]) for k in sorted(payload.keys(), key=str)}
        if isinstance(payload, list):
            return [NosanaClient._canonicalize_payload(item) for item in payload]
        return payload

    @staticmethod
    def state_hash(payload: Mapping[str, Any]) -> str:
        """
        Deterministic SHA-256 hash for Solana state attestation.
        """
        canonical_payload = NosanaClient._canonicalize_payload(payload)
        canonical = json.dumps(canonical_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_iso(ts: str) -> datetime:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def build_mesh_sync_envelope(
        self,
        *,
        state_delta: Mapping[str, Any],
        node_pubkey: str,
        shared_key_hex: str,
        prev_state_hash: Optional[str] = None,
        ttl_seconds: int = DEFAULT_SYNC_TTL_SECONDS,
        issued_at: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build encrypted sync packet for NATS + Solana attestation verification.
        """
        issued_dt = self._parse_iso(issued_at) if issued_at else self._utc_now()
        expires_dt = issued_dt + timedelta(seconds=max(1, ttl_seconds))

        digest = self.state_hash(state_delta)
        actual_message_id = message_id or hashlib.sha256(
            f"{node_pubkey}:{digest}:{issued_dt.isoformat()}:{uuid.uuid4().hex}".encode("utf-8")
        ).hexdigest()[:32]
        encrypted = self.encrypt_sync_payload(
            {
                "state_delta": state_delta,
                "state_hash": digest,
                "prev_state_hash": prev_state_hash,
                "message_id": actual_message_id,
            },
            shared_key_hex=shared_key_hex,
        )
        envelope = {
            "protocol_version": MESH_SYNC_PROTOCOL_VERSION,
            "channel": "jarvis.mesh.sync",
            "node_pubkey": node_pubkey,
            "message_id": actual_message_id,
            "issued_at": issued_dt.isoformat(),
            "expires_at": expires_dt.isoformat(),
            "ttl_seconds": int(max(1, ttl_seconds)),
            "state_hash": digest,
            "prev_state_hash": prev_state_hash,
            "encrypted_payload": encrypted,
        }
        self._last_mesh_event = {
            "action": "build_envelope",
            "message_id": actual_message_id,
            "node_pubkey": node_pubkey,
            "issued_at": envelope["issued_at"],
            "expires_at": envelope["expires_at"],
            "state_hash": digest,
            "prev_state_hash": prev_state_hash,
        }
        return envelope

    def _prune_replay_cache(self, now: datetime) -> None:
        cutoff = now.timestamp() - 3600.0
        stale_ids = [message_id for message_id, seen_ts in self._seen_message_ids.items() if seen_ts < cutoff]
        for message_id in stale_ids:
            self._seen_message_ids.pop(message_id, None)

    def validate_mesh_sync_envelope(
        self,
        envelope: Mapping[str, Any],
        *,
        shared_key_hex: str,
        seen_message_ids: Optional[MutableMapping[str, float]] = None,
        now_iso: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate and decrypt sync envelope with replay protection and attestation checks.
        """
        required = (
            "protocol_version",
            "message_id",
            "issued_at",
            "expires_at",
            "state_hash",
            "encrypted_payload",
        )
        for field in required:
            if field not in envelope:
                result = {"valid": False, "reason": f"missing_{field}"}
                self._last_mesh_validation = result
                return result

        if str(envelope.get("protocol_version")) != MESH_SYNC_PROTOCOL_VERSION:
            result = {"valid": False, "reason": "invalid_protocol_version"}
            self._last_mesh_validation = result
            return result

        message_id = str(envelope.get("message_id", "")).strip()
        if not message_id:
            result = {"valid": False, "reason": "missing_message_id"}
            self._last_mesh_validation = result
            return result

        now = self._parse_iso(now_iso) if now_iso else self._utc_now()
        issued_at = self._parse_iso(str(envelope.get("issued_at")))
        expires_at = self._parse_iso(str(envelope.get("expires_at")))

        if (issued_at - now).total_seconds() > MAX_CLOCK_SKEW_SECONDS:
            result = {"valid": False, "reason": "clock_skew"}
            self._last_mesh_validation = result
            return result
        if now > expires_at:
            result = {"valid": False, "reason": "stale_commitment"}
            self._last_mesh_validation = result
            return result

        replay_cache = seen_message_ids if seen_message_ids is not None else self._seen_message_ids
        if message_id in replay_cache:
            result = {"valid": False, "reason": "replay_detected"}
            self._last_mesh_validation = result
            return result

        encrypted_payload = envelope.get("encrypted_payload")
        if not isinstance(encrypted_payload, Mapping):
            result = {"valid": False, "reason": "invalid_encrypted_payload"}
            self._last_mesh_validation = result
            return result

        decrypted = self.decrypt_sync_payload(encrypted_payload, shared_key_hex=shared_key_hex)
        if "state_delta" not in decrypted:
            result = {"valid": False, "reason": "partial_sync_data"}
            self._last_mesh_validation = result
            return result
        if not isinstance(decrypted.get("state_delta"), Mapping):
            result = {"valid": False, "reason": "partial_sync_data"}
            self._last_mesh_validation = result
            return result

        envelope_state_hash = str(envelope.get("state_hash", ""))
        decrypted_state_hash = str(decrypted.get("state_hash", ""))
        if not envelope_state_hash or envelope_state_hash != decrypted_state_hash:
            result = {"valid": False, "reason": "hash_mismatch"}
            self._last_mesh_validation = result
            return result

        expected_hash = self.state_hash(decrypted["state_delta"])
        if expected_hash != envelope_state_hash:
            result = {"valid": False, "reason": "hash_mismatch"}
            self._last_mesh_validation = result
            return result

        envelope_prev_hash = envelope.get("prev_state_hash")
        decrypted_prev_hash = decrypted.get("prev_state_hash")
        if envelope_prev_hash and envelope_prev_hash != decrypted_prev_hash:
            result = {"valid": False, "reason": "prev_hash_mismatch"}
            self._last_mesh_validation = result
            return result

        replay_cache[message_id] = now.timestamp()
        if replay_cache is self._seen_message_ids:
            self._prune_replay_cache(now)

        result = {
            "valid": True,
            "reason": "ok",
            "message_id": message_id,
            "state_hash": envelope_state_hash,
            "state_delta": decrypted["state_delta"],
            "prev_state_hash": envelope_prev_hash,
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        self._last_mesh_validation = result
        return result

    def verify_and_unpack_sync_envelope(
        self,
        envelope: Mapping[str, Any],
        *,
        shared_key_hex: str,
        seen_message_ids: Optional[MutableMapping[str, float]] = None,
        now_iso: Optional[str] = None,
    ) -> Dict[str, Any]:
        validation = self.validate_mesh_sync_envelope(
            envelope,
            shared_key_hex=shared_key_hex,
            seen_message_ids=seen_message_ids,
            now_iso=now_iso,
        )
        if not validation.get("valid"):
            raise ValueError(str(validation.get("reason", "invalid_mesh_envelope")))
        return validation

    async def publish_mesh_sync(
        self,
        envelope: Mapping[str, Any],
        *,
        publish_fn: Any,
    ) -> Dict[str, Any]:
        """
        Publish a mesh envelope through an injected NATS-like publisher.
        """
        subject = str(envelope.get("channel") or "jarvis.mesh.sync")
        body = json.dumps(dict(envelope), separators=(",", ":"), sort_keys=True)
        result = publish_fn(subject, body)
        if inspect.isawaitable(result):
            await result
        self._last_mesh_event = {
            "action": "publish_envelope",
            "subject": subject,
            "message_id": envelope.get("message_id"),
            "state_hash": envelope.get("state_hash"),
            "published_at": self._utc_now().isoformat(),
        }
        return {"subject": subject, "message_id": envelope.get("message_id"), "published": True}

    async def run_heavy_workload(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Async helper for resilient provider integration.
        """
        result = await asyncio.to_thread(self.submit_job, payload)
        self._last_job_summary = {
            "status": result.get("status", "unknown") if isinstance(result, Mapping) else "unknown",
            "job_id": result.get("id") if isinstance(result, Mapping) else None,
            "market_id": result.get("market_id") if isinstance(result, Mapping) else None,
            "model": payload.get("model") if isinstance(payload, Mapping) else None,
            "submitted_at": self._utc_now().isoformat(),
        }
        return result

    def get_runtime_status(self) -> Dict[str, Any]:
        """
        Operator-facing runtime details for AI control plane.
        """
        return {
            "configured": self.is_configured,
            "last_job_summary": dict(self._last_job_summary),
            "last_mesh_event": dict(self._last_mesh_event),
            "last_mesh_validation": dict(self._last_mesh_validation),
            "mesh_protocol": {
                "version": MESH_SYNC_PROTOCOL_VERSION,
                "ttl_seconds_default": DEFAULT_SYNC_TTL_SECONDS,
                "max_clock_skew_seconds": MAX_CLOCK_SKEW_SECONDS,
                "replay_cache_size": len(self._seen_message_ids),
            },
        }


_nosana_client: Optional[NosanaClient] = None


def get_nosana_client() -> NosanaClient:
    global _nosana_client
    if _nosana_client is None:
        _nosana_client = NosanaClient()
    return _nosana_client

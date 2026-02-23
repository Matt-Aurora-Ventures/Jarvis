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
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import requests
from nacl.secret import SecretBox
from nacl.utils import random as nacl_random

logger = logging.getLogger(__name__)


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
    def state_hash(payload: Mapping[str, Any]) -> str:
        """
        Deterministic SHA-256 hash for Solana state attestation.
        """
        canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def build_mesh_sync_envelope(
        self,
        *,
        state_delta: Mapping[str, Any],
        node_pubkey: str,
        shared_key_hex: str,
    ) -> Dict[str, Any]:
        """
        Build encrypted sync packet for NATS and Solana registry verification.
        """
        digest = self.state_hash(state_delta)
        encrypted = self.encrypt_sync_payload(
            {"state_delta": state_delta, "state_hash": digest},
            shared_key_hex=shared_key_hex,
        )
        return {
            "channel": "jarvis.mesh.sync",
            "node_pubkey": node_pubkey,
            "state_hash": digest,
            "encrypted_payload": encrypted,
        }

    async def run_heavy_workload(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Async helper for resilient provider integration.
        """
        return await asyncio.to_thread(self.submit_job, payload)


_nosana_client: Optional[NosanaClient] = None


def get_nosana_client() -> NosanaClient:
    global _nosana_client
    if _nosana_client is None:
        _nosana_client = NosanaClient()
    return _nosana_client

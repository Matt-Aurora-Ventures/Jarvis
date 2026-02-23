"""
Nosana decentralized compute client.

Focus:
- Select the cheapest market that meets model VRAM constraints
- Build Ollama-compatible job payloads from templates
- Submit and track jobs on the Nosana API
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import requests

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


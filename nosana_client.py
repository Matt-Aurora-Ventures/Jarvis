"""Client wrapper for dispatching inference jobs to Nosana."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class NosanaClient:
    def __init__(self, base_url: str = "https://dashboard.nosana.io", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def submit_job(self, job_spec: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/api/jobs", json=job_spec, headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def submit_job_file(self, path: str | Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as handle:
            job_spec = json.load(handle)
        return await self.submit_job(job_spec)

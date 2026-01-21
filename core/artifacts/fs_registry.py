"""Filesystem-backed artifact registry for research outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class ArtifactRecord:
    artifact_type: str
    version: str
    created_at: str
    status: str
    sources: list[str]
    assumptions: list[str]
    risk_notes: list[str]
    payload: Dict[str, Any]


class FilesystemArtifactRegistry:
    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root or Path(__file__).resolve().parents[2] / "artifacts")
        self.root.mkdir(parents=True, exist_ok=True)

    def _run_dir(self, job_type: str, timestamp: Optional[str] = None) -> Path:
        run_stamp = timestamp or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        path = self.root / job_type / run_stamp
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def write_markdown(self, path: Path, content: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def save_artifact(
        self,
        job_type: str,
        artifact: ArtifactRecord,
        timestamp: Optional[str] = None,
    ) -> Path:
        run_dir = self._run_dir(job_type, timestamp=timestamp)
        file_path = run_dir / f"{artifact.artifact_type}.json"
        self.write_json(file_path, {
            "artifact_type": artifact.artifact_type,
            "version": artifact.version,
            "created_at": artifact.created_at,
            "status": artifact.status,
            "sources": artifact.sources,
            "assumptions": artifact.assumptions,
            "risk_notes": artifact.risk_notes,
            "payload": artifact.payload,
        })
        return file_path

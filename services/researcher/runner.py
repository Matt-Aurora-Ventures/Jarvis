"""Research service wrapper for AI-Researcher jobs (stubbed)."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from typing import Any, Dict

from core.artifacts.fs_registry import ArtifactRecord, FilesystemArtifactRegistry
from services.researcher.models import ResearchArtifacts, ResearchMission
from services.researcher.normalize import normalize_output


class ResearchService:
    def __init__(self, registry: FilesystemArtifactRegistry | None = None) -> None:
        self.registry = registry or FilesystemArtifactRegistry()

    def _run_ai_researcher(self, mission: ResearchMission) -> Dict[str, Any]:
        image = os.environ.get("AI_RESEARCHER_DOCKER_IMAGE")
        output_dir = os.environ.get("AI_RESEARCHER_OUTPUT_DIR")
        if image and output_dir:
            command = [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{output_dir}:/output",
                image,
                "--topic",
                mission.topic,
                "--scope",
                mission.scope,
            ]
            subprocess.run(command, check=False)
            return {}

        return {
            "report_markdown": (
                f"# Research Report (Stub)\n\n"
                f"Topic: {mission.topic}\n"
                f"Scope: {mission.scope}\n"
                "Status: INCOMPLETE (AI-Researcher runner not configured).\n"
            ),
            "claims_json": [],
            "change_proposals_json": [],
            "next_questions": ["Configure AI-Researcher runner and rerun job."],
            "citation_list": [],
            "recommendations": [],
            "risk_assessment": "INCOMPLETE: AI-Researcher output not configured.",
        }

    def _persist_artifacts(self, mission: ResearchMission, artifacts: ResearchArtifacts) -> None:
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        base_sources = artifacts.citation_list or []
        assumptions = ["AI-Researcher runner may be stubbed. Verify outputs."]

        self.registry.write_markdown(
            self.registry._run_dir(mission.job_type, timestamp) / "report.md",
            artifacts.report_markdown,
        )

        self.registry.save_artifact(
            mission.job_type,
            ArtifactRecord(
                artifact_type="claim_set",
                version="1.0",
                created_at=timestamp,
                status="INCOMPLETE" if not artifacts.claims_json else "COMPLETE",
                sources=base_sources,
                assumptions=assumptions,
                risk_notes=[artifacts.risk_assessment],
                payload={"claims": artifacts.claims_json},
            ),
            timestamp=timestamp,
        )

        self.registry.save_artifact(
            mission.job_type,
            ArtifactRecord(
                artifact_type="change_proposals",
                version="1.0",
                created_at=timestamp,
                status="PROPOSED" if artifacts.change_proposals_json else "NONE",
                sources=base_sources,
                assumptions=assumptions,
                risk_notes=[artifacts.risk_assessment],
                payload={"proposals": artifacts.change_proposals_json},
            ),
            timestamp=timestamp,
        )

        self.registry.save_artifact(
            mission.job_type,
            ArtifactRecord(
                artifact_type="research_summary",
                version="1.0",
                created_at=timestamp,
                status="COMPLETE",
                sources=base_sources,
                assumptions=assumptions,
                risk_notes=[artifacts.risk_assessment],
                payload={
                    "recommendations": artifacts.recommendations,
                    "next_questions": artifacts.next_questions,
                },
            ),
            timestamp=timestamp,
        )

    def run_finance_research_job(self, mission: ResearchMission) -> ResearchArtifacts:
        raw = self._run_ai_researcher(mission)
        artifacts = normalize_output(raw, mission)
        self._persist_artifacts(mission, artifacts)
        return artifacts

    def run_aiml_upgrade_job(self, mission: ResearchMission) -> ResearchArtifacts:
        raw = self._run_ai_researcher(mission)
        artifacts = normalize_output(raw, mission)
        self._persist_artifacts(mission, artifacts)
        return artifacts

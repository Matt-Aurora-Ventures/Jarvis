"""Normalize AI-Researcher outputs into Jarvis artifact structures."""

from __future__ import annotations

from typing import Any, Dict, List

from services.researcher.models import ResearchArtifacts, ResearchMission


def normalize_output(raw: Dict[str, Any], mission: ResearchMission) -> ResearchArtifacts:
    report_markdown = raw.get("report_markdown") or f"# Research Report\n\nTopic: {mission.topic}\n"
    claims_json = raw.get("claims_json") or []
    change_proposals_json = raw.get("change_proposals_json") or []
    next_questions = raw.get("next_questions") or []
    citation_list = raw.get("citation_list") or []
    recommendations = raw.get("recommendations") or []
    risk_assessment = raw.get("risk_assessment") or "INCOMPLETE: risk assessment missing."

    return ResearchArtifacts(
        report_markdown=report_markdown,
        claims_json=claims_json,
        change_proposals_json=change_proposals_json,
        next_questions=next_questions,
        citation_list=citation_list,
        risk_assessment=risk_assessment,
        recommendations=recommendations,
    )

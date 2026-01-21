"""Models for research missions and artifacts."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ResearchMission:
    topic: str
    job_type: str
    scope: str
    requester: str = "system"
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ResearchArtifacts:
    report_markdown: str
    claims_json: List[Dict[str, Any]]
    change_proposals_json: List[Dict[str, Any]]
    next_questions: List[str]
    citation_list: List[str]
    risk_assessment: str
    recommendations: List[str]

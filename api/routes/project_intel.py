"""
Project intelligence API routes for KR8TIV.

Provides endpoints for:
- Project/task/milestone tracking
- Progress and status snapshots
- Memory/conversation export in multiple formats
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Security, status
from pydantic import BaseModel, Field

from api.auth.key_auth import api_key_header, api_key_query, validate_key
from core.extracted.kr8tiv_memory.conversation_export import (
    ConversationExportFormat,
    ConversationExporter,
    ExportOptions,
)
from core.extracted.kr8tiv_memory.project_tracking import (
    MilestoneType,
    ProjectStatus,
    ProjectTracker,
)

logger = logging.getLogger("jarvis.api.project_intel")

router = APIRouter(prefix="/api/project-intel", tags=["project-intel"])

_trackers: dict[str, ProjectTracker] = {}
_exporters: dict[str, ConversationExporter] = {}
_service_lock = threading.Lock()


def _project_data_dir() -> str:
    return os.getenv("KR8TIV_PROJECT_TRACKING_DIR", "./data/kr8tiv/project_tracking")


def _export_data_dir() -> str:
    return os.getenv("KR8TIV_MEMORY_EXPORT_DIR", "./exports/kr8tiv_memory")


def _tenant_storage_path(base_dir: str, tenant_id: str) -> str:
    # Keep tenant data isolated on disk for safer multi-tenant operation.
    return str(Path(base_dir) / tenant_id)


def _validate_tenant_id(tenant_id: str) -> str:
    tenant = tenant_id.strip()
    if not tenant:
        raise HTTPException(status_code=400, detail="Invalid tenant id")
    if len(tenant) > 64:
        raise HTTPException(status_code=400, detail="Tenant id too long")
    if not all(ch.isalnum() or ch in ("-", "_") for ch in tenant):
        raise HTTPException(status_code=400, detail="Tenant id must be alphanumeric, dash, or underscore")
    return tenant


def _require_api_key_enabled() -> bool:
    return os.getenv("PROJECT_INTEL_REQUIRE_API_KEY", "true").lower() == "true"


def _require_tenant_header() -> bool:
    return os.getenv("PROJECT_INTEL_REQUIRE_TENANT", "false").lower() == "true"


async def require_project_intel_access(
    header_key: Optional[str] = Security(api_key_header),
    query_key: Optional[str] = Security(api_key_query),
) -> Optional[str]:
    if not _require_api_key_enabled():
        return None

    key = header_key or query_key
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide via X-API-Key header or api_key query param",
        )

    if validate_key(key) is None:
        logger.warning("project-intel auth failed: invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    return key


def get_tenant_id(x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID")) -> str:
    if not x_tenant_id:
        if _require_tenant_header():
            raise HTTPException(status_code=400, detail="Missing required X-Tenant-ID header")
        return "default"

    return _validate_tenant_id(x_tenant_id)


def get_project_tracker(tenant_id: str) -> ProjectTracker:
    tracker = _trackers.get(tenant_id)
    if tracker is not None:
        return tracker

    with _service_lock:
        tracker = _trackers.get(tenant_id)
        if tracker is None:
            data_dir = _tenant_storage_path(_project_data_dir(), tenant_id)
            tracker = ProjectTracker(data_dir=data_dir)
            _trackers[tenant_id] = tracker
    return tracker


def get_conversation_exporter(tenant_id: str) -> ConversationExporter:
    exporter = _exporters.get(tenant_id)
    if exporter is not None:
        return exporter

    with _service_lock:
        exporter = _exporters.get(tenant_id)
        if exporter is None:
            output_dir = _tenant_storage_path(_export_data_dir(), tenant_id)
            exporter = ConversationExporter(output_dir=output_dir, instance_id=f"kr8tiv-{tenant_id}")
            _exporters[tenant_id] = exporter
    return exporter


def _resolve_export_output_path(exporter: ConversationExporter, output_path: Optional[str]) -> Optional[str]:
    if not output_path:
        return None

    base = exporter.output_dir.resolve()
    candidate = Path(output_path)
    if candidate.is_absolute():
        raise HTTPException(status_code=400, detail="Absolute output_path is not allowed")

    resolved = (base / candidate).resolve()
    if not resolved.is_relative_to(base):
        raise HTTPException(status_code=400, detail="Invalid output_path outside export directory")

    return str(resolved)


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    status: ProjectStatus = ProjectStatus.ACTIVE
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    priority: int = Field(default=5, ge=0, le=10)
    depends_on: list[str] = Field(default_factory=list)
    due_date: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateMilestoneRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    milestone_type: MilestoneType = MilestoneType.CHECKPOINT
    target_date: Optional[datetime] = None
    criteria: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExportOptionsRequest(BaseModel):
    format: ConversationExportFormat = ConversationExportFormat.MARKDOWN
    include_memories: bool = True
    include_conversations: bool = True
    include_knowledge_graph: bool = True
    include_statistics: bool = True
    include_metadata: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    tags_filter: Optional[list[str]] = None
    topics_filter: Optional[list[str]] = None
    max_memories: int = 100
    max_conversations: int = 500
    truncate_long_content: bool = True
    max_content_length: int = 2000


class ExportRequest(BaseModel):
    options: ExportOptionsRequest = Field(default_factory=ExportOptionsRequest)
    memories: list[dict[str, Any]] = Field(default_factory=list)
    conversations: list[dict[str, Any]] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
    output_path: Optional[str] = Field(default=None, max_length=255)
    return_content: bool = False


def _build_export_options(options: ExportOptionsRequest) -> ExportOptions:
    return ExportOptions(
        format=options.format,
        include_memories=options.include_memories,
        include_conversations=options.include_conversations,
        include_knowledge_graph=options.include_knowledge_graph,
        include_statistics=options.include_statistics,
        include_metadata=options.include_metadata,
        start_date=options.start_date,
        end_date=options.end_date,
        tags_filter=options.tags_filter,
        topics_filter=options.topics_filter,
        max_memories=options.max_memories,
        max_conversations=options.max_conversations,
        truncate_long_content=options.truncate_long_content,
        max_content_length=options.max_content_length,
    )


@router.post("/projects")
async def create_project(
    request: CreateProjectRequest,
    _auth: Optional[str] = Depends(require_project_intel_access),
    tenant_id: str = Depends(get_tenant_id),
):
    tracker = get_project_tracker(tenant_id)
    project = await tracker.create_project(
        name=request.name,
        description=request.description,
        tags=request.tags,
        status=request.status,
        metadata=request.metadata,
    )
    return project.to_dict()


@router.get("/projects")
async def list_projects(
    status: Optional[list[ProjectStatus]] = Query(default=None),
    tags: Optional[list[str]] = Query(default=None),
    _auth: Optional[str] = Depends(require_project_intel_access),
    tenant_id: str = Depends(get_tenant_id),
):
    tracker = get_project_tracker(tenant_id)
    projects = await tracker.list_projects(status_filter=status, tag_filter=tags)
    return {
        "count": len(projects),
        "projects": [p.to_dict() for p in projects],
    }


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    _auth: Optional[str] = Depends(require_project_intel_access),
    tenant_id: str = Depends(get_tenant_id),
):
    tracker = get_project_tracker(tenant_id)
    project = await tracker.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return project.to_dict()


@router.post("/projects/{project_id}/tasks")
async def create_task(
    project_id: str,
    request: CreateTaskRequest,
    _auth: Optional[str] = Depends(require_project_intel_access),
    tenant_id: str = Depends(get_tenant_id),
):
    tracker = get_project_tracker(tenant_id)
    task = await tracker.create_task(
        project_id=project_id,
        title=request.title,
        description=request.description,
        priority=request.priority,
        depends_on=request.depends_on,
        due_date=request.due_date,
        metadata=request.metadata,
    )
    if not task:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return task.to_dict()


@router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: str,
    _auth: Optional[str] = Depends(require_project_intel_access),
    tenant_id: str = Depends(get_tenant_id),
):
    tracker = get_project_tracker(tenant_id)
    task = await tracker.complete_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return task.to_dict()


@router.post("/projects/{project_id}/milestones")
async def create_milestone(
    project_id: str,
    request: CreateMilestoneRequest,
    _auth: Optional[str] = Depends(require_project_intel_access),
    tenant_id: str = Depends(get_tenant_id),
):
    tracker = get_project_tracker(tenant_id)
    milestone = await tracker.create_milestone(
        project_id=project_id,
        title=request.title,
        description=request.description,
        milestone_type=request.milestone_type,
        target_date=request.target_date,
        criteria=request.criteria,
        task_ids=request.task_ids,
        metadata=request.metadata,
    )
    if not milestone:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return milestone.to_dict()


@router.get("/projects/{project_id}/status")
async def get_project_status(
    project_id: str,
    _auth: Optional[str] = Depends(require_project_intel_access),
    tenant_id: str = Depends(get_tenant_id),
):
    tracker = get_project_tracker(tenant_id)
    status = await tracker.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return status


@router.get("/stats")
async def get_stats(
    _auth: Optional[str] = Depends(require_project_intel_access),
    tenant_id: str = Depends(get_tenant_id),
):
    return get_project_tracker(tenant_id).get_stats()


@router.post("/exports")
async def export_memory(
    request: ExportRequest,
    _auth: Optional[str] = Depends(require_project_intel_access),
    tenant_id: str = Depends(get_tenant_id),
):
    exporter = get_conversation_exporter(tenant_id)

    async def _memories():
        return request.memories

    async def _conversations():
        return request.conversations

    async def _entities():
        return request.entities

    async def _relationships():
        return request.relationships

    async def _statistics():
        return request.statistics

    exporter.get_memories_fn = _memories
    exporter.get_conversations_fn = _conversations
    exporter.get_entities_fn = _entities
    exporter.get_relationships_fn = _relationships
    exporter.get_statistics_fn = _statistics

    options = _build_export_options(request.options)

    if request.return_content:
        result = await exporter.export_to_string(options=options)
    else:
        safe_output_path = _resolve_export_output_path(exporter, request.output_path)
        result = await exporter.export(options=options, output_path=safe_output_path)

    payload = result.to_dict()
    if result.content is not None:
        payload["content"] = result.content

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "Export failed")

    return payload

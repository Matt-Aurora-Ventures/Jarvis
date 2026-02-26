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
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

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

_tracker: Optional[ProjectTracker] = None
_exporter: Optional[ConversationExporter] = None


def _project_data_dir() -> str:
    return os.getenv("KR8TIV_PROJECT_TRACKING_DIR", "./data/kr8tiv/project_tracking")


def _export_data_dir() -> str:
    return os.getenv("KR8TIV_MEMORY_EXPORT_DIR", "./exports/kr8tiv_memory")


def get_project_tracker() -> ProjectTracker:
    global _tracker
    if _tracker is None:
        _tracker = ProjectTracker(data_dir=_project_data_dir())
    return _tracker


def get_conversation_exporter() -> ConversationExporter:
    global _exporter
    if _exporter is None:
        _exporter = ConversationExporter(output_dir=_export_data_dir(), instance_id="kr8tiv")
    return _exporter


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
    output_path: Optional[str] = None
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
async def create_project(request: CreateProjectRequest):
    tracker = get_project_tracker()
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
):
    tracker = get_project_tracker()
    projects = await tracker.list_projects(status_filter=status, tag_filter=tags)
    return {
        "count": len(projects),
        "projects": [p.to_dict() for p in projects],
    }


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    tracker = get_project_tracker()
    project = await tracker.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return project.to_dict()


@router.post("/projects/{project_id}/tasks")
async def create_task(project_id: str, request: CreateTaskRequest):
    tracker = get_project_tracker()
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
async def complete_task(task_id: str):
    tracker = get_project_tracker()
    task = await tracker.complete_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return task.to_dict()


@router.post("/projects/{project_id}/milestones")
async def create_milestone(project_id: str, request: CreateMilestoneRequest):
    tracker = get_project_tracker()
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
async def get_project_status(project_id: str):
    tracker = get_project_tracker()
    status = await tracker.get_project_status(project_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return status


@router.get("/stats")
async def get_stats():
    return get_project_tracker().get_stats()


@router.post("/exports")
async def export_memory(request: ExportRequest):
    exporter = get_conversation_exporter()

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
        result = await exporter.export(options=options, output_path=request.output_path)

    payload = result.to_dict()
    if result.content is not None:
        payload["content"] = result.content

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "Export failed")

    return payload

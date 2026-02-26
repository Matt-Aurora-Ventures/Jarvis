from __future__ import annotations

from datetime import datetime

import pytest

from core.extracted.kr8tiv_memory.project_tracking import (
    MilestoneType,
    ProjectStatus,
    ProjectTracker,
    TaskStatus,
)


@pytest.mark.asyncio
async def test_create_project_task_and_milestone_flow(tmp_path):
    tracker = ProjectTracker(data_dir=str(tmp_path))

    project = await tracker.create_project(
        name="Kr8tiv Launch",
        description="Ship first marketplace release",
        status=ProjectStatus.ACTIVE,
    )
    assert project.name == "Kr8tiv Launch"
    assert project.status == ProjectStatus.ACTIVE

    task_a = await tracker.create_task(
        project_id=project.id,
        title="Build API",
        description="Implement premium API endpoints",
    )
    assert task_a is not None
    assert task_a.status == TaskStatus.PENDING

    task_b = await tracker.create_task(
        project_id=project.id,
        title="Integrate Billing",
        description="Wire x402 gate",
        depends_on=[task_a.id],
    )
    assert task_b is not None
    assert task_b.status == TaskStatus.BLOCKED

    await tracker.complete_task(task_a.id)
    task_b_updated = await tracker.get_task(task_b.id)
    assert task_b_updated is not None
    assert task_b_updated.status == TaskStatus.PENDING

    milestone = await tracker.create_milestone(
        project_id=project.id,
        title="MVP",
        description="Minimum launch features done",
        milestone_type=MilestoneType.DELIVERABLE,
        task_ids=[task_a.id, task_b.id],
        target_date=datetime(2026, 3, 1),
    )
    assert milestone is not None
    assert milestone.progress_percentage == 50.0


@pytest.mark.asyncio
async def test_project_tracker_persists_to_disk(tmp_path):
    tracker = ProjectTracker(data_dir=str(tmp_path))
    project = await tracker.create_project(
        name="Persistent Project",
        description="Should survive re-instantiation",
    )

    tracker_reloaded = ProjectTracker(data_dir=str(tmp_path))
    loaded = await tracker_reloaded.get_project(project.id)

    assert loaded is not None
    assert loaded.name == "Persistent Project"


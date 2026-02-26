from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.fastapi_app import create_app
from api.routes import project_intel


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("KR8TIV_PROJECT_TRACKING_DIR", str(tmp_path / "tracking"))
    monkeypatch.setenv("KR8TIV_MEMORY_EXPORT_DIR", str(tmp_path / "exports"))
    project_intel._tracker = None
    project_intel._exporter = None

    app = FastAPI()
    app.include_router(project_intel.router)

    with TestClient(app) as test_client:
        yield test_client

    project_intel._tracker = None
    project_intel._exporter = None


def test_project_task_complete_status_flow(client: TestClient):
    create_project = client.post(
        "/api/project-intel/projects",
        json={
            "name": "KR8TIV Launch",
            "description": "Ship first release",
            "tags": ["launch"],
        },
    )
    assert create_project.status_code == 200
    project = create_project.json()
    project_id = project["id"]

    create_task = client.post(
        f"/api/project-intel/projects/{project_id}/tasks",
        json={
            "title": "Implement API",
            "description": "Expose route endpoints",
            "priority": 7,
            "due_date": datetime(2026, 3, 1).isoformat(),
        },
    )
    assert create_task.status_code == 200
    task = create_task.json()
    assert task["status"] == "pending"

    complete_task = client.post(f"/api/project-intel/tasks/{task['id']}/complete")
    assert complete_task.status_code == 200
    assert complete_task.json()["status"] == "completed"

    status_snapshot = client.get(f"/api/project-intel/projects/{project_id}/status")
    assert status_snapshot.status_code == 200
    payload = status_snapshot.json()
    assert payload["task_stats"]["completed"] == 1
    assert payload["progress_percentage"] == 100.0


def test_export_markdown_content(client: TestClient):
    response = client.post(
        "/api/project-intel/exports",
        json={
            "return_content": True,
            "options": {
                "format": "markdown",
            },
            "memories": [
                {
                    "content": "KR8TIV prioritizes clean API contracts.",
                    "tags": ["api"],
                    "created_at": datetime.now().isoformat(),
                }
            ],
            "conversations": [],
            "statistics": {"total_projects": 1},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "# KR8TIV Memory Export" in payload["content"]
    assert "self-evolving ai companion" not in payload["content"].lower()


def test_route_is_wired_in_app_factory(tmp_path, monkeypatch):
    monkeypatch.setenv("KR8TIV_PROJECT_TRACKING_DIR", str(tmp_path / "tracking"))
    monkeypatch.setenv("KR8TIV_MEMORY_EXPORT_DIR", str(tmp_path / "exports"))
    project_intel._tracker = None
    project_intel._exporter = None

    app = create_app()
    with TestClient(app) as test_client:
        response = test_client.get("/api/project-intel/stats")
        assert response.status_code == 200
        assert "total_projects" in response.json()

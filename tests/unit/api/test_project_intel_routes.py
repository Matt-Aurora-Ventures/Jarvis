from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth.key_auth import register_key
from api.fastapi_app import create_app
from api.routes import project_intel


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("KR8TIV_PROJECT_TRACKING_DIR", str(tmp_path / "tracking"))
    monkeypatch.setenv("KR8TIV_MEMORY_EXPORT_DIR", str(tmp_path / "exports"))
    monkeypatch.setenv("PROJECT_INTEL_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("PROJECT_INTEL_REQUIRE_TENANT", "false")
    register_key("test-project-intel-key", {"name": "pytest"})
    project_intel._trackers.clear()
    project_intel._exporters.clear()

    app = FastAPI()
    app.include_router(project_intel.router)

    with TestClient(app) as test_client:
        yield test_client

    project_intel._trackers.clear()
    project_intel._exporters.clear()


@pytest.fixture
def auth_headers():
    return {"X-API-Key": "test-project-intel-key"}


def test_auth_required(client: TestClient):
    response = client.get("/api/project-intel/stats")
    assert response.status_code == 401


def test_project_task_complete_status_flow(client: TestClient, auth_headers):
    create_project = client.post(
        "/api/project-intel/projects",
        json={
            "name": "KR8TIV Launch",
            "description": "Ship first release",
            "tags": ["launch"],
        },
        headers=auth_headers,
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
        headers=auth_headers,
    )
    assert create_task.status_code == 200
    task = create_task.json()
    assert task["status"] == "pending"

    complete_task = client.post(
        f"/api/project-intel/tasks/{task['id']}/complete",
        headers=auth_headers,
    )
    assert complete_task.status_code == 200
    assert complete_task.json()["status"] == "completed"

    status_snapshot = client.get(
        f"/api/project-intel/projects/{project_id}/status",
        headers=auth_headers,
    )
    assert status_snapshot.status_code == 200
    payload = status_snapshot.json()
    assert payload["task_stats"]["completed"] == 1
    assert payload["progress_percentage"] == 100.0


def test_export_markdown_content(client: TestClient, auth_headers):
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
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "# KR8TIV Memory Export" in payload["content"]
    assert "self-evolving ai companion" not in payload["content"].lower()


def test_export_rejects_path_traversal(client: TestClient, auth_headers):
    traversal = client.post(
        "/api/project-intel/exports",
        json={
            "return_content": False,
            "output_path": "../escape.md",
            "options": {"format": "markdown"},
            "memories": [],
            "conversations": [],
        },
        headers=auth_headers,
    )
    assert traversal.status_code == 400
    assert "output_path" in traversal.json()["detail"]


def test_tenant_isolation(client: TestClient, auth_headers):
    alpha_headers = {**auth_headers, "X-Tenant-ID": "alpha"}
    beta_headers = {**auth_headers, "X-Tenant-ID": "beta"}

    create_project = client.post(
        "/api/project-intel/projects",
        json={"name": "Alpha Build", "description": "tenant alpha"},
        headers=alpha_headers,
    )
    assert create_project.status_code == 200

    alpha_list = client.get("/api/project-intel/projects", headers=alpha_headers)
    beta_list = client.get("/api/project-intel/projects", headers=beta_headers)

    assert alpha_list.status_code == 200
    assert beta_list.status_code == 200
    assert alpha_list.json()["count"] == 1
    assert beta_list.json()["count"] == 0


def test_route_is_wired_in_app_factory(tmp_path, monkeypatch):
    monkeypatch.setenv("KR8TIV_PROJECT_TRACKING_DIR", str(tmp_path / "tracking"))
    monkeypatch.setenv("KR8TIV_MEMORY_EXPORT_DIR", str(tmp_path / "exports"))
    monkeypatch.setenv("PROJECT_INTEL_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("PROJECT_INTEL_REQUIRE_TENANT", "false")
    register_key("test-project-intel-key", {"name": "pytest"})
    project_intel._trackers.clear()
    project_intel._exporters.clear()

    app = create_app()
    with TestClient(app) as test_client:
        response = test_client.get(
            "/api/project-intel/stats",
            headers={"X-API-Key": "test-project-intel-key"},
        )
        assert response.status_code == 200
        assert "total_projects" in response.json()

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


def test_project_lists_tasks_and_milestones(client: TestClient, auth_headers):
    create_project = client.post(
        "/api/project-intel/projects",
        json={"name": "KR8TIV Ops", "description": "ship features"},
        headers=auth_headers,
    )
    assert create_project.status_code == 200
    project_id = create_project.json()["id"]

    create_task = client.post(
        f"/api/project-intel/projects/{project_id}/tasks",
        json={"title": "Wire context", "description": "connect retrieval"},
        headers=auth_headers,
    )
    assert create_task.status_code == 200

    create_milestone = client.post(
        f"/api/project-intel/projects/{project_id}/milestones",
        json={"title": "M1", "description": "first integration"},
        headers=auth_headers,
    )
    assert create_milestone.status_code == 200

    task_list = client.get(f"/api/project-intel/projects/{project_id}/tasks", headers=auth_headers)
    milestone_list = client.get(
        f"/api/project-intel/projects/{project_id}/milestones",
        headers=auth_headers,
    )

    assert task_list.status_code == 200
    assert task_list.json()["count"] == 1
    assert task_list.json()["tasks"][0]["title"] == "Wire context"

    assert milestone_list.status_code == 200
    assert milestone_list.json()["count"] == 1
    assert milestone_list.json()["milestones"][0]["title"] == "M1"


def test_project_links_and_similarity(client: TestClient, auth_headers):
    create_a = client.post(
        "/api/project-intel/projects",
        json={"name": "Alpha", "description": "memory retrieval"},
        headers=auth_headers,
    )
    create_b = client.post(
        "/api/project-intel/projects",
        json={"name": "Beta", "description": "memory retrieval tooling"},
        headers=auth_headers,
    )
    assert create_a.status_code == 200
    assert create_b.status_code == 200
    source_id = create_a.json()["id"]
    target_id = create_b.json()["id"]

    tracker = project_intel.get_project_tracker("default")
    tracker.projects[source_id].embedding = [1.0, 0.0, 0.0]
    tracker.projects[target_id].embedding = [0.9, 0.1, 0.0]

    link = client.post(
        f"/api/project-intel/projects/{source_id}/links/{target_id}",
        json={"link_type": "related_to", "shared_concepts": ["memory", "supermemory"]},
        headers=auth_headers,
    )
    assert link.status_code == 200
    link_payload = link.json()
    assert link_payload["source_project_id"] == source_id
    assert link_payload["target_project_id"] == target_id
    assert link_payload["link_type"] == "related_to"
    assert link_payload["shared_concepts"] == ["memory", "supermemory"]

    similar = client.get(
        f"/api/project-intel/projects/{source_id}/similar?limit=5",
        headers=auth_headers,
    )
    assert similar.status_code == 200
    payload = similar.json()
    assert payload["count"] == 1
    assert payload["projects"][0]["project"]["id"] == target_id
    assert payload["projects"][0]["similarity"] > 0


def test_project_tasks_endpoint_returns_404_for_unknown_project(client: TestClient, auth_headers):
    response = client.get("/api/project-intel/projects/missing/tasks", headers=auth_headers)
    assert response.status_code == 404


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

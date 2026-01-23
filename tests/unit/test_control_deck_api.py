import pytest


def test_control_deck_actions_endpoint():
    pytest.importorskip("flask")
    from web.task_web import app

    client = app.test_client()
    response = client.get("/api/actions")
    assert response.status_code == 200
    payload = response.get_json()
    assert "pending" in payload
    assert "timeline" in payload

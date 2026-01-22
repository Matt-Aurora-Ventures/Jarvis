"""Tests for error tracker deduplication."""

import os


def test_error_tracker_deduplication(tmp_path, monkeypatch):
    # Isolate error DB and log
    monkeypatch.setenv("JARVIS_ERROR_DB", str(tmp_path / "errors.json"))
    monkeypatch.setenv("JARVIS_ERROR_LOG", str(tmp_path / "errors.log"))

    # Reset singleton for test isolation
    import importlib
    module = importlib.import_module("core.logging.error_tracker")
    module.ERROR_DB_PATH = str(tmp_path / "errors.json")
    module.ERROR_LOG_PATH = str(tmp_path / "errors.log")
    module.ErrorTracker._instance = None

    tracker = module.ErrorTracker()
    err = ValueError("boom")

    err_id1 = tracker.track_error(err, context="unit.test", component="unit")
    err_id2 = tracker.track_error(err, context="unit.test", component="unit")

    assert err_id1 == err_id2
    assert tracker.errors[err_id1]["count"] == 2

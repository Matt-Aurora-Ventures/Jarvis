"""Tests for single-instance file lock."""

from pathlib import Path


def test_instance_lock_singleton(tmp_path, monkeypatch):
    from core.utils import instance_lock

    # Redirect lock dir to temp for isolation
    monkeypatch.setattr(instance_lock, "_default_lock_dir", lambda: Path(tmp_path))

    lock1 = instance_lock.acquire_instance_lock("test-token", name="telegram_polling", max_wait_seconds=0)
    assert lock1 is not None

    # Second attempt should fail immediately
    lock2 = instance_lock.acquire_instance_lock("test-token", name="telegram_polling", max_wait_seconds=0)
    assert lock2 is None

    lock1.close()

    # After release, lock should be acquirable again
    lock3 = instance_lock.acquire_instance_lock("test-token", name="telegram_polling", max_wait_seconds=0)
    assert lock3 is not None
    lock3.close()

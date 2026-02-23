"""
Tests for jobs/model_upgrader.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs.model_upgrader import ModelSpec, ModelUpgrader, UpgradeAction


def test_decision_tree_auto_upgrade_when_better_and_same_size():
    current = ModelSpec(
        name="qwen2.5:1.5b",
        size_gb=2.1,
        mmlu=70.0,
        humaneval=40.0,
        math=55.0,
        tokens_per_second=80.0,
    )
    candidate = ModelSpec(
        name="qwen2.6:1.5b",
        size_gb=2.1,
        mmlu=76.0,
        humaneval=45.0,
        math=60.0,
        tokens_per_second=82.0,
    )

    action = ModelUpgrader.decide_upgrade(current, candidate)
    assert action == UpgradeAction.AUTO_UPGRADE


def test_decision_tree_notify_when_better_but_heavier():
    current = ModelSpec(
        name="qwen2.5:1.5b",
        size_gb=2.1,
        mmlu=70.0,
        humaneval=40.0,
        math=55.0,
        tokens_per_second=80.0,
    )
    candidate = ModelSpec(
        name="qwen2.7:7b",
        size_gb=8.2,
        mmlu=80.0,
        humaneval=49.0,
        math=65.0,
        tokens_per_second=70.0,
    )

    action = ModelUpgrader.decide_upgrade(current, candidate)
    assert action == UpgradeAction.NOTIFY_HEAVIER


def test_hot_swap_updates_lifeos_config(tmp_path):
    cfg_path = tmp_path / "lifeos.config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "providers": {"ollama": {"model": "old:model"}},
                "router": {"fast_model": "old:model", "deep_model": "old:model"},
            }
        ),
        encoding="utf-8",
    )

    upgrader = ModelUpgrader(config_path=cfg_path)
    changed = upgrader.hot_swap_local_model("new:model")
    assert changed is True

    updated = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert updated["providers"]["ollama"]["model"] == "new:model"
    assert updated["router"]["fast_model"] == "new:model"
    assert updated["router"]["deep_model"] == "new:model"


def test_weekly_guard_blocks_second_run_same_week(tmp_path):
    state_path = tmp_path / "model_upgrader_state.json"
    state_path.write_text(json.dumps({"last_scan_at": "2026-02-22T03:00:00+00:00"}), encoding="utf-8")

    upgrader = ModelUpgrader(state_path=state_path)
    assert upgrader.should_run_weekly("2026-02-23T03:00:00+00:00") is False


def test_update_arena_panel_replaces_existing_alias(tmp_path):
    arena_path = tmp_path / "arena.py"
    arena_path.write_text(
        "PANEL: Dict[str, str] = {\n"
        '    "claude": "anthropic/old-model",\n'
        '    "gpt": "openai/gpt-old",\n'
        "}\n",
        encoding="utf-8",
    )

    upgrader = ModelUpgrader(arena_path=arena_path)
    changed = upgrader.update_arena_panel({"claude": "anthropic/new-model"})
    assert changed is True

    updated = arena_path.read_text(encoding="utf-8")
    assert '"claude": "anthropic/new-model"' in updated
    assert "old-model" not in updated

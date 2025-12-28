"""Web Control Deck for Jarvis using Flask."""

import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request

# Add the project root to Python path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import (
    config,
    diagnostics,
    jarvis,
    missions,
    research_engine,
    state,
    system_profiler,
    task_manager,
)

RESOURCE_MONITOR_DIR = ROOT / "data" / "resource_monitor"
SECURITY_LOG_PATH = RESOURCE_MONITOR_DIR / "security_log.jsonl"
NETWORK_LOG_PATH = RESOURCE_MONITOR_DIR / "network_log.jsonl"

ALLOWED_CONFIG_PATHS = {
    "actions.allow_ui",
    "actions.require_confirm",
    "observer.enabled",
    "observer.mode",
    "missions.enabled",
    "idle_research.enabled",
    "learn_mode.enabled",
    "process_guard.auto_kill",
    "process_guard.force_kill",
    "network_monitor.enabled",
    "resource_monitor.enabled",
}

app = Flask(__name__)


def _read_jsonl_tail(path: Path, limit: int = 20) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: List[Dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _set_nested_value(data: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cursor = data
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    cursor[parts[-1]] = value


def _load_local_config() -> Dict[str, Any]:
    local_path = config.LOCAL_CONFIG
    if not local_path.exists():
        return {}
    try:
        return json.loads(local_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_local_config(payload: Dict[str, Any]) -> None:
    config.LOCAL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    config.LOCAL_CONFIG.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


@app.route("/")
def index():
    """Main control deck page."""
    tm = task_manager.get_task_manager()
    tasks = tm.list_tasks(limit=50)
    stats = tm.get_stats()
    return render_template("index.html", tasks=tasks, stats=stats)


@app.route("/api/status", methods=["GET"])
def api_status():
    current = state.read_state()
    return jsonify(
        {
            "daemon_running": state.is_running(),
            "voice_status": current.get("mic_status", "off"),
            "chat_active": current.get("chat_active", False),
            "missions_enabled": current.get("missions_enabled", False),
            "observer_enabled": current.get("passive_enabled", False),
            "resource_monitor": current.get("resource_monitor_enabled", False),
            "ui_actions_enabled": current.get("ui_actions_enabled", False),
            "last_update": current.get("updated_at", ""),
        }
    )


@app.route("/api/resources", methods=["GET"])
def api_resources():
    current = state.read_state()
    profile = system_profiler.read_profile()
    return jsonify(
        {
            "cpu_load": current.get("resource_cpu_load", profile.cpu_load),
            "ram_free_gb": current.get("resource_ram_free_gb", profile.ram_free_gb),
            "ram_total_gb": current.get("resource_ram_total_gb", profile.ram_total_gb),
            "disk_free_gb": current.get("resource_disk_free_gb", profile.disk_free_gb),
            "net_rx_mbps": current.get("net_rx_mbps", 0.0),
            "net_tx_mbps": current.get("net_tx_mbps", 0.0),
            "net_packets_per_sec": current.get("net_packets_per_sec", 0.0),
        }
    )


@app.route("/api/security/recent", methods=["GET"])
def api_security_recent():
    recent = _read_jsonl_tail(SECURITY_LOG_PATH, limit=20)
    network = _read_jsonl_tail(NETWORK_LOG_PATH, limit=10)
    return jsonify({"events": recent, "network": network})


@app.route("/api/config", methods=["GET"])
def api_get_config():
    cfg = config.load_config()
    response = {
        "actions": cfg.get("actions", {}),
        "observer": cfg.get("observer", {}),
        "missions": cfg.get("missions", {}),
        "learn_mode": cfg.get("learn_mode", {}),
        "idle_research": cfg.get("idle_research", {}),
        "resource_monitor": cfg.get("resource_monitor", {}),
        "network_monitor": cfg.get("network_monitor", {}),
        "process_guard": cfg.get("process_guard", {}),
    }
    return jsonify(response)


@app.route("/api/config/toggle", methods=["POST"])
def api_toggle_config():
    payload = request.get_json() or {}
    path = payload.get("path", "")
    value = payload.get("value")
    if path not in ALLOWED_CONFIG_PATHS:
        return jsonify({"error": "Path not allowed"}), 400
    local_cfg = _load_local_config()
    _set_nested_value(local_cfg, path, value)
    _save_local_config(local_cfg)
    return jsonify({"success": True, "path": path, "value": value})


@app.route("/api/actions/run", methods=["POST"])
def api_run_action():
    payload = request.get_json() or {}
    action = payload.get("action", "")
    runners = {
        "hyperliquid_snapshot": missions._run_hyperliquid_snapshot,
        "hyperliquid_backtest": missions._run_hyperliquid_backtest,
        "dex_api_scout": missions._run_dex_api_scout,
        "prompt_pack": missions._run_prompt_pack_builder,
        "ai_news": missions._run_ai_news_scan,
        "directive_digest": missions._run_directive_digest,
        "business_suggestions": missions._run_business_suggestions,
        "learn_mode": missions._run_learn_mode,
        "self_tests": jarvis._run_self_tests,
        "diagnostics": diagnostics.run_diagnostics,
    }
    runner = runners.get(action)
    if not runner:
        return jsonify({"error": "Unknown action"}), 400
    try:
        result = runner()
        return jsonify({"success": True, "result": _serialize(result)})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/research", methods=["POST"])
def api_research():
    payload = request.get_json() or {}
    topic = str(payload.get("topic", "")).strip()
    focus = str(payload.get("focus", "")).strip()
    max_pages = int(payload.get("max_pages", 4))
    if not topic:
        return jsonify({"error": "Topic is required"}), 400
    engine = research_engine.get_research_engine()
    result = engine.research_topic(topic, max_pages=max_pages, focus=focus)
    return jsonify(result)


@app.route("/api/tasks", methods=["GET"])
def api_get_tasks():
    """Get all tasks as JSON."""
    tm = task_manager.get_task_manager()
    status_filter = request.args.get("status")
    priority_filter = request.args.get("priority")

    if status_filter:
        status_filter = task_manager.TaskStatus(status_filter)
    if priority_filter:
        priority_filter = task_manager.TaskPriority(priority_filter)

    tasks = tm.list_tasks(status=status_filter, priority=priority_filter, limit=100)

    return jsonify(
        [
            {
                "id": task.id,
                "title": task.title,
                "priority": task.priority.value,
                "status": task.status.value,
                "created_at": task.created_at,
                "completed_at": task.completed_at,
                "created_str": datetime.fromtimestamp(task.created_at).strftime(
                    "%Y-%m-%d %H:%M"
                ),
            }
            for task in tasks
        ]
    )


@app.route("/api/tasks", methods=["POST"])
def api_add_task():
    """Add a new task."""
    data = request.get_json()

    if not data or "title" not in data:
        return jsonify({"error": "Title is required"}), 400

    priority = data.get("priority", "medium")
    priority = task_manager.TaskPriority(priority)

    tm = task_manager.get_task_manager()
    task = tm.add_task(data["title"], priority)

    return (
        jsonify(
            {
                "id": task.id,
                "title": task.title,
                "priority": task.priority.value,
                "status": task.status.value,
                "created_at": task.created_at,
            }
        ),
        201,
    )


@app.route("/api/tasks/<task_id>/start", methods=["POST"])
def api_start_task(task_id):
    """Start a task."""
    tm = task_manager.get_task_manager()

    if tm.start_task(task_id):
        return jsonify({"success": True})
    return jsonify({"error": "Task not found"}), 404


@app.route("/api/tasks/<task_id>/complete", methods=["POST"])
def api_complete_task(task_id):
    """Complete a task."""
    tm = task_manager.get_task_manager()

    if tm.complete_task(task_id):
        return jsonify({"success": True})
    return jsonify({"error": "Task not found"}), 404


@app.route("/api/stats")
def api_get_stats():
    """Get task statistics."""
    tm = task_manager.get_task_manager()
    stats = tm.get_stats()
    return jsonify(stats)


if __name__ == "__main__":
    templates_dir = ROOT / "web" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)

    app.run(host="127.0.0.1", port=5000, debug=True)

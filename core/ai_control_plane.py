"""
AI Control Plane snapshot builder.

Collects consensus/context/upgrader/compute status into a single payload
for operator-facing dashboards.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from core.runtime_capabilities import build_runtime_capability_report
from core.resilient_provider import get_provider_health_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONSENSUS_LOG_PATH = ROOT / "logs" / "consensus_arena.jsonl"
DEFAULT_UPGRADER_STATE_PATH = ROOT / "data" / "model_upgrader_state.json"
PRIMARY_CONFIG_PATH = ROOT / "lifeos" / "config" / "jarvis.json"
LEGACY_CONFIG_PATH = ROOT / "lifeos" / "config" / "lifeos.config.json"


def _safe_read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _last_jsonl_entry(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            return None
        payload = json.loads(lines[-1])
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _resolve_config_path() -> Path:
    if PRIMARY_CONFIG_PATH.exists():
        return PRIMARY_CONFIG_PATH
    return LEGACY_CONFIG_PATH


def _active_local_model() -> str:
    config = _safe_read_json(_resolve_config_path(), {})
    if not isinstance(config, dict):
        return ""

    providers = config.get("providers", {})
    if isinstance(providers, dict):
        ollama = providers.get("ollama", {})
        if isinstance(ollama, dict) and ollama.get("model"):
            return str(ollama.get("model"))

    router = config.get("router", {})
    if isinstance(router, dict):
        if router.get("fast_model"):
            return str(router.get("fast_model"))
    return ""


def _consensus_panel(
    runtime_components: Mapping[str, Any],
    provider_health: Mapping[str, Any],
) -> Dict[str, Any]:
    from core.consensus.arena import PANEL
    from core.consensus.scoring import MODERATE_CONSENSUS_THRESHOLD, STRONG_CONSENSUS_THRESHOLD

    arena_runtime = runtime_components.get("arena", {}) if isinstance(runtime_components, Mapping) else {}
    status = str(arena_runtime.get("status", "unknown"))
    reason = arena_runtime.get("reason")
    fallback = arena_runtime.get("fallback")

    log_path = Path(os.getenv("JARVIS_CONSENSUS_AUDIT_LOG", str(DEFAULT_CONSENSUS_LOG_PATH)))
    last_run = _last_jsonl_entry(log_path)

    explainability = (
        "Consensus arena is ready. Model selection uses weighted scoring, semantic agreement, and confidence signals."
    )
    if status in ("degraded", "disabled"):
        explainability = f"Consensus arena fallback active due to {reason}; route defaults to {fallback}."
    elif isinstance(last_run, dict):
        consensus = last_run.get("consensus", {})
        scoring = last_run.get("scoring", {})
        model = (consensus or {}).get("model")
        tier = (scoring or {}).get("consensus_tier")
        if model:
            explainability = f"Latest synthesis selected `{model}` with consensus tier `{tier or 'unknown'}`."

    return {
        "status": status,
        "reason": reason,
        "fallback": fallback,
        "panel_models": dict(PANEL),
        "thresholds": {
            "strong": STRONG_CONSENSUS_THRESHOLD,
            "moderate": MODERATE_CONSENSUS_THRESHOLD,
        },
        "provider_routes": provider_health.get("routes", {}),
        "latest_run": last_run,
        "explainability": explainability,
    }


def _context_panel(runtime_components: Mapping[str, Any]) -> Dict[str, Any]:
    memory_runtime = (
        runtime_components.get("supermemory_hooks", {}) if isinstance(runtime_components, Mapping) else {}
    )
    status = str(memory_runtime.get("status", "unknown"))
    reason = memory_runtime.get("reason")
    fallback = memory_runtime.get("fallback")

    telemetry: Dict[str, Any] = {}
    try:
        from bots.shared.supermemory_client import get_hook_telemetry

        telemetry = get_hook_telemetry()
    except Exception:
        telemetry = {}

    pre = telemetry.get("pre_recall", {}) if isinstance(telemetry, dict) else {}
    post = telemetry.get("post_response", {}) if isinstance(telemetry, dict) else {}
    static_profile = pre.get("static_profile", []) if isinstance(pre, dict) else []
    dynamic_profile = pre.get("dynamic_profile", []) if isinstance(pre, dict) else []
    recent_injections = post.get("facts_extracted", []) if isinstance(post, dict) else []

    explainability = "Dual-profile memory hooks inject static and dynamic context before each LLM response."
    if status in ("degraded", "disabled"):
        explainability = f"Memory hook fallback active due to {reason}; context injection is bypassed."

    return {
        "status": status,
        "reason": reason,
        "fallback": fallback,
        "static_profile": static_profile,
        "dynamic_profile": dynamic_profile,
        "recent_memory_injections": recent_injections,
        "latest_hook_events": telemetry,
        "explainability": explainability,
    }


def _upgrade_panel(runtime_components: Mapping[str, Any]) -> Dict[str, Any]:
    upgrader_runtime = (
        runtime_components.get("model_upgrader", {}) if isinstance(runtime_components, Mapping) else {}
    )
    status = str(upgrader_runtime.get("status", "unknown"))
    reason = upgrader_runtime.get("reason")
    last_scan_at = upgrader_runtime.get("last_scan_at")
    state_path = Path(str(upgrader_runtime.get("state_file") or DEFAULT_UPGRADER_STATE_PATH))
    state_payload = _safe_read_json(state_path, {})
    if not isinstance(state_payload, dict):
        state_payload = {}

    last_result = state_payload.get("last_result", {})
    if not isinstance(last_result, dict):
        last_result = {}

    explainability = "Weekly upgrader compares benchmark deltas and model size constraints before any hot-swap."
    if status in ("degraded", "disabled"):
        explainability = f"Upgrader attention needed: {reason}."
    elif last_result:
        action = last_result.get("action", "unknown")
        explainability = f"Latest upgrade decision: `{action}`."

    return {
        "status": status,
        "reason": reason,
        "last_scan_at": last_scan_at,
        "active_local_model": _active_local_model(),
        "last_result": last_result,
        "restart_command_configured": bool(os.getenv("JARVIS_RESTART_CMD", "").strip()),
        "explainability": explainability,
    }


def _compute_panel(
    runtime_components: Mapping[str, Any],
    provider_health: Mapping[str, Any],
) -> Dict[str, Any]:
    nosana_runtime = runtime_components.get("nosana", {}) if isinstance(runtime_components, Mapping) else {}
    nosana_status = str(nosana_runtime.get("status", "unknown"))
    nosana_reason = nosana_runtime.get("reason")
    nosana_fallback = nosana_runtime.get("fallback")
    mesh_sync_runtime = runtime_components.get("mesh_sync", {}) if isinstance(runtime_components, Mapping) else {}
    mesh_attestation_runtime = runtime_components.get("mesh_attestation", {}) if isinstance(runtime_components, Mapping) else {}

    nosana_runtime_details: Dict[str, Any] = {}
    mesh_sync_details: Dict[str, Any] = {}
    mesh_attestation_details: Dict[str, Any] = {}
    mesh_protocol = {"version": "1.0", "replay_protection": True, "hash_attestation": "sha256"}
    try:
        from services.compute.nosana_client import get_nosana_client

        nosana_runtime_details = get_nosana_client().get_runtime_status()
        mesh_protocol = nosana_runtime_details.get("mesh_protocol", mesh_protocol)
    except Exception:
        nosana_runtime_details = {}

    try:
        from services.compute.mesh_sync_service import get_mesh_sync_service

        mesh_sync_details = get_mesh_sync_service().get_status()
    except Exception:
        mesh_sync_details = {}

    try:
        from services.compute.mesh_attestation_service import get_mesh_attestation_service

        mesh_attestation_details = get_mesh_attestation_service().get_status()
    except Exception:
        mesh_attestation_details = {}

    explainability = "Heavy workloads route locally unless Nosana is explicitly enabled and configured."
    if nosana_status in ("degraded", "disabled", "unconfigured"):
        explainability = f"Nosana route fallback active due to {nosana_reason}; using local/other providers."

    return {
        "status": nosana_status,
        "reason": nosana_reason,
        "fallback": nosana_fallback,
        "provider_routes": provider_health.get("routes", {}),
        "nosana_runtime": nosana_runtime_details,
        "mesh_sync": {
            "status": str(mesh_sync_runtime.get("status", "unknown")),
            "reason": mesh_sync_runtime.get("reason"),
            "fallback": mesh_sync_runtime.get("fallback"),
            "runtime": mesh_sync_details,
        },
        "mesh_attestation": {
            "status": str(mesh_attestation_runtime.get("status", "unknown")),
            "reason": mesh_attestation_runtime.get("reason"),
            "fallback": mesh_attestation_runtime.get("fallback"),
            "runtime": mesh_attestation_details,
        },
        "mesh_protocol": mesh_protocol,
        "explainability": explainability,
    }


def build_ai_control_plane_snapshot() -> Dict[str, Any]:
    runtime_report = build_runtime_capability_report()
    runtime_components = runtime_report.get("components", {})
    provider_health = get_provider_health_json()

    consensus = _consensus_panel(runtime_components, provider_health)
    context = _context_panel(runtime_components)
    upgrade = _upgrade_panel(runtime_components)
    compute = _compute_panel(runtime_components, provider_health)

    statuses = [consensus.get("status"), context.get("status"), upgrade.get("status"), compute.get("status")]
    if any(s in ("error", "failed") for s in statuses):
        overall = "error"
    elif any(s == "degraded" for s in statuses):
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runtime": runtime_report,
        "panels": {
            "consensus": consensus,
            "context": context,
            "upgrade": upgrade,
            "compute": compute,
        },
    }


__all__ = ["build_ai_control_plane_snapshot"]

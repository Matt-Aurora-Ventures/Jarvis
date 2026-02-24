"""
Runtime capability and degraded-mode reporting for consensus/context features.
"""

from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
MODEL_UPGRADER_STATE_PATH = ROOT / "data" / "model_upgrader_state.json"


def env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _arena_status() -> Dict[str, Any]:
    enabled = env_flag("JARVIS_USE_ARENA", True)
    litellm_ready = module_available("litellm")
    openrouter_key = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())

    if not enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "reason": "flag_disabled",
            "fallback": "local_ollama",
        }
    if not litellm_ready:
        return {
            "enabled": True,
            "status": "degraded",
            "reason": "litellm_missing",
            "fallback": "local_ollama",
        }
    if not openrouter_key:
        return {
            "enabled": True,
            "status": "degraded",
            "reason": "openrouter_api_key_missing",
            "fallback": "local_ollama",
        }
    return {
        "enabled": True,
        "status": "ready",
        "reason": None,
        "fallback": None,
    }


def _supermemory_status() -> Dict[str, Any]:
    enabled = env_flag("JARVIS_SUPERMEMORY_HOOKS", True)
    package_ready = module_available("supermemory")
    api_key_present = bool(os.environ.get("SUPERMEMORY_API_KEY", "").strip())

    if not enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "reason": "hooks_flag_disabled",
            "fallback": "no_context_injection",
        }
    if not package_ready:
        return {
            "enabled": True,
            "status": "degraded",
            "reason": "supermemory_package_missing",
            "fallback": "no_context_injection",
        }
    if not api_key_present:
        return {
            "enabled": True,
            "status": "degraded",
            "reason": "supermemory_api_key_missing",
            "fallback": "no_context_injection",
        }
    return {
        "enabled": True,
        "status": "ready",
        "reason": None,
        "fallback": None,
    }


def _nosana_status() -> Dict[str, Any]:
    enabled = env_flag("JARVIS_USE_NOSANA", False)
    api_key_present = bool(os.environ.get("NOSANA_API_KEY", "").strip())

    if not enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "reason": "flag_disabled",
            "fallback": "skip_heavy_compute_route",
        }
    if not api_key_present:
        return {
            "enabled": True,
            "status": "degraded",
            "reason": "nosana_api_key_missing",
            "fallback": "skip_heavy_compute_route",
        }
    return {
        "enabled": True,
        "status": "ready",
        "reason": None,
        "fallback": None,
    }


def _mesh_sync_status() -> Dict[str, Any]:
    enabled = env_flag("JARVIS_USE_MESH_SYNC", env_flag("JARVIS_MESH_SYNC_ENABLED", False))
    shared_key = bool(
        os.environ.get("JARVIS_MESH_SHARED_KEY", "").strip()
        or os.environ.get("JARVIS_MESH_SYNC_KEY", "").strip()
    )
    node_pubkey = bool(os.environ.get("JARVIS_MESH_NODE_PUBKEY", "").strip())
    nats_ready = module_available("nats")

    if not enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "reason": "flag_disabled",
            "fallback": "mesh_sync_bypassed",
        }
    if not shared_key:
        return {
            "enabled": True,
            "status": "degraded",
            "reason": "mesh_shared_key_missing",
            "fallback": "mesh_sync_bypassed",
        }
    if not node_pubkey:
        return {
            "enabled": True,
            "status": "degraded",
            "reason": "mesh_node_pubkey_missing",
            "fallback": "mesh_sync_bypassed",
        }
    if not nats_ready:
        return {
            "enabled": True,
            "status": "degraded",
            "reason": "nats_client_missing",
            "fallback": "mesh_sync_bypassed",
        }
    return {
        "enabled": True,
        "status": "ready",
        "reason": None,
        "fallback": None,
    }


def _mesh_attestation_status() -> Dict[str, Any]:
    enabled = env_flag("JARVIS_USE_MESH_ATTEST", env_flag("JARVIS_MESH_ATTESTATION_ENABLED", False))
    program_id = bool(os.environ.get("JARVIS_MESH_PROGRAM_ID", "").strip())
    keypair_path = os.environ.get("JARVIS_MESH_KEYPAIR_PATH", "").strip() or os.environ.get("TREASURY_WALLET_PATH", "").strip()
    solana_ready = module_available("solana")
    solders_ready = module_available("solders")

    if not enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "reason": "flag_disabled",
            "fallback": "attestation_bypassed",
        }
    if not program_id:
        return {
            "enabled": True,
            "status": "degraded",
            "reason": "mesh_program_id_missing",
            "fallback": "attestation_bypassed",
        }
    if not keypair_path:
        return {
            "enabled": True,
            "status": "degraded",
            "reason": "mesh_keypair_path_missing",
            "fallback": "attestation_bypassed",
        }
    if not solana_ready or not solders_ready:
        return {
            "enabled": True,
            "status": "degraded",
            "reason": "solana_dependencies_missing",
            "fallback": "attestation_bypassed",
        }
    return {
        "enabled": True,
        "status": "ready",
        "reason": None,
        "fallback": None,
    }


def _model_upgrader_status(state_path: Path = MODEL_UPGRADER_STATE_PATH) -> Dict[str, Any]:
    enabled = env_flag("JARVIS_MODEL_UPGRADER_ENABLED", True)
    state = _read_json(state_path)
    last_scan_at = str(state.get("last_scan_at", "")).strip() or None

    if not enabled:
        status = "disabled"
        reason = "flag_disabled"
    elif last_scan_at:
        status = "ready"
        reason = None
    else:
        status = "degraded"
        reason = "never_scanned"

    return {
        "enabled": enabled,
        "status": status,
        "reason": reason,
        "last_scan_at": last_scan_at,
        "state_file": str(state_path),
    }


def build_runtime_capability_report() -> Dict[str, Any]:
    components = {
        "arena": _arena_status(),
        "supermemory_hooks": _supermemory_status(),
        "nosana": _nosana_status(),
        "mesh_sync": _mesh_sync_status(),
        "mesh_attestation": _mesh_attestation_status(),
        "model_upgrader": _model_upgrader_status(),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "components": components,
    }


def collect_degraded_mode_messages(report: Dict[str, Any]) -> List[str]:
    messages: List[str] = []
    components = report.get("components", {})
    for name, info in components.items():
        if not isinstance(info, dict):
            continue
        status = str(info.get("status", "unknown"))
        if status not in {"degraded", "disabled"}:
            continue
        reason = info.get("reason") or "unspecified"
        fallback = info.get("fallback")
        if fallback:
            messages.append(f"{name}: {status} ({reason}) -> fallback={fallback}")
        else:
            messages.append(f"{name}: {status} ({reason})")
    return messages


__all__ = [
    "MODEL_UPGRADER_STATE_PATH",
    "build_runtime_capability_report",
    "collect_degraded_mode_messages",
    "env_flag",
    "module_available",
]

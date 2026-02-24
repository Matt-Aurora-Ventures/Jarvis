"""
Weekly model upgrader daemon for Jarvis.

Responsibilities:
- Poll local Ollama inventory
- Evaluate candidate model upgrades with deterministic decision tree
- Hot-swap active local model in LifeOS config
- Optionally refresh consensus arena panel from OpenRouter frontier models
- Persist run-state for weekly cadence
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import requests

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = ROOT / "data" / "model_upgrader_state.json"
DEFAULT_ARENA_PATH = ROOT / "core" / "consensus" / "arena.py"
PRIMARY_CONFIG_PATH = ROOT / "lifeos" / "config" / "jarvis.json"
LEGACY_CONFIG_PATH = ROOT / "lifeos" / "config" / "lifeos.config.json"
DEFAULT_CONFIG_CANDIDATES = [
    PRIMARY_CONFIG_PATH,
    LEGACY_CONFIG_PATH,
]


class UpgradeAction(str, Enum):
    """Decision-tree outcomes for model upgrades."""

    AUTO_UPGRADE = "auto_upgrade"
    NOTIFY_HEAVIER = "notify_heavier"
    SKIP = "skip"


@dataclass(frozen=True)
class ModelSpec:
    """Comparable model metadata for upgrade decisions."""

    name: str
    size_gb: float
    mmlu: float
    humaneval: float
    math: float
    tokens_per_second: float = 0.0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ModelSpec":
        return cls(
            name=str(payload.get("name", "")),
            size_gb=float(payload.get("size_gb", 0.0) or 0.0),
            mmlu=float(payload.get("mmlu", 0.0) or 0.0),
            humaneval=float(payload.get("humaneval", 0.0) or 0.0),
            math=float(payload.get("math", 0.0) or 0.0),
            tokens_per_second=float(payload.get("tokens_per_second", 0.0) or 0.0),
        )


class OllamaModelManager:
    """Minimal Ollama API wrapper used by the upgrader."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout_seconds: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def list_installed_models(self) -> List[Dict[str, Any]]:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            return list(payload.get("models", []))
        except Exception as exc:
            logger.warning("Failed to query Ollama tags: %s", exc)
            return []

    def pull_model(self, model_name: str) -> bool:
        try:
            completed = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                logger.warning("ollama pull failed for %s: %s", model_name, completed.stderr.strip())
                return False
            return True
        except Exception as exc:
            logger.warning("ollama pull execution failed for %s: %s", model_name, exc)
            return False


class ModelUpgrader:
    """Coordinator for local-model upgrade scans."""

    def __init__(
        self,
        *,
        config_path: Optional[Path] = None,
        state_path: Optional[Path] = None,
        arena_path: Optional[Path] = None,
        model_manager: Optional[OllamaModelManager] = None,
    ):
        self.config_path = config_path or self._resolve_default_config_path()
        self.state_path = state_path or DEFAULT_STATE_PATH
        self.arena_path = arena_path or DEFAULT_ARENA_PATH
        self.model_manager = model_manager or OllamaModelManager()
        self._ensure_config_file_ready()

    @staticmethod
    def _parse_iso(ts: str) -> datetime:
        normalized = ts.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    def _resolve_default_config_path(self) -> Path:
        for candidate in DEFAULT_CONFIG_CANDIDATES:
            if candidate.exists():
                return candidate
        return DEFAULT_CONFIG_CANDIDATES[-1]

    def _ensure_config_file_ready(self) -> None:
        """
        Ensure the configured file exists.

        We prefer `lifeos/config/jarvis.json` and bootstrap it from
        `lifeos.config.json` if needed.
        """
        if self.config_path.exists():
            return

        # If we're targeting jarvis.json and legacy config exists, clone it.
        if self.config_path == PRIMARY_CONFIG_PATH and LEGACY_CONFIG_PATH.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                LEGACY_CONFIG_PATH.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            return

        # Fallback: create an empty JSON object.
        self._save_json_file(self.config_path, {})

    def _load_json_file(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load JSON file %s: %s", path, exc)
            return default

    def _save_json_file(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")

    def _load_state(self) -> Dict[str, Any]:
        return self._load_json_file(self.state_path, default={})

    def _save_state(self, payload: Dict[str, Any]) -> None:
        self._save_json_file(self.state_path, payload)

    def _load_config(self) -> Dict[str, Any]:
        return self._load_json_file(self.config_path, default={})

    def _save_config(self, payload: Dict[str, Any]) -> None:
        self._save_json_file(self.config_path, payload)

    def _active_model_from_config(self, config: Mapping[str, Any]) -> str:
        providers = config.get("providers", {}) if isinstance(config, Mapping) else {}
        ollama = providers.get("ollama", {}) if isinstance(providers, Mapping) else {}
        if isinstance(ollama, Mapping) and ollama.get("model"):
            return str(ollama["model"])

        router = config.get("router", {}) if isinstance(config, Mapping) else {}
        if isinstance(router, Mapping) and router.get("fast_model"):
            return str(router["fast_model"])
        return ""

    def should_run_weekly(self, now_iso: Optional[str] = None) -> bool:
        """
        Weekly guard: run only if last scan is >= 7 days ago.
        """
        state = self._load_state()
        last_scan_at = str(state.get("last_scan_at", "")).strip()
        if not last_scan_at:
            return True

        now = self._parse_iso(now_iso) if now_iso else self._utc_now()
        last = self._parse_iso(last_scan_at)
        delta_days = (now - last).total_seconds() / 86400.0
        return delta_days >= 7.0

    def mark_scan_complete(self, now_iso: Optional[str] = None) -> None:
        now = self._parse_iso(now_iso) if now_iso else self._utc_now()
        state = self._load_state()
        state["last_scan_at"] = now.isoformat()
        self._save_state(state)

    def persist_scan_result(self, result: Mapping[str, Any], now_iso: Optional[str] = None) -> None:
        """
        Persist both scan timestamp and last decision payload for operator dashboards.
        """
        now = self._parse_iso(now_iso) if now_iso else self._utc_now()
        state = self._load_state()
        state["last_scan_at"] = now.isoformat()
        state["last_result"] = dict(result)
        self._save_state(state)

    def get_last_scan_summary(self) -> Dict[str, Any]:
        state = self._load_state()
        if not isinstance(state, dict):
            return {}
        summary = {}
        last_scan_at = state.get("last_scan_at")
        if last_scan_at:
            summary["last_scan_at"] = last_scan_at
        if isinstance(state.get("last_result"), dict):
            summary["last_result"] = state.get("last_result")
        return summary

    @staticmethod
    def decide_upgrade(
        current: ModelSpec,
        candidate: ModelSpec,
        *,
        max_size_gb: float = 30.0,
        min_mmlu_gain_pct: float = 8.0,
        min_tps_ratio: float = 0.95,
    ) -> UpgradeAction:
        """
        Decision tree:
        - better + same/lighter + <= max size => auto-upgrade
        - better + heavier (or exceeds max size) => notify
        - otherwise skip
        """
        if current.mmlu <= 0:
            return UpgradeAction.SKIP
        gain_pct = ((candidate.mmlu - current.mmlu) / current.mmlu) * 100.0
        if gain_pct < min_mmlu_gain_pct:
            return UpgradeAction.SKIP

        candidate_is_heavier = candidate.size_gb > current.size_gb
        exceeds_size_cap = candidate.size_gb > max_size_gb
        tps_ok = (
            current.tokens_per_second <= 0
            or candidate.tokens_per_second <= 0
            or (candidate.tokens_per_second / current.tokens_per_second) >= min_tps_ratio
        )

        if not candidate_is_heavier and not exceeds_size_cap and tps_ok:
            return UpgradeAction.AUTO_UPGRADE
        return UpgradeAction.NOTIFY_HEAVIER

    def hot_swap_local_model(self, new_model: str) -> bool:
        """
        Update active model references in LifeOS config.
        """
        config = self._load_config()
        if not config:
            return False

        providers = config.setdefault("providers", {})
        if not isinstance(providers, dict):
            providers = {}
            config["providers"] = providers
        ollama = providers.setdefault("ollama", {})
        if not isinstance(ollama, dict):
            ollama = {}
            providers["ollama"] = ollama

        router = config.setdefault("router", {})
        if not isinstance(router, dict):
            router = {}
            config["router"] = router

        changed = False
        if ollama.get("model") != new_model:
            ollama["model"] = new_model
            changed = True
        if router.get("fast_model") != new_model:
            router["fast_model"] = new_model
            changed = True
        if router.get("deep_model") != new_model:
            router["deep_model"] = new_model
            changed = True

        if not changed:
            return False

        self._save_config(config)
        return True

    def rollback_local_model(self, previous_model: str) -> bool:
        """
        Roll back config references to a previously active model.
        """
        changed = self.hot_swap_local_model(previous_model)
        docker_image = os.getenv("JARVIS_DOCKER_IMAGE", "").strip()
        rollback_tag = os.getenv("JARVIS_ROLLBACK_TAG", "").strip()
        if docker_image and rollback_tag:
            try:
                subprocess.run(
                    ["docker", "image", "tag", f"{docker_image}:{rollback_tag}", f"{docker_image}:latest"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except Exception as exc:
                logger.warning("Docker rollback tagging failed: %s", exc)
        if changed:
            self.log_event(
                "rollback",
                {"restored_model": previous_model, "config_path": str(self.config_path)},
            )
        return changed

    def graceful_restart(self) -> bool:
        """
        Trigger a graceful restart using a configurable command.

        Configure with `JARVIS_RESTART_CMD`, for example:
        `docker compose restart jarvis`
        """
        restart_cmd = os.getenv("JARVIS_RESTART_CMD", "").strip()
        if not restart_cmd:
            return False
        try:
            completed = subprocess.run(
                restart_cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                logger.warning("Graceful restart command failed: %s", completed.stderr.strip())
                return False
            return True
        except Exception as exc:
            logger.warning("Graceful restart execution failed: %s", exc)
            return False

    def scan_openrouter_frontier_models(self, *, timeout_seconds: int = 15) -> Dict[str, str]:
        """
        Discover likely frontier models and map them to panel aliases.
        """
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            return {}

        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            response = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            models = payload.get("data", [])
        except Exception as exc:
            logger.warning("OpenRouter model scan failed: %s", exc)
            return {}

        found: Dict[str, str] = {}
        for item in models:
            model_id = str(item.get("id", ""))
            if not model_id:
                continue
            low = model_id.lower()
            if "claude" in low and "claude" not in found:
                found["claude"] = model_id
            elif "grok" in low and "grok" not in found:
                found["grok"] = model_id
            elif "gemini" in low and "gemini" not in found:
                found["gemini"] = model_id
            elif ("o3" in low or "/o3-" in low) and "o3" not in found:
                found["o3"] = model_id
            elif ("gpt-5" in low or "gpt-" in low) and "gpt" not in found:
                found["gpt"] = model_id
        return found

    def update_arena_panel(self, additions: Mapping[str, str]) -> bool:
        """
        Add discovered models into core/consensus/arena.py PANEL dict.
        """
        if not additions:
            return False
        if not self.arena_path.exists():
            return False

        text = self.arena_path.read_text(encoding="utf-8")
        panel_match = re.search(
            r'(PANEL:\s*Dict\[str,\s*str\]\s*=\s*\{)(?P<body>.*?)(\n\})',
            text,
            flags=re.DOTALL,
        )
        if not panel_match:
            return False

        body = panel_match.group("body")
        changed = False
        for alias, model_id in additions.items():
            alias_pattern = re.compile(rf'("{re.escape(alias)}"\s*:\s*")[^"]+(")')
            if alias_pattern.search(body):
                replaced = alias_pattern.sub(rf'\1{model_id}\2', body)
                if replaced != body:
                    body = replaced
                    changed = True
            else:
                line = f'    "{alias}": "{model_id}",'
                body = body + ("" if body.endswith("\n") else "\n") + line
                changed = True

        if not changed:
            return False

        updated = text[: panel_match.start("body")] + body + text[panel_match.end("body") :]
        self.arena_path.write_text(updated, encoding="utf-8")
        return True

    def log_event(self, event_type: str, payload: Mapping[str, Any]) -> None:
        """
        Best-effort audit log to Supermemory shared namespace.
        """
        try:
            from bots.shared.supermemory_client import get_memory_client

            client = get_memory_client("model_upgrader")
            if not client.is_available:
                return
            message = json.dumps({"event": event_type, **dict(payload)}, ensure_ascii=True)
            # Fire-and-forget style for script usage.
            import asyncio

            asyncio.run(
                client.add_shared_learning(
                    content=message,
                    category="model_upgrader",
                    metadata={"source": "jobs.model_upgrader"},
                )
            )
        except Exception as exc:
            logger.debug("Supermemory event log skipped: %s", exc)

    def run_weekly_scan(
        self,
        *,
        candidates: Iterable[ModelSpec],
        current: Optional[ModelSpec] = None,
        now_iso: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute one scan cycle with explicit candidate list.
        """
        candidate_list = list(candidates)
        if not force and not self.should_run_weekly(now_iso=now_iso):
            return {"status": "skipped", "reason": "weekly_guard"}

        config = self._load_config()
        active_model = self._active_model_from_config(config)
        current_model = current
        installed_models = self.model_manager.list_installed_models()
        if current_model is None and active_model:
            current_model = next((item for item in candidate_list if item.name == active_model), None)
            if current_model is None:
                current_model = ModelSpec(
                    name=active_model,
                    size_gb=0.0,
                    mmlu=0.0,
                    humaneval=0.0,
                    math=0.0,
                    tokens_per_second=0.0,
                )

        ranked = sorted(candidate_list, key=lambda c: (c.mmlu, c.humaneval, c.math), reverse=True)
        if not ranked or current_model is None:
            frontier = self.scan_openrouter_frontier_models()
            panel_changed = self.update_arena_panel(frontier)
            result = {
                "status": "completed",
                "action": UpgradeAction.SKIP.value,
                "reason": "insufficient_candidate_data",
                "panel_updated": panel_changed,
                "installed_models_count": len(installed_models),
            }
            self.persist_scan_result(result, now_iso=now_iso)
            return result

        best = ranked[0]
        action = self.decide_upgrade(current_model, best)
        result: Dict[str, Any] = {
            "status": "completed",
            "action": action.value,
            "current_model": current_model.name,
            "candidate_model": best.name,
        }

        if action == UpgradeAction.AUTO_UPGRADE:
            pulled = self.model_manager.pull_model(best.name)
            swapped = self.hot_swap_local_model(best.name) if pulled else False
            result["pulled"] = pulled
            result["swapped"] = swapped
            result["restarted"] = self.graceful_restart() if swapped else False
        elif action == UpgradeAction.NOTIFY_HEAVIER:
            result["notify"] = (
                f"Candidate {best.name} improved benchmarks but is heavier "
                f"({best.size_gb:.2f}GB vs {current_model.size_gb:.2f}GB)."
            )

        frontier = self.scan_openrouter_frontier_models()
        result["panel_updated"] = self.update_arena_panel(frontier)
        result["frontier_models_found"] = len(frontier)
        result["installed_models_count"] = len(installed_models)

        self.persist_scan_result(result, now_iso=now_iso)
        self.log_event("weekly_scan", result)
        return result


def _parse_candidate_specs(raw_json: str) -> List[ModelSpec]:
    payload = json.loads(raw_json)
    if not isinstance(payload, list):
        raise ValueError("MODEL_UPGRADER_CANDIDATES_JSON must decode to a list")
    return [ModelSpec.from_mapping(item) for item in payload if isinstance(item, Mapping)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis model upgrader")
    parser.add_argument("--weekly-scan", action="store_true", help="Run weekly scan cycle")
    parser.add_argument("--force", action="store_true", help="Ignore weekly guard")
    parser.add_argument("--config-path", type=Path, default=None)
    parser.add_argument("--state-path", type=Path, default=None)
    parser.add_argument("--arena-path", type=Path, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    upgrader = ModelUpgrader(
        config_path=args.config_path,
        state_path=args.state_path,
        arena_path=args.arena_path,
    )

    if not args.weekly_scan:
        logger.info("No action requested. Use --weekly-scan.")
        return 0

    raw_candidates = os.getenv("MODEL_UPGRADER_CANDIDATES_JSON", "[]")
    try:
        candidates = _parse_candidate_specs(raw_candidates)
    except Exception as exc:
        logger.warning("Failed to parse MODEL_UPGRADER_CANDIDATES_JSON: %s", exc)
        candidates = []

    result = upgrader.run_weekly_scan(candidates=candidates, force=args.force)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

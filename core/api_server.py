"""
API Server for Jarvis Frontend.
Provides REST endpoints for the Electron/React frontend.
"""

import csv
import json
import os
import threading
import time
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from core import config, conversation, passive, providers, proactive, secrets, state, autonomous_learner, autonomous_controller, research_engine, prompt_distiller, service_discovery, google_integration, google_manager, ability_acquisition

ROOT = Path(__file__).resolve().parents[1]
PORT = 8765

TRADER_DIR = ROOT / "data" / "trader"
SOLANA_DEX_DIR = TRADER_DIR / "solana_dex"
SOLANA_SCANNER_DIR = TRADER_DIR / "solana_scanner"
TOKEN_UNIVERSE_PATH = SOLANA_DEX_DIR / "token_universe.json"
DEX_BACKTEST_RESULTS_PATH = SOLANA_DEX_DIR / "backtest_results.json"
DEX_BACKTEST_STATUS_PATH = SOLANA_DEX_DIR / "backtest_status.json"
TRADING_BACKTESTS_PATH = TRADER_DIR / "backtests.jsonl"
STRATEGIES_PATH = TRADER_DIR / "strategies.json"
SCANNER_TRENDING_CSV = SOLANA_SCANNER_DIR / "birdeye_trending_tokens.csv"

_BACKTEST_THREAD: Optional[threading.Thread] = None
_BACKTEST_LOCK = threading.Lock()


def _read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _read_json_lines(path: Path, limit: int = 50) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    results: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    if limit and len(results) > limit:
        return results[-limit:]
    return results


def _write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _format_duration(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m"


def _summarize_active_time(hours: int = 24) -> float:
    entries = passive.load_recent_activity(hours=hours)
    total = 0.0
    for entry in entries:
        for session in entry.get("sessions", []) or []:
            total += float(session.get("dur_s", 0) or 0)
    return total


def _compute_focus_score(entries: List[Dict[str, Any]]) -> int:
    app_time: Dict[str, float] = {}
    total = 0.0
    for entry in entries:
        for session in entry.get("sessions", []) or []:
            app_name = session.get("app") or entry.get("app") or "Unknown"
            duration = float(session.get("dur_s", 0) or 0)
            total += duration
            app_time[app_name] = app_time.get(app_name, 0.0) + duration
    if total <= 0:
        return 0
    top_app = max(app_time.values()) if app_time else 0.0
    return int((top_app / total) * 100)


def _load_trading_strategies() -> List[Dict[str, Any]]:
    payload = _read_json_file(STRATEGIES_PATH, {})
    strategies = payload.get("strategies")
    if isinstance(strategies, list):
        return strategies
    return []


def _load_solana_tokens() -> List[Dict[str, Any]]:
    tokens = _read_json_file(TOKEN_UNIVERSE_PATH, [])
    if isinstance(tokens, list) and tokens:
        return tokens

    if not SCANNER_TRENDING_CSV.exists():
        return []
    parsed: List[Dict[str, Any]] = []
    try:
        with open(SCANNER_TRENDING_CSV, "r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                parsed.append(
                    {
                        "symbol": row.get("symbol", ""),
                        "name": row.get("name", ""),
                        "address": row.get("address", ""),
                        "volume24hUSD": float(row.get("volume24hUSD", 0) or 0),
                        "price": float(row.get("price", 0) or 0),
                        "liquidity": float(row.get("liquidity", 0) or 0),
                    }
                )
    except OSError:
        return []
    return parsed


def _dex_backtest_status() -> Dict[str, Any]:
    status = _read_json_file(DEX_BACKTEST_STATUS_PATH, {})
    if not isinstance(status, dict):
        status = {}
    status.setdefault("running", False)
    return status


def _format_dex_backtests(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    formatted: List[Dict[str, Any]] = []
    for entry in results:
        token = entry.get("token", {}) or {}
        strategy = entry.get("best_strategy", {}) or {}
        window_days = entry.get("window_days") or 30
        windows = entry.get("windows") or 3
        total_days = int(window_days) * int(windows)
        end = datetime.utcnow().date()
        start = end - timedelta(days=total_days)
        window_rois = strategy.get("window_rois") or []
        win_rate = 0.0
        if window_rois:
            positives = sum(1 for roi in window_rois if roi > 0)
            win_rate = positives / len(window_rois)
        formatted.append(
            {
                "strategy_name": strategy.get("strategy_id", "unknown"),
                "token_symbol": token.get("symbol", ""),
                "passed": bool(strategy.get("roi_90d", 0) > 0),
                "window_start": start.isoformat(),
                "window_end": end.isoformat(),
                "total_trades": strategy.get("total_trades", 0),
                "sharpe_ratio": None,
                "win_rate": win_rate,
            }
        )
    return formatted


def _format_pipeline_backtests(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    formatted: List[Dict[str, Any]] = []
    for entry in results:
        formatted.append(
            {
                "strategy_name": entry.get("strategy", "unknown"),
                "token_symbol": entry.get("symbol", ""),
                "passed": entry.get("error") is None and float(entry.get("roi", 0) or 0) >= 0,
                "window_start": entry.get("period_start"),
                "window_end": entry.get("period_end"),
                "total_trades": entry.get("total_trades", 0),
                "sharpe_ratio": entry.get("sharpe_ratio"),
                "win_rate": float(entry.get("win_rate", 0) or 0),
            }
        )
    return formatted


class JarvisAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Jarvis API."""

    def _send_json(self, data: Dict[str, Any], status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _read_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length:
            body = self.rfile.read(content_length)
            return json.loads(body.decode())
        return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            self._handle_status()
        elif path == "/api/stats":
            self._handle_stats()
        elif path == "/api/health":
            self._handle_health()
        elif path == "/api/settings/keys":
            self._handle_get_keys()
        elif path == "/api/suggestions":
            self._handle_suggestions()
        elif path == "/api/autonomous":
            self._handle_autonomous()
        elif path == "/api/autonomous/enable":
            self._handle_enable_autonomous()
        elif path == "/api/autonomous/status":
            self._handle_autonomous_status()
        elif path == "/api/research":
            self._handle_research()
        elif path == "/api/research/topics":
            self._handle_research_topics()
        elif path == "/api/learning":
            self._handle_learning_report()
        elif path == "/api/services/discover":
            self._handle_discover_services()
        elif path == "/api/services/signup":
            self._handle_service_signup()
        elif path == "/api/services/integrate":
            self._handle_service_integrate()
        elif path == "/api/services/integrated":
            self._handle_integrated_services()
        elif path == "/api/google/setup":
            self._handle_google_setup()
        elif path == "/api/google/authenticate":
            self._handle_google_authenticate()
        elif path == "/api/google/status":
            self._handle_google_status()
        elif path == "/api/google/sync":
            self._handle_google_sync()
        elif path == "/api/abilities/discover":
            self._handle_discover_abilities()
        elif path == "/api/abilities/acquire":
            self._handle_acquire_abilities()
        elif path == "/api/abilities/status":
            self._handle_abilities_status()
        elif path == "/api/voice/status":
            self._handle_voice_status()
        elif path == "/api/voice/config":
            self._handle_voice_config_get()
        elif path == "/api/costs/tts":
            self._handle_tts_costs()
        elif path == "/api/trading/stats":
            self._handle_trading_stats()
        elif path == "/api/trading/solana/tokens":
            self._handle_trading_solana_tokens()
        elif path == "/api/trading/backtests":
            self._handle_trading_backtests()
        # Enhanced Trading Dashboard endpoints
        elif path == "/api/wallet/status":
            self._handle_wallet_status()
        elif path == "/api/wallet/transactions":
            self._handle_wallet_transactions()
        elif path == "/api/sniper/status":
            self._handle_sniper_status()
        elif path == "/api/sniper/config":
            self._handle_sniper_config_get()
        elif path == "/api/scan/history":
            self._handle_scan_history()
        elif path == "/api/trending/momentum":
            self._handle_trending_momentum()
        elif path == "/api/jarvis/status":
            self._handle_jarvis_status()
        elif path == "/api/system/info":
            self._handle_system_info()
        # Phase 1 Enhancement: Live Position Monitoring + DeFi Tools
        elif path == "/api/position/active":
            self._handle_position_active()
        elif path.startswith("/api/tools/token/"):
            mint = path.split("/api/tools/token/")[1]
            self._handle_tools_token(mint)
        elif path.startswith("/api/tools/rugcheck/"):
            mint = path.split("/api/tools/rugcheck/")[1]
            self._handle_tools_rugcheck(mint)
        # Phase 1: Chart data
        elif path.startswith("/api/chart/"):
            parts = path.split("/api/chart/")[1].split("/")
            mint = parts[0] if parts else ""
            self._handle_chart(mint)
        # Phase 1: Strategies list
        elif path == "/api/strategies/list":
            self._handle_strategies_list()
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/chat":
            self._handle_chat()
        elif path == "/api/research":
            self._handle_research()
        elif path == "/api/settings/keys":
            self._handle_save_key()
        elif path == "/api/voice/start":
            self._handle_voice_start()
        elif path == "/api/voice/stop":
            self._handle_voice_stop()
        elif path == "/api/voice/toggle":
            self._handle_voice_toggle()
        elif path == "/api/voice/config":
            self._handle_voice_config_set()
        elif path == "/api/voice/test":
            self._handle_voice_test()
        elif path == "/api/trading/solana/scan":
            self._handle_trading_solana_scan()
        elif path == "/api/trading/backtests/run":
            self._handle_trading_backtests_run()
        # Enhanced Trading Dashboard endpoints (POST)
        elif path == "/api/jarvis/chat":
            self._handle_jarvis_chat()
        elif path == "/api/sniper/config":
            self._handle_sniper_config_set()
        # Phase 1 Enhancement: Position Exit
        elif path == "/api/position/exit":
            self._handle_position_exit()
        # Phase 1: Trade execution
        elif path == "/api/trade":
            self._handle_trade()
        else:
            self._send_json({"error": "Not found"}, 404)

    def _handle_status(self):
        """Get system status."""
        current_state = state.read_state()
        self._send_json({
            "daemon": "running" if current_state.get("daemon_running") else "stopped",
            "voice": current_state.get("mic_status", "off"),
            "monitoring": "on" if current_state.get("passive_observation") else "off",
            "chat_active": current_state.get("chat_active", False),
        })

    def _handle_stats(self):
        """Get dashboard statistics."""
        try:
            entries = passive.load_recent_activity(hours=24)
            active_seconds = _summarize_active_time(hours=24)
            focus_score = _compute_focus_score(entries)
            suggestions = proactive.get_recent_suggestions(count=10)
            try:
                from core import task_manager
                tasks_completed = task_manager.get_task_manager().get_stats().get("completed", 0)
            except Exception:
                tasks_completed = 0

            self._send_json({
                "activeTime": _format_duration(active_seconds),
                "tasksCompleted": tasks_completed,
                "suggestionsGiven": len(suggestions),
                "focusScore": focus_score,
            })
        except Exception as e:
            self._send_json({
                "activeTime": "0h 0m",
                "tasksCompleted": 0,
                "suggestionsGiven": 0,
                "focusScore": 0,
            })

    def _handle_chat(self):
        """Handle chat message."""
        body = self._read_body()
        message = body.get("message", "")
        
        if not message:
            self._send_json({"error": "No message provided"}, 400)
            return

        try:
            response = conversation.generate_response(message, "")
            self._send_json({"response": response})
        except Exception as e:
            self._send_json({"response": f"Error: {str(e)}"}, 500)

    def _handle_research(self):
        """Handle research request."""
        body = self._read_body()
        topic = body.get("topic", "")
        depth = body.get("depth", "medium")
        
        if not topic:
            self._send_json({"error": "No topic provided"}, 400)
            return

        try:
            results = proactive.research_topic(topic, depth)
            self._send_json(results)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_get_keys(self):
        """Get masked API keys."""
        keys = {}
        providers_list = ["gemini", "groq", "anthropic", "openai", "trello", "github"]
        
        for provider in providers_list:
            key = ""
            if provider == "gemini":
                key = secrets.get_gemini_key()
            elif provider == "groq":
                key = secrets.get_groq_key()
            elif provider == "anthropic":
                key = secrets.get_anthropic_key()
            elif provider == "openai":
                key = secrets.get_openai_key()
            
            # Mask the key for display
            if key:
                keys[provider] = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
            else:
                keys[provider] = ""
        
        self._send_json(keys)

    def _handle_save_key(self):
        """Save an API key."""
        body = self._read_body()
        provider = body.get("provider", "")
        key = body.get("key", "")
        
        if not provider or not key:
            self._send_json({"error": "Provider and key required"}, 400)
            return

        try:
            keys_path = ROOT / "secrets" / "keys.json"
            keys_data = {}
            
            if keys_path.exists():
                with open(keys_path, "r") as f:
                    keys_data = json.load(f)
            
            # Map provider to key name
            key_names = {
                "gemini": "google_api_key",
                "groq": "groq_api_key",
                "anthropic": "anthropic_api_key",
                "openai": "openai_api_key",
                "trello": "trello_api_key",
                "github": "github_token",
            }
            
            if provider in key_names:
                keys_data[key_names[provider]] = key
                
                keys_path.parent.mkdir(parents=True, exist_ok=True)
                with open(keys_path, "w") as f:
                    json.dump(keys_data, indent=2, fp=f)
                
                self._send_json({"success": True})
            else:
                self._send_json({"error": "Unknown provider"}, 400)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_suggestions(self):
        """Get recent suggestions."""
        try:
            suggestions = proactive.get_recent_suggestions(count=10)
            self._send_json({"suggestions": suggestions})
        except Exception as e:
            self._send_json({"suggestions": []})

    def _handle_voice_start(self):
        """Start voice listening."""
        state.update_state(mic_status="listening")
        self._send_json({"success": True})

    def _handle_voice_stop(self):
        """Stop voice listening."""
        state.update_state(mic_status="off")
        self._send_json({"success": True})

    def _handle_voice_toggle(self):
        """Enable/disable voice in config and state."""
        body = self._read_body()
        enabled = bool(body.get("enabled", True))
        try:
            updated = config.update_local_config({"voice": {"enabled": enabled}})
            if enabled:
                state.update_state(voice_enabled=True, mic_status="idle")
            else:
                state.update_state(voice_enabled=False, mic_status="off")
            self._send_json({"success": True, "enabled": enabled, "config": updated.get("voice", {})})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_voice_config_get(self):
        """Return current voice configuration."""
        cfg = config.load_config()
        self._send_json(cfg.get("voice", {}))

    def _handle_voice_config_set(self):
        """Update voice configuration values."""
        body = self._read_body()
        updates: Dict[str, Any] = {}
        allowed = {
            "tts_engine": "tts_engine",
            "openai_voice": "openai_tts_voice",
            "openai_tts_voice": "openai_tts_voice",
            "model": "openai_tts_model",
            "openai_tts_model": "openai_tts_model",
            "speech_voice": "speech_voice",
            "barge_in_enabled": "barge_in_enabled",
            "wake_word": "wake_word",
            "voice_clone_voice": "voice_clone_voice",
            "voice_clone_enabled": "voice_clone_enabled",
            "local_stt_enabled": "local_stt_enabled",
            "local_stt_engine": "local_stt_engine",
            "local_whisper_model": "local_whisper_model",
        }
        for key, target in allowed.items():
            if key in body:
                updates[target] = body[key]
        if not updates:
            self._send_json({"error": "No supported voice settings provided"}, 400)
            return
        try:
            merged = config.update_local_config({"voice": updates})
            self._send_json({"success": True, "config": merged.get("voice", {})})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_voice_status(self):
        """Return runtime voice status for UI."""
        current_state = state.read_state()
        cfg = config.load_config()
        voice_cfg = cfg.get("voice", {})
        try:
            from core import voice as voice_module
            runtime = voice_module.get_voice_runtime_status()
        except Exception:
            runtime = {"speaking": False, "last_spoken_at": 0.0, "last_spoken_text": ""}
        mic_status = current_state.get("mic_status", "off")
        self._send_json({
            "enabled": voice_cfg.get("enabled", True),
            "listening": mic_status in {"listening", "capturing", "chat"},
            "speaking": runtime.get("speaking", False),
            "bargeInEnabled": voice_cfg.get("barge_in_enabled", True),
            "mode": voice_cfg.get("mode", "unknown"),
            "micStatus": mic_status,
            "voiceError": current_state.get("voice_error", ""),
            "lastSpokenAt": runtime.get("last_spoken_at", 0.0),
            "lastSpokenText": runtime.get("last_spoken_text", ""),
            "ttsEngine": voice_cfg.get("tts_engine", ""),
            "localSttEnabled": voice_cfg.get("local_stt_enabled", False),
        })

    def _handle_voice_test(self):
        """Speak a test phrase using the configured TTS engine."""
        body = self._read_body()
        text = body.get("text", "Voice system test.")
        try:
            from core import voice as voice_module
            success = voice_module.speak_text(text)
            self._send_json({"success": bool(success)})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_tts_costs(self):
        """Return OpenAI TTS cost estimates."""
        try:
            from scripts import monitor_tts_costs
            hourly = monitor_tts_costs.get_hourly_stats()
            daily = monitor_tts_costs.get_daily_stats()
            projected = hourly.get("total_cost_usd", 0.0) * 24 * 30
            self._send_json({
                "hour": hourly.get("total_cost_usd", 0.0),
                "today": daily.get("total_cost_usd", 0.0),
                "projected": round(projected, 2),
            })
        except Exception as e:
            self._send_json({"hour": 0.0, "today": 0.0, "projected": 0.0})

    def _handle_health(self):
        """Return system + provider health for monitoring UI."""
        try:
            from core import system_profiler
            profile = system_profiler.read_profile()
        except Exception:
            profile = None
        current_state = state.read_state()
        provider_health = providers.provider_health_check()

        payload = {
            "profile": {
                "cpu_load": getattr(profile, "cpu_load", 0.0),
                "ram_total_gb": getattr(profile, "ram_total_gb", 0.0),
                "ram_free_gb": getattr(profile, "ram_free_gb", 0.0),
                "disk_free_gb": getattr(profile, "disk_free_gb", 0.0),
                "os_version": getattr(profile, "os_version", ""),
            },
            "network": {
                "rx_mbps": current_state.get("net_rx_mbps", 0.0),
                "tx_mbps": current_state.get("net_tx_mbps", 0.0),
                "packets_per_sec": current_state.get("net_packets_per_sec", 0.0),
            },
            "llm": {
                "last_provider": current_state.get("last_llm_provider", ""),
                "last_model": current_state.get("last_llm_model", ""),
                "last_latency_ms": current_state.get("last_llm_latency_ms", 0),
                "last_errors": provider_health.get("last_errors", {}),
                "available_providers": provider_health.get("available_providers", []),
            },
            "voice": {
                "enabled": current_state.get("voice_enabled", False),
                "mic_status": current_state.get("mic_status", "off"),
                "voice_error": current_state.get("voice_error", ""),
            },
        }
        self._send_json(payload)

    def _handle_trading_stats(self):
        """Return trading dashboard summary metrics."""
        strategies = _load_trading_strategies()
        approved = [s for s in strategies if s.get("approved_for_live")]
        active_strategies = len(approved) if approved else len(strategies)

        tokens = _load_solana_tokens()
        if tokens:
            volumes = []
            for token in tokens:
                volume = token.get("volume24hUSD")
                if volume is None:
                    volume = token.get("volume_24h")
                volumes.append(float(volume or 0))
            avg_volume = sum(volumes) / len(volumes) if volumes else 0.0
        else:
            avg_volume = 0.0

        status = _dex_backtest_status()
        backtests_running = 1 if status.get("running") else 0

        self._send_json({
            "activeStrategies": active_strategies,
            "backtestsRunning": backtests_running,
            "solanaTokens": len(tokens),
            "avgVolume": avg_volume,
            "lastBacktestAt": status.get("completed_at") or status.get("started_at"),
        })

    def _handle_trading_solana_tokens(self):
        """Return cached Solana tokens for trading dashboard."""
        tokens = _load_solana_tokens()
        normalized = []
        for token in tokens:
            normalized.append(
                {
                    "symbol": token.get("symbol", ""),
                    "name": token.get("name", ""),
                    "address": token.get("address", ""),
                    "volume24hUSD": float(token.get("volume24hUSD", token.get("volume_24h", 0)) or 0),
                    "price": token.get("price"),
                    "liquidity": float(token.get("liquidity", token.get("reserve_usd", 0)) or 0),
                }
            )
        self._send_json({"tokens": normalized})

    def _handle_trading_backtests(self):
        """Return recent backtest results for UI."""
        dex_results = _read_json_file(DEX_BACKTEST_RESULTS_PATH, [])
        if isinstance(dex_results, list) and dex_results:
            results = _format_dex_backtests(dex_results)
        else:
            pipeline_results = _read_json_lines(TRADING_BACKTESTS_PATH, limit=50)
            results = _format_pipeline_backtests(pipeline_results)
        self._send_json({"results": results, "status": _dex_backtest_status()})

    def _handle_trading_solana_scan(self):
        """Scan Solana pools and store token universe."""
        try:
            from scripts import solana_dex_backtest
            tokens = solana_dex_backtest.collect_token_universe(
                limit_tokens=50,
                pages=2,
                min_liquidity_usd=50000,
                min_volume_usd=50000,
                sleep_seconds=0.2,
            )
            if tokens:
                SOLANA_DEX_DIR.mkdir(parents=True, exist_ok=True)
                TOKEN_UNIVERSE_PATH.write_text(json.dumps(tokens, indent=2))
            self._send_json({"success": True, "count": len(tokens), "tokens": tokens})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_trading_backtests_run(self):
        """Kick off Solana DEX backtests in a background thread."""
        global _BACKTEST_THREAD

        with _BACKTEST_LOCK:
            if _BACKTEST_THREAD and _BACKTEST_THREAD.is_alive():
                self._send_json({"success": False, "status": "already_running"})
                return

            def _run_backtests() -> None:
                status = {
                    "running": True,
                    "started_at": datetime.utcnow().isoformat(),
                    "completed_at": None,
                    "error": None,
                }
                _write_json_file(DEX_BACKTEST_STATUS_PATH, status)
                try:
                    from scripts import solana_dex_backtest

                    tokens = solana_dex_backtest.collect_token_universe(
                        limit_tokens=30,
                        pages=3,
                        min_liquidity_usd=50000,
                        min_volume_usd=50000,
                        sleep_seconds=0.25,
                    )
                    SOLANA_DEX_DIR.mkdir(parents=True, exist_ok=True)
                    TOKEN_UNIVERSE_PATH.write_text(json.dumps(tokens, indent=2))

                    strategies = solana_dex_backtest.build_strategies(
                        max_strategies=20,
                        capital_usd=10.0,
                        fee_bps=30.0,
                        slippage_bps=20.0,
                        risk_per_trade=0.02,
                        stop_loss_pct=0.03,
                        take_profit_pct=0.06,
                        max_position_pct=0.25,
                    )
                    results: List[Dict[str, Any]] = []
                    for token in tokens:
                        entry = solana_dex_backtest.backtest_token(
                            token,
                            strategies,
                            timeframe="hour",
                            window_days=30,
                            windows=3,
                            sleep_seconds=0.25,
                            min_candles_ratio=0.3,
                            min_trades=1,
                        )
                        if entry:
                            results.append(entry)

                    if results:
                        results.sort(key=lambda item: item.get("score", 0), reverse=True)
                        DEX_BACKTEST_RESULTS_PATH.write_text(json.dumps(results, indent=2))
                        top5 = results[:5]
                        (SOLANA_DEX_DIR / "top5.json").write_text(json.dumps(top5, indent=2))
                        (SOLANA_DEX_DIR / "top5.md").write_text(
                            solana_dex_backtest.render_top5_markdown(top5)
                        )
                        for entry in top5:
                            solana_dex_backtest.write_bot_config(entry)

                    status["completed_at"] = datetime.utcnow().isoformat()
                except Exception as exc:
                    status["error"] = str(exc)
                finally:
                    status["running"] = False
                    _write_json_file(DEX_BACKTEST_STATUS_PATH, status)

            _BACKTEST_THREAD = threading.Thread(target=_run_backtests, daemon=True)
            _BACKTEST_THREAD.start()
            self._send_json({"success": True, "status": "started"})

    def _handle_autonomous(self):
        """Get autonomous learner summary."""
        try:
            summary = autonomous_learner.get_autonomous_summary()
            self._send_json(summary)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_enable_autonomous(self):
        """Enable/disable autonomous improvements."""
        body = self._read_body()
        enable = body.get("enable", False)
        
        try:
            autonomous_learner.enable_autonomous_improvements(enable)
            self._send_json({"success": True, "enabled": enable})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_autonomous_status(self):
        """Get detailed autonomous controller status."""
        try:
            controller = autonomous_controller.get_autonomous_controller()
            status = controller.get_status()
            self._send_json(status)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_research(self):
        """Handle research request."""
        body = self._read_body()
        topic = body.get("topic", "")
        
        if not topic:
            self._send_json({"error": "Topic required"}, 400)
            return
        
        try:
            engine = research_engine.get_research_engine()
            result = engine.research_topic(topic, max_pages=5)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_research_topics(self):
        """Get research topics and queue."""
        try:
            controller = autonomous_controller.get_autonomous_controller()
            topics = controller.schedule["priority_topics"]
            self._send_json({"topics": topics})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_learning_report(self):
        """Get comprehensive learning report."""
        try:
            distiller = prompt_distiller.get_prompt_distiller()
            report = distiller.get_learning_report()
            self._send_json(report)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_discover_services(self):
        """Get available services for integration."""
        try:
            discovery = service_discovery.get_service_discovery()
            services = discovery.discover_services()
            self._send_json({"services": services})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_service_signup(self):
        """Initiate signup for a service."""
        body = self._read_body()
        service_id = body.get("service_id", "")
        
        if not service_id:
            self._send_json({"error": "service_id required"}, 400)
            return
        
        try:
            discovery = service_discovery.get_service_discovery()
            result = discovery.initiate_signup(service_id)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_service_integrate(self):
        """Integrate a service with API key."""
        body = self._read_body()
        service_id = body.get("service_id", "")
        api_key = body.get("api_key", "")
        
        if not service_id or not api_key:
            self._send_json({"error": "service_id and api_key required"}, 400)
            return
        
        try:
            discovery = service_discovery.get_service_discovery()
            result = discovery.integrate_service(service_id, api_key)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_integrated_services(self):
        """Get list of integrated services."""
        try:
            discovery = service_discovery.get_service_discovery()
            services = discovery.get_integrated_services()
            self._send_json({"services": services})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_google_setup(self):
        """Set up Google credentials."""
        body = self._read_body()
        client_id = body.get("client_id", "")
        client_secret = body.get("client_secret", "")
        project_id = body.get("project_id", "")
        
        if not all([client_id, client_secret, project_id]):
            self._send_json({"error": "All fields required: client_id, client_secret, project_id"}, 400)
            return
        
        try:
            integration = google_integration.get_google_integration()
            success = integration.setup_credentials(client_id, client_secret, project_id)
            if success:
                self._send_json({"success": True, "message": "Google credentials configured"})
            else:
                self._send_json({"error": "Failed to configure credentials"}, 500)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_google_authenticate(self):
        """Authenticate with Google."""
        body = self._read_body()
        services = body.get("services", ["drive", "gmail", "calendar", "sheets"])
        
        try:
            integration = google_integration.get_google_integration()
            result = integration.authenticate(services)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_google_status(self):
        """Get Google integration status."""
        try:
            integration = google_integration.get_google_integration()
            status = integration.get_status()
            
            # Add sync status
            manager = google_manager.get_google_manager()
            status["last_sync_results"] = {}
            
            return self._send_json(status)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_google_sync(self):
        """Trigger Google services sync."""
        body = self._read_body()
        service = body.get("service", "all")
        
        try:
            manager = google_manager.get_google_manager()
            results = {}
            
            if service in ["all", "drive"]:
                results["drive"] = manager.sync_drive()
            
            if service in ["all", "gmail"]:
                results["gmail"] = manager.scan_gmail()
            
            if service in ["all", "calendar"]:
                results["calendar"] = manager.sync_calendar()
            
            if service in ["all", "analyze"]:
                results["analysis"] = manager.analyze_drive_content()
            
            self._send_json({"success": True, "results": results})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_discover_abilities(self):
        """Discover new open-source abilities."""
        try:
            acquisition = ability_acquisition.get_ability_acquisition()
            discoveries = acquisition.discover_open_source_models()
            self._send_json({"success": True, "discoveries": discoveries})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_acquire_abilities(self):
        """Trigger ability acquisition cycle."""
        try:
            acquisition = ability_acquisition.get_ability_acquisition()
            result = acquisition.run_acquisition_cycle()
            self._send_json({"success": True, "result": result})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_abilities_status(self):
        """Get ability acquisition status."""
        try:
            acquisition = ability_acquisition.get_ability_acquisition()
            status = acquisition.get_status()
            self._send_json(status)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def log_message(self, format, *args):
        # Suppress default logging
        pass

    # =========================================================================
    # Enhanced Trading Dashboard Handlers
    # =========================================================================

    def _fetch_spl_token_holdings(self, address: str, sol_price: float) -> List[Dict[str, Any]]:
        """Fetch SPL token holdings for a wallet address."""
        tokens = []
        try:
            import urllib.request
            from core import solana_execution, birdeye

            endpoints = solana_execution.load_solana_rpc_endpoints()
            if not endpoints:
                return []

            # Get token accounts using getTokenAccountsByOwner
            for ep in endpoints[:2]:
                try:
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getTokenAccountsByOwner",
                        "params": [
                            address,
                            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                            {"encoding": "jsonParsed"}
                        ]
                    }
                    req = urllib.request.Request(
                        ep.url,
                        data=json.dumps(payload).encode(),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data = json.loads(resp.read())
                        if "result" in data and "value" in data["result"]:
                            for account in data["result"]["value"]:
                                try:
                                    info = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                                    mint = info.get("mint", "")
                                    token_amount = info.get("tokenAmount", {})
                                    amount = float(token_amount.get("uiAmount", 0) or 0)

                                    if amount <= 0:
                                        continue

                                    # Try to get token price and metadata
                                    token_price = 0.0
                                    symbol = mint[:8] + "..."
                                    try:
                                        price_data = birdeye.fetch_token_price(mint)
                                        if price_data and "value" in price_data:
                                            token_price = float(price_data["value"])
                                        # Try to get symbol from metadata
                                        meta = birdeye.fetch_token_metadata(mint)
                                        if meta and "symbol" in meta:
                                            symbol = meta["symbol"]
                                    except Exception:
                                        pass

                                    tokens.append({
                                        "mint": mint,
                                        "symbol": symbol,
                                        "amount": round(amount, 6),
                                        "price_usd": round(token_price, 8),
                                        "value_usd": round(amount * token_price, 2),
                                    })
                                except Exception:
                                    continue
                            break
                except Exception:
                    continue

            # Sort by value descending
            tokens.sort(key=lambda x: x.get("value_usd", 0), reverse=True)
            return tokens[:20]  # Return top 20 tokens

        except Exception:
            return []

    def _handle_wallet_status(self):
        """Get wallet address, SOL balance, and token holdings."""
        try:
            from core import solana_wallet
            from core import solana_execution
            
            keypair = solana_wallet.load_keypair()
            if not keypair:
                self._send_json({
                    "address": None,
                    "balance_sol": 0,
                    "balance_usd": 0,
                    "tokens": [],
                    "connected": False,
                    "error": "No wallet configured"
                })
                return
            
            address = str(keypair.pubkey())
            
            # Try to get balance from RPC
            balance_sol = 0.0
            try:
                import urllib.request
                endpoints = solana_execution.load_solana_rpc_endpoints()
                if endpoints:
                    for ep in endpoints[:2]:  # Try first 2 endpoints
                        try:
                            payload = {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "getBalance",
                                "params": [address]
                            }
                            req = urllib.request.Request(
                                ep.url,
                                data=json.dumps(payload).encode(),
                                headers={"Content-Type": "application/json"}
                            )
                            with urllib.request.urlopen(req, timeout=10) as resp:
                                data = json.loads(resp.read())
                                if "result" in data:
                                    balance_sol = data["result"]["value"] / 1e9
                                    break
                        except Exception:
                            continue
            except Exception:
                pass
            
            # Fetch SOL price from BirdEye API
            sol_price = 20.0  # Fallback price
            try:
                from core import birdeye
                sol_mint = "So11111111111111111111111111111111111111112"
                price_data = birdeye.fetch_token_price(sol_mint)
                if price_data and "value" in price_data:
                    sol_price = float(price_data["value"])
            except Exception:
                pass

            # Fetch SPL token holdings
            spl_tokens = self._fetch_spl_token_holdings(address, sol_price)

            self._send_json({
                "address": address,
                "address_short": f"{address[:6]}...{address[-4:]}",
                "balance_sol": round(balance_sol, 6),
                "balance_usd": round(balance_sol * sol_price, 2),
                "sol_price": sol_price,
                "tokens": spl_tokens,
                "connected": True,
            })
        except Exception as e:
            self._send_json({"error": str(e), "connected": False}, 500)

    def _handle_wallet_transactions(self):
        """Get recent wallet transactions."""
        try:
            # Read from sniper trade log if available
            trade_log = ROOT / "data" / "sniper" / "trade_log.jsonl"
            transactions = []
            
            if trade_log.exists():
                lines = trade_log.read_text().strip().split("\n")
                for line in reversed(lines[-50:]):  # Last 50 trades
                    try:
                        tx = json.loads(line)
                        transactions.append({
                            "symbol": tx.get("symbol", "?"),
                            "type": "sell" if tx.get("pnl_usd", 0) != 0 else "buy",
                            "amount_usd": abs(tx.get("pnl_usd", 0)),
                            "pnl_pct": tx.get("pnl_pct", 0),
                            "reason": tx.get("reason", ""),
                            "timestamp": tx.get("timestamp", 0),
                            "is_paper": tx.get("is_paper", True),
                        })
                    except Exception:
                        continue
            
            self._send_json({"transactions": transactions})
        except Exception as e:
            self._send_json({"error": str(e), "transactions": []}, 500)

    def _handle_sniper_status(self):
        """Get micro-cap sniper status and state."""
        try:
            from core import micro_cap_sniper
            
            sniper = micro_cap_sniper.get_sniper()
            status = sniper.get_status()
            state = sniper.state.to_dict()
            
            self._send_json({
                **status,
                "state": state,
                "config": sniper.config.to_dict(),
            })
        except Exception as e:
            self._send_json({
                "error": str(e),
                "strategy": "MicroCapSniper",
                "mode": "OFFLINE",
            }, 500)

    def _handle_sniper_config_get(self):
        """Get sniper configuration."""
        try:
            from core import micro_cap_sniper
            sniper = micro_cap_sniper.get_sniper()
            self._send_json(sniper.config.to_dict())
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_sniper_config_set(self):
        """Update sniper configuration."""
        body = self._read_body()
        try:
            from core import micro_cap_sniper
            sniper = micro_cap_sniper.get_sniper()
            
            # Update allowed config fields
            allowed = ["take_profit_pct", "stop_loss_pct", "max_hold_minutes", 
                      "min_liquidity_usd", "is_paper", "require_approval"]
            for key in allowed:
                if key in body:
                    setattr(sniper.config, key, body[key])
            
            self._send_json({"success": True, "config": sniper.config.to_dict()})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_scan_history(self):
        """Get historical scan results."""
        try:
            trade_log = ROOT / "data" / "sniper" / "trade_log.jsonl"
            scans = []
            
            if trade_log.exists():
                lines = trade_log.read_text().strip().split("\n")
                for line in reversed(lines[-100:]):
                    try:
                        tx = json.loads(line)
                        scans.append({
                            "mint": tx.get("mint", ""),
                            "symbol": tx.get("symbol", "?"),
                            "entry_price": tx.get("entry_price", 0),
                            "exit_price": tx.get("exit_price", 0),
                            "pnl_usd": tx.get("pnl_usd", 0),
                            "pnl_pct": tx.get("pnl_pct", 0),
                            "reason": tx.get("reason", ""),
                            "is_paper": tx.get("is_paper", True),
                            "timestamp": tx.get("timestamp", 0),
                        })
                    except Exception:
                        continue
            
            # Also try to get last scan candidates
            candidates_file = ROOT / "data" / "sniper" / "last_scan.json"
            last_scan = None
            if candidates_file.exists():
                try:
                    last_scan = json.loads(candidates_file.read_text())
                except Exception:
                    pass
            
            self._send_json({
                "trades": scans,
                "last_scan": last_scan,
                "total_trades": len(scans),
            })
        except Exception as e:
            self._send_json({"error": str(e), "trades": []}, 500)

    def _handle_trending_momentum(self):
        """Get trending tokens with momentum signals."""
        try:
            tokens = []
            
            # Try DexScreener first
            try:
                from core import dexscreener
                momentum = dexscreener.get_momentum_tokens(limit=30)
                for pair in momentum:
                    tokens.append({
                        "symbol": pair.base_token_symbol,
                        "name": pair.base_token_name,
                        "address": pair.base_token_address,
                        "price": pair.price_usd,
                        "price_change_5m": pair.price_change_5m,
                        "price_change_1h": pair.price_change_1h,
                        "price_change_24h": pair.price_change_24h,
                        "volume_24h": pair.volume_24h,
                        "liquidity": pair.liquidity_usd,
                        "source": "dexscreener",
                    })
            except Exception:
                pass
            
            # Try BirdEye trending
            if not tokens:
                try:
                    from core import birdeye
                    trending = birdeye.fetch_trending_tokens(limit=30)
                    if trending and "tokens" in trending:
                        for t in trending["tokens"]:
                            tokens.append({
                                "symbol": t.get("symbol", ""),
                                "name": t.get("name", ""),
                                "address": t.get("address", ""),
                                "price": t.get("price", 0),
                                "price_change_24h": t.get("priceChange24h", 0),
                                "volume_24h": t.get("volume24h", 0),
                                "liquidity": t.get("liquidity", 0),
                                "source": "birdeye",
                            })
                except Exception:
                    pass
            
            self._send_json({
                "tokens": tokens,
                "count": len(tokens),
                "updated_at": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            self._send_json({"error": str(e), "tokens": []}, 500)

    def _handle_jarvis_chat(self):
        """Handle chat message to Jarvis."""
        body = self._read_body()
        message = body.get("message", "")
        
        if not message:
            self._send_json({"error": "No message provided"}, 400)
            return
        
        try:
            # Use the conversation module
            response = conversation.generate_response(message, "")
            
            self._send_json({
                "response": response,
                "timestamp": time.time(),
            })
        except Exception as e:
            self._send_json({"response": f"Error: {str(e)}"}, 500)

    def _handle_jarvis_status(self):
        """Get Jarvis system status and capabilities."""
        try:
            current_state = state.read_state()
            
            # Get uptime
            import os
            import psutil
            process = psutil.Process(os.getpid())
            uptime_seconds = time.time() - process.create_time()
            
            # Format uptime
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            uptime_str = f"{hours}h {minutes}m"
            
            # Get provider status
            provider_health = providers.provider_health_check()
            
            self._send_json({
                "name": "Jarvis",
                "version": "2.2.0",
                "status": "online",
                "uptime": uptime_str,
                "uptime_seconds": int(uptime_seconds),
                "daemon_running": current_state.get("daemon_running", False),
                "voice_enabled": current_state.get("voice_enabled", False),
                "mic_status": current_state.get("mic_status", "off"),
                "available_providers": provider_health.get("available_providers", []),
                "last_llm_provider": current_state.get("last_llm_provider", ""),
                "capabilities": [
                    "trading", "research", "voice", "automation",
                    "solana", "scanning", "backtesting"
                ],
            })
        except Exception as e:
            self._send_json({
                "name": "Jarvis",
                "status": "error",
                "error": str(e),
            }, 500)

    def _handle_system_info(self):
        """Get computer system information."""
        try:
            import psutil
            import platform
            
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            
            # Network stats
            net = psutil.net_io_counters()
            
            self._send_json({
                "os": platform.system(),
                "os_version": platform.version(),
                "machine": platform.machine(),
                "cpu": {
                    "percent": cpu_percent,
                    "cores": psutil.cpu_count(),
                    "cores_physical": psutil.cpu_count(logical=False),
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "percent_used": memory.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent_used": round(disk.percent, 1),
                },
                "network": {
                    "bytes_sent": net.bytes_sent,
                    "bytes_recv": net.bytes_recv,
                },
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    # =========================================================================
    # Phase 1 Enhancement: Live Position Monitoring + DeFi Tools
    # =========================================================================

    def _handle_position_active(self):
        """Get active position with live price data."""
        try:
            position_file = ROOT / "data" / "active_position.json"
            sniper_state = ROOT / "data" / "sniper" / "sniper_state.json"
            
            position = None
            source = "none"
            
            # Check active_position.json first (from position_monitor)
            if position_file.exists():
                try:
                    position = json.loads(position_file.read_text())
                    source = "position_monitor"
                except Exception:
                    pass
            
            # Also check sniper state
            if not position and sniper_state.exists():
                try:
                    state = json.loads(sniper_state.read_text())
                    if state.get("active_position"):
                        position = state["active_position"]
                        source = "sniper"
                except Exception:
                    pass
            
            if not position:
                self._send_json({
                    "has_position": False,
                    "position": None,
                })
                return
            
            # Fetch live price from DexScreener
            mint = position.get("mint", "")
            entry_price = position.get("entry_price", 0)
            tp_price = position.get("take_profit_price") or position.get("tp_price", 0)
            sl_price = position.get("stop_loss_price") or position.get("sl_price", 0)
            
            current_price = entry_price  # Default to entry if can't fetch
            try:
                import urllib.request
                url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = json.loads(resp.read())
                    if data.get("pairs"):
                        for pair in data["pairs"]:
                            if pair.get("chainId") == "solana":
                                current_price = float(pair.get("priceUsd", entry_price))
                                break
            except Exception:
                pass
            
            # Calculate P&L
            pnl_pct = ((current_price - entry_price) / entry_price) if entry_price > 0 else 0
            pnl_usd = (current_price - entry_price) * position.get("quantity", 0)
            
            # Time in position
            entry_time = position.get("entry_time", time.time())
            time_held_minutes = (time.time() - entry_time) / 60
            
            self._send_json({
                "has_position": True,
                "source": source,
                "mint": mint,
                "symbol": position.get("symbol", "?"),
                "entry_price": entry_price,
                "current_price": current_price,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "quantity": position.get("quantity", 0),
                "position_usd": position.get("position_usd", 0),
                "pnl_pct": round(pnl_pct * 100, 2),
                "pnl_usd": round(pnl_usd, 4),
                "time_held_minutes": round(time_held_minutes, 1),
                "is_paper": position.get("is_paper", True),
                "max_hold_until": position.get("max_hold_until"),
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_position_exit(self):
        """Manually exit current position."""
        body = self._read_body()
        reason = body.get("reason", "MANUAL_EXIT")
        
        try:
            position_file = ROOT / "data" / "active_position.json"
            sniper_state = ROOT / "data" / "sniper" / "sniper_state.json"
            
            # Check which position source exists
            if position_file.exists():
                position = json.loads(position_file.read_text())
                
                # For paper trades, just clear the file
                if position.get("is_paper", True):
                    position_file.unlink()
                    self._send_json({
                        "success": True,
                        "reason": reason,
                        "message": "Paper position closed"
                    })
                else:
                    # Live exit would need actual swap execution
                    self._send_json({
                        "success": False,
                        "error": "Live exit not implemented via API"
                    }, 501)
                return
            
            # Try sniper state
            if sniper_state.exists():
                from core import micro_cap_sniper
                sniper = micro_cap_sniper.get_sniper()
                
                if sniper.state.active_position:
                    # Get current price and record exit
                    mint = sniper.state.active_position.get("mint", "")
                    entry_price = sniper.state.active_position.get("entry_price", 0)
                    
                    # Fetch current price
                    current_price = entry_price
                    try:
                        import urllib.request
                        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
                        with urllib.request.urlopen(url, timeout=5) as resp:
                            data = json.loads(resp.read())
                            if data.get("pairs"):
                                for pair in data["pairs"]:
                                    if pair.get("chainId") == "solana":
                                        current_price = float(pair.get("priceUsd", entry_price))
                                        break
                    except Exception:
                        pass
                    
                    trade_record = sniper.record_exit(reason, current_price)
                    self._send_json({
                        "success": True,
                        "reason": reason,
                        "trade": trade_record,
                    })
                else:
                    self._send_json({"error": "No active position"}, 400)
            else:
                self._send_json({"error": "No active position found"}, 400)
                
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_tools_token(self, mint: str):
        """Get detailed token information."""
        try:
            token_data = {
                "mint": mint,
                "symbol": None,
                "name": None,
                "price": None,
                "price_change_24h": None,
                "volume_24h": None,
                "liquidity": None,
                "market_cap": None,
                "holders": None,
                "created_at": None,
            }
            
            # Try DexScreener first
            try:
                import urllib.request
                url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read())
                    if data.get("pairs"):
                        for pair in data["pairs"]:
                            if pair.get("chainId") == "solana":
                                token_data.update({
                                    "symbol": pair.get("baseToken", {}).get("symbol"),
                                    "name": pair.get("baseToken", {}).get("name"),
                                    "price": float(pair.get("priceUsd", 0)),
                                    "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0)),
                                    "volume_24h": float(pair.get("volume", {}).get("h24", 0)),
                                    "liquidity": float(pair.get("liquidity", {}).get("usd", 0)),
                                    "market_cap": pair.get("fdv"),
                                    "dex": pair.get("dexId"),
                                    "pair_address": pair.get("pairAddress"),
                                })
                                break
            except Exception as e:
                token_data["dexscreener_error"] = str(e)
            
            # Try BirdEye for additional data
            try:
                from core import birdeye
                overview = birdeye.fetch_token_overview(mint)
                if overview:
                    token_data["holders"] = overview.get("holder")
                    if not token_data["symbol"]:
                        token_data["symbol"] = overview.get("symbol")
                    if not token_data["name"]:
                        token_data["name"] = overview.get("name")
            except Exception:
                pass
            
            self._send_json(token_data)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_tools_rugcheck(self, mint: str):
        """Check token for rug pull risk indicators."""
        try:
            # Try the rugcheck module if available
            rug_data = {
                "mint": mint,
                "risk_score": None,
                "risk_level": "unknown",
                "warnings": [],
                "details": {},
            }
            
            try:
                from core import rugcheck
                result = rugcheck.check_token(mint)
                if result:
                    rug_data.update({
                        "risk_score": result.get("score", 0),
                        "risk_level": result.get("risk_level", "unknown"),
                        "warnings": result.get("warnings", []),
                        "details": result,
                    })
            except ImportError:
                # Fallback: basic checks from DexScreener data
                try:
                    import urllib.request
                    url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
                    with urllib.request.urlopen(url, timeout=10) as resp:
                        data = json.loads(resp.read())
                        if data.get("pairs"):
                            pair = None
                            for p in data["pairs"]:
                                if p.get("chainId") == "solana":
                                    pair = p
                                    break
                            
                            if pair:
                                warnings = []
                                liquidity = float(pair.get("liquidity", {}).get("usd", 0))
                                volume = float(pair.get("volume", {}).get("h24", 0))
                                
                                if liquidity < 10000:
                                    warnings.append("Low liquidity (<$10K)")
                                if liquidity < 50000:
                                    warnings.append("Moderate liquidity risk")
                                if volume < 50000:
                                    warnings.append("Low 24h volume")
                                
                                # Simple risk scoring
                                risk_score = 0
                                if liquidity < 10000: risk_score += 40
                                elif liquidity < 50000: risk_score += 20
                                if volume < 50000: risk_score += 20
                                if volume < 10000: risk_score += 20
                                
                                risk_level = "low"
                                if risk_score >= 60: risk_level = "high"
                                elif risk_score >= 30: risk_level = "medium"
                                
                                rug_data.update({
                                    "risk_score": risk_score,
                                    "risk_level": risk_level,
                                    "warnings": warnings,
                                    "details": {
                                        "liquidity_usd": liquidity,
                                        "volume_24h": volume,
                                        "symbol": pair.get("baseToken", {}).get("symbol"),
                                    }
                                })
                except Exception as e:
                    rug_data["error"] = str(e)
            except Exception as e:
                rug_data["error"] = str(e)
            
            self._send_json(rug_data)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_chart(self, mint: str):
        """Get OHLCV chart data for a token."""
        try:
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            
            timeframe = params.get("timeframe", ["15m"])[0]
            limit = int(params.get("limit", ["100"])[0])
            
            # Try BirdEye first
            try:
                from core import birdeye
                ohlcv = birdeye.fetch_ohlcv(mint, timeframe=timeframe, limit=limit)
                if ohlcv:
                    candles = birdeye.normalize_ohlcv(ohlcv)
                    self._send_json({
                        "success": True,
                        "mint": mint,
                        "timeframe": timeframe,
                        "candles": candles,
                        "source": "birdeye"
                    })
                    return
            except Exception as e:
                logger.warning(f"BirdEye OHLCV failed: {e}")
            
            # Fallback to DexScreener for price history
            try:
                import urllib.request
                url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
                req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    pairs = data.get("pairs", [])
                    if pairs:
                        pair = pairs[0]
                        # DexScreener doesn't provide full OHLCV, generate synthetic
                        current_price = float(pair.get("priceUsd", 0))
                        price_change = float(pair.get("priceChange", {}).get("h24", 0))
                        
                        # Generate synthetic candles based on price change
                        import time as time_module
                        now = int(time_module.time())
                        candles = []
                        
                        # Simple model: linear interpolation from 24h ago
                        old_price = current_price / (1 + price_change / 100) if price_change != -100 else current_price
                        
                        for i in range(min(limit, 96)):  # Max 96 15-min candles (24h)
                            t = now - (i * 900)  # 15 min intervals
                            progress = i / 96
                            price = old_price + (current_price - old_price) * (1 - progress)
                            variance = price * 0.002  # 0.2% variance
                            import random
                            candles.append({
                                "timestamp": t,
                                "open": price + random.uniform(-variance, variance),
                                "high": price + random.uniform(0, variance * 2),
                                "low": price - random.uniform(0, variance * 2),
                                "close": price + random.uniform(-variance, variance),
                                "volume": 0
                            })
                        
                        candles.reverse()
                        self._send_json({
                            "success": True,
                            "mint": mint,
                            "timeframe": timeframe,
                            "candles": candles,
                            "source": "dexscreener_synthetic"
                        })
                        return
            except Exception as e:
                logger.warning(f"DexScreener fallback failed: {e}")
            
            self._send_json({"success": False, "error": "No chart data available"})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_strategies_list(self):
        """Get list of all 81 trading strategies."""
        try:
            strategies = []
            catalog_path = ROOT / "data" / "notion_deep" / "strategy_catalog.json"
            
            if catalog_path.exists():
                with open(catalog_path) as f:
                    catalog = json.load(f)
                    strategies = catalog.get("strategies", [])
            else:
                # Return sample strategies if catalog doesn't exist
                strategies = [
                    {"id": "STRAT-001", "name": "200-Day MA Long", "category": "Trend Following", "status": "active"},
                    {"id": "STRAT-002", "name": "RSI Mean Reversion", "category": "Mean Reversion", "status": "testing"},
                    {"id": "STRAT-003", "name": "Funding Rate Arb", "category": "Carry", "status": "active"},
                    {"id": "STRAT-004", "name": "Breakout Volume", "category": "Breakout", "status": "testing"},
                    {"id": "STRAT-005", "name": "Momentum Rankings", "category": "Cross-Sectional", "status": "pending"},
                ]
            
            self._send_json({"strategies": strategies, "count": len(strategies)})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_trade(self):
        """Execute a trade with TP/SL."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length)) if content_length else {}
            
            mint = body.get("mint")
            side = body.get("side", "buy")  # buy or sell
            amount_sol = body.get("amount_sol", 0)
            tp_pct = body.get("tp_pct", 20)  # Take profit %
            sl_pct = body.get("sl_pct", 10)  # Stop loss %
            
            if not mint or amount_sol <= 0:
                self._send_json({"error": "Invalid trade parameters"}, 400)
                return
            
            # For now, simulate the trade (paper trading)
            import time as time_module
            trade_id = f"TRADE-{int(time_module.time())}"
            
            # Get current price
            current_price = 0
            try:
                import urllib.request
                url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
                req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    pairs = data.get("pairs", [])
                    if pairs:
                        current_price = float(pairs[0].get("priceUsd", 0))
            except Exception:
                pass
            
            tp_price = current_price * (1 + tp_pct / 100)
            sl_price = current_price * (1 - sl_pct / 100)
            
            result = {
                "success": True,
                "trade_id": trade_id,
                "side": side,
                "mint": mint,
                "amount_sol": amount_sol,
                "entry_price": current_price,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "tp_pct": tp_pct,
                "sl_pct": sl_pct,
                "status": "paper",
                "message": "Trade simulated (paper mode)"
            }
            
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)


def run_server(port: int = PORT):

    """Run the API server."""
    server = HTTPServer(("0.0.0.0", port), JarvisAPIHandler)
    print(f"Jarvis API server running on http://localhost:{port}")
    server.serve_forever()



def start_server_thread(port: int = PORT) -> threading.Thread:
    """Start the API server in a background thread."""
    thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    run_server()

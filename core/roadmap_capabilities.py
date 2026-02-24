"""
Capability-driven roadmap status builder.

Generates feature states for the roadmap page based on lightweight,
deterministic probes of available backend/frontend capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]

STATE_CATALOG: Dict[str, Dict[str, Any]] = {
    "live": {"label": "Live", "score": 1.0},
    "backend_only": {"label": "Backend-only", "score": 0.75},
    "prototype": {"label": "Prototype", "score": 0.5},
    "mock": {"label": "Mock", "score": 0.25},
    "planned": {"label": "Planned", "score": 0.0},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Probe:
    def __init__(self, root: Path):
        self.root = root
        self._text_cache: Dict[str, str] = {}

    def _path(self, relative_path: str) -> Path:
        return self.root / relative_path

    def exists(self, relative_path: str) -> bool:
        return self._path(relative_path).exists()

    def contains(self, relative_path: str, pattern: str) -> bool:
        text = self.read_text(relative_path)
        return bool(text and pattern in text)

    def contains_any(self, relative_path: str, patterns: List[str]) -> bool:
        text = self.read_text(relative_path)
        if not text:
            return False
        return any(p in text for p in patterns)

    def read_text(self, relative_path: str) -> str:
        if relative_path in self._text_cache:
            return self._text_cache[relative_path]
        path = self._path(relative_path)
        if not path.exists():
            self._text_cache[relative_path] = ""
            return ""
        try:
            value = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            value = ""
        self._text_cache[relative_path] = value
        return value


FeatureState = Tuple[str, List[str], str | None]
FeatureProbe = Callable[[Probe], FeatureState]


@dataclass(frozen=True)
class FeatureDefinition:
    key: str
    name: str
    description: str
    probe: FeatureProbe


@dataclass(frozen=True)
class PhaseDefinition:
    id: int
    title: str
    features: List[FeatureDefinition]


def _state(state: str, evidence: List[str], note: str | None = None) -> FeatureState:
    return state, evidence, note


def _charts_state(probe: Probe) -> FeatureState:
    path = "frontend/src/components/trading/TradingChart.jsx"
    if probe.exists(path):
        return _state("live", [path], "Primary trading chart is implemented in the production trading surface.")
    return _state("planned", [])


def _order_panel_state(probe: Probe) -> FeatureState:
    primary_ui_paths = [
        "frontend/src/components/OrderPanel.jsx",
        "frontend/src/components/trading/OrderPanel.jsx",
    ]
    mock_ui_path = "frontend/src/components/orders/LimitOrderManager.jsx"
    api_path = "api/fastapi_app.py"

    if any(probe.contains(path, "/api/trade") for path in primary_ui_paths) and probe.contains(api_path, "/api/trade"):
        return _state(
            "live",
            primary_ui_paths + [api_path],
            "Primary order-panel UI is wired to the paper-trade backend contract.",
        )

    if probe.contains_any(mock_ui_path, ["Generate mock orders", "Math.random"]):
        return _state("mock", [mock_ui_path], "Order panel contains simulated order data.")

    if any(probe.exists(path) for path in primary_ui_paths + [mock_ui_path]):
        return _state(
            "prototype",
            [path for path in primary_ui_paths + [mock_ui_path] if probe.exists(path)],
            "Order panel exists but lacks verified backend execution wiring.",
        )
    return _state("planned", [])


def _order_book_state(probe: Probe) -> FeatureState:
    paths = [
        "frontend/src/components/depth/DepthChart.jsx",
        "frontend/src/components/dom/DepthOfMarket.jsx",
    ]
    if any(probe.contains(path, "/api/market/depth") for path in paths):
        return _state("live", paths, "Order-book components consume live backend depth snapshots.")
    for path in paths:
        if probe.contains(path, "Math.random"):
            return _state("mock", [path], "Depth/order-book data is simulated.")
    if any(probe.exists(path) for path in paths):
        return _state("prototype", paths, "Order-book components exist but are not proven with live feed evidence.")
    return _state("planned", [])


def _auto_trading_state(probe: Probe) -> FeatureState:
    evidence = []
    for path in ["core/trading_coliseum.py", "bots/public_trading_bot_supervisor.py"]:
        if probe.exists(path):
            evidence.append(path)
    if evidence and probe.contains("api/fastapi_app.py", "/api/sentinel/status"):
        return _state("live", evidence + ["api/fastapi_app.py"], "Sentinel status API exposes auto-trading control-plane visibility.")
    if evidence:
        return _state("backend_only", evidence, "Auto-trading orchestration exists in backend modules.")
    return _state("planned", [])


def _coliseum_state(probe: Probe) -> FeatureState:
    path = "core/trading_coliseum.py"
    api_path = "api/fastapi_app.py"
    ui_path = "frontend/src/pages/AIControlPlane.jsx"
    if probe.exists(path) and probe.contains(api_path, "/api/sentinel/coliseum"):
        evidence = [path, api_path]
        if probe.contains(ui_path, "/api/sentinel/coliseum"):
            evidence.append(ui_path)
            return _state("live", evidence, "Coliseum summary is exposed through API and surfaced in operator UI.")
        return _state("backend_only", evidence, "Coliseum summary endpoint is available but UI wiring is partial.")

    if probe.exists(path):
        return _state("backend_only", [path], "Coliseum engine exists in backend; UI evidence remains limited.")
    return _state("planned", [])


def _approval_gate_state(probe: Probe) -> FeatureState:
    evidence = []
    for path in ["core/approval_gate.py", "jarvis-sniper/src/app/api/investments/decisions/route.ts"]:
        if probe.exists(path):
            evidence.append(path)
    if probe.contains("api/fastapi_app.py", "/api/sentinel/approvals/pending"):
        return _state("live", evidence + ["api/fastapi_app.py"], "Approval-gate endpoints are available for web control surfaces.")
    if evidence:
        return _state("backend_only", evidence, "Approval gate capability exists but is not unified in roadmap UI.")
    return _state("planned", [])


def _kill_switch_state(probe: Probe) -> FeatureState:
    evidence = []
    for path in ["core/trading/emergency_stop.py", "jarvis-sniper/src/app/api/investments/kill-switch/route.ts"]:
        if probe.exists(path):
            evidence.append(path)
    if probe.contains("api/fastapi_app.py", "/api/sentinel/kill-switch/activate"):
        return _state("live", evidence + ["api/fastapi_app.py"], "Kill-switch APIs are exposed for operator control.")
    if evidence:
        return _state("backend_only", evidence, "Kill-switch capability exists on backend routes/primitives.")
    return _state("planned", [])


def _signal_aggregator_state(probe: Probe) -> FeatureState:
    api_path = "api/fastapi_app.py"
    ui_path = "frontend/src/pages/AIControlPlane.jsx"
    evidence = []
    for path in ["core/signal_aggregator.py", "core/signals/signal_aggregator.py"]:
        if probe.exists(path):
            evidence.append(path)
    if evidence and probe.contains(api_path, "/api/intel/signal-aggregator"):
        live_evidence = evidence + [api_path]
        if probe.contains(ui_path, "/api/intel/signal-aggregator"):
            live_evidence.append(ui_path)
            return _state("live", live_evidence, "Signal aggregator feed is exposed and rendered in operator UI.")
        return _state("backend_only", live_evidence, "Signal aggregator endpoint exists but UI wiring is partial.")
    if evidence:
        return _state("backend_only", evidence, "Signal aggregation is implemented in backend modules.")
    return _state("planned", [])


def _smart_money_state(probe: Probe) -> FeatureState:
    ui_path = "frontend/src/components/smartmoney/SmartMoneyTracker.jsx"
    if probe.contains(ui_path, "/api/intel/smart-money"):
        return _state("live", [ui_path, "api/fastapi_app.py"], "Smart Money panel is connected to backend feed endpoints.")
    if probe.contains(ui_path, "mockSmartWallets"):
        return _state("mock", [ui_path], "Smart Money UI currently uses static mock wallet datasets.")
    if probe.exists(ui_path):
        return _state("prototype", [ui_path], "Smart Money UI exists but lacks explicit live provenance.")
    return _state("planned", [])


def _sentiment_state(probe: Probe) -> FeatureState:
    ui_path = "frontend/src/components/social/SocialSentiment.jsx"
    if probe.contains(ui_path, "/api/intel/sentiment"):
        return _state("live", [ui_path, "api/fastapi_app.py"], "Sentiment panel is connected to backend sentiment feed endpoints.")
    if probe.contains(ui_path, "MOCK_TOKEN_SENTIMENT"):
        return _state("mock", [ui_path], "Sentiment UI currently uses mock social datasets.")

    backend_path = "core/sentiment_aggregator.py"
    if probe.exists(backend_path):
        return _state("backend_only", [backend_path], "Sentiment aggregation exists in backend modules.")
    return _state("planned", [])


def _ml_regime_state(probe: Probe) -> FeatureState:
    path = "core/ml_regime_detector.py"
    api_path = "api/fastapi_app.py"
    ui_path = "frontend/src/pages/AIControlPlane.jsx"
    if probe.exists(path) and probe.contains(api_path, "/api/intel/ml-regime"):
        evidence = [path, api_path]
        if probe.contains(ui_path, "/api/intel/ml-regime"):
            evidence.append(ui_path)
            return _state("live", evidence, "ML regime endpoint is exposed and rendered in operator UI.")
        return _state("backend_only", evidence, "ML regime endpoint exists but UI wiring is partial.")
    if probe.exists(path):
        return _state("backend_only", [path], "ML regime detection exists in backend.")
    return _state("planned", [])


def _voice_trading_state(probe: Probe) -> FeatureState:
    api_path = "api/fastapi_app.py"
    ui_path = "frontend/src/pages/AIControlPlane.jsx"
    evidence = []
    for path in ["core/voice/trading_commands.py", "api/fastapi_app.py"]:
        if probe.exists(path):
            evidence.append(path)
    if evidence and probe.contains(api_path, "/api/lifeos/voice/status"):
        live_evidence = evidence + [api_path]
        if probe.contains(ui_path, "/api/lifeos/voice/status"):
            live_evidence.append(ui_path)
            return _state("live", live_evidence, "Voice readiness endpoint is exposed and rendered in operator UI.")
        return _state("backend_only", live_evidence, "Voice readiness endpoint exists but UI wiring is partial.")
    if evidence:
        return _state("backend_only", evidence, "Voice command support exists; roadmap-grade operator UX still pending.")
    return _state("planned", [])


def _mirror_test_state(probe: Probe) -> FeatureState:
    candidates = [
        "jobs/mirror_test.py",
        "core/mirror_test_engine.py",
        "scripts/mirror_test.py",
        "core/self_improvement_engine_v2.py",
    ]
    api_path = "api/fastapi_app.py"
    ui_path = "frontend/src/pages/AIControlPlane.jsx"
    evidence = [path for path in candidates if probe.exists(path)]
    if evidence and probe.contains(api_path, "/api/lifeos/mirror/status"):
        live_evidence = evidence + [api_path]
        if probe.contains(ui_path, "/api/lifeos/mirror/status"):
            live_evidence.append(ui_path)
            return _state("live", live_evidence, "Mirror Test telemetry is available in API and surfaced in operator UI.")
        return _state("backend_only", live_evidence, "Mirror Test endpoint exists; operator UI coverage is partial.")
    if evidence:
        return _state("backend_only", evidence, "Mirror/self-correction capability exists outside unified roadmap UI.")
    return _state("planned", [])


def _knowledge_state(probe: Probe) -> FeatureState:
    api_path = "api/fastapi_app.py"
    ui_path = "frontend/src/pages/AIControlPlane.jsx"
    evidence = []
    for path in ["bots/shared/supermemory_client.py", "bots/shared/knowledge_graph.py", "core/trading_knowledge.py"]:
        if probe.exists(path):
            evidence.append(path)
    if evidence and probe.contains(api_path, "/api/lifeos/knowledge/status"):
        live_evidence = evidence + [api_path]
        if probe.contains(ui_path, "/api/lifeos/knowledge/status"):
            live_evidence.append(ui_path)
            return _state("live", live_evidence, "Knowledge readiness endpoint is exposed and rendered in operator UI.")
        return _state("backend_only", live_evidence, "Knowledge endpoint exists but UI wiring is partial.")
    if evidence:
        return _state("backend_only", evidence, "Knowledge and memory primitives exist in backend services.")
    return _state("planned", [])


def _mev_dashboard_state(probe: Probe) -> FeatureState:
    ui_path = "frontend/src/components/mev/MEVDetector.jsx"
    api_path = "api/fastapi_app.py"
    ai_control_path = "frontend/src/pages/AIControlPlane.jsx"
    if probe.contains(api_path, "/api/advanced/mev") and (
        probe.contains(ui_path, "/api/advanced/mev")
        or probe.contains(ai_control_path, "/api/advanced/mev")
    ):
        return _state(
            "live",
            [ui_path, api_path, ai_control_path],
            "MEV dashboard is backed by live API data and operator control-plane wiring.",
        )
    if probe.contains_any(ui_path, ["Generate mock MEV events", "Math.random"]):
        return _state("mock", [ui_path], "MEV panel currently simulates events.")
    if probe.exists(ui_path):
        return _state("prototype", [ui_path], "MEV panel exists but lacks verified live feed evidence.")
    return _state("planned", [])


def _perps_state(probe: Probe) -> FeatureState:
    ui_path = "frontend/src/components/perps/PerpsSniper.tsx"
    api_path = "api/fastapi_app.py"
    ai_control_path = "frontend/src/pages/AIControlPlane.jsx"
    if (
        probe.contains(api_path, "/api/advanced/perps/status")
        and not probe.contains(ui_path, "Prototype preview only")
        and (
            probe.contains(ui_path, "/api/advanced/perps/status")
            or probe.contains(ai_control_path, "/api/advanced/perps/status")
        )
    ):
        return _state(
            "live",
            [ui_path, api_path, ai_control_path],
            "Perps surface is promoted with production-readiness API and operator visibility.",
        )
    if probe.contains(ui_path, "Prototype preview only"):
        return _state("prototype", [ui_path], "Perps panel explicitly marked as prototype.")

    evidence = []
    for path in [ui_path, "frontend/src/components/perps/usePerpsData.ts", "web/perps_api.py"]:
        if probe.exists(path):
            evidence.append(path)
    if len(evidence) >= 2:
        return _state("backend_only", evidence, "Perps backend/data flow exists; production UX promotion remains pending.")
    return _state("planned", [])


def _multi_dex_state(probe: Probe) -> FeatureState:
    api_path = "api/fastapi_app.py"
    ui_path = "frontend/src/components/dex/DEXAnalytics.jsx"
    ai_control_path = "frontend/src/pages/AIControlPlane.jsx"
    if probe.contains(api_path, "/api/advanced/multi-dex") and (
        probe.contains(ui_path, "/api/advanced/multi-dex")
        or probe.contains(ai_control_path, "/api/advanced/multi-dex")
    ):
        return _state(
            "live",
            ["core/jupiter_api.py", ui_path, api_path, ai_control_path],
            "Multi-DEX route comparison is API-backed and surfaced in operator UI.",
        )

    evidence = []
    for path in ["core/jupiter_api.py", ui_path]:
        if probe.exists(path):
            evidence.append(path)
    if evidence:
        return _state("backend_only", evidence, "Multi-DEX primitives exist but unified production routing is incomplete.")
    return _state("planned", [])


def _analytics_state(probe: Probe) -> FeatureState:
    ui_path = "frontend/src/components/analytics/PortfolioAnalytics.jsx"
    api_path = "api/fastapi_app.py"
    if probe.contains(ui_path, "/api/analytics/portfolio") and probe.contains(api_path, "/api/analytics/portfolio"):
        return _state(
            "live",
            [ui_path, api_path],
            "Portfolio analytics panel consumes dedicated backend analytics endpoint.",
        )
    if probe.exists(ui_path):
        return _state("prototype", [ui_path], "Analytics UI exists; roadmap evidence gating is still pending.")
    return _state("planned", [])


def _performance_state(probe: Probe) -> FeatureState:
    evidence = ["api/middleware/compression.py", "api/middleware/timeout.py"]
    api_path = "api/fastapi_app.py"
    ui_path = "frontend/src/pages/AIControlPlane.jsx"
    if all(probe.exists(path) for path in evidence) and probe.contains(api_path, "/api/runtime/capabilities"):
        full_evidence = evidence + [api_path]
        if probe.contains(ui_path, "/api/runtime/capabilities"):
            full_evidence.append(ui_path)
            return _state("live", full_evidence, "Runtime capability telemetry is exposed and visible in operator UI.")
        return _state("backend_only", full_evidence, "Runtime capability telemetry endpoint exists without UI evidence.")
    if all(probe.exists(path) for path in evidence):
        return _state("backend_only", evidence)
    return _state("planned", [])


def _mobile_state(probe: Probe) -> FeatureState:
    evidence = []
    for path in ["frontend/src/components/MobileNav.jsx", "frontend/src/components/ResponsiveLayout.jsx"]:
        if probe.exists(path):
            evidence.append(path)
    if evidence and probe.contains("frontend/src/components/MainLayout.jsx", "MobileNav"):
        return _state(
            "live",
            evidence + ["frontend/src/components/MainLayout.jsx"],
            "Mobile navigation is integrated into the primary application layout.",
        )
    if evidence:
        return _state("prototype", evidence, "Responsive/mobile scaffolding exists but acceptance gating is incomplete.")
    return _state("planned", [])


def _themes_state(probe: Probe) -> FeatureState:
    evidence = [
        "frontend/src/contexts/ThemeContext.jsx",
        "frontend/src/styles/tokens.css",
    ]
    if all(probe.exists(path) for path in evidence):
        full_evidence = evidence.copy()
        if probe.contains("frontend/src/main.jsx", "ThemeProvider"):
            full_evidence.append("frontend/src/main.jsx")
        if probe.contains("frontend/src/components/MainLayout.jsx", "ThemeToggle"):
            full_evidence.append("frontend/src/components/MainLayout.jsx")
            return _state("live", full_evidence, "Theme provider and toggle are wired in the main UI.")
        return _state("backend_only", full_evidence, "Theme primitives exist but toggle wiring is incomplete.")
    return _state("planned", [])


def _onboarding_state(probe: Probe) -> FeatureState:
    coach_path = "frontend/src/components/onboarding/OnboardingCoach.jsx"
    layout_path = "frontend/src/components/MainLayout.jsx"
    if probe.exists(coach_path) and probe.contains(layout_path, "OnboardingCoach"):
        return _state("live", [coach_path, layout_path], "Onboarding coach is embedded in the primary layout.")
    if probe.exists(coach_path):
        return _state("prototype", [coach_path])
    return _state("planned", [])


PHASES: List[PhaseDefinition] = [
    PhaseDefinition(
        id=1,
        title="Trading Core",
        features=[
            FeatureDefinition("charts", "Charts", "TradingView with real-time candles", _charts_state),
            FeatureDefinition("order_panel", "Order Panel", "Buy/Sell with TP/SL, position sizing", _order_panel_state),
            FeatureDefinition("order_book", "Order Book", "Live depth, whale alerts, spread", _order_book_state),
        ],
    ),
    PhaseDefinition(
        id=2,
        title="Sentinel Mode",
        features=[
            FeatureDefinition(
                "auto_trading",
                "Auto-Trading",
                "Master toggle, phase indicator (Trial -> Savage)",
                _auto_trading_state,
            ),
            FeatureDefinition("coliseum", "Coliseum", "81 strategies grid with live backtest results", _coliseum_state),
            FeatureDefinition(
                "approval_gate",
                "Approval Gate",
                "Pending trades queue, one-click approve/reject",
                _approval_gate_state,
            ),
            FeatureDefinition("kill_switch", "Kill Switch", "Emergency cancel all trades", _kill_switch_state),
        ],
    ),
    PhaseDefinition(
        id=3,
        title="Intelligence Layer",
        features=[
            FeatureDefinition(
                "signal_aggregator",
                "Signal Aggregator",
                "Multi-source trending (Birdeye + Gecko + DexScreener)",
                _signal_aggregator_state,
            ),
            FeatureDefinition("smart_money", "Smart Money", "GMGN insider tracking, whale patterns", _smart_money_state),
            FeatureDefinition("sentiment", "Sentiment", "Real-time X/Twitter via Grok", _sentiment_state),
            FeatureDefinition("ml_regime", "ML Regime", "Volatility prediction, strategy switching", _ml_regime_state),
        ],
    ),
    PhaseDefinition(
        id=4,
        title="LifeOS Integration",
        features=[
            FeatureDefinition("voice_trading", "Voice Trading", '"Buy $50 of SOL" natural language', _voice_trading_state),
            FeatureDefinition(
                "mirror_test",
                "Mirror Test",
                "Self-correction dashboard, improvement history",
                _mirror_test_state,
            ),
            FeatureDefinition(
                "knowledge",
                "Knowledge",
                "Notes search, research viewer, trading journal",
                _knowledge_state,
            ),
        ],
    ),
    PhaseDefinition(
        id=5,
        title="Advanced Tools",
        features=[
            FeatureDefinition(
                "mev_dashboard",
                "MEV Dashboard",
                "Jito bundles, sandwich scanner, SOR visualizer",
                _mev_dashboard_state,
            ),
            FeatureDefinition("perps", "Perps", "Jupiter perps, 30x leverage, funding rates", _perps_state),
            FeatureDefinition(
                "multi_dex",
                "Multi-DEX",
                "Quote comparison (Jupiter/Raydium/Orca)",
                _multi_dex_state,
            ),
            FeatureDefinition(
                "analytics",
                "Analytics",
                "Equity curve, trade heatmap, drawdown analysis",
                _analytics_state,
            ),
        ],
    ),
    PhaseDefinition(
        id=6,
        title="Polish & Scale",
        features=[
            FeatureDefinition(
                "performance",
                "Performance",
                "WebSocket, code splitting, virtual scroll",
                _performance_state,
            ),
            FeatureDefinition("mobile", "Mobile", "PWA, push notifications, touch charts", _mobile_state),
            FeatureDefinition("themes", "Themes", "Dark/light toggle, accent colors", _themes_state),
            FeatureDefinition(
                "onboarding",
                "Onboarding",
                "Interactive tutorial, tooltips",
                _onboarding_state,
            ),
        ],
    ),
]


def _phase_status(states: List[str]) -> str:
    if states and all(state == "live" for state in states):
        return "completed"
    if any(state != "planned" for state in states):
        return "in-progress"
    return "not-started"


def _phase_progress(states: List[str]) -> int:
    if not states:
        return 0
    score = sum(float(STATE_CATALOG.get(state, {}).get("score", 0.0)) for state in states)
    return round((score / len(states)) * 100)


def build_roadmap_capability_snapshot(
    *,
    root: Path = ROOT,
) -> Dict[str, Any]:
    probe = Probe(root)
    phase_payloads: List[Dict[str, Any]] = []
    state_counts = {key: 0 for key in STATE_CATALOG}

    for phase in PHASES:
        feature_payloads: List[Dict[str, Any]] = []
        feature_states: List[str] = []

        for feature in phase.features:
            state, evidence, note = feature.probe(probe)
            if state not in STATE_CATALOG:
                state = "planned"
            feature_states.append(state)
            state_counts[state] += 1

            feature_payloads.append(
                {
                    "key": feature.key,
                    "name": feature.name,
                    "description": feature.description,
                    "state": state,
                    "state_label": STATE_CATALOG[state]["label"],
                    "done": state == "live",
                    "evidence": evidence,
                    "note": note,
                }
            )

        phase_payloads.append(
            {
                "id": phase.id,
                "title": phase.title,
                "status": _phase_status(feature_states),
                "progress_percent": _phase_progress(feature_states),
                "features": feature_payloads,
            }
        )

    total_features = sum(len(phase.features) for phase in PHASES)
    completed_features = state_counts.get("live", 0)
    if total_features <= 0:
        overall_progress = 0
    else:
        weighted = sum(
            state_counts[state] * float(STATE_CATALOG[state]["score"]) for state in STATE_CATALOG
        )
        overall_progress = round((weighted / total_features) * 100)

    return {
        "status": "healthy",
        "generated_at": _utc_now(),
        "summary": {
            "total_features": total_features,
            "completed_features": completed_features,
            "overall_progress_percent": overall_progress,
            "state_counts": state_counts,
        },
        "phases": phase_payloads,
        "state_catalog": {
            key: {"label": value["label"], "score": value["score"]} for key, value in STATE_CATALOG.items()
        },
        "source": "capability_probes_v1",
    }


__all__ = ["build_roadmap_capability_snapshot", "STATE_CATALOG"]

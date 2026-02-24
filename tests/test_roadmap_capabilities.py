from pathlib import Path

from core.roadmap_capabilities import build_roadmap_capability_snapshot


def _write_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _find_feature(payload: dict, phase_id: int, feature_key: str) -> dict:
    phase = next((item for item in payload["phases"] if item["id"] == phase_id), None)
    assert phase is not None
    feature = next((item for item in phase["features"] if item["key"] == feature_key), None)
    assert feature is not None
    return feature


def test_build_roadmap_capability_snapshot_maps_mock_prototype_and_backend_only(tmp_path):
    _write_file(
        tmp_path,
        "frontend/src/components/smartmoney/SmartMoneyTracker.jsx",
        "const mockSmartWallets = [];",
    )
    _write_file(
        tmp_path,
        "frontend/src/components/social/SocialSentiment.jsx",
        "const MOCK_TOKEN_SENTIMENT = [];",
    )
    _write_file(
        tmp_path,
        "frontend/src/components/depth/DepthChart.jsx",
        "const size = Math.random();",
    )
    _write_file(
        tmp_path,
        "frontend/src/components/perps/PerpsSniper.tsx",
        "Prototype preview only. Canonical production surface is jarvis-sniper.",
    )
    _write_file(tmp_path, "core/trading_coliseum.py", "class TradingColiseum: ...")

    payload = build_roadmap_capability_snapshot(root=tmp_path)

    assert _find_feature(payload, 3, "smart_money")["state"] == "mock"
    assert _find_feature(payload, 3, "sentiment")["state"] == "mock"
    assert _find_feature(payload, 1, "order_book")["state"] == "mock"
    assert _find_feature(payload, 5, "perps")["state"] == "prototype"
    assert _find_feature(payload, 2, "coliseum")["state"] == "backend_only"


def test_build_roadmap_capability_snapshot_summary_counts_match_feature_total(tmp_path):
    _write_file(tmp_path, "frontend/src/pages/TradingNew.jsx", "export default function TradingNew() {}")
    _write_file(
        tmp_path,
        "frontend/src/components/perps/usePerpsData.ts",
        "export function usePerpsData() { return {}; }",
    )
    _write_file(
        tmp_path,
        "jobs/model_upgrader.py",
        "def run_weekly_scan(): return {}",
    )

    payload = build_roadmap_capability_snapshot(root=tmp_path)
    total = payload["summary"]["total_features"]
    counted = sum(payload["summary"]["state_counts"].values())

    assert total > 0
    assert counted == total


def test_capability_snapshot_marks_order_panel_coliseum_and_mirror_live_when_api_and_ui_are_wired(tmp_path):
    _write_file(
        tmp_path,
        "frontend/src/components/OrderPanel.jsx",
        "fetch('/api/trade', { method: 'POST' });",
    )
    _write_file(
        tmp_path,
        "frontend/src/pages/AIControlPlane.jsx",
        "fetch('/api/sentinel/coliseum'); fetch('/api/lifeos/mirror/status');",
    )
    _write_file(
        tmp_path,
        "api/fastapi_app.py",
        "@app.post('/api/trade')\n@app.get('/api/sentinel/coliseum')\n@app.get('/api/lifeos/mirror/status')",
    )
    _write_file(tmp_path, "core/trading_coliseum.py", "class TradingColiseum: ...")
    _write_file(tmp_path, "core/self_improvement_engine_v2.py", "class SelfImprovementEngine: ...")

    payload = build_roadmap_capability_snapshot(root=tmp_path)

    assert _find_feature(payload, 1, "order_panel")["state"] == "live"
    assert _find_feature(payload, 2, "coliseum")["state"] == "live"
    assert _find_feature(payload, 4, "mirror_test")["state"] == "live"


def test_capability_snapshot_marks_intelligence_and_lifeos_features_live_when_wired(tmp_path):
    _write_file(
        tmp_path,
        "frontend/src/pages/AIControlPlane.jsx",
        "fetch('/api/intel/signal-aggregator'); fetch('/api/intel/ml-regime'); fetch('/api/lifeos/voice/status'); fetch('/api/lifeos/knowledge/status');",
    )
    _write_file(
        tmp_path,
        "api/fastapi_app.py",
        "@app.get('/api/intel/signal-aggregator')\n@app.get('/api/intel/ml-regime')\n@app.get('/api/lifeos/voice/status')\n@app.get('/api/lifeos/knowledge/status')",
    )
    _write_file(tmp_path, "core/signal_aggregator.py", "def get_momentum_opportunities(): ...")
    _write_file(tmp_path, "core/ml_regime_detector.py", "class VolatilityRegimeDetector: ...")
    _write_file(tmp_path, "core/voice/trading_commands.py", "class VoiceTradingCommandProcessor: ...")
    _write_file(tmp_path, "bots/shared/supermemory_client.py", "def pre_recall(): ...")

    payload = build_roadmap_capability_snapshot(root=tmp_path)

    assert _find_feature(payload, 3, "signal_aggregator")["state"] == "live"
    assert _find_feature(payload, 3, "ml_regime")["state"] == "live"
    assert _find_feature(payload, 4, "voice_trading")["state"] == "live"
    assert _find_feature(payload, 4, "knowledge")["state"] == "live"


def test_capability_snapshot_marks_advanced_and_polish_features_live_when_wired(tmp_path):
    _write_file(
        tmp_path,
        "frontend/src/pages/AIControlPlane.jsx",
        "fetch('/api/advanced/mev'); fetch('/api/advanced/multi-dex'); fetch('/api/advanced/perps/status'); fetch('/api/analytics/portfolio'); fetch('/api/runtime/capabilities'); fetch('/api/polish/themes/status'); fetch('/api/polish/onboarding/status');",
    )
    _write_file(
        tmp_path,
        "api/fastapi_app.py",
        "@app.get('/api/advanced/mev')\n@app.get('/api/advanced/multi-dex')\n@app.get('/api/advanced/perps/status')\n@app.get('/api/analytics/portfolio')\n@app.get('/api/runtime/capabilities')\n@app.get('/api/polish/themes/status')\n@app.get('/api/polish/onboarding/status')",
    )
    _write_file(tmp_path, "frontend/src/components/mev/MEVDetector.jsx", "fetch('/api/advanced/mev')")
    _write_file(tmp_path, "frontend/src/components/dex/DEXAnalytics.jsx", "fetch('/api/advanced/multi-dex')")
    _write_file(tmp_path, "frontend/src/components/perps/PerpsSniper.tsx", "fetch('/api/advanced/perps/status')")
    _write_file(tmp_path, "frontend/src/components/perps/usePerpsData.ts", "export function usePerpsData() {}")
    _write_file(tmp_path, "web/perps_api.py", "def health(): return {'ok': True}")
    _write_file(tmp_path, "frontend/src/components/analytics/PortfolioAnalytics.jsx", "fetch('/api/analytics/portfolio')")
    _write_file(tmp_path, "api/middleware/compression.py", "class CompressionMiddleware: ...")
    _write_file(tmp_path, "api/middleware/timeout.py", "class TimeoutMiddleware: ...")
    _write_file(
        tmp_path,
        "frontend/src/components/MainLayout.jsx",
        "import MobileNav from './MobileNav'; import OnboardingCoach from './onboarding/OnboardingCoach'; import ThemeToggle from './ui/ThemeToggle';",
    )
    _write_file(tmp_path, "frontend/src/components/MobileNav.jsx", "export default function MobileNav() {}")
    _write_file(tmp_path, "frontend/src/main.jsx", "import { ThemeProvider } from './contexts/ThemeContext'")
    _write_file(tmp_path, "frontend/src/contexts/ThemeContext.jsx", "export function ThemeProvider({ children }) { return children }")
    _write_file(tmp_path, "frontend/src/styles/tokens.css", ":root { --bg-primary: #000; }")
    _write_file(tmp_path, "frontend/src/components/onboarding/OnboardingCoach.jsx", "export default function OnboardingCoach() {}")

    payload = build_roadmap_capability_snapshot(root=tmp_path)

    assert _find_feature(payload, 5, "mev_dashboard")["state"] == "live"
    assert _find_feature(payload, 5, "perps")["state"] == "live"
    assert _find_feature(payload, 5, "multi_dex")["state"] == "live"
    assert _find_feature(payload, 5, "analytics")["state"] == "live"
    assert _find_feature(payload, 6, "performance")["state"] == "live"
    assert _find_feature(payload, 6, "mobile")["state"] == "live"
    assert _find_feature(payload, 6, "themes")["state"] == "live"
    assert _find_feature(payload, 6, "onboarding")["state"] == "live"


def test_roadmap_capabilities_endpoint_returns_payload(client, monkeypatch):
    monkeypatch.setattr(
        "core.roadmap_capabilities.build_roadmap_capability_snapshot",
        lambda: {
            "status": "healthy",
            "generated_at": "2026-02-24T10:00:00+00:00",
            "phases": [{"id": 1, "title": "Trading Core", "features": []}],
            "summary": {"total_features": 0, "state_counts": {}},
            "state_catalog": {},
        },
    )

    response = client.get("/api/roadmap/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["phases"][0]["title"] == "Trading Core"


def test_roadmap_capabilities_endpoint_degrades_on_error(client, monkeypatch):
    def _raise():
        raise RuntimeError("roadmap boom")

    monkeypatch.setattr("core.roadmap_capabilities.build_roadmap_capability_snapshot", _raise)

    response = client.get("/api/roadmap/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert "roadmap boom" in payload["error"]

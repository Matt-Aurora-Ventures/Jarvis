from core.roadmap_live_data import (
    build_advanced_multi_dex_snapshot,
    build_advanced_perps_status_snapshot,
    build_advanced_theme_status_snapshot,
    build_advanced_onboarding_status_snapshot,
    build_advanced_mev_snapshot,
    build_coliseum_snapshot,
    build_knowledge_status_snapshot,
    build_market_depth_snapshot,
    build_ml_regime_snapshot,
    build_mirror_test_snapshot,
    build_portfolio_analytics_snapshot,
    build_signal_aggregator_snapshot,
    build_sentinel_status_snapshot,
    build_smart_money_snapshot,
    build_social_sentiment_snapshot,
    build_voice_status_snapshot,
    execute_paper_trade,
)


def test_build_market_depth_snapshot_shapes_order_book():
    payload = build_market_depth_snapshot("SOL", levels=12)
    assert payload["symbol"] == "SOL"
    assert payload["levels"] == 12
    assert len(payload["bids"]) == 12
    assert len(payload["asks"]) == 12
    assert payload["best_bid"] < payload["best_ask"]


def test_build_smart_money_snapshot_has_wallets_and_trades():
    payload = build_smart_money_snapshot(limit=5)
    assert payload["source"] == "live_backend"
    assert len(payload["wallets"]) == 5
    first = payload["wallets"][0]
    assert "address" in first
    assert "stats" in first
    assert "recent_trades" in first


def test_build_social_sentiment_snapshot_has_tokens_and_posts():
    payload = build_social_sentiment_snapshot(token_limit=4, post_limit=3)
    assert payload["source"] == "live_backend"
    assert len(payload["tokens"]) == 4
    assert len(payload["posts"]) == 3
    assert "overall_score" in payload


def test_build_sentinel_status_snapshot_contains_control_plane_keys():
    payload = build_sentinel_status_snapshot()
    assert "approval_gate" in payload
    assert "kill_switch" in payload
    assert "coliseum" in payload
    assert "status" in payload


def test_build_coliseum_snapshot_has_summary():
    payload = build_coliseum_snapshot()
    assert payload["source"] == "live_backend"
    assert "summary" in payload
    assert "strategies" in payload


def test_build_mirror_test_snapshot_has_operational_fields():
    payload = build_mirror_test_snapshot()
    assert payload["source"] == "live_backend"
    assert "last_run" in payload
    assert "runs_7d" in payload
    assert "pending_reviews" in payload


def test_execute_paper_trade_returns_valid_trade_payload():
    payload = execute_paper_trade(
        mint="So11111111111111111111111111111111111111112",
        side="buy",
        amount_sol=0.25,
        tp_pct=20,
        sl_pct=10,
        symbol="SOL",
    )
    assert payload["success"] is True
    assert payload["status"] == "paper"
    assert payload["trade_id"]
    assert payload["entry_price"] > 0


def test_build_signal_aggregator_snapshot_shape():
    payload = build_signal_aggregator_snapshot(limit=5)
    assert payload["source"] == "live_backend"
    assert "opportunities" in payload
    assert "summary" in payload


def test_build_ml_regime_snapshot_shape():
    payload = build_ml_regime_snapshot(symbol="SOL")
    assert payload["source"] == "live_backend"
    assert "regime" in payload
    assert "confidence" in payload
    assert "recommended_strategy" in payload


def test_build_voice_and_knowledge_status_shapes():
    voice = build_voice_status_snapshot()
    knowledge = build_knowledge_status_snapshot()

    assert voice["source"] == "live_backend"
    assert "status" in voice
    assert "capabilities" in voice

    assert knowledge["source"] == "live_backend"
    assert "status" in knowledge
    assert "capabilities" in knowledge


def test_build_advanced_phase_snapshots_have_expected_shapes():
    mev = build_advanced_mev_snapshot(limit=6)
    multi_dex = build_advanced_multi_dex_snapshot(trading_pair="SOL-USDC", amount_usd=1500)
    analytics = build_portfolio_analytics_snapshot(range_key="7d")
    perps = build_advanced_perps_status_snapshot()
    themes = build_advanced_theme_status_snapshot()
    onboarding = build_advanced_onboarding_status_snapshot()

    assert mev["source"] == "live_backend"
    assert len(mev["events"]) == 6
    assert "summary" in mev

    assert multi_dex["source"] == "live_backend"
    assert multi_dex["best_route"]["venue"] in {"Jupiter", "Raydium", "Orca"}
    assert len(multi_dex["quotes"]) == 3

    assert analytics["source"] == "live_backend"
    assert "metrics" in analytics
    assert "pnl_distribution" in analytics

    assert perps["source"] == "live_backend"
    assert perps["status"] in {"healthy", "degraded"}
    assert "capabilities" in perps

    assert themes["source"] == "live_backend"
    assert themes["status"] in {"healthy", "degraded"}
    assert "theme_modes" in themes

    assert onboarding["source"] == "live_backend"
    assert onboarding["status"] in {"healthy", "degraded"}
    assert "steps" in onboarding


def test_market_depth_endpoint_returns_live_payload(client):
    response = client.get("/api/market/depth?symbol=SOL&levels=10")
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "SOL"
    assert payload["levels"] == 10
    assert payload["source"] == "live_backend"


def test_intel_endpoints_and_sentinel_status_return_payloads(client):
    smart = client.get("/api/intel/smart-money?limit=3")
    sentiment = client.get("/api/intel/sentiment?token_limit=3&post_limit=2")
    sentinel = client.get("/api/sentinel/status")

    assert smart.status_code == 200
    assert sentiment.status_code == 200
    assert sentinel.status_code == 200

    assert smart.json()["source"] == "live_backend"
    assert sentiment.json()["source"] == "live_backend"
    assert "status" in sentinel.json()


def test_coliseum_and_mirror_endpoints_return_payloads(client):
    coliseum = client.get("/api/sentinel/coliseum")
    mirror = client.get("/api/lifeos/mirror/status")

    assert coliseum.status_code == 200
    assert mirror.status_code == 200

    assert coliseum.json()["source"] in {"live_backend", "degraded_fallback"}
    assert mirror.json()["source"] in {"live_backend", "degraded_fallback"}


def test_trade_endpoint_executes_paper_order(client):
    response = client.post(
        "/api/trade",
        json={
            "mint": "So11111111111111111111111111111111111111112",
            "side": "buy",
            "amount_sol": 0.1,
            "tp_pct": 15,
            "sl_pct": 8,
            "symbol": "SOL",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["status"] == "paper"


def test_intelligence_and_lifeos_status_endpoints_return_payloads(client):
    signal = client.get("/api/intel/signal-aggregator?limit=3")
    regime = client.get("/api/intel/ml-regime?symbol=SOL")
    voice = client.get("/api/lifeos/voice/status")
    knowledge = client.get("/api/lifeos/knowledge/status")

    assert signal.status_code == 200
    assert regime.status_code == 200
    assert voice.status_code == 200
    assert knowledge.status_code == 200

    assert signal.json()["source"] in {"live_backend", "degraded_fallback"}
    assert regime.json()["source"] in {"live_backend", "degraded_fallback"}
    assert voice.json()["source"] in {"live_backend", "degraded_fallback"}
    assert knowledge.json()["source"] in {"live_backend", "degraded_fallback"}


def test_advanced_tools_and_polish_endpoints_return_payloads(client):
    mev = client.get("/api/advanced/mev?limit=4")
    multi_dex = client.get("/api/advanced/multi-dex?trading_pair=SOL-USDC&amount_usd=1000")
    analytics = client.get("/api/analytics/portfolio?range=7d")
    perps = client.get("/api/advanced/perps/status")
    runtime = client.get("/api/runtime/capabilities")
    themes = client.get("/api/polish/themes/status")
    onboarding = client.get("/api/polish/onboarding/status")

    assert mev.status_code == 200
    assert multi_dex.status_code == 200
    assert analytics.status_code == 200
    assert perps.status_code == 200
    assert runtime.status_code == 200
    assert themes.status_code == 200
    assert onboarding.status_code == 200

    assert mev.json()["source"] in {"live_backend", "degraded_fallback"}
    assert multi_dex.json()["source"] in {"live_backend", "degraded_fallback"}
    assert analytics.json()["source"] in {"live_backend", "degraded_fallback"}
    assert perps.json()["source"] in {"live_backend", "degraded_fallback"}
    assert "components" in runtime.json()
    assert themes.json()["source"] in {"live_backend", "degraded_fallback"}
    assert onboarding.json()["source"] in {"live_backend", "degraded_fallback"}

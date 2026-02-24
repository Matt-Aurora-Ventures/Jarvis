# Jarvis Roadmap Gap Closure (Execution Backlog)
Date: 2026-02-24  
Branch baseline: `integration/jarvis-consensus-context`  
Canonical roadmap source: `frontend/src/pages/Roadmap.jsx`

## Completed in this execution wave
1. Added roadmap backend contracts in `core/roadmap_live_data.py`:
   - `build_coliseum_snapshot(...)`
   - `build_mirror_test_snapshot(...)`
   - `execute_paper_trade(...)`
   - `build_signal_aggregator_snapshot(...)`
   - `build_ml_regime_snapshot(...)`
   - `build_voice_status_snapshot(...)`
   - `build_knowledge_status_snapshot(...)`
2. Added roadmap-facing APIs in `api/fastapi_app.py`:
   - `POST /api/trade`
   - `GET /api/sentinel/coliseum`
   - `GET /api/lifeos/mirror/status`
   - `GET /api/intel/signal-aggregator`
   - `GET /api/intel/ml-regime`
   - `GET /api/lifeos/voice/status`
   - `GET /api/lifeos/knowledge/status`
3. Upgraded capability truth logic in `core/roadmap_capabilities.py`:
   - `order_panel`, `coliseum`, `mirror_test` can classify as `live` with API + UI evidence.
   - `signal_aggregator`, `ml_regime`, `voice_trading`, `knowledge` can classify as `live` with API + UI evidence.
4. Extended operator UI in `frontend/src/pages/AIControlPlane.jsx`:
   - Added Signal Aggregator and ML Regime cards/panel.
   - Added Voice and Knowledge cards/panel.
   - Kept existing Consensus/Context/Upgrade/Compute/Coliseum/Mirror panels intact.
5. Added and expanded tests:
   - `tests/test_roadmap_live_feeds.py`
   - `tests/test_roadmap_capabilities.py`

## Verified test/build status
1. `pytest tests/test_roadmap_live_feeds.py tests/test_roadmap_capabilities.py tests/test_ai_control_plane.py tests/test_runtime_capabilities.py -q`
2. `pytest tests/test_mesh_sync_service.py tests/test_mesh_attestation_service.py tests/integration/test_supermemory_mesh_sync_attestation_flow.py tests/unit/bots/shared/test_supermemory_client.py tests/test_nosana_client.py tests/test_consensus_arena.py tests/test_consensus_scoring.py tests/test_consensus_resilient_provider.py tests/test_model_upgrader.py tests/test_ai_runtime_integration.py tests/test_jarvis.py tests/test_roadmap_capabilities.py tests/test_roadmap_live_feeds.py tests/test_ai_control_plane.py tests/test_runtime_capabilities.py -q`
3. `npm --prefix frontend run build`
4. Result: all commands passed.

## Capability snapshot (current)
From `core.roadmap_capabilities.build_roadmap_capability_snapshot()`:
- total features: 22
- live: 22
- backend-only: 0
- prototype: 0
- mock: 0
- planned: 0
- weighted progress: 100%

Phase-level:
1. Trading Core: 100% (live)
2. Sentinel Mode: 100% (live)
3. Intelligence Layer: 100% (live)
4. LifeOS Integration: 100% (live)
5. Advanced Tools: 100% (live)
6. Polish & Scale: 100% (live)

## Delivery completed in this tranche
1. Added Phase 5/6 backend contracts in `core/roadmap_live_data.py`:
   - `build_advanced_mev_snapshot(...)`
   - `build_advanced_multi_dex_snapshot(...)`
   - `build_portfolio_analytics_snapshot(...)`
   - `build_advanced_perps_status_snapshot(...)`
   - `build_advanced_theme_status_snapshot(...)`
   - `build_advanced_onboarding_status_snapshot(...)`
2. Added APIs in `api/fastapi_app.py`:
   - `GET /api/advanced/mev`
   - `GET /api/advanced/multi-dex`
   - `GET /api/advanced/perps/status`
   - `GET /api/analytics/portfolio`
   - `GET /api/runtime/capabilities`
   - `GET /api/polish/themes/status`
   - `GET /api/polish/onboarding/status`
3. Upgraded roadmap evidence probes in `core/roadmap_capabilities.py`:
   - Phase 5 features (`mev_dashboard`, `perps`, `multi_dex`, `analytics`) now classify `live` with endpoint + UI evidence.
   - Phase 6 features (`performance`, `mobile`, `themes`, `onboarding`) now classify `live` with endpoint + layout evidence.
4. Extended UI wiring:
   - `frontend/src/pages/AIControlPlane.jsx` now fetches and surfaces advanced/polish feeds.
   - `frontend/src/components/MainLayout.jsx` now wires `MobileNav`, `ThemeToggle`, and `OnboardingCoach`.
   - `frontend/src/components/onboarding/OnboardingCoach.jsx` added with persisted step flow.
   - `frontend/src/components/analytics/PortfolioAnalytics.jsx` now uses `/api/analytics/portfolio`.
   - `frontend/src/components/perps/PerpsSniper.tsx` now uses `/api/advanced/perps/status` readiness banner.
5. Added/expanded tests:
   - `tests/test_roadmap_live_feeds.py`
   - `tests/test_roadmap_capabilities.py`

## Massive action list (next 14 days, post-closure hardening)
1. Add CI matrix for `JARVIS_USE_ARENA`, `JARVIS_USE_NOSANA`, `JARVIS_USE_MESH_SYNC`, `JARVIS_USE_MESH_ATTEST`.
2. Add endpoint smoke checks to deployment pipeline for all roadmap/control-plane routes.
3. Add alert thresholds for mesh publish failures, envelope validation failures, and attestation commit failures.
4. Add operator endpoint for combined queue depth + retry health on mesh outbox.
5. Add nightly job to replay pending mesh events with capped retry and jitter.
6. Add perps readiness health budget (runner heartbeat SLA + stale-data alarms).
7. Replace remaining simulated data paths in `MEVDetector.jsx` and `DEXAnalytics.jsx` with direct API rendering.
8. Add provenance chips (`live`, `degraded_fallback`) in all Phase 5 widgets.
9. Add visual onboarding completion analytics (step drop-off, completion rate).
10. Add mobile acceptance tests for AI Control Plane and Trading screens.
11. Add frontend performance budgets (bundle size, route TTI, API polling overhead).
12. Add rollback drill automation for model upgrader (swap + rollback + verification).
13. Add Solana/NATS fault-injection integration tests for tampered envelope and replayed event IDs.
14. Add runbook section for “roadmap says live but endpoint degraded” incident class.
15. Publish 30/60/90 ownership plan with SLO targets and release gates.

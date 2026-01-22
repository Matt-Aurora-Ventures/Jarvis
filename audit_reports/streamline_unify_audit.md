Streamline & Unify Audit (Logic, Autonomy, Compression, Utility)

## Scope & Method
- Reviewed core architecture and optimization guidance.
- Sampled model routing, agent routing, self-improvement, compression directive, and service discovery.

## Commands Run
- `sed -n '1,200p' README.md`
- `sed -n '1,200p' SYSTEM_ARCHITECTURE.md`
- `sed -n '1,200p' OPTIMIZATION_ROADMAP.md`
- `rg -n "model" core | head -n 200`
- `sed -n '1,220p' core/compression_directive.py`
- `sed -n '1,240p' core/model_router/router.py`
- `sed -n '240,520p' core/model_router/router.py`
- `sed -n '1,240p' core/agents/base.py`
- `sed -n '1,260p' core/self_improvement_engine_v2.py`
- `sed -n '1,220p' core/service_discovery.py`

## Primary Findings
1. **Model routing logic is duplicated.**
   - `core/model_router/router.py` implements provider selection with priorities, rate-limits, caching, and fallbacks.
   - `core/agents/base.py` separately defines provider chains and fallback logic in `BaseAgent.generate()`.
   - This creates two sources of truth for model selection and cost/latency tuning.

2. **Self-improvement relies on a separate routing stack.**
   - `core/self_improvement_engine_v2.py` uses `life_os_router.MiniMaxRouter()` instead of the centralized ModelRouter.
   - The nightly mirror test therefore bypasses global routing health checks and capabilities logic.

3. **Compression strategy is stated but not concretely integrated.**
   - `core/compression_directive.py` defines a full compression-first architecture and autonomy loop, but there is no referenced implementation path in the router/agent subsystems.

4. **Service discovery has separate provider metadata.**
   - `core/service_discovery.py` maintains a registry of free AI services and API endpoints that isn’t currently connected to the ModelRouter provider list.

## Streamline & Unify Recommendations (High-Level)
1. **Unify model routing behind a single interface.**
   - Centralize all routing in `core/model_router/router.py` and make BaseAgent call it.
   - Consolidate provider priorities, cost/latency, and capability metadata in one registry so changes propagate consistently.

2. **Route self-improvement through the same router.**
   - Wire `SelfImprovementEngine` to use ModelRouter for reflection and grading to inherit global health checks, caching, and fallback behavior.

3. **Connect service discovery to provider registry.**
   - When a service is integrated via `ServiceDiscovery`, auto-register the provider and capabilities inside ModelRouter.
   - This ensures discovery immediately benefits routing decisions.

4. **Operationalize compression directive.**
   - Create a thin, measurable pipeline (e.g., embeddings + summary + residual storage) that follows the directive’s “compress then reconstruct” loop.
   - Add evaluation hooks (semantic retention + performance impact) to align with the directive.

## Execution Loop (Repeat Until Converged)
Run the following loop per subsystem (routing, autonomy, compression, utility) on a fixed cadence (weekly or per release):

1. **Instrument**
   - Add counters for request volume, latency, error rate, and cost by provider and capability.
2. **Consolidate**
   - Remove duplicate routing logic and move to a single routing interface.
3. **Validate**
   - Compare A/B metrics (latency, cost, quality) before/after changes.
4. **Reinforce**
   - Persist successful configuration changes back into the router and service registry.
5. **Harden**
   - Add regression tests for router selection, fallback behavior, and compression evaluation.

### Loop Exit Criteria
- Single routing path used by BaseAgent and self-improvement flows.
- Service discovery updates provider registry automatically.
- Compression pipeline has measurable reconstruction metrics and is used by at least one subsystem.

## Next Actions (Ordered Backlog)
1. **Unify routing paths** by delegating `BaseAgent.generate()` to the ModelRouter.
2. **Router-enable self-improvement** so mirror tests use the same health/capability logic.
3. **Register discovered services** in the ModelRouter when integrating new providers.
4. **Pilot compression pipeline** with a minimal text + time-series prototype and evaluation harness.

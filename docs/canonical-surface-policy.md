# Canonical Surface Policy

## Scope
- Canonical production UI: `jarvis-sniper`
- Canonical perps engine: `core/jupiter_perps`

## Non-Canonical Surfaces
- `jarvis-web-terminal`
- `web/templates/trading.html`
- `web_demo`
- `web/trading_web.py`

These surfaces are prototype-only. They may be used for internal exploration but must not be treated as production truth.

## Rules
1. Default launcher points to `jarvis-sniper` only.
2. Prototype launchers must display a warning banner.
3. PRs that modify non-canonical surfaces require override label: `allow-non-canonical-surface-change`.
4. Product claims and release notes must reference canonical surfaces only.

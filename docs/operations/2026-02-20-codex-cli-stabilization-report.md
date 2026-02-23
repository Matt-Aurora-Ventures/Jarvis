# Codex CLI Stabilization Report (2026-02-20)

## Scope
Persistent fix for `codex: not found` in OpenClaw/ClawdBot container startup while keeping Anthropic provider flow unchanged.

## Root Cause
`@openai/codex` installation could succeed, but the `codex` executable was not guaranteed to be resolvable on `PATH` inside container runtime shells.

## Evidence
- NPM package exports a `codex` binary (`npm view @openai/codex bin` => `codex`).
- Startup scripts previously installed Codex but did not enforce deterministic binary resolution/symlinking.
- Compose validation initially showed shell interpolation drift around `NPM_PREFIX`; fixed by escaping runtime shell variables with `$$`.

## Implemented Fixes
1. `docker/clawdbot-gateway/entrypoint.sh`
- Added deterministic codex bootstrap:
  - install check
  - npm global prefix discovery
  - `/usr/local/bin/codex` symlink creation when needed
  - startup logging for resolved/unresolved codex command

2. `docker/clawdbot-gateway/docker-compose.yml`
- Matt startup block now:
  - validates codex install
  - resolves npm prefix at runtime (`$$(...)`)
  - creates `/usr/local/bin/codex` symlink
- Added codex fallback wiring in generated config:
  - `tools.codex.command_fallback = "npx --yes @openai/codex"`
  - `skills.entries.coding-agent.command_fallback = "npx --yes @openai/codex"`

3. `deploy/clawdbot-redundancy/entrypoint.sh`
- Added explicit Codex bootstrap step for Matt/`INSTALL_CODEX=true`:
  - install check
  - npm prefix lookup
  - symlink enforcement
  - fallback logging

4. `deploy/clawdbot-redundancy/docker-compose.clawdbots.yml`
- Enabled persistent Codex bootstrap on Matt container via `INSTALL_CODEX=true`.

## Security Decision
- Codex remains CLI-login first; OpenAI API key is not required for Codex CLI auth.
- Anthropic provider path remains primary where configured.

## Verification Performed
- `docker compose -f docker/clawdbot-gateway/docker-compose.yml config --quiet` (passes)
- `docker compose -f deploy/clawdbot-redundancy/docker-compose.clawdbots.yml config --quiet` (passes)
- Runtime target container `openclaw-ydy8-openclaw-1` was not reachable from this local workspace Docker context, so in-container checks must be run on VPS.

## VPS Runtime Verification Commands
```sh
# Inside VPS

docker exec -it openclaw-ydy8-openclaw-1 sh -lc '
which node
which npm
npm -v
npm config get prefix
npm root -g
echo "$PATH"
ls -la "$(npm config get prefix)/bin" | grep codex || true
find / -type f -name codex 2>/dev/null | head
codex --version || npx --yes @openai/codex --version
'

# Restart check
docker restart openclaw-ydy8-openclaw-1
docker exec -it openclaw-ydy8-openclaw-1 sh -lc 'codex --version && echo "$PATH"'

# Auth check
# (interactive)
docker exec -it openclaw-ydy8-openclaw-1 sh -lc 'codex --login'
```

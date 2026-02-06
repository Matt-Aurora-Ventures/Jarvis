# Agent Notes / Handoffs

## 2026-02-02
- Status: Ralph Wiggum loop active.
- Bots running on VPS: Friday, Matt, Jarvis (single instances).
- Issues: Matt log still shows old 409 conflict lines; Jarvis has transient Telegram 502 errors.
- Desktop access: Tailscale online; SSH from VPS to desktop still denied (need admin to add key to administrators_authorized_keys).
- GSD consolidated into docs/ULTIMATE_MASTER_GSD_UPDATE_JAN_31_1515.md (single source of truth).

## Next Actions
- Fix SSH auth for VPS -> desktop (admin step required)
- Remove OpenAI API key warning in llm_client for Codex CLI
- Confirm no new 409 conflicts in logs
- Continue autonomy + creativity enhancements per GSD

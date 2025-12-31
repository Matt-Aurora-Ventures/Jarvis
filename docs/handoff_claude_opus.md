# Handoff Brief for Claude Opus

## Repository & Branch
- **Repo:** Matt-Aurora-Ventures/Jarvis
- **Branch:** `improvement/sample_1767118456` (pushed)
- **Latest commit:** `feat: improve UI actions and provider reliability`

## What Was Done
1. **UI Actions / Voice Chat Fixes**
   - All browser-related actions now accept keyword arguments and force Firefox Developer Edition to respect the user's Safari prohibition.
   - `open_notes`, `new_window`, `new_tab` accept optional params so `[ACTION: ...]` calls during voice chat no longer throw signature errors.
2. **Provider Reliability**
   - Added Groq throttling + backoff to avoid 429 storms during voice sessions.
   - Ollama fallback gated by a lightweight health check; if the local server is down, the provider chain skips it.
   - Readability extractor now receives decoded HTML, avoiding the "bytes-like object" TypeError.
3. **Roadmap / Hygiene**
   - Phase 7 QA list updated to include recurring context pruning/compression cycles.
   - Authored `docs/context_hygiene_plan.md` outlining the scoring, compression, and archiving strategy for research/memory data.

## Outstanding Work (ordered priority)
1. **Voice Wake-Word Gating**
   - Modify `core/voice.py` so unsolicited speech (without wake word “Jarvis”) is observed but not acted on.
   - Update voice tests / add a regression scenario in the conversation backtester.
2. **Provider Health Reporting**
   - Extend `lifeos providers check` to report Groq/Ollama health + last error.
   - Optional: CLI command to verify before starting voice chat.
3. **Research Extraction Tests & Hygiene Runner**
   - Add unit tests for readability fallback (mock HTTP response) so we never regress.
   - Implement `core/context_hygiene.py` + CLI hook (`lifeos hygiene run`) per the new plan.
4. **Voice Chat Validation**
   - After the above, run a full voice-chat session to confirm `[ACTION]` calls succeed and provider fallback behavior is stable (no Safari triggers).

## Suggested Prompt for Claude Opus
```
You are taking over the LifeOS/Jarvis repo on branch improvement/sample_1767118456.
Recent work (already merged on this branch):
- UI actions now accept keyword params and always use Firefox Developer Edition.
- Groq provider calls are throttled/backed-off; Ollama fallback is gated by a health check.
- Readability fallback fixed; context hygiene roadmap + plan documented in docs/context_hygiene_plan.md.

Your next priorities:
1. Implement wake-word gating in core/voice.py so only commands prefixed with "Jarvis" (or hotkey-triggered) execute. Add regression coverage (e.g., conversation backtest fixture).
2. Improve provider diagnostics (lifeos providers check) to surface Groq latency/status and Ollama availability.
3. Add research extraction unit tests and wire up the context hygiene runner per docs/context_hygiene_plan.md (CLI command + scheduling hook).
4. Run or script a voice-chat validation pass covering provider fallback and UI actions.

Repo has many existing untracked files from earlier work; ignore unless needed. Current git status shows only those legacy items; newly touched files are committed and pushed.
```

## Quick Testing Notes
- No automated tests were run post-fix due to environment constraints; run `PYTHONPATH=. python3 tests/test_conversation_backtest.py` and `python3 test_provider_fixes.py` once the wake-word changes are in place.
- Verify provider health via `lifeos providers check` after restarting the daemon.

## Misc
- Voice chats should be restarted after toggling config/state flags (`lifeos on --apply`).
- Remember the user’s requirement: never open Safari; only use Firefox Developer Edition for UI automation.

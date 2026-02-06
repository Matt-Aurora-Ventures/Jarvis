# Subagent Orchestration (Speed Layer)

Goal: make the fleet *faster* by fanning out work into parallel “subagent” tasks, then synthesizing.

This is **non-destructive by design**: subagents write artifacts; they do not deploy or mutate infra unless explicitly commanded elsewhere.

---

## What’s Implemented (Repo)

### 1) Internal Subagents (In-Process)

File: `core/agents/orchestration.py`

- Runs tasks concurrently using a thread pool (`max_workers`).
- Uses the internal agent registry (`core/agents/registry.py`) to route tasks to:
  - `researcher`, `operator`, `trader`, `architect`
- Tracks spawned tasks via `core/agents/manager.py`
- Writes durable artifacts to: `data/subagents/<session>/`

### 2) CLI Wrapper

File: `scripts/run_subagents.py`

Run multiple tasks in parallel:

```bash
python scripts/run_subagents.py --session "ops:fixit-48h" \
  --task "Summarize last 48h Telegram errors and propose fixes" \
  --task "Audit model/provider config for invalid model IDs" \
  --task "Propose watchdog + healthcheck tuning"
```

Or provide a JSON spec:

```bash
python scripts/run_subagents.py --session "ops:fixit-48h" --spec .planning/subagents_spec.json
```

Spec format:

```json
{
  "tasks": [
    {"description": "Task A", "role": "researcher"},
    {"description": "Task B", "role": "architect"}
  ]
}
```

---

## Cross-Bot Subagents (Fleet-Level) – Next

There is an existing file-bus dispatcher:
- `bots/shared/multi_agent.py` (`MultiAgentDispatcher`)

Important fix shipped:
- Default shared state dir now resolves to `/root/clawdbots/data` (shared volume mount), via `CLAWDBOTS_STATE_DIR`.

Next work (pending):
- add per-bot “task inbox” workers that pick up tasks and write results back.

---

## Ralph Loop Alignment

Use subagents to keep the main context clean:
- Main agent = scheduler + synthesizer
- Subagents = do the heavy lifting + write artifacts

Recommended loop outputs per iteration:
- `.planning/TODO_FLEET_STABILIZATION_*.md` updated
- `reports/telegram_mega_fixit.md` regenerated
- `data/subagents/<session>/...` artifacts appended


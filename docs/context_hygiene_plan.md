# Context Hygiene & Compression Plan

## Goals
- Keep long-term storage (memory JSON, research.db, knowledge_graph) lean without losing signal.
- Automatically compress or delete stale/low-value entries so on-disk usage stays predictable.
- Ensure distilled summaries remain searchable even after raw artifacts are pruned.

## Scheduled Cycle
| Phase | Frequency | Description |
| --- | --- | --- |
| Snapshot | Every 48h (configurable) | Record current counts/size for memory files, research notes, and knowledge graph to `data/hygiene_snapshots.json`. |
| Scoring | Same run | Assign each entry a score using recency, reference count, and tags. Entries linked to active tickets/tasks receive a boost. |
| Compression | Same run | 1) Merge multiple research notes on the same topic into a single markdown summary in `data/summaries/`. 2) Replace raw note content with the summary path once merged. |
| Prune | Same run | Delete or archive entries whose score < threshold and age > retention days (default 14). Database rows are moved to `data/archive` for manual restore. |
| Audit Report | Weekly | Write a short report (counts in/out, space saved) to `lifeos/reports/context_hygiene.md` so MCP doctor can flag regressions. |

## Implementation Sketch
1. **Scoring helper** (`core/context_hygiene.py`):
   - `calculate_entry_score(entry)` uses: `max(0, 100 - age_days*5) + references*10 + priority_boost`.
   - Accepts adapters for memory JSON files, SQLite rows, or knowledge graph nodes.
2. **Compression**:
   - Research notes older than 7 days: concatenate insights/applications into a single markdown summary, replace `content` column with `[COMPRESSED -> path]` token, store summary file.
   - Memory entries: keep only the latest summary per topic; earlier ones downgraded to one-line bullets.
   - Knowledge graph: keep top-N related concepts, drop low-confidence ones.
3. **Pruning thresholds**:
   - Memory: keep last 200 factual entries, else archive to `data/archive/memory_YYYYMM.json`.
   - Research: keep at most 50 notes per topic; rest compressed.
   - Knowledge graph: drop concepts with confidence <0.4 and no references in 30 days.
4. **Automation hook**:
   - Add CLI command `lifeos hygiene run` (future work) so user can trigger manually.
   - Hook into MCP doctor nightly job to run `context_hygiene.run()` when system idle.
5. **Safety**:
   - Every destructive step writes to archive directory first (JSON/CSV dump) with timestamp.
   - Logs summary to `lifeos/logs/context_hygiene.log` for troubleshooting.

## Next Steps
- Implement `core/context_hygiene.py` with adapters for memory + research DB.
- Create CLI command + MCP doctor hook.
- Add unit tests that simulate oversized research.db and verify entries are compressed/pruned as expected.

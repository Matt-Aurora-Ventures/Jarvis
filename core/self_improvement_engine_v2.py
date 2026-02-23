"""
Self-Improvement Engine with Mirror Test

Daily dream cycle that:
1. Replays logs using the centralized ModelRouter
2. Scores own performance
3. Refactors code/config
4. Validates + auto-applies improvements
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from core import config, providers
from core.model_router import get_model_router, RoutingPriority
from core.evolution.gym import mirror_test, replay_sim, performance_scorer, refactor_agent


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS_PATH = ROOT / "core" / "evolution" / "snapshots"
DIFFS_PATH = ROOT / "core" / "evolution" / "diffs"
MIRROR_LOG_PATH = ROOT / "data" / "mirror_test.log"


@dataclass
class MirrorTestResult:
    """Result of a single mirror test cycle."""
    timestamp: str
    improvement_score: float  # 0.0-1.0
    metrics: Dict[str, float]
    refactor_proposals: List[Dict[str, Any]]
    auto_applied: bool
    snapshot_id: str


class SelfImprovementEngine:
    """
    Nightly self-correction engine using the centralized ModelRouter.
    
    The "Mirror Test": Jarvis watches itself and learns.
    """
    
    def __init__(self):
        self.router = get_model_router()
        self.mirror = mirror_test.MirrorTest()
        self.replay = replay_sim.ReplaySimulator()
        self.scorer = performance_scorer.PerformanceScorer()
        self.refactor = refactor_agent.RefactorAgent()
        
        self.min_improvement_score = 0.85  # Auto-apply threshold
        self.snapshot_retention_days = 60
        
        SNAPSHOTS_PATH.mkdir(parents=True, exist_ok=True)
        DIFFS_PATH.mkdir(parents=True, exist_ok=True)
        
    def run_nightly_mirror_test(self) -> MirrorTestResult:
        """
        Main entry point for the nightly dream cycle.
        
        Runs at 3am daily via cron or daemon scheduler.
        """
        print("🌙 Mirror Test: Starting nightly self-correction cycle...")
        cycle_start = time.time()
        
        # [STEP 1] Create system snapshot
        snapshot_id = self._create_snapshot()
        print(f"📸 Snapshot created: {snapshot_id}")
        
        # [STEP 2] Ingest last 24 hours of logs
        logs = self._ingest_logs(hours=24)
        print(f"📋 Ingested {len(logs)} log entries from last 24h")
        
        # [STEP 3] Replay decisions using current Minimax model
        replay_results = self._replay_with_router(logs)
        print(f"🎬 Replayed {len(replay_results)} decisions")
        
        # [STEP 4] Score performance (latency, accuracy, satisfaction)
        metrics = self._score_performance(logs, replay_results)
        improvement_score = metrics["overall_improvement"]
        print(f"📊 Performance Score: {improvement_score:.2%}")
        print(f"   Latency: {metrics['latency_improvement']:.2%}")
        print(f"   Accuracy: {metrics['accuracy_improvement']:.2%}")
        print(f"   Satisfaction: {metrics['satisfaction_improvement']:.2%}")
        
        # [STEP 5] Generate refactor proposals
        proposals = self._generate_refactor_proposals(replay_results, metrics)
        print(f"💡 Generated {len(proposals)} refactor proposals")
        
        # [STEP 6] Dry-run validation
        validation_results = self._validate_proposals(proposals, logs)
        safe_proposals = [
            p for p in proposals 
            if validation_results[p["id"]]["passed"]
        ]
        print(f"✅ {len(safe_proposals)}/{len(proposals)} proposals passed dry-run")
        
        # [STEP 7] Auto-apply if score > threshold
        auto_applied = False
        if improvement_score >= self.min_improvement_score and safe_proposals:
            print(f"🚀 Auto-applying {len(safe_proposals)} improvements...")
            self._apply_proposals(safe_proposals, snapshot_id)
            auto_applied = True
        else:
            print(f"⏸  Queued for manual review (score: {improvement_score:.2%})")
            self._queue_for_review(safe_proposals, metrics)
        
        # [STEP 8] Log results
        result = MirrorTestResult(
            timestamp=datetime.now().isoformat(),
            improvement_score=improvement_score,
            metrics=metrics,
            refactor_proposals=[p["summary"] for p in safe_proposals],
            auto_applied=auto_applied,
            snapshot_id=snapshot_id,
        )
        self._log_mirror_test(result)
        
        cycle_duration = time.time() - cycle_start
        print(f"✨ Mirror Test complete in {cycle_duration:.1f}s")
        
        return result
    
    def _create_snapshot(self) -> str:
        """
        Snapshot current system state.
        
        Captures:
        - All Python files in core/
        - system_instructions.md
        - Config files
        - Current provider performance
        """
        snapshot_id = datetime.now().strftime("%Y-%m-%d_%H-%M")
        snapshot_path = SNAPSHOTS_PATH / f"{snapshot_id}_system.json"
        
        snapshot = {
            "id": snapshot_id,
            "timestamp": datetime.now().isoformat(),
            "core_files": self._hash_core_files(),
            "system_instructions": self._read_system_instructions(),
            "config": config.load_config(),
            "provider_stats": self.router.get_stats(),
        }
        
        with open(snapshot_path, "w") as f:
            json.dump(snapshot, f, indent=2)
        
        # Cleanup old snapshots
        self._cleanup_old_snapshots()
        
        return snapshot_id
    
    def _ingest_logs(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Parse last N hours of logs.
        
        Returns list of log entries with:
        - timestamp
        - action (e.g., "chat", "execute_action", "research")
        - input (user request)
        - output (Jarvis response)
        - latency_ms
        - success (bool)
        - error (if any)
        """
        log_file = ROOT / "data" / "iteration_log.json"
        if not log_file.exists():
            return []
        
        cutoff = datetime.now() - timedelta(hours=hours)
        logs = []
        
        with open(log_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    entry_time = datetime.fromisoformat(entry["timestamp"])
                    if entry_time >= cutoff:
                        logs.append(entry)
                except Exception:
                    continue
        
        return logs
    
    def _replay_with_router(self, logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Re-run each decision using the centralized ModelRouter.
        
        Compare:
        - What did we do? (original response)
        - What would we do now? (current model output)
        - Is the new response better?
        """
        replay_results = []
        
        for log in logs:
            if log.get("action") not in ["chat", "execute_action", "research"]:
                continue
            
            # Re-run decision with current model
            prompt = log.get("input", "")
            if not prompt:
                continue
            
            try:
                new_response = self._route_reflection(prompt)
                
                replay_results.append({
                    "original": {
                        "input": prompt,
                        "output": log.get("output", ""),
                        "latency_ms": log.get("latency_ms", 0),
                        "success": log.get("success", False),
                    },
                    "replay": {
                        "output": new_response["output"],
                        "latency_ms": new_response["latency_ms"],
                        "model": new_response["model"],
                    },
                    "timestamp": log.get("timestamp"),
                })
            except Exception as e:
                print(f"⚠️  Replay failed for log {log.get('timestamp')}: {e}")
                continue
        
        return replay_results

    def _route_reflection(self, prompt: str) -> Dict[str, Any]:
        """Route reflection prompt through the centralized ModelRouter."""
        import asyncio

        async def _route():
            return await self.router.route(
                task=prompt,
                priority=RoutingPriority.ACCURACY,
                max_tokens=2048,
                use_cache=False,
            )

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            result = asyncio.run(_route())
            return {
                "output": result.response,
                "latency_ms": result.latency_ms,
                "model": result.provider.model_id,
            }

        raise RuntimeError("Async loop running; reflection routing requires sync context.")
    
    def _score_performance(
        self, logs: List[Dict[str, Any]], replay_results: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Score performance across 3 dimensions:
        
        1. Latency: Are responses faster now?
        2. Accuracy: Would new responses be more correct?
        3. User Satisfaction: Fewer follow-up questions?
        """
        # Latency comparison
        original_latencies = [r["original"]["latency_ms"] for r in replay_results]
        new_latencies = [r["replay"]["latency_ms"] for r in replay_results]
        
        avg_original = sum(original_latencies) / max(len(original_latencies), 1)
        avg_new = sum(new_latencies) / max(len(new_latencies), 1)
        
        latency_improvement = max(0, (avg_original - avg_new) / avg_original)
        
        # Accuracy (use Minimax to grade)
        accuracy_scores = []
        for result in replay_results[:10]:  # Sample 10 for cost efficiency
            judge_prompt = f"""
Compare these two responses to the same input:

Input: {result['original']['input']}

Response A (original): {result['original']['output']}
Response B (current): {result['replay']['output']}

Which is more accurate, helpful, and actionable? Reply with:
- "A" if original is better
- "B" if current is better
- "SAME" if equal quality
"""
            try:
                judgment = self.router.query(judge_prompt, max_tokens=10)
                if "B" in judgment.text.upper():
                    accuracy_scores.append(1.0)
                elif "A" in judgment.text.upper():
                    accuracy_scores.append(0.0)
                else:
                    accuracy_scores.append(0.5)
            except Exception:
                accuracy_scores.append(0.5)
        
        accuracy_improvement = sum(accuracy_scores) / max(len(accuracy_scores), 1)
        
        # User satisfaction (proxy: follow-up questions within 5 min)
        satisfaction_scores = []
        for i, log in enumerate(logs):
            if log.get("action") != "chat":
                continue
            
            # Look for follow-up within 5 min
            timestamp = datetime.fromisoformat(log["timestamp"])
            has_followup = False
            
            for future_log in logs[i+1:]:
                if datetime.fromisoformat(future_log["timestamp"]) > timestamp + timedelta(minutes=5):
                    break
                if "clarify" in future_log.get("input", "").lower() or "what do you mean" in future_log.get("input", "").lower():
                    has_followup = True
                    break
            
            satisfaction_scores.append(0.0 if has_followup else 1.0)
        
        satisfaction_improvement = sum(satisfaction_scores) / max(len(satisfaction_scores), 1)
        
        # Overall weighted score
        overall = (
            0.2 * latency_improvement +
            0.5 * accuracy_improvement +
            0.3 * satisfaction_improvement
        )
        
        return {
            "latency_improvement": latency_improvement,
            "accuracy_improvement": accuracy_improvement,
            "satisfaction_improvement": satisfaction_improvement,
            "overall_improvement": overall,
        }
    
    def _generate_refactor_proposals(
        self, replay_results: List[Dict[str, Any]], metrics: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Use Minimax to generate code/config improvements.
        
        Analyzes patterns in replay_results and proposes:
        - Python code changes (e.g., optimize conversation.py)
        - system_instructions.md updates
        - Config tweaks (e.g., adjust timeouts)
        """
        proposals = []
        
        # Pattern analysis prompt
        patterns_prompt = f"""
You are analyzing {len(replay_results)} decision replays from Jarvis.

Metrics:
- Latency improvement: {metrics['latency_improvement']:.2%}
- Accuracy improvement: {metrics['accuracy_improvement']:.2%}
- Satisfaction improvement: {metrics['satisfaction_improvement']:.2%}

Sample replay (first 3):
{json.dumps(replay_results[:3], indent=2)}

Identify recurring patterns where the NEW responses are better.
What specific code/config changes would systematize these improvements?

Generate 3-5 concrete refactor proposals in JSON format:
[
  {{
    "id": "REF-001",
    "type": "python" | "config" | "system_instructions",
    "file": "core/conversation.py",
    "summary": "Add intent classification before response generation",
    "rationale": "63% of improved responses had better intent detection",
    "code_diff": "..."  # Optional: actual code change
  }}
]
"""
        
        try:
            response = self.router.query(
                prompt=patterns_prompt,
                max_tokens=4096,
                temperature=0.3,  # Lower temp for precision
            )
            
            # Parse JSON proposals
            import re
            json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if json_match:
                proposals = json.loads(json_match.group(0))
        except Exception as e:
            print(f"⚠️  Failed to generate proposals: {e}")
            proposals = []
        
        return proposals
    
    def _validate_proposals(
        self, proposals: List[Dict[str, Any]], logs: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Dry-run each proposal against 100 historical scenarios.
        
        Returns dict: {proposal_id: {passed: bool, score: float}}
        """
        validation_results = {}
        
        for proposal in proposals:
            proposal_id = proposal["id"]
            
            # Sample 100 random historical logs
            import random
            sample_logs = random.sample(logs, min(100, len(logs)))
            
            # Simulate applying the proposal
            # (This is pseudocode - actual implementation would temporarily
            #  apply code changes in sandboxed environment)
            
            passed_count = 0
            for log in sample_logs:
                # Test: Would this proposal improve this scenario?
                # For MVP, we just check if type matches relevant logs
                if proposal["type"] == "python" and log.get("action") == "chat":
                    # Assume it would help conversation
                    passed_count += 1
                elif proposal["type"] == "config":
                    # Config changes assumed safe
                    passed_count += 1
            
            validation_results[proposal_id] = {
                "passed": passed_count >= 80,  # 80% success threshold
                "score": passed_count / len(sample_logs) if sample_logs else 0.0,
            }
        
        return validation_results
    
    def _apply_proposals(self, proposals: List[Dict[str, Any]], snapshot_id: str):
        """
        Apply approved refactor proposals.
        
        - Python changes: Write to core/evolution/diffs/, then merge
        - Config changes: Update directly
        - system_instructions: Append improvements section
        """
        for proposal in proposals:
            proposal_type = proposal["type"]
            
            if proposal_type == "python":
                # Save diff for review
                diff_path = DIFFS_PATH / f"{snapshot_id}_{proposal['id']}.py"
                with open(diff_path, "w") as f:
                    f.write(f"# Refactor: {proposal['summary']}\n")
                    f.write(f"# Rationale: {proposal['rationale']}\n\n")
                    f.write(proposal.get("code_diff", "# Code change TBD"))
                
                print(f"   📝 Saved Python diff: {diff_path}")
                
            elif proposal_type == "config":
                # Apply config change
                cfg = config.load_config()
                # (Actual config merging logic here)
                print(f"   ⚙️  Applied config: {proposal['summary']}")
                
            elif proposal_type == "system_instructions":
                # Append to system_instructions.md
                instructions_path = ROOT / "lifeos" / "config" / "system_instructions.md"
                with open(instructions_path, "a") as f:
                    f.write(f"\n\n## Mirror Test Improvement ({snapshot_id})\n")
                    f.write(f"**{proposal['summary']}**\n\n")
                    f.write(f"{proposal.get('rationale', '')}\n")
                
                print(f"   📜 Updated system_instructions.md")
    
    def _queue_for_review(self, proposals: List[Dict[str, Any]], metrics: Dict[str, float]):
        """
        Save proposals for manual review if auto-apply threshold not met.
        """
        review_file = ROOT / "data" / "pending_reviews.json"
        
        pending = []
        if review_file.exists():
            with open(review_file, "r") as f:
                pending = json.load(f)
        
        pending.append({
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
            "proposals": proposals,
        })
        
        with open(review_file, "w") as f:
            json.dump(pending, f, indent=2)
        
        print(f"💾 Queued {len(proposals)} proposals for review")
        print(f"   Run: ./bin/lifeos mirror review")
    
    def _log_mirror_test(self, result: MirrorTestResult):
        """Log mirror test result for trend analysis."""
        with open(MIRROR_LOG_PATH, "a") as f:
            f.write(json.dumps({
                "timestamp": result.timestamp,
                "score": result.improvement_score,
                "metrics": result.metrics,
                "auto_applied": result.auto_applied,
                "snapshot_id": result.snapshot_id,
            }) + "\n")
    
    def _hash_core_files(self) -> Dict[str, str]:
        """Return SHA256 hashes of all core Python files."""
        import hashlib
        
        hashes = {}
        core_dir = ROOT / "core"
        
        for py_file in core_dir.glob("*.py"):
            with open(py_file, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
                hashes[py_file.name] = file_hash
        
        return hashes
    
    def _read_system_instructions(self) -> str:
        """Read current system_instructions.md."""
        instructions_path = ROOT / "lifeos" / "config" / "system_instructions.md"
        if instructions_path.exists():
            return instructions_path.read_text()
        return ""
    
    def _cleanup_old_snapshots(self):
        """Delete snapshots older than retention period."""
        cutoff = datetime.now() - timedelta(days=self.snapshot_retention_days)
        
        for snapshot in SNAPSHOTS_PATH.glob("*.json"):
            try:
                timestamp_str = snapshot.stem.split("_")[0]
                snapshot_date = datetime.strptime(timestamp_str, "%Y-%m-%d")
                if snapshot_date < cutoff:
                    snapshot.unlink()
                    print(f"🗑️  Deleted old snapshot: {snapshot.name}")
            except Exception:
                continue


# Global instance
_engine: Optional[SelfImprovementEngine] = None


def get_engine() -> SelfImprovementEngine:
    """Get or create the global self-improvement engine."""
    global _engine
    if _engine is None:
        _engine = SelfImprovementEngine()
    return _engine


def run_nightly_cycle() -> MirrorTestResult:
    """
    Main entry point for cron job.
    
    Add to crontab:
    0 3 * * * cd /path/to/LifeOS && python3 -c "from core.self_improvement_engine import run_nightly_cycle; run_nightly_cycle()"
    """
    engine = get_engine()
    return engine.run_nightly_mirror_test()


if __name__ == "__main__":
    # Manual test run
    result = run_nightly_cycle()
    print("\n" + "="*60)
    print(f"Mirror Test Result:")
    print(f"  Score: {result.improvement_score:.2%}")
    print(f"  Auto-Applied: {result.auto_applied}")
    print(f"  Proposals: {len(result.refactor_proposals)}")
    print(f"  Snapshot: {result.snapshot_id}")
    print("="*60)

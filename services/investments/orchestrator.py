"""Master Orchestrator — runs the full agent pipeline per cycle.

Pipeline: analysts (parallel) → debate → risk officer → trader → record → schedule reflection.
In dry-run mode, basket state is mocked from a JSON file.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import asyncpg
import redis.asyncio as aioredis

from services.investments.agents.chatgpt_agent import ChatGPTMacroAnalyst
from services.investments.agents.claude_agent import ClaudeRiskAnalyst
from services.investments.agents.dexter_agent import DexterFundamentalAnalyst
from services.investments.agents.grok_agent import GrokSentimentAnalyst
from services.investments.config import InvestmentConfig
from services.investments.consensus.debate import AdversarialDebate
from services.investments.consensus.reflection import ReflectionEngine
from services.investments.consensus.risk_officer import RiskOfficer
from services.investments.consensus.trader import TraderAgent
from services.investments.safety import SafetySystem

logger = logging.getLogger("investments.orchestrator")


class Orchestrator:
    """Wires all agents together and runs one investment cycle."""

    def __init__(self, cfg: InvestmentConfig, db: asyncpg.Pool, rds: aioredis.Redis) -> None:
        self.cfg = cfg
        self.db = db
        self.redis = rds

        # Safety
        self.safety = SafetySystem(db, rds)

        # Analysts
        self.grok = GrokSentimentAnalyst(cfg.xai_api_key, cfg.grok_sentiment_model)
        self.claude = ClaudeRiskAnalyst(cfg.anthropic_api_key, cfg.claude_risk_model)
        self.chatgpt = ChatGPTMacroAnalyst(cfg.openai_api_key, cfg.chatgpt_macro_model)
        self.dexter = DexterFundamentalAnalyst(cfg.birdeye_api_key)

        # Consensus
        self.debate = AdversarialDebate(cfg.anthropic_api_key, cfg.openai_api_key)
        self.risk_officer = RiskOfficer(cfg.anthropic_api_key, cfg.claude_risk_model)
        self.trader = TraderAgent(cfg.xai_api_key, cfg.grok_trader_model)

        # Reflection
        self.reflection = ReflectionEngine(db)

        # Phase 2: Alvara basket manager (lazy-init, only when not dry-run)
        self._alvara: Any = None

        # Phase 3: Bridge controller + trigger (lazy-init)
        self._bridge_controller: Any = None
        self._bridge_trigger: Any = None

        # Phase 4: Staking cranker (lazy-init)
        self._staking_cranker: Any = None

    def _get_alvara(self) -> Any:
        if self._alvara is None:
            from services.investments.alvara_manager import AlvaraManager
            self._alvara = AlvaraManager(self.cfg)
        return self._alvara

    def _get_bridge(self) -> tuple[Any, Any]:
        if self._bridge_controller is None:
            from services.investments.bridge_controller import BridgeController
            from services.investments.bridge_trigger import BridgeTrigger
            self._bridge_controller = BridgeController(self.cfg, self.db, self.redis)
            self._bridge_trigger = BridgeTrigger(
                self.cfg, self.db, self.redis, self._bridge_controller, self.safety,
            )
        return self._bridge_controller, self._bridge_trigger

    def _get_cranker(self) -> Any:
        if self._staking_cranker is None:
            from services.investments.staking_cranker import StakingCranker
            self._staking_cranker = StakingCranker(self.cfg, self.db, self.redis)
        return self._staking_cranker

    async def run_cycle(self) -> dict[str, Any]:
        """Execute one full investment cycle. Returns decision record."""
        cycle_start = datetime.now(timezone.utc)
        logger.info("Investment cycle started at %s", cycle_start.isoformat())

        # Gate: kill switch
        if await self.safety.is_killed():
            logger.warning("Kill switch active — skipping cycle")
            return {"status": "killed", "ts": cycle_start.isoformat()}

        # Gate: loss limiter
        loss_ok, loss_msg = await self.safety.check_loss_limits()
        if not loss_ok:
            logger.warning("Loss limiter triggered: %s", loss_msg)
            return {"status": "loss_halt", "reason": loss_msg, "ts": cycle_start.isoformat()}

        # Gate: idempotency
        cycle_key = f"cycle:{cycle_start.strftime('%Y-%m-%d')}"
        if not await self.safety.check_idempotency(cycle_key):
            logger.info("Cycle already ran today — skipping")
            return {"status": "already_ran", "ts": cycle_start.isoformat()}

        try:
            basket = await self._get_basket_state()
            current_weights = {t: d["weight"] for t, d in basket["tokens"].items()}
            token_list = list(basket["tokens"].keys())
            nav = basket["nav_usd"]

            # -- Step 1: Get calibration hints (needed by analysts) --
            calibration = await self.reflection.get_calibration_hints(limit=5)

            # -- Step 2: Run all analysts in parallel --
            logger.info("Running %d analysts on %d tokens...", 4, len(token_list))

            # Build input structures matching each agent's signature
            grok_tokens = [{"symbol": t, "name": t} for t in token_list]
            dexter_tokens = [
                {"symbol": t, "address": basket["tokens"][t].get("address", "")}
                for t in token_list
            ]
            basket_state_for_llm = {
                "tokens": [
                    {
                        "symbol": t,
                        "weight": d["weight"],
                        "value_usd": d["price_usd"] * d["weight"] * nav,
                        "change_24h": d.get("change_24h", 0),
                    }
                    for t, d in basket["tokens"].items()
                ],
                "nav_usd": nav,
            }
            market_data_stub = {
                "btc_change_24h": 0,
                "eth_change_24h": 0,
                "fear_greed": "N/A",
            }

            grok_task = self.grok.analyze_basket(grok_tokens)
            claude_task = self.claude.analyze(
                basket_state_for_llm, market_data_stub, calibration,
            )
            chatgpt_task = self.chatgpt.analyze(
                basket_state_for_llm, market_data_stub, calibration,
            )
            dexter_task = self.dexter.analyze(dexter_tokens)

            grok_report, claude_report, chatgpt_report, dexter_report = (
                await asyncio.gather(
                    grok_task, claude_task, chatgpt_task, dexter_task,
                    return_exceptions=True,
                )
            )

            # Coerce exceptions to empty dicts
            analyst_reports = {
                "grok_sentiment": grok_report if not isinstance(grok_report, Exception) else {"error": str(grok_report)},
                "claude_risk": claude_report if not isinstance(claude_report, Exception) else {"error": str(claude_report)},
                "chatgpt_macro": chatgpt_report if not isinstance(chatgpt_report, Exception) else {"error": str(chatgpt_report)},
                "dexter_fundamental": dexter_report if not isinstance(dexter_report, Exception) else {"error": str(dexter_report)},
            }
            logger.info("Analyst reports collected: %s", list(analyst_reports.keys()))

            # -- Step 3: Adversarial debate (Bull vs Bear, up to 3 rounds) --
            logger.info("Starting adversarial debate...")
            rounds = await self.debate.run_debate(analyst_reports, basket, calibration)
            final_bull = rounds[-1]["bull_thesis"] if rounds else {}
            final_bear = rounds[-1]["bear_thesis"] if rounds else {}
            logger.info("Debate finished: %d rounds", len(rounds))

            # -- Step 4: Risk officer evaluation --
            proposed_weights = final_bull.get("proposed_weights", current_weights)
            proposed_action = final_bull.get("proposed_action", "HOLD")
            token_liquidities = {t: d["liquidity_usd"] for t, d in basket["tokens"].items()}

            daily_changes = await self._get_daily_changes_pct()
            risk_assessment = await self.risk_officer.evaluate(
                proposed_action=proposed_action,
                proposed_weights=proposed_weights,
                current_weights=current_weights,
                basket_nav_usd=nav,
                token_liquidities=token_liquidities,
                risk_report=analyst_reports.get("claude_risk", {}),
                daily_changes_so_far_pct=daily_changes,
            )
            logger.info(
                "Risk officer: approved=%s, violations=%d",
                risk_assessment.get("approved"),
                len(risk_assessment.get("risk_violations", [])),
            )

            # -- Step 5: Trader final decision --
            decision_history = await self._get_recent_decisions(5)
            trade_decision = await self.trader.decide(
                bull_thesis=final_bull,
                bear_thesis=final_bear,
                risk_assessment=risk_assessment,
                analyst_reports=analyst_reports,
                current_weights=current_weights,
                basket_nav_usd=nav,
                calibration_hints=calibration,
                decision_history=decision_history,
            )
            logger.info(
                "Trader decision: action=%s, confidence=%.2f",
                trade_decision.get("action"),
                trade_decision.get("confidence", 0),
            )

            # -- Step 6: Safety check on proposed weights --
            if trade_decision["action"] == "REBALANCE":
                safe, safe_msg = await self.safety.check_portfolio_limits(
                    trade_decision.get("final_weights", {}),
                    current_weights,
                )
                if not safe:
                    logger.warning("Safety vetoed rebalance: %s", safe_msg)
                    trade_decision["action"] = "HOLD"
                    trade_decision["reasoning"] = (trade_decision.get("reasoning") or "") + f" [Safety override: {safe_msg}]"

            # -- Step 7: Execute (dry-run or real) --
            tx_hash = await self._execute_decision(trade_decision, current_weights)

            # -- Step 8: Record decision to database --
            decision_id = await self._store_decision(
                trade_decision=trade_decision,
                analyst_reports=analyst_reports,
                debate_rounds=rounds,
                risk_assessment=risk_assessment,
                nav=nav,
                tx_hash=tx_hash,
            )

            # -- Step 9: Broadcast via Redis pub/sub --
            await self.redis.publish(
                "investments:decisions",
                json.dumps({
                    "decision_id": decision_id,
                    "action": trade_decision["action"],
                    "confidence": trade_decision.get("confidence", 0),
                    "nav_usd": nav,
                    "ts": cycle_start.isoformat(),
                }),
            )

            elapsed = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            logger.info("Cycle complete in %.1fs — decision_id=%s", elapsed, decision_id)

            return {
                "status": "completed",
                "decision_id": decision_id,
                "action": trade_decision["action"],
                "confidence": trade_decision.get("confidence", 0),
                "nav_usd": nav,
                "tx_hash": tx_hash,
                "elapsed_s": elapsed,
                "ts": cycle_start.isoformat(),
            }

        except Exception:
            logger.exception("Cycle failed")
            await self.safety.clear_idempotency(cycle_key)
            raise

    # ── Basket State ───────────────────────────────────────────────────────

    async def _get_basket_state(self) -> dict[str, Any]:
        """Get current basket state. Dry-run reads mock JSON; live reads from chain."""
        if self.cfg.dry_run:
            mock_path = Path(__file__).parent / "mock_basket.json"
            if mock_path.exists():
                return json.loads(mock_path.read_text())
            return {
                "tokens": {
                    "ALVA": {"weight": 0.10, "price_usd": 0.50, "liquidity_usd": 200_000},
                    "WETH": {"weight": 0.25, "price_usd": 3200.0, "liquidity_usd": 5_000_000},
                    "cbBTC": {"weight": 0.20, "price_usd": 95000.0, "liquidity_usd": 3_000_000},
                    "USDC": {"weight": 0.15, "price_usd": 1.0, "liquidity_usd": 50_000_000},
                    "AERO": {"weight": 0.15, "price_usd": 1.80, "liquidity_usd": 500_000},
                    "DEGEN": {"weight": 0.15, "price_usd": 0.012, "liquidity_usd": 300_000},
                },
                "nav_usd": 200.0,
            }

        return await self._get_alvara().get_basket_state()

    async def _execute_decision(
        self, decision: dict, current_weights: dict
    ) -> Optional[str]:
        """Execute the trade decision. Returns tx hash or None."""
        if decision["action"] == "HOLD":
            return None

        if self.cfg.dry_run:
            logger.info(
                "[DRY RUN] Would execute %s: %s",
                decision["action"],
                decision.get("final_weights", {}),
            )
            return "0x_dry_run_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        return await self._get_alvara().rebalance(decision.get("final_weights", {}))

    # ── Bridge + Staking Helpers ───────────────────────────────────────────

    async def check_and_bridge_fees(self) -> Optional[int]:
        """Check if fees should be bridged. Called by scheduler."""
        _, trigger = self._get_bridge()
        return await trigger.check_and_trigger()

    async def advance_bridge_jobs(self) -> list[dict]:
        """Advance all pending bridge jobs. Called by scheduler."""
        controller, _ = self._get_bridge()
        return await controller.advance_all_pending()

    async def run_staking_deposit(self) -> dict:
        """Deposit pending USDC rewards to staking pool. Called by scheduler."""
        return await self._get_cranker().run_deposit_cycle()

    # ── Database Helpers ───────────────────────────────────────────────────

    async def _store_decision(
        self,
        trade_decision: dict,
        analyst_reports: dict,
        debate_rounds: list,
        risk_assessment: dict,
        nav: float,
        tx_hash: Optional[str],
    ) -> int:
        row = await self.db.fetchrow(
            """
            INSERT INTO inv_decisions (
                basket_id, action, final_weights, reasoning, confidence,
                grok_sentiment_report, claude_risk_report,
                chatgpt_macro_report, dexter_fundamental_report,
                debate_rounds, risk_assessment, nav_usd, tx_hash, created_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW()
            ) RETURNING id
            """,
            self.cfg.basket_id,
            trade_decision.get("action", "HOLD"),
            json.dumps(trade_decision.get("final_weights", {})),
            trade_decision.get("reasoning", ""),
            trade_decision.get("confidence", 0.0),
            json.dumps(analyst_reports.get("grok_sentiment", {})),
            json.dumps(analyst_reports.get("claude_risk", {})),
            json.dumps(analyst_reports.get("chatgpt_macro", {})),
            json.dumps(analyst_reports.get("dexter_fundamental", {})),
            json.dumps([dict(r) for r in debate_rounds], default=str),
            json.dumps(dict(risk_assessment), default=str),
            nav,
            tx_hash,
        )
        return row["id"]

    async def _get_recent_decisions(self, limit: int = 5) -> list[dict]:
        rows = await self.db.fetch(
            """
            SELECT id, action, confidence, nav_usd, reasoning, created_at
            FROM inv_decisions
            WHERE basket_id = $1
            ORDER BY created_at DESC LIMIT $2
            """,
            self.cfg.basket_id,
            limit,
        )
        return [dict(r) for r in rows]

    async def _get_daily_changes_pct(self) -> float:
        row = await self.db.fetchrow(
            """
            SELECT COALESCE(SUM(
                (SELECT SUM(ABS(v::float)) FROM jsonb_each_text(final_weights::jsonb) AS t(k, v))
            ), 0) as total
            FROM inv_decisions
            WHERE basket_id = $1
              AND action = 'REBALANCE'
              AND created_at > NOW() - INTERVAL '24 hours'
            """,
            self.cfg.basket_id,
        )
        return float(row["total"] or 0) if row else 0.0

    # ── Snapshot Writer ────────────────────────────────────────────────────

    async def snapshot_nav(self) -> None:
        """Write current NAV to the time-series table. Called by scheduler."""
        basket = await self._get_basket_state()
        await self.db.execute(
            "INSERT INTO inv_nav_snapshots (basket_id, nav_usd) VALUES ($1, $2)",
            self.cfg.basket_id,
            basket["nav_usd"],
        )

    async def close(self) -> None:
        """Clean up HTTP clients."""
        for agent_attr in ("grok", "claude", "chatgpt", "trader"):
            agent = getattr(self, agent_attr, None)
            if agent is not None:
                try:
                    await agent.close()
                except Exception:
                    pass
        if self._alvara:
            try:
                await self._alvara.close()
            except Exception:
                pass

"""LogicCore: 5-phase transparency engine for trading decisions."""

from __future__ import annotations

import logging
import math
import os
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from core import config
from core.trading_strategies import ArbitrageScanner, MeanReversion, TrendFollower, TradeSignal


logger = logging.getLogger(__name__)


@dataclass
class LogicCoreConfig:
    """Thresholds and settings for LogicCore decisions."""

    max_loss_pct: float = 0.02
    position_size_pct: float = 0.08
    min_velocity_per_hour: float = 0.25
    min_confidence: float = 0.55
    min_roi_pct: float = 0.015
    top_percentile: float = 0.01
    entry_offset_pct: float = 0.001
    atr_period: int = 14
    atr_multiplier: float = 1.5
    risk_reward: float = 3.0
    execute_on_pass: bool = False
    default_expected_time_minutes: float = 45.0


@dataclass
class TelegramConfig:
    enabled: bool = False
    bot_token_env: str = "TELEGRAM_BOT_TOKEN"
    chat_id_env: str = "TELEGRAM_CHAT_ID"
    timeout_seconds: int = 10


@dataclass
class MarketSnapshot:
    symbol: str
    prices: List[float]
    volumes: Optional[List[float]] = None
    volatility: Optional[float] = None
    fear_greed: Optional[float] = None
    news_event: bool = False
    candidates: Optional[List["TradeCandidate"]] = None
    dex_prices: Optional[Dict[str, float]] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeCandidate:
    symbol: str
    expected_roi_pct: float
    expected_time_minutes: float
    confidence: float = 0.5
    direction: Optional[str] = None  # "long" | "short"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def velocity_per_hour(self) -> float:
        hours = max(self.expected_time_minutes / 60.0, 1e-6)
        return self.expected_roi_pct / hours


@dataclass
class ExecutionPlan:
    entry: float
    stop: float
    take_profits: List[float]
    risk_reward: float
    direction: str
    atr: float


@dataclass
class GateDecision:
    allowed: bool
    checks: List[Tuple[str, bool, str]] = field(default_factory=list)

    def reasons(self) -> List[str]:
        return [detail for _, ok, detail in self.checks if not ok]


@dataclass
class LogicDecision:
    strategy: str
    sentiment: str
    decision: str
    candidate: Optional[TradeCandidate]
    gate: GateDecision
    plan: Optional[ExecutionPlan]
    metrics: Dict[str, Any]


class LogicCore:
    """5-phase decision engine with transparency broadcast."""

    def __init__(
        self,
        logic_config: Optional[LogicCoreConfig] = None,
        telegram_config: Optional[TelegramConfig] = None,
        *,
        executor: Optional[Callable[[ExecutionPlan, TradeCandidate, LogicDecision], Any]] = None,
        log: Optional[logging.Logger] = None,
    ):
        self.config = logic_config or self._load_logic_config()
        self.telegram = telegram_config or self._load_telegram_config()
        self.executor = executor
        self.log = log or logger

    def run_cycle(self, snapshot: MarketSnapshot) -> LogicDecision:
        sentiment_label, sentiment_score = self._classify_sentiment(snapshot)
        regime, trend_score = self._classify_regime(snapshot.prices)
        strategy = self._select_strategy(snapshot, regime)

        candidates = self._prepare_candidates(snapshot, strategy, sentiment_score)
        best = self._select_best_candidate(candidates)

        signal = self._strategy_signal(strategy, snapshot)
        gate = self._gate_trade(snapshot, best, signal)

        plan: Optional[ExecutionPlan] = None
        if gate.allowed and best:
            plan = self._build_plan(snapshot, best, regime)

        decision = LogicDecision(
            strategy=strategy,
            sentiment=sentiment_label,
            decision="EXECUTE" if gate.allowed and plan else "WAIT",
            candidate=best,
            gate=gate,
            plan=plan,
            metrics={
                "sentiment_score": round(sentiment_score, 3),
                "regime": regime,
                "trend_score": round(trend_score, 3),
                "signal": signal.to_dict() if signal else None,
            },
        )

        self._broadcast(decision)

        if decision.decision == "EXECUTE" and plan and best and self.config.execute_on_pass:
            if self.executor:
                self.executor(plan, best, decision)

        return decision

    def _load_logic_config(self) -> LogicCoreConfig:
        cfg = config.load_config()
        logic_cfg = cfg.get("logic_core", {}) if isinstance(cfg, dict) else {}
        allowed = set(LogicCoreConfig().__dict__.keys())
        return LogicCoreConfig(**{k: v for k, v in logic_cfg.items() if k in allowed})

    def _load_telegram_config(self) -> TelegramConfig:
        cfg = config.load_config()
        telegram_cfg = cfg.get("telegram", {}) if isinstance(cfg, dict) else {}
        return TelegramConfig(
            enabled=bool(telegram_cfg.get("enabled", False)),
            bot_token_env=str(telegram_cfg.get("bot_token_env", "TELEGRAM_BOT_TOKEN")),
            chat_id_env=str(telegram_cfg.get("chat_id_env", "TELEGRAM_CHAT_ID")),
            timeout_seconds=int(telegram_cfg.get("timeout_seconds", 10)),
        )

    def _classify_sentiment(self, snapshot: MarketSnapshot) -> Tuple[str, float]:
        prices = snapshot.prices
        volumes = snapshot.volumes or []

        volatility = snapshot.volatility
        if volatility is None:
            volatility = self._compute_volatility(prices)

        volume_score = 0.0
        if len(volumes) >= 5:
            recent = volumes[-1]
            avg = statistics.mean(volumes[-5:])
            if avg > 0:
                volume_score = (recent - avg) / avg

        fear_greed = snapshot.fear_greed
        fg_score = 0.0
        if fear_greed is not None:
            fg_score = (fear_greed - 50.0) / 100.0

        sentiment_score = 0.5
        sentiment_score += max(-0.2, min(0.2, volume_score * 0.15))
        sentiment_score -= min(0.25, volatility * 3.0)
        sentiment_score += max(-0.25, min(0.25, fg_score))
        sentiment_score = max(0.0, min(1.0, sentiment_score))

        if sentiment_score >= 0.6:
            label = "Bullish"
        elif sentiment_score <= 0.4:
            label = "Bearish"
        else:
            label = "Neutral"
        return label, sentiment_score

    def _classify_regime(self, prices: List[float]) -> Tuple[str, float]:
        if len(prices) < 5:
            return "chopping", 0.0

        slope, r2 = self._linear_regression(prices)
        trend_score = abs(r2)
        slope_pct = 0.0
        if prices[-1] != 0:
            slope_pct = slope / prices[-1]

        if trend_score > 0.6 and abs(slope_pct) > 0.001:
            return "trending", trend_score
        return "chopping", trend_score

    def _select_strategy(self, snapshot: MarketSnapshot, regime: str) -> str:
        if snapshot.news_event:
            return "Arbitrage"
        if regime == "trending":
            return "Momentum"
        return "MeanReversion"

    def _prepare_candidates(
        self,
        snapshot: MarketSnapshot,
        strategy: str,
        sentiment_score: float,
    ) -> List[TradeCandidate]:
        if snapshot.candidates:
            return list(snapshot.candidates)

        volatility = snapshot.volatility or self._compute_volatility(snapshot.prices)
        expected_roi = max(0.01, min(0.15, volatility * 2.5 + sentiment_score * 0.02))
        candidate = TradeCandidate(
            symbol=snapshot.symbol,
            expected_roi_pct=expected_roi,
            expected_time_minutes=self.config.default_expected_time_minutes,
            confidence=0.5 + (sentiment_score - 0.5) * 0.3,
            metadata={"source": "fallback_estimate", "strategy": strategy},
        )
        return [candidate]

    def _select_best_candidate(self, candidates: List[TradeCandidate]) -> Optional[TradeCandidate]:
        if not candidates:
            return None

        ranked = sorted(candidates, key=lambda c: c.velocity_per_hour(), reverse=True)
        cutoff = max(1, int(math.ceil(len(ranked) * self.config.top_percentile)))
        return ranked[:cutoff][0]

    def _strategy_signal(self, strategy: str, snapshot: MarketSnapshot) -> Optional[TradeSignal]:
        if not snapshot.prices:
            return None

        if strategy == "MeanReversion":
            return MeanReversion().analyze(snapshot.prices, snapshot.symbol)
        if strategy == "Momentum":
            return TrendFollower().analyze(snapshot.prices, snapshot.symbol)
        if strategy == "Arbitrage" and snapshot.dex_prices:
            return ArbitrageScanner().scan_multi_dex(snapshot.symbol, snapshot.dex_prices)
        return None

    def _gate_trade(
        self,
        snapshot: MarketSnapshot,
        candidate: Optional[TradeCandidate],
        signal: Optional[TradeSignal],
    ) -> GateDecision:
        checks: List[Tuple[str, bool, str]] = []

        if not candidate:
            return GateDecision(allowed=False, checks=[("candidates", False, "no_candidate")])

        current_price = snapshot.prices[-1] if snapshot.prices else 0.0
        atr = self._estimate_atr(snapshot.prices, self.config.atr_period)
        stop_distance_pct = 0.0
        if current_price > 0:
            stop_distance_pct = (atr * self.config.atr_multiplier) / current_price

        capital_risk_pct = stop_distance_pct * self.config.position_size_pct
        ruin_ok = capital_risk_pct <= self.config.max_loss_pct
        checks.append(("ruin_check", ruin_ok, f"risk={capital_risk_pct:.4f} cap={self.config.max_loss_pct:.4f}"))

        velocity = candidate.velocity_per_hour()
        velocity_ok = velocity >= self.config.min_velocity_per_hour
        checks.append(("velocity_check", velocity_ok, f"velocity/hr={velocity:.3f} min={self.config.min_velocity_per_hour:.3f}"))

        roi_ok = candidate.expected_roi_pct >= self.config.min_roi_pct
        checks.append(("roi_check", roi_ok, f"roi={candidate.expected_roi_pct:.3f} min={self.config.min_roi_pct:.3f}"))

        signal_ok = False
        if signal:
            signal_ok = signal.action != "HOLD" and signal.confidence >= self.config.min_confidence
        checks.append(("setup_check", signal_ok, f"signal={signal.action if signal else 'none'} conf={signal.confidence if signal else 0:.2f}"))

        allowed = all(ok for _, ok, _ in checks)
        return GateDecision(allowed=allowed, checks=checks)

    def _build_plan(
        self,
        snapshot: MarketSnapshot,
        candidate: TradeCandidate,
        regime: str,
    ) -> ExecutionPlan:
        prices = snapshot.prices
        current_price = prices[-1] if prices else 0.0
        atr = self._estimate_atr(prices, self.config.atr_period)

        direction = candidate.direction
        if not direction:
            direction = self._infer_direction(prices, regime)

        if direction == "long":
            entry = current_price * (1 - self.config.entry_offset_pct)
            stop = entry - (atr * self.config.atr_multiplier)
            risk = max(entry - stop, 0.0)
            tp1 = entry + risk
            tp2 = entry + (risk * 2)
            tp3 = entry + (risk * self.config.risk_reward)
        else:
            entry = current_price * (1 + self.config.entry_offset_pct)
            stop = entry + (atr * self.config.atr_multiplier)
            risk = max(stop - entry, 0.0)
            tp1 = entry - risk
            tp2 = entry - (risk * 2)
            tp3 = entry - (risk * self.config.risk_reward)

        return ExecutionPlan(
            entry=entry,
            stop=stop,
            take_profits=[tp1, tp2, tp3],
            risk_reward=self.config.risk_reward,
            direction=direction,
            atr=atr,
        )

    def _broadcast(self, decision: LogicDecision) -> None:
        message = self._format_broadcast(decision)
        sent = self._send_telegram(message)
        if not sent:
            self.log.warning("LogicCore Telegram broadcast failed; check TELEGRAM_BOT_TOKEN/CHAT_ID.")

    def _format_broadcast(self, decision: LogicDecision) -> str:
        plan = decision.plan
        candidate = decision.candidate

        logic_lines = []
        for name, ok, detail in decision.gate.checks:
            status = "Met" if ok else "Fail"
            logic_lines.append(f"- {name}: {status} ({detail})")

        execution_lines = ["- Entry: N/A", "- Stop: N/A", "- TP Target: N/A"]
        if plan:
            execution_lines = [
                f"- Entry: ${plan.entry:.6f}",
                f"- Stop: ${plan.stop:.6f}",
                f"- TP1: ${plan.take_profits[0]:.6f}",
                f"- TP2: ${plan.take_profits[1]:.6f}",
                f"- TP3: ${plan.take_profits[2]:.6f}",
            ]

        rr = f"1:{int(decision.plan.risk_reward) if decision.plan else 0}"
        roi = f"{candidate.expected_roi_pct * 100:.2f}%" if candidate else "N/A"
        velocity = f"{candidate.velocity_per_hour():.3f}/hr" if candidate else "N/A"

        return "\n".join(
            [
                "🧠 LOGIC CORE DECISION",
                "----------------------",
                f"🎯 STRATEGY: {decision.strategy}",
                f"📊 SENTIMENT: {decision.sentiment}",
                "",
                f"✅ DECISION: {decision.decision}",
                "",
                "🔍 THE LOGIC:",
                *logic_lines,
                f"- Risk/Reward: {rr}",
                f"- ROI/Time: {roi} @ {velocity}",
                "",
                "📉 EXECUTION:",
                *execution_lines,
            ]
        )

    def _send_telegram(self, message: str) -> bool:
        token = os.getenv(self.telegram.bot_token_env, "")
        chat_id = os.getenv(self.telegram.chat_id_env, "")
        if not (self.telegram.enabled and token and chat_id):
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        try:
            resp = requests.post(url, json=payload, timeout=self.telegram.timeout_seconds)
            return resp.ok
        except requests.RequestException:
            return False

    def _compute_volatility(self, prices: List[float]) -> float:
        if len(prices) < 3:
            return 0.0
        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] == 0:
                continue
            returns.append(math.log(prices[i] / prices[i - 1]))
        if len(returns) < 2:
            return 0.0
        return statistics.stdev(returns)

    def _linear_regression(self, prices: List[float]) -> Tuple[float, float]:
        n = len(prices)
        if n < 2:
            return 0.0, 0.0
        xs = list(range(n))
        mean_x = statistics.mean(xs)
        mean_y = statistics.mean(prices)
        ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, prices))
        ss_xx = sum((x - mean_x) ** 2 for x in xs)
        slope = ss_xy / ss_xx if ss_xx else 0.0

        ss_tot = sum((y - mean_y) ** 2 for y in prices)
        ss_res = sum((y - (slope * x + mean_y - slope * mean_x)) ** 2 for x, y in zip(xs, prices))
        r2 = 1 - (ss_res / ss_tot) if ss_tot else 0.0
        return slope, r2

    def _estimate_atr(self, prices: List[float], period: int) -> float:
        if len(prices) < 2:
            return 0.0
        ranges = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
        if not ranges:
            return 0.0
        window = ranges[-period:] if period > 0 else ranges
        return statistics.mean(window)

    def _infer_direction(self, prices: List[float], regime: str) -> str:
        if len(prices) < 2:
            return "long"
        if regime == "trending":
            slope, _ = self._linear_regression(prices)
            return "long" if slope >= 0 else "short"
        if regime == "chopping":
            mean_price = statistics.mean(prices[-min(len(prices), 20):])
            return "short" if prices[-1] > mean_price else "long"
        return "long"

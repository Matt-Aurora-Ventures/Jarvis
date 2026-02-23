"""
Paper-Trading Coliseum - Automated Strategy Backtesting

Runs 81 extracted strategies through 10 randomized 90-day simulations.
Auto-prunes strategies that fail 5+ tests.
Promotes high-performing strategies to live candidates.
"""

import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import random

from core import life_os_router, config


ROOT = Path(__file__).resolve().parents[1]
COLISEUM_PATH = ROOT / "data" / "trading" / "coliseum"
ARENA_DB = COLISEUM_PATH / "arena_results.db"
HISTORICAL_PATH = COLISEUM_PATH / "historical_snapshots"
CEMETERY_PATH = COLISEUM_PATH / "strategy_cemetery"
LIVE_CANDIDATES_PATH = ROOT / "data" / "trading" / "live_candidates"

STRATEGY_CATALOG = ROOT / "data" / "notion_deep" / "strategy_catalog.json"


@dataclass
class BacktestResult:
    """Result of a single backtest run."""
    strategy_id: str
    window_start: str
    window_end: str
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    final_pnl: float
    passed: bool
    data_source: str = "synthetic_randomized"
    promotable: bool = False
    validation_excluded: bool = True


class TradingColiseum:
    """
    Auto-backtesting arena for trading strategies.
    
    Lifecycle:
    1. Load strategy from catalog
    2. Run 10 randomized 90-day simulations (3 months each)
    3. Auto-prune on 5 failures
    4. Promote on Sharpe >1.5 across all tests
    """
    
    def __init__(self):
        self.router = life_os_router.MiniMaxRouter()
        
        # Create directories
        COLISEUM_PATH.mkdir(parents=True, exist_ok=True)
        HISTORICAL_PATH.mkdir(parents=True, exist_ok=True)
        CEMETERY_PATH.mkdir(parents=True, exist_ok=True)
        LIVE_CANDIDATES_PATH.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Auto-prune thresholds
        self.max_consecutive_failures = 5
        self.min_sharpe_for_promotion = 1.5
        self.min_win_rate = 0.45
        self.max_drawdown_threshold = 0.25
    
    def _init_database(self):
        """Create arena results database."""
        conn = sqlite3.connect(ARENA_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT NOT NULL,
                window_start TEXT NOT NULL,
                window_end TEXT NOT NULL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                win_rate REAL,
                profit_factor REAL,
                total_trades INTEGER,
                final_pnl REAL,
                passed INTEGER,
                timestamp TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_status (
                strategy_id TEXT PRIMARY KEY,
                total_tests INTEGER DEFAULT 0,
                passed_tests INTEGER DEFAULT 0,
                failed_tests INTEGER DEFAULT 0,
                consecutive_failures INTEGER DEFAULT 0,
                status TEXT DEFAULT 'testing',
                last_updated TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cemetery (
                strategy_id TEXT PRIMARY KEY,
                deleted_at TEXT NOT NULL,
                reason TEXT,
                final_stats TEXT,
                autopsy TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def run_all_strategies(self) -> Dict[str, Any]:
        """
        Run backtests on all strategies in catalog.
        
        Returns summary of promotions, deletions, and pending.
        """
        print("⚔️  Paper-Trading Coliseum: Starting arena battles...\n")
        
        # Load strategy catalog
        strategies = self._load_strategies()
        print(f"📋 Loaded {len(strategies)} strategies from catalog\n")
        
        summary = {
            "total_strategies": len(strategies),
            "tested": 0,
            "promoted": 0,
            "deleted": 0,
            "pending": 0,
        }
        
        for strategy in strategies:
            strategy_id = strategy["strategy_id"]
            
            # Check if already processed
            status = self._get_strategy_status(strategy_id)
            if status["status"] in ("promoted", "deleted"):
                continue
            
            print(f"🎯 Testing: {strategy['name']} ({strategy_id})")
            
            # Run 10 randomized backtests
            results = self._run_strategy_backtests(strategy)
            summary["tested"] += 1
            
            # Evaluate results
            decision = self._evaluate_strategy(strategy_id, results)
            
            if decision == "PROMOTE":
                self._promote_strategy(strategy)
                summary["promoted"] += 1
                print(f"   ✅ PROMOTED to live candidates\n")
                
            elif decision == "DELETE":
                self._delete_strategy(strategy, results)
                summary["deleted"] += 1
                print(f"   ❌ DELETED (moved to cemetery)\n")
                
            else:
                summary["pending"] += 1
                print(f"   ⏸  PENDING (needs more tests)\n")
        
        print("\n" + "="*60)
        print(f"Coliseum Summary:")
        print(f"  Tested: {summary['tested']}")
        print(f"  Promoted: {summary['promoted']}")
        print(f"  Deleted: {summary['deleted']}")
        print(f"  Pending: {summary['pending']}")
        print("="*60 + "\n")
        
        return summary
    
    def _load_strategies(self) -> List[Dict[str, Any]]:
        """Load all strategies from catalog."""
        if not STRATEGY_CATALOG.exists():
            return []
        
        with open(STRATEGY_CATALOG, "r") as f:
            data = json.load(f)
        
        # Handle both list and dict formats
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "strategies" in data:
            return data["strategies"]
        else:
            return []
    
    def _run_strategy_backtests(self, strategy: Dict[str, Any]) -> List[BacktestResult]:
        """
        Run 10 randomized 90-day backtests for a strategy.
        
        Uses Minimax 2.1 to simulate trading logic rapidly.
        """
        results = []
        strategy_id = strategy["strategy_id"]
        
        # Generate 10 random 90-day windows from last 2 years
        windows = self._generate_random_windows(count=10, days=90)
        
        for i, (start, end) in enumerate(windows):
            print(f"   🔄 Run {i+1}/10: {start} to {end}")
            
            # Simulate backtest (this is pseudocode - actual implementation
            # would pull OHLCV data and run strategy logic)
            result = self._simulate_backtest(strategy, start, end)
            results.append(result)

            # Store for traceability, but never treat randomized outputs as scored validation.
            self._store_result(result)

            if result.validation_excluded:
                print("   [coliseum] synthetic/randomized run excluded from scoring and promotions")
                continue

            # Update strategy status
            self._update_strategy_status(strategy_id, result)
            
            # Check for auto-prune (5 consecutive failures)
            status = self._get_strategy_status(strategy_id)
            if status["consecutive_failures"] >= self.max_consecutive_failures:
                print(f"   ⚠️  5 consecutive failures - auto-prune triggered")
                break
        
        return results
    
    def _simulate_backtest(
        self, strategy: Dict[str, Any], start_date: str, end_date: str
    ) -> BacktestResult:
        """
        Simulate a backtest using Minimax 2.1.
        
        For MVP, generates realistic random results.
        In production, this would:
        1. Fetch OHLCV data for window
        2. Convert strategy description to executable code
        3. Run simulation
        4. Return actual metrics
        """
        # Randomize performance (for demonstration)
        # Real implementation would run actual strategy logic
        
        sharpe = random.uniform(-1.0, 3.0)
        max_dd = random.uniform(0.05, 0.40)
        win_rate = random.uniform(0.30, 0.70)
        profit_factor = random.uniform(0.5, 2.5)
        total_trades = random.randint(20, 200)
        final_pnl = random.uniform(-5000, 10000)
        
        # Randomized simulation output is explicitly non-promotable.
        return BacktestResult(
            strategy_id=strategy["strategy_id"],
            window_start=start_date,
            window_end=end_date,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            final_pnl=final_pnl,
            passed=False,
            data_source="synthetic_randomized",
            promotable=False,
            validation_excluded=True,
        )
    
    def _generate_random_windows(self, count: int, days: int) -> List[Tuple[str, str]]:
        """Generate random non-overlapping date windows."""
        windows = []
        end_date = datetime.now()
        start_range = end_date - timedelta(days=730)  # 2 years back
        
        for _ in range(count):
            random_start = start_range + timedelta(
                days=random.randint(0, 730 - days)
            )
            random_end = random_start + timedelta(days=days)
            
            windows.append((
                random_start.strftime("%Y-%m-%d"),
                random_end.strftime("%Y-%m-%d"),
            ))
        
        return windows
    
    def _store_result(self, result: BacktestResult):
        """Store backtest result in database."""
        conn = sqlite3.connect(ARENA_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO backtest_results (
                strategy_id, window_start, window_end, sharpe_ratio,
                max_drawdown, win_rate, profit_factor, total_trades,
                final_pnl, passed, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.strategy_id,
            result.window_start,
            result.window_end,
            result.sharpe_ratio,
            result.max_drawdown,
            result.win_rate,
            result.profit_factor,
            result.total_trades,
            result.final_pnl,
            1 if result.passed else 0,
            datetime.now().isoformat(),
        ))
        
        conn.commit()
        conn.close()
    
    def _update_strategy_status(self, strategy_id: str, result: BacktestResult):
        """Update strategy status after each backtest."""
        conn = sqlite3.connect(ARENA_DB)
        cursor = conn.cursor()
        
        # Get current status
        cursor.execute(
            "SELECT * FROM strategy_status WHERE strategy_id = ?",
            (strategy_id,)
        )
        row = cursor.fetchone()
        
        if row:
            total, passed, failed, consec_fail = row[1], row[2], row[3], row[4]
            total += 1
            
            if result.passed:
                passed += 1
                consec_fail = 0
            else:
                failed += 1
                consec_fail += 1
            
            cursor.execute("""
                UPDATE strategy_status
                SET total_tests = ?, passed_tests = ?, failed_tests = ?,
                    consecutive_failures = ?, last_updated = ?
                WHERE strategy_id = ?
            """, (total, passed, failed, consec_fail, datetime.now().isoformat(), strategy_id))
        else:
            cursor.execute("""
                INSERT INTO strategy_status (
                    strategy_id, total_tests, passed_tests, failed_tests,
                    consecutive_failures, status, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy_id, 1,
                1 if result.passed else 0,
                0 if result.passed else 1,
                0 if result.passed else 1,
                "testing",
                datetime.now().isoformat(),
            ))
        
        conn.commit()
        conn.close()
    
    def _get_strategy_status(self, strategy_id: str) -> Dict[str, Any]:
        """Get current status of a strategy."""
        conn = sqlite3.connect(ARENA_DB)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM strategy_status WHERE strategy_id = ?",
            (strategy_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "consecutive_failures": 0,
                "status": "new",
            }
        
        return {
            "total_tests": row[1],
            "passed_tests": row[2],
            "failed_tests": row[3],
            "consecutive_failures": row[4],
            "status": row[5],
        }
    
    def _evaluate_strategy(
        self, strategy_id: str, results: List[BacktestResult]
    ) -> str:
        """
        Evaluate whether to PROMOTE, DELETE, or keep PENDING.
        
        Promotion Criteria:
        - Sharpe > 1.5 across ALL tests
        - Max Drawdown < 25% in ALL tests
        - Win Rate > 45% on average
        
        Deletion Criteria:
        - 5 consecutive failures
        """
        status = self._get_strategy_status(strategy_id)

        if not results or any(getattr(r, "validation_excluded", False) for r in results):
            return "PENDING"

        # Check deletion
        if status["consecutive_failures"] >= self.max_consecutive_failures:
            return "DELETE"
        
        # Check promotion (need at least 10 tests)
        if status["total_tests"] >= 10:
            avg_sharpe = sum(r.sharpe_ratio for r in results) / len(results)
            avg_win_rate = sum(r.win_rate for r in results) / len(results)
            max_dd = max(r.max_drawdown for r in results)
            
            if (
                avg_sharpe >= self.min_sharpe_for_promotion and
                avg_win_rate >= self.min_win_rate and
                max_dd < self.max_drawdown_threshold
            ):
                return "PROMOTE"
        
        return "PENDING"
    
    def _promote_strategy(self, strategy: Dict[str, Any]):
        """Promote strategy to live candidates."""
        strategy_id = strategy["strategy_id"]
        
        # Save to live_candidates/
        output_file = LIVE_CANDIDATES_PATH / f"{strategy_id}.json"
        with open(output_file, "w") as f:
            json.dump(strategy, f, indent=2)
        
        # Update database status
        conn = sqlite3.connect(ARENA_DB)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE strategy_status SET status = 'promoted' WHERE strategy_id = ?",
            (strategy_id,)
        )
        conn.commit()
        conn.close()
    
    def _delete_strategy(self, strategy: Dict[str, Any], results: List[BacktestResult]):
        """Delete strategy and move to cemetery with autopsy."""
        strategy_id = strategy["strategy_id"]
        
        # Generate autopsy using Minimax
        autopsy = self._generate_autopsy(strategy, results)
        
        # Move to cemetery
        conn = sqlite3.connect(ARENA_DB)
        cursor = conn.cursor()
        
        # Get final stats
        status = self._get_strategy_status(strategy_id)
        final_stats = json.dumps(status)
        
        cursor.execute("""
            INSERT OR REPLACE INTO cemetery (
                strategy_id, deleted_at, reason, final_stats, autopsy
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            strategy_id,
            datetime.now().isoformat(),
            f"{status['consecutive_failures']} consecutive failures",
            final_stats,
            autopsy,
        ))
        
        # Save autopsy file
        autopsy_file = CEMETERY_PATH / f"{strategy_id}_autopsy.md"
        with open(autopsy_file, "w") as f:
            f.write(f"# Strategy Autopsy: {strategy['name']}\n\n")
            f.write(f"**Deleted:** {datetime.now().isoformat()}\n\n")
            f.write(f"**Reason:** {status['consecutive_failures']} consecutive failures\n\n")
            f.write(f"## Stats\n\n")
            f.write(autopsy)
        
        # Update status
        cursor.execute(
            "UPDATE strategy_status SET status = 'deleted' WHERE strategy_id = ?",
            (strategy_id,)
        )
        
        conn.commit()
        conn.close()
    
    def _generate_autopsy(
        self, strategy: Dict[str, Any], results: List[BacktestResult]
    ) -> str:
        """Use Minimax to generate failure analysis."""
        prompt = f"""
Analyze why this trading strategy failed backtesting:

Strategy: {strategy['name']}
Category: {strategy['category']}
Entry Conditions: {strategy.get('entry_conditions', [])}
Exit Conditions: {strategy.get('exit_conditions', [])}

Backtest Results:
{json.dumps([
    {
        'sharpe': r.sharpe_ratio,
        'max_dd': r.max_drawdown,
        'win_rate': r.win_rate,
        'passed': r.passed
    }
    for r in results
], indent=2)}

Provide a 2-paragraph autopsy explaining:
1. Why this strategy failed
2. What could be learned for future strategies
"""
        
        try:
            response = self.router.query(prompt, max_tokens=512)
            return response.text
        except Exception:
            return "Autopsy generation failed."


def run_coliseum() -> Dict[str, Any]:
    """Main entry point for paper-trading coliseum."""
    coliseum = TradingColiseum()
    return coliseum.run_all_strategies()


if __name__ == "__main__":
    summary = run_coliseum()

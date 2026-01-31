#!/usr/bin/env python3
"""
LAYER 2: Backup TP/SL Monitor

Runs independently via Clawdbot cron every 2 minutes.
If primary monitor is dead OR TP/SL conditions are met, executes trades.

Features:
- Checks if primary monitor is alive (via Redis heartbeat)
- Only acts if primary is dead OR position needs immediate exit
- Uses execution locks to prevent double-sells
- Sends alerts via Telegram

Usage:
    python backup-tpsl-monitor.py [--force]
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tg_bot"))

import redis
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BACKUP-TPSL] %(levelname)s: %(message)s"
)

# Prevent HTTP client libraries from logging URLs that may contain secrets
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
BAGS_API_BASE = "https://api.bags.fm"

# Load bot env if cron didn't source it (common)
def _load_env_file(path: str) -> None:
    try:
        if not os.path.exists(path):
            return
        with open(path, "r") as f:
            for line in f.read().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                os.environ.setdefault(k, v)
    except Exception as e:
        logger.warning(f"Failed to load env file {path}: {e}")

# Try common locations
_load_env_file(os.path.join(os.path.dirname(__file__), "..", "tg_bot", ".env"))
_load_env_file(os.path.join(os.path.dirname(__file__), "..", ".env"))

def _load_telegram_token_from_secrets() -> str:
    """Best-effort load Telegram bot token from secrets files (do not log value)."""
    for p in (
        "/root/clawd/secrets/keys.json",
        "/root/clawd/secrets/jarvis-keys.json",
    ):
        try:
            if not os.path.exists(p):
                continue
            with open(p, "r") as f:
                data = json.load(f)
            # keys.json format: { telegram: { bot_token: "..." } }
            tg = data.get("telegram") if isinstance(data, dict) else None
            if isinstance(tg, dict) and tg.get("bot_token"):
                return str(tg.get("bot_token"))
            # jarvis-keys.json format: { telegram_bots: { jarvistrades_bot: "..." } }
            tgb = data.get("telegram_bots") if isinstance(data, dict) else None
            if isinstance(tgb, dict):
                # prefer main trading bot if present
                for k in ("jarvistrades", "jarvistrades_bot", "public_bot", "treasury_bot"):
                    if tgb.get(k):
                        return str(tgb.get(k))
        except Exception:
            continue
    return ""


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "") or _load_telegram_token_from_secrets()

# Alerts should go to the main group by default
ALERT_CHAT_ID = (
    os.environ.get("TELEGRAM_ALERT_CHAT_ID")
    or os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID")
    or os.environ.get("BROADCAST_CHAT_ID")
    or ""
)

# Primary TP/SL job runs on a 5-minute interval. Treat it as dead only if we
# miss >1 full cycle (plus buffer) to avoid false "dead" flaps.
PRIMARY_DEAD_THRESHOLD_SECONDS = 420  # 7 min


class BackupTPSLMonitor:
    def __init__(self):
        self.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        self.http = httpx.AsyncClient(timeout=30.0)
        self.force_mode = "--force" in sys.argv
        
    async def close(self):
        await self.http.aclose()

    def is_primary_alive(self) -> bool:
        """Check if primary monitor is running."""
        try:
            data = self.redis.get("jarvis:monitor_heartbeat:primary")
            if not data:
                return False
            status = json.loads(data)
            last_ts = status.get("timestamp", 0)
            return (time.time() - last_ts) < PRIMARY_DEAD_THRESHOLD_SECONDS
        except Exception as e:
            logger.error(f"Heartbeat check failed: {e}")
            return False

    def get_all_positions(self) -> Dict[int, List[Dict]]:
        """Get all positions from Redis, keyed by user_id."""
        result = {}
        try:
            keys = self.redis.keys("jarvis:positions:*")
            for key in keys:
                try:
                    user_id = int(key.split(":")[-1])
                    data = self.redis.get(key)
                    if data:
                        positions = json.loads(data)
                        if positions:
                            result[user_id] = positions
                except (ValueError, json.JSONDecodeError):
                    continue
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
        return result

    def acquire_lock(self, position_id: str) -> bool:
        """Try to acquire execution lock."""
        lock_key = f"jarvis:exec_lock:{position_id}"
        lock_data = json.dumps({
            "source": "backup_monitor",
            "acquired_at": datetime.now(timezone.utc).isoformat(),
        })
        result = self.redis.set(lock_key, lock_data, nx=True, ex=60)
        return result is True

    def release_lock(self, position_id: str):
        """Release execution lock."""
        self.redis.delete(f"jarvis:exec_lock:{position_id}")

    async def get_token_price(self, mint: str) -> Optional[float]:
        """Get current token price.

        Jupiter's public endpoint can 401; prefer lite-api and fallback.
        """
        endpoints = [
            f"https://lite-api.jup.ag/price/v2?ids={mint}",
            f"https://api.jup.ag/price/v2?ids={mint}",
        ]
        for url in endpoints:
            try:
                resp = await self.http.get(url)
                logger.info(f"HTTP Request: GET {url} \"HTTP/1.1 {resp.status_code} {resp.reason_phrase}\"")
                if resp.status_code == 200:
                    data = resp.json()
                    price = float(data.get("data", {}).get(mint, {}).get("price", 0) or 0)
                    if price > 0:
                        return price
            except Exception as e:
                logger.warning(f"Price fetch failed for {mint} via {url}: {e}")

        # Final fallback: DexScreener public API
        try:
            ds = await self.http.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}")
            if ds.status_code == 200:
                j = ds.json()
                pairs = j.get("pairs") or []
                if pairs:
                    # take highest liquidity
                    best = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                    price = float(best.get("priceUsd", 0) or 0)
                    if price > 0:
                        return price
        except Exception as e:
            logger.warning(f"DexScreener price fallback failed for {mint}: {e}")

        return None

    async def execute_sell(self, position: Dict, user_wallet: str) -> Dict:
        """Execute a sell via bags.fm API."""
        token_mint = position.get("address")
        amount = position.get("amount", 0)
        
        try:
            # Get swap quote
            quote_url = f"{BAGS_API_BASE}/trade/quote"
            quote_params = {
                "inputMint": token_mint,
                "outputMint": "So11111111111111111111111111111111111111112",  # SOL
                "amount": str(int(amount * 1e9)),  # Convert to lamports
                "slippageBps": 500,  # 5% slippage
            }
            quote_resp = await self.http.get(quote_url, params=quote_params)
            
            if quote_resp.status_code != 200:
                return {"success": False, "error": f"Quote failed: {quote_resp.text}"}

            quote = quote_resp.json()
            
            # Execute swap
            swap_url = f"{BAGS_API_BASE}/trade/swap"
            swap_payload = {
                "userPublicKey": user_wallet,
                "quoteResponse": quote,
            }
            swap_resp = await self.http.post(swap_url, json=swap_payload)
            
            if swap_resp.status_code == 200:
                result = swap_resp.json()
                return {
                    "success": True,
                    "tx_hash": result.get("txid"),
                    "source": "backup_monitor",
                }
            else:
                return {"success": False, "error": f"Swap failed: {swap_resp.text}"}
                
        except Exception as e:
            logger.error(f"Sell execution error: {e}")
            return {"success": False, "error": str(e)}

    async def send_alert(self, message: str, chat_id: str = None):
        """Send alert via Telegram (best-effort)."""
        if not TELEGRAM_BOT_TOKEN or ":" not in TELEGRAM_BOT_TOKEN:
            logger.warning("Backup couldn't send its own alert because TELEGRAM_BOT_TOKEN is currently empty/invalid")
            return

        target = chat_id or ALERT_CHAT_ID
        if not target:
            logger.warning("Backup TP/SL alert skipped: no ALERT_CHAT_ID configured")
            return

        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            # Use plain text (no parse_mode) to avoid Telegram entity parse failures.
            await self.http.post(url, json={
                "chat_id": target,
                "text": message,
                "disable_web_page_preview": True,
            })
        except Exception as e:
            logger.error(f"Alert send failed: {e}")

    async def check_position(self, user_id: int, position: Dict) -> Optional[Dict]:
        """
        Check if a position should trigger TP/SL.
        Returns alert dict if triggered, None otherwise.
        """
        token_mint = position.get("address")
        entry_price = float(position.get("entry_price", 0) or 0)
        
        if not token_mint or entry_price <= 0:
            return None

        # Get current price
        current_price = await self.get_token_price(token_mint)
        if not current_price:
            return None

        position["current_price"] = current_price
        
        # Check take-profit
        tp_pct = position.get("tp_percent", position.get("take_profit"))
        if tp_pct is not None:
            tp_price = entry_price * (1 + float(tp_pct) / 100)
            already = bool(position.get("tp_triggered") or position.get("take_profit_triggered"))
            if current_price >= tp_price and not already:
                return {
                    "type": "take_profit",
                    "position": position,
                    "price": current_price,
                    "trigger_price": tp_price,
                    "user_id": user_id,
                }

        # Check stop-loss
        sl_pct = position.get("sl_percent", position.get("stop_loss"))
        if sl_pct is not None:
            sl_price = entry_price * (1 - float(sl_pct) / 100)
            already = bool(position.get("sl_triggered") or position.get("stop_loss_triggered"))
            if current_price <= sl_price and not already:
                return {
                    "type": "stop_loss",
                    "position": position,
                    "price": current_price,
                    "trigger_price": sl_price,
                    "user_id": user_id,
                }

        return None

    async def process_alert(self, alert: Dict) -> bool:
        """Process a triggered alert.

        SAFE EXECUTE MODE:
        - If primary monitor is alive → alert only (no execution)
        - If primary monitor is DEAD → attempt to execute sell
        
        Guarded with Redis locks to prevent double-sells.
        """
        position = alert["position"]
        pos_id = position.get("id", "unknown")
        user_id = alert["user_id"]

        # Try to acquire lock
        if not self.acquire_lock(pos_id):
            logger.info(f"Position {pos_id} already locked, skipping")
            return False

        try:
            symbol = position.get("symbol", "TOKEN")
            alert_type = alert["type"].replace("_", " ").title()
            current_price = alert["price"]
            entry_price = float(position.get("entry_price", 0) or 0)
            pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price else 0

            primary_alive = self.is_primary_alive()
            
            # SAFE EXECUTE: Only execute if primary is dead
            executed = False
            tx_hash = None
            
            if not primary_alive:
                logger.warning(f"⚠️ Primary DEAD - attempting safe execute for position {pos_id}")
                
                # Get user wallet from position or fallback
                user_wallet = position.get("wallet_address")
                
                if user_wallet:
                    result = await self.execute_sell(position, user_wallet)
                    if result.get("success"):
                        executed = True
                        tx_hash = result.get("tx_hash")
                        logger.info(f"✅ Safe execute SUCCESS for {pos_id}: {tx_hash}")
                    else:
                        logger.error(f"❌ Safe execute FAILED for {pos_id}: {result.get('error')}")
                else:
                    logger.warning(f"No wallet found for position {pos_id}, cannot execute")
            
            # Build alert message
            if executed:
                status_line = f"✅ EXECUTED via backup monitor\nTX: `{tx_hash[:16]}...`" if tx_hash else "✅ EXECUTED via backup monitor"
            elif primary_alive:
                status_line = "✅ Primary monitor alive (alert-only)"
            else:
                status_line = "⚠️ Primary DEAD - execution failed (check wallet config)"

            message = (
                "🚨 *TP/SL ALERT (Backup Monitor)*\n\n"
                f"{alert_type} triggered for *{symbol}*\n\n"
                f"Entry: ${entry_price:.6f}\n"
                f"Current: ${current_price:.6f}\n"
                f"P&L: {pnl_pct:+.1f}%\n\n"
                f"{status_line}\n"
                f"Position ID: `{pos_id}`"
            )

            await self.send_alert(message)
            
            # Mark as triggered to prevent repeat alerts (support both legacy and new field names)
            if alert["type"] == "take_profit":
                position["take_profit_triggered"] = True
                position["tp_triggered"] = True
            elif alert["type"] == "stop_loss":
                position["stop_loss_triggered"] = True
                position["sl_triggered"] = True
            else:
                position[f"{alert['type']}_triggered"] = True
            
            # If executed, also mark as closed
            if executed:
                position["status"] = "closed"
                position["closed_at"] = datetime.now(timezone.utc).isoformat()
                position["close_tx"] = tx_hash
                position["close_source"] = "backup_monitor"
            
            # Update in Redis
            all_positions = json.loads(self.redis.get(f"jarvis:positions:{user_id}") or "[]")
            for p in all_positions:
                if p.get("id") == pos_id:
                    if alert["type"] == "take_profit":
                        p["take_profit_triggered"] = True
                        p["tp_triggered"] = True
                    elif alert["type"] == "stop_loss":
                        p["stop_loss_triggered"] = True
                        p["sl_triggered"] = True
                    else:
                        p[f"{alert['type']}_triggered"] = True
                    if executed:
                        p["status"] = "closed"
                        p["closed_at"] = datetime.now(timezone.utc).isoformat()
                        p["close_tx"] = tx_hash
                        p["close_source"] = "backup_monitor"
                    break
            self.redis.set(f"jarvis:positions:{user_id}", json.dumps(all_positions))
            
            return True
            
        finally:
            self.release_lock(pos_id)

    async def run(self):
        """Main monitoring loop (single pass for cron)."""
        logger.info("Backup TP/SL monitor starting...")
        
        # Update our heartbeat
        self.redis.set("jarvis:monitor_heartbeat:backup", json.dumps({
            "last_check": datetime.now(timezone.utc).isoformat(),
            "timestamp": time.time(),
        }), ex=300)

        # Check if primary is alive
        primary_alive = self.is_primary_alive()
        
        if primary_alive and not self.force_mode:
            logger.info("Primary monitor is alive, running passive check only")
        else:
            if not primary_alive:
                logger.warning("⚠️ Primary monitor appears DEAD - taking over monitoring")
            else:
                logger.info("Force mode enabled, checking all positions")

        # Get all positions
        all_positions = self.get_all_positions()
        
        if not all_positions:
            logger.info("No positions to monitor")
            return

        total_checked = 0
        alerts_triggered = 0

        for user_id, positions in all_positions.items():
            for position in positions:
                total_checked += 1
                
                alert = await self.check_position(user_id, position)
                
                if alert:
                    alerts_triggered += 1
                    logger.warning(f"🚨 {alert['type']} triggered for position {position.get('id')}")
                    await self.process_alert(alert)

        logger.info(f"Check complete: {total_checked} positions, {alerts_triggered} alerts")


async def main():
    monitor = BackupTPSLMonitor()
    try:
        await monitor.run()
    finally:
        await monitor.close()


if __name__ == "__main__":
    asyncio.run(main())

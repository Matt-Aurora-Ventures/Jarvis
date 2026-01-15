"""
Sync Treasury Positions with Limit Orders

Reconciles positions.json with limit_orders.json to fix any
positions that were closed by TP/SL but not properly updated.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Paths
DATA_DIR = Path(__file__).parent.parent
POSITIONS_FILE = DATA_DIR / "bots" / "treasury" / ".positions.json"
HISTORY_FILE = DATA_DIR / "bots" / "treasury" / ".trade_history.json"
ORDERS_FILE = DATA_DIR / "data" / "limit_orders.json"


def load_json(path: Path) -> list | dict:
    """Load JSON file."""
    if not path.exists():
        return [] if "history" in str(path) or "positions" in str(path) else {}
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data):
    """Save JSON file."""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def sync_positions():
    """Sync positions with executed orders."""
    positions = load_json(POSITIONS_FILE)
    history = load_json(HISTORY_FILE)
    orders = load_json(ORDERS_FILE)

    if isinstance(positions, list):
        # Convert list to dict format
        positions = {p['id']: p for p in positions}

    print(f"Loaded {len(positions)} open positions")
    print(f"Loaded {len(history)} historical trades")
    print(f"Loaded {len(orders)} orders")

    # Find completed orders
    completed_orders = {
        oid: order for oid, order in orders.items()
        if order.get('status') == 'COMPLETED'
    }

    print(f"\nCompleted orders: {len(completed_orders)}")

    # Check each open position against completed orders
    positions_to_close = []

    for pos_id, pos in list(positions.items()):
        if pos.get('status') != 'OPEN':
            continue

        tp_order_id = pos.get('tp_order_id')
        sl_order_id = pos.get('sl_order_id')

        # Check if TP or SL was executed
        closed_by = None
        order_result = None

        if tp_order_id and tp_order_id in completed_orders:
            closed_by = 'TAKE_PROFIT'
            order_result = completed_orders[tp_order_id]
        elif sl_order_id and sl_order_id in completed_orders:
            closed_by = 'STOP_LOSS'
            order_result = completed_orders[sl_order_id]

        if closed_by:
            positions_to_close.append({
                'pos_id': pos_id,
                'position': pos,
                'closed_by': closed_by,
                'order_result': order_result
            })

    print(f"\nPositions to sync (closed but not updated): {len(positions_to_close)}")

    if not positions_to_close:
        print("All positions are in sync!")
        return

    # Close the positions
    for item in positions_to_close:
        pos_id = item['pos_id']
        pos = item['position']
        order_result = item['order_result']
        closed_by = item['closed_by']

        exit_price = order_result.get('triggered_price', 0)
        result_data = order_result.get('result', {})

        # Calculate P&L
        entry_price = pos.get('entry_price', 0)
        if entry_price > 0 and exit_price > 0:
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            pnl_usd = pos.get('amount_usd', 0) * (pnl_pct / 100)
        else:
            pnl_pct = 0
            pnl_usd = 0

        # Update position
        pos['status'] = 'CLOSED'
        pos['closed_at'] = order_result.get('triggered_at')
        pos['exit_price'] = exit_price
        pos['pnl_pct'] = pnl_pct
        pos['pnl_usd'] = pnl_usd

        print(f"\n  Closing {pos.get('token_symbol', 'UNKNOWN')} ({pos_id}):")
        print(f"    Closed by: {closed_by}")
        print(f"    Entry: ${entry_price:.8f}")
        print(f"    Exit: ${exit_price:.8f}")
        print(f"    P&L: ${pnl_usd:+.4f} ({pnl_pct:+.2f}%)")
        print(f"    TX: {result_data.get('signature', 'N/A')[:20]}...")

        # Move to history
        history.append(pos)
        del positions[pos_id]

    # Save updated files
    save_json(POSITIONS_FILE, list(positions.values()))
    save_json(HISTORY_FILE, history)

    print(f"\n[OK] Synced {len(positions_to_close)} positions")
    print(f"  Remaining open positions: {len(positions)}")
    print(f"  Total historical trades: {len(history)}")


def print_summary():
    """Print summary of current state."""
    positions = load_json(POSITIONS_FILE)
    history = load_json(HISTORY_FILE)
    orders = load_json(ORDERS_FILE)

    if isinstance(positions, list):
        positions = {p['id']: p for p in positions}

    print("\n" + "="*60)
    print("TREASURY SUMMARY")
    print("="*60)

    # Win/Loss stats from history
    if history:
        wins = [t for t in history if t.get('pnl_usd', 0) > 0]
        losses = [t for t in history if t.get('pnl_usd', 0) < 0]
        total_pnl = sum(t.get('pnl_usd', 0) for t in history)

        print(f"\nTrade History ({len(history)} trades):")
        print(f"  Wins: {len(wins)}")
        print(f"  Losses: {len(losses)}")
        print(f"  Win Rate: {len(wins)/len(history)*100:.1f}%" if history else "N/A")
        print(f"  Total P&L: ${total_pnl:+.4f}")

        print("\n  Recent trades:")
        for t in history[-5:]:
            symbol = t.get('token_symbol', '???')
            pnl = t.get('pnl_usd', 0)
            pnl_pct = t.get('pnl_pct', 0)
            emoji = 'WIN' if pnl > 0 else 'LOSS'
            print(f"    {emoji} {symbol}: ${pnl:+.4f} ({pnl_pct:+.2f}%)")

    # Open positions
    if positions:
        print(f"\nOpen Positions ({len(positions)}):")
        for pid, pos in positions.items():
            symbol = pos.get('token_symbol', '???')
            entry = pos.get('entry_price', 0)
            current = pos.get('current_price', entry)
            tp = pos.get('take_profit_price', 0)
            sl = pos.get('stop_loss_price', 0)

            if entry > 0 and current > 0:
                unrealized_pct = ((current - entry) / entry) * 100
            else:
                unrealized_pct = 0

            emoji = 'UP' if unrealized_pct >= 0 else 'DOWN'
            print(f"  {emoji} {symbol}: Entry ${entry:.6f} | Current ${current:.6f} ({unrealized_pct:+.1f}%)")
            print(f"      TP: ${tp:.6f} | SL: ${sl:.6f}")

    # Active orders
    active_orders = [o for o in orders.values() if o.get('status') == 'ACTIVE']
    print(f"\nActive Orders: {len(active_orders)}")


def create_missing_orders():
    """Create TP/SL orders for positions that don't have them."""
    positions = load_json(POSITIONS_FILE)
    orders = load_json(ORDERS_FILE)

    if isinstance(positions, list):
        positions = {p['id']: p for p in positions}

    print("\nChecking for missing orders...")

    positions_needing_orders = []

    for pos_id, pos in positions.items():
        if pos.get('status') != 'OPEN':
            continue

        tp_order_id = pos.get('tp_order_id')
        sl_order_id = pos.get('sl_order_id')

        has_tp = tp_order_id and tp_order_id in orders and orders[tp_order_id].get('status') == 'ACTIVE'
        has_sl = sl_order_id and sl_order_id in orders and orders[sl_order_id].get('status') == 'ACTIVE'

        if not has_tp or not has_sl:
            positions_needing_orders.append({
                'pos_id': pos_id,
                'position': pos,
                'needs_tp': not has_tp,
                'needs_sl': not has_sl
            })

    if not positions_needing_orders:
        print("All positions have active orders!")
        return

    print(f"\nPositions needing orders: {len(positions_needing_orders)}")

    import uuid

    for item in positions_needing_orders:
        pos_id = item['pos_id']
        pos = item['position']
        symbol = pos.get('token_symbol', '???')
        token_mint = pos.get('token_mint', '')
        entry_price = pos.get('entry_price', 0)
        amount = pos.get('amount', 0)
        tp_price = pos.get('take_profit_price', 0)
        sl_price = pos.get('stop_loss_price', 0)

        # Get token decimals - estimate from amount
        if amount > 1000000:
            decimals = 9
        elif amount > 1000:
            decimals = 6
        else:
            decimals = 9

        amount_smallest = int(amount * (10 ** decimals))

        print(f"\n  {symbol} ({pos_id}):")
        print(f"    Entry: ${entry_price:.8f} | Amount: {amount:.4f}")

        if item['needs_tp']:
            tp_id = str(uuid.uuid4())[:8]
            orders[tp_id] = {
                'type': 'TAKE_PROFIT',
                'token_mint': token_mint,
                'amount': amount_smallest,
                'target_price': tp_price,
                'output_mint': 'So11111111111111111111111111111111111111112',
                'created_at': datetime.utcnow().isoformat(),
                'status': 'ACTIVE',
                'triggered_at': None,
                'result': None
            }
            pos['tp_order_id'] = tp_id
            print(f"    Created TP order {tp_id} at ${tp_price:.8f}")

        if item['needs_sl']:
            sl_id = str(uuid.uuid4())[:8]
            orders[sl_id] = {
                'type': 'STOP_LOSS',
                'token_mint': token_mint,
                'amount': amount_smallest,
                'target_price': sl_price,
                'output_mint': 'So11111111111111111111111111111111111111112',
                'created_at': datetime.utcnow().isoformat(),
                'status': 'ACTIVE',
                'triggered_at': None,
                'result': None
            }
            pos['sl_order_id'] = sl_id
            print(f"    Created SL order {sl_id} at ${sl_price:.8f}")

    # Save updated files
    save_json(POSITIONS_FILE, list(positions.values()))
    save_json(ORDERS_FILE, orders)

    print(f"\n[OK] Created orders for {len(positions_needing_orders)} positions")


if __name__ == "__main__":
    print("Treasury Position Sync Tool")
    print("-" * 40)

    sync_positions()
    create_missing_orders()
    print_summary()

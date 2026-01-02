"""
Flask API Backend for Jarvis Frontend
Provides REST API endpoints for the React dashboard.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from pathlib import Path
import json
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import config, solana_scanner, trading_coliseum
from scripts import monitor_tts_costs

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

ROOT = Path(__file__).resolve().parents[1]


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get dashboard stats."""
    return jsonify({
        'activeTime': '2h 34m',
        'tasksCompleted': 12,
        'suggestionsGiven': 5,
        'focusScore': 85,
    })


@app.route('/api/voice/status', methods=['GET'])
def get_voice_status():
    """Get voice system status."""
    cfg = config.load_config()
    voice_cfg = cfg.get('voice', {})
    
    return jsonify({
        'enabled': voice_cfg.get('speak_responses', True),
        'listening': False,  # Would connect to actual voice state
        'speaking': False,
        'bargeInEnabled': voice_cfg.get('barge_in_enabled', True),
    })


@app.route('/api/voice/config', methods=['POST'])
def update_voice_config():
    """Update voice configuration."""
    data = request.json
    # Save to config file
    return jsonify({'success': True})


@app.route('/api/voice/test', methods=['POST'])
def test_voice():
    """Test voice output."""
    data = request.json
    text = data.get('text', 'Test')
    # Trigger voice output
    return jsonify({'success': True})


@app.route('/api/costs/tts', methods=['GET'])
def get_tts_costs():
    """Get TTS cost stats."""
    hourly = monitor_tts_costs.get_hourly_stats()
    daily = monitor_tts_costs.get_daily_stats()
    
    hourly_cost = hourly.get('total_cost_usd', 0)
    projected = hourly_cost * 24 * 30 if hourly_cost > 0 else 0
    
    return jsonify({
        'hour': hourly.get('total_cost_usd', 0),
        'today': daily.get('total_cost_usd', 0),
        'projected': projected,
    })


@app.route('/api/trading/stats', methods=['GET'])
def get_trading_stats():
    """Get trading statistics."""
    return jsonify({
        'activeStrategies': 5,
        'backtestsRunning': 0,
        'solanaTokens': 50,
        'avgVolume': 250000,
    })


@app.route('/api/trading/solana/tokens', methods=['GET'])
def get_solana_tokens():
    """Get Solana token list."""
    tokens_file = ROOT / "data" / "trader" / "solana_scanner" / "birdeye_trending_tokens.csv"
    
    if not tokens_file.exists():
        return jsonify({'tokens': []})
    
    import csv
    tokens = []
    with open(tokens_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tokens.append({
                'symbol': row.get('symbol', ''),
                'name': row.get('name', ''),
                'volume24hUSD': float(row.get('volume24hUSD', 0) or 0),
                'price': float(row.get('price', 0) or 0),
                'liquidity': float(row.get('liquidity', 0) or 0),
            })
    
    # Sort by volume
    tokens.sort(key=lambda x: x['volume24hUSD'], reverse=True)
    
    return jsonify({'tokens': tokens})


@app.route('/api/trading/solana/scan', methods=['POST'])
def scan_solana():
    """Trigger Solana token scan."""
    try:
        result = solana_scanner.scan_all(
            trending_limit=50,
            new_token_hours=3,
            top_trader_limit=50,
        )
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trading/backtests', methods=['GET'])
def get_backtests():
    """Get backtest results."""
    # Read from trading_coliseum database
    results_file = ROOT / "data" / "trading" / "coliseum" / "arena_results.db"
    
    if not results_file.exists():
        return jsonify({'results': []})
    
    import sqlite3
    conn = sqlite3.connect(results_file)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT strategy_id, window_start, window_end, sharpe_ratio, 
               max_drawdown, win_rate, total_trades, passed
        FROM backtest_results
        ORDER BY timestamp DESC
        LIMIT 20
    """)
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'strategy_name': row[0],
            'window_start': row[1],
            'window_end': row[2],
            'sharpe_ratio': row[3],
            'max_drawdown': row[4],
            'win_rate': row[5],
            'total_trades': row[6],
            'passed': bool(row[7]),
        })
    
    conn.close()
    
    return jsonify({'results': results})


@app.route('/api/trading/backtests/run', methods=['POST'])
def run_backtests():
    """Run backtests in background."""
    try:
        # Trigger async backtest
        import threading
        def run_async():
            trading_coliseum.run_coliseum()
        
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        
        return jsonify({'success': True, 'message': 'Backtests started'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)

"""
Real-Time Progress Dashboard Server
Shows live updates of trading pipeline and all Jarvis activities
"""

from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
from pathlib import Path
import json
import time

app = Flask(__name__)
CORS(app)

ROOT = Path(__file__).resolve().parents[1]
PROGRESS_FILE = ROOT / "data" / "trading" / "pipeline_progress.json"
LOG_FILE = ROOT / "data" / "trading" / "pipeline.log"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Jarvis Progress Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Courier New', monospace;
            background: #0a0e27;
            color: #00ff88;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 20px;
            border: 2px solid #00ff88;
            margin-bottom: 20px;
            background: rgba(0,255,136,0.1);
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .stat-box {
            border: 1px solid #00ff88;
            padding: 15px;
            background: rgba(0,255,136,0.05);
        }
        .stat-label { 
            font-size: 12px; 
            color: #00ff88; 
            opacity: 0.7;
            margin-bottom: 5px;
        }
        .stat-value { 
            font-size: 32px; 
            font-weight: bold;
            color: #ffffff;
        }
        .progress-bar {
            height: 30px;
            background: rgba(0,255,136,0.1);
            border: 1px solid #00ff88;
            margin: 10px 0;
            position: relative;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00ff88, #00cc6a);
            transition: width 0.3s;
        }
        .progress-text {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #fff;
            font-weight: bold;
            text-shadow: 0 0 5px #000;
        }
        .log-container {
            border: 1px solid #00ff88;
            padding: 15px;
            background: #000;
            height: 400px;
            overflow-y: auto;
            font-size: 14px;
            line-height: 1.6;
        }
        .log-line { margin: 2px 0; }
        .error { color: #ff4444; }
        .success { color: #00ff88; }
        .warning { color: #ffaa00; }
        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 3px;
            font-weight: bold;
            margin: 10px 0;
        }
        .status-running { background: #00ff88; color: #000; }
        .status-completed { background: #00cc6a; color: #fff; }
        .status-error { background: #ff4444; color: #fff; }
        .blink { animation: blink 1s infinite; }
        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0.3; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚡ JARVIS PROGRESS DASHBOARD ⚡</h1>
        <p>Real-Time Execution Monitor</p>
        <div id="status-badge" class="status-badge status-running blink">LOADING...</div>
    </div>
    
    <div class="status-grid">
        <div class="stat-box">
            <div class="stat-label">TOKENS SCANNED</div>
            <div class="stat-value" id="tokens-scanned">0</div>
            <div class="stat-label">of <span id="tokens-total">50</span></div>
        </div>
        <div class="stat-box">
            <div class="stat-label">BACKTESTS COMPLETED</div>
            <div class="stat-value" id="backtests-completed">0</div>
            <div class="stat-label">of <span id="backtests-total">2500</span></div>
        </div>
        <div class="stat-box">
            <div class="stat-label">STRATEGIES TESTED</div>
            <div class="stat-value" id="strategies-tested">0</div>
            <div class="stat-label">of <span id="strategies-total">50</span></div>
        </div>
        <div class="stat-box">
            <div class="stat-label">ELAPSED TIME</div>
            <div class="stat-value" id="elapsed">0s</div>
        </div>
    </div>
    
    <div class="stat-box">
        <div class="stat-label">CURRENT TASK</div>
        <div id="current-task" style="font-size: 18px; margin-top: 10px; color: #fff;">
            Initializing...
        </div>
    </div>
    
    <div style="margin: 20px 0;">
        <div class="stat-label">TOKENS PROGRESS</div>
        <div class="progress-bar">
            <div class="progress-fill" id="tokens-progress" style="width: 0%"></div>
            <div class="progress-text" id="tokens-pct">0%</div>
        </div>
    </div>
    
    <div style="margin: 20px 0;">
        <div class="stat-label">BACKTESTS PROGRESS</div>
        <div class="progress-bar">
            <div class="progress-fill" id="backtests-progress" style="width: 0%"></div>
            <div class="progress-text" id="backtests-pct">0%</div>
        </div>
    </div>
    
    <div class="stat-label">LIVE LOG</div>
    <div class="log-container" id="log"></div>
    
    <script>
        function updateDashboard() {
            fetch('/api/progress')
                .then(r => r.json())
                .then(data => {
                    // Update status badge
                    const badge = document.getElementById('status-badge');
                    badge.textContent = data.status.toUpperCase();
                    badge.className = 'status-badge status-' + data.status;
                    if (data.status === 'running' || data.status === 'backtesting') {
                        badge.classList.add('blink');
                    }
                    
                    // Update stats
                    document.getElementById('tokens-scanned').textContent = data.tokens_scanned;
                    document.getElementById('tokens-total').textContent = data.tokens_total;
                    document.getElementById('backtests-completed').textContent = data.backtests_completed;
                    document.getElementById('backtests-total').textContent = data.backtests_total;
                    document.getElementById('strategies-tested').textContent = data.strategies_tested;
                    document.getElementById('strategies-total').textContent = data.strategies_total;
                    document.getElementById('elapsed').textContent = Math.floor(data.elapsed_seconds) + 's';
                    document.getElementById('current-task').textContent = data.current_task;
                    
                    // Update progress bars
                    const tokensPct = (data.tokens_scanned / data.tokens_total * 100).toFixed(1);
                    const backtestsPct = (data.backtests_completed / data.backtests_total * 100).toFixed(1);
                    
                    document.getElementById('tokens-progress').style.width = tokensPct + '%';
                    document.getElementById('tokens-pct').textContent = tokensPct + '%';
                    document.getElementById('backtests-progress').style.width = backtestsPct + '%';
                    document.getElementById('backtests-pct').textContent = backtestsPct + '%';
                })
                .catch(e => console.error('Error:', e));
            
            fetch('/api/logs')
                .then(r => r.json())
                .then(data => {
                    const logDiv = document.getElementById('log');
                    logDiv.innerHTML = data.logs.map(line => {
                        let className = '';
                        if (line.includes('ERROR') || line.includes('❌')) className = 'error';
                        else if (line.includes('✅') || line.includes('SUCCESS')) className = 'success';
                        else if (line.includes('⚠️') || line.includes('WARNING')) className = 'warning';
                        return `<div class="log-line ${className}">${line}</div>`;
                    }).join('');
                    logDiv.scrollTop = logDiv.scrollHeight;
                })
                .catch(e => console.error('Error:', e));
        }
        
        // Update every 500ms
        setInterval(updateDashboard, 500);
        updateDashboard();
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/progress')
def get_progress():
    try:
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE) as f:
                return jsonify(json.load(f))
        return jsonify({
            "status": "not_started",
            "tokens_scanned": 0,
            "tokens_total": 50,
            "backtests_completed": 0,
            "backtests_total": 2500,
            "strategies_tested": 0,
            "strategies_total": 50,
            "current_task": "Waiting to start...",
            "elapsed_seconds": 0,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logs')
def get_logs():
    try:
        if LOG_FILE.exists():
            with open(LOG_FILE) as f:
                lines = f.readlines()
                return jsonify({"logs": lines[-100:]})  # Last 100 lines
        return jsonify({"logs": ["No logs yet..."]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 JARVIS PROGRESS DASHBOARD")
    print("="*60)
    print(f"Open: http://localhost:5001")
    print(f"Progress file: {PROGRESS_FILE}")
    print(f"Log file: {LOG_FILE}")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5001, debug=False)

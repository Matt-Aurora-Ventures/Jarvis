"""
Jarvis Ecosystem Dashboard
The central command center for all Jarvis operations.
Features:
- Real-time Trading Pipeline Status
- Security Monitoring (Network/Process)
- Direct Communication Interface
- System Logs & Health
"""

from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
from pathlib import Path
import json
import time
import os
import psutil
from datetime import datetime

app = Flask(__name__)
CORS(app)

ROOT = Path(__file__).resolve().parents[1]
PROGRESS_FILE = ROOT / "data" / "trading" / "pipeline_progress.json"
LOG_FILE = ROOT / "data" / "trading" / "pipeline.log"
SYSTEM_LOG = ROOT / "data" / "jarvis.log"  # Main log file
MESSAGES_FILE = ROOT / "data" / "user_messages.json"

# Initialize message history
if not MESSAGES_FILE.exists():
    MESSAGES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MESSAGES_FILE, 'w') as f:
        json.dump([], f)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>JARVIS ECOSYSTEM | COMMAND CENTER</title>
    <style>
        :root {
            --bg-dark: #050510;
            --bg-panel: #0a0e17;
            --primary: #00ff88;
            --secondary: #00ccff;
            --alert: #ff4444;
            --warning: #ffaa00;
            --text-dim: rgba(255, 255, 255, 0.6);
            --border: 1px solid rgba(0, 255, 136, 0.2);
        }
        * { box-sizing: border-box; }
        body {
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            background: var(--bg-dark);
            color: var(--primary);
            margin: 0;
            padding: 20px;
            height: 100vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        
        /* HEADER */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 2px solid var(--primary);
            margin-bottom: 20px;
            text-transform: uppercase;
        }
        h1 { margin: 0; font-size: 24px; letter-spacing: 2px; text-shadow: 0 0 10px var(--primary); }
        .system-status { display: flex; gap: 20px; font-size: 14px; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .dot-green { background: var(--primary); box-shadow: 0 0 8px var(--primary); animation: pulse 2s infinite; }
        
        /* GRID LAYOUT */
        .grid-container {
            display: grid;
            grid-template-columns: 350px 1fr 350px;
            grid-template-rows: 1fr 1fr;
            gap: 20px;
            flex-grow: 1;
            overflow: hidden;
        }
        
        .panel {
            background: var(--bg-panel);
            border: var(--border);
            padding: 15px;
            display: flex;
            flex-direction: column;
            position: relative;
        }
        .panel h2 { 
            margin-top: 0; 
            font-size: 16px; 
            border-bottom: 1px solid rgba(255,255,255,0.1); 
            padding-bottom: 10px;
            color: var(--secondary);
            display: flex;
            justify-content: space-between;
        }
        
        /* SECURITY PANEL */
        .security-list { font-size: 12px; overflow-y: auto; flex-grow: 1; }
        .sec-item { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .sec-alert { color: var(--alert); }
        .sec-ok { color: var(--primary); }
        
        /* CHAT PANEL */
        .chat-container { display: flex; flex-direction: column; flex-grow: 1; overflow: hidden; }
        .chat-history { flex-grow: 1; overflow-y: auto; padding-right: 10px; margin-bottom: 10px; font-size: 13px; }
        .message { margin-bottom: 8px; padding: 8px; border-radius: 4px; }
        .msg-user { background: rgba(0, 204, 255, 0.1); border-left: 2px solid var(--secondary); text-align: right; }
        .msg-jarvis { background: rgba(0, 255, 136, 0.1); border-left: 2px solid var(--primary); }
        .chat-input { display: flex; gap: 10px; }
        input[type="text"] { 
            flex-grow: 1; background: #000; border: 1px solid #333; color: white; padding: 10px; 
            font-family: inherit;
        }
        button { 
            background: var(--bg-panel); color: var(--primary); border: 1px solid var(--primary); 
            padding: 0 20px; cursor: pointer; font-weight: bold; font-family: inherit; text-transform: uppercase;
        }
        button:hover { background: var(--primary); color: black; }

        /* TRADING PANEL */
        .progress-bar { height: 20px; background: rgba(255,255,255,0.1); margin: 5px 0 15px 0; position: relative; }
        .progress-fill { height: 100%; background: var(--primary); width: 0%; transition: width 0.5s; }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
        .stat-box { background: rgba(255,255,255,0.03); padding: 10px; text-align: center; }
        .stat-val { font-size: 20px; font-weight: bold; color: white; }
        .stat-lbl { font-size: 10px; text-transform: uppercase; color: var(--text-dim); }

        /* LOGS */
        .log-container {
            font-size: 11px;
            color: var(--text-dim);
            overflow-y: auto;
            flex-grow: 1;
            font-family: 'Menlo', monospace;
        }
        .log-line { margin-bottom: 2px; padding-left: 5px; }
        .log-err { color: var(--alert); }
        .log-warn { color: var(--warning); }
        .log-info { color: var(--secondary); }

        /* ANIMATIONS */
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: #000; }
        ::-webkit-scrollbar-thumb { background: #333; }
        ::-webkit-scrollbar-thumb:hover { background: var(--primary); }
    </style>
</head>
<body>
    <header>
        <div style="display: flex; align-items: center; gap: 15px;">
            <div style="font-size: 32px;">👁️</div>
            <div>
                <h1>JARVIS ECOSYSTEM</h1>
                <div style="font-size: 10px; letter-spacing: 4px; color: var(--secondary);">OBSERVABILITY DASHBOARD</div>
            </div>
        </div>
        <div class="system-status">
            <div><span class="status-dot dot-green"></span>SYSTEM ONLINE</div>
            <div><span class="status-dot dot-green"></span>SECURE</div>
            <div id="clock">00:00:00</div>
        </div>
    </header>

    <div class="grid-container">
        <!-- LEFT COLUMN: SECURITY -->
        <div class="panel" style="grid-row: span 2;">
            <h2>🛡️ SECURITY MONITOR <span style="font-size: 10px;">LIVE</span></h2>
            <div class="security-list" id="security-feed">
                <!-- Populated by JS -->
                <div class="sec-item"><span class="sec-ok">Scanning network...</span></div>
            </div>
            <div style="margin-top: 10px; border-top: 1px solid #333; padding-top: 10px;">
                 <div class="stat-lbl">ACTIVE CONNECTIONS</div>
                 <div class="stat-val" id="conn-count">0</div>
            </div>
        </div>

        <!-- CENTER TOP: TRADING STATUS -->
        <div class="panel">
            <h2>📈 TRADING PIPELINE</h2>
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span>STATUS: <span id="pipeline-status" style="color: white;">LOADING</span></span>
                <span id="elapsed-time">0s</span>
            </div>
            
            <div class="stat-lbl">TOKENS</div>
            <div class="progress-bar"><div class="progress-fill" id="prog-tokens"></div></div>
            
            <div class="stat-lbl">BACKTESTS</div>
            <div class="progress-bar"><div class="progress-fill" id="prog-backtests"></div></div>
            
            <div class="stat-grid">
                <div class="stat-box">
                    <div class="stat-val" id="val-scanned">0</div>
                    <div class="stat-lbl">TOKENS SCANNED</div>
                </div>
                <div class="stat-box">
                    <div class="stat-val" id="val-tested">0</div>
                    <div class="stat-lbl">STRATEGIES</div>
                </div>
            </div>
            <div style="margin-top: 10px; font-size: 12px; color: white;">
                CURRENT: <span id="current-task" style="color: var(--secondary);">...</span>
            </div>
        </div>

        <!-- RIGHT TOP: SYSTEM LOGS -->
        <div class="panel" style="grid-row: span 2;">
            <h2>📝 SYSTEM LOGS</h2>
            <div class="log-container" id="sys-logs">
                <!-- Populated by JS -->
            </div>
        </div>

        <!-- CENTER BOTTOM: COMM LINK -->
        <div class="panel">
            <h2>💬 COMM LINK</h2>
            <div class="chat-container">
                <div class="chat-history" id="chat-history"></div>
                <div class="chat-input">
                    <input type="text" id="msg-input" placeholder="Enter instructions or log error..." onkeypress="if(event.key==='Enter') sendMsg()">
                    <button onclick="sendMsg()">SEND</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        function updateClock() {
            document.getElementById('clock').textContent = new Date().toLocaleTimeString();
        }
        setInterval(updateClock, 1000);

        // Fetch Pipeline Data
        async function updatePipeline() {
            try {
                const res = await fetch('/api/progress');
                const data = await res.json();
                
                document.getElementById('pipeline-status').textContent = data.status.toUpperCase();
                document.getElementById('current-task').textContent = data.current_task;
                document.getElementById('elapsed-time').textContent = Math.floor(data.elapsed_seconds) + 's';
                
                document.getElementById('val-scanned').textContent = data.tokens_scanned;
                document.getElementById('val-tested').textContent = data.strategies_tested;
                
                const tPct = (data.tokens_scanned / 50) * 100;
                const bPct = (data.backtests_completed / 2500) * 100;
                
                document.getElementById('prog-tokens').style.width = tPct + '%';
                document.getElementById('prog-backtests').style.width = bPct + '%';
            } catch(e) {}
        }

        // Fetch Security Data
        async function updateSecurity() {
            try {
                const res = await fetch('/api/security');
                const data = await res.json();
                
                // Update Traffic Stats
                document.getElementById('conn-count').innerHTML = `
                    <div style="font-size:12px">ACTIVE: ${data.net_stats.total_conns}</div>
                    <div style="font-size:10px; color:var(--secondary)">
                        TX: ${data.net_stats.sent_sec} | RX: ${data.net_stats.recv_sec}
                    </div>
                `;
                
                // Update Event Feed
                const feed = document.getElementById('security-feed');
                feed.innerHTML = data.events.map(e => {
                    let color = 'sec-ok';
                    if(e.level === 'warning') color = 'sec-alert';
                    
                    return `
                    <div class="sec-item">
                        <span style="color:var(--text-dim)">[${e.time}]</span>
                        <span style="font-weight:bold; color:var(--primary)">${e.type}</span>
                        <span class="${color}">${e.msg}</span>
                    </div>
                    `;
                }).join('');
            } catch(e) {}
        }

        // Fetch Logs
        async function updateLogs() {
            try {
                const res = await fetch('/api/logs');
                const data = await res.json();
                const container = document.getElementById('sys-logs');
                container.innerHTML = data.logs.map(l => {
                    let cls = 'log-line';
                    if(l.includes('ERROR')) cls += ' log-err';
                    else if(l.includes('WARN')) cls += ' log-warn';
                    else if(l.includes('INFO')) cls += ' log-info';
                    return `<div class="${cls}">${l}</div>`;
                }).join('');
                container.scrollTop = container.scrollHeight;
            } catch(e) {}
        }

        // Chat Status
        async function updateChat() {
            try {
                const res = await fetch('/api/messages');
                const msgs = await res.json();
                const history = document.getElementById('chat-history');
                history.innerHTML = msgs.map(m => `
                    <div class="message ${m.role === 'user' ? 'msg-user' : 'msg-jarvis'}">
                        <strong>${m.role === 'user' ? 'YOU' : 'JARVIS'}:</strong> ${m.text}
                    </div>
                `).join('');
                history.scrollTop = history.scrollHeight;
            } catch(e) {}
        }

        async function sendMsg() {
            const input = document.getElementById('msg-input');
            const text = input.value.trim();
            if(!text) return;
            
            input.value = '';
            await fetch('/api/messages', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text})
            });
            updateChat();
        }

        // Update Loops
        setInterval(updatePipeline, 1000);
        setInterval(updateSecurity, 2000);
        setInterval(updateLogs, 1000);
        setInterval(updateChat, 2000);
        
        updatePipeline();
        updateSecurity();
        updateLogs();
        updateChat();
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
    except: pass
    return jsonify({
        "status": "waiting", "tokens_scanned": 0, "backtests_completed": 0,
        "elapsed_seconds": 0, "current_task": "Connecting..."
    })

# SECURITY INTELLIGENCE
class SecurityMonitor:
    def __init__(self):
        self.known_pids = set()
        self.known_conns = set()
        self.events = []
        self.last_net_io = psutil.net_io_counters()
        self.last_check = time.time()
        
        # Initialize baselines
        for p in psutil.process_iter(['pid']):
            self.known_pids.add(p.info['pid'])
            
    def scan(self):
        timestamp = datetime.now().strftime("%H:%M:%S")
        alerts = []
        
        # 1. PROCESS MONITORING (New Spawns)
        current_pids = set()
        for p in psutil.process_iter(['pid', 'name', 'username']):
            pid = p.info['pid']
            current_pids.add(pid)
            if pid not in self.known_pids:
                alerts.append({
                    "type": "PROCESS", 
                    "msg": f"New Process: {p.info['name']} ({pid})",
                    "level": "info"
                })
        self.known_pids = current_pids

        # 2. NETWORK TRAFFIC ANALYSIS (Packet/Byte Flow)
        net_io = psutil.net_io_counters()
        bytes_sent = net_io.bytes_sent - self.last_net_io.bytes_sent
        bytes_recv = net_io.bytes_recv - self.last_net_io.bytes_recv
        self.last_net_io = net_io
        
        # Detect Anomalous Traffic Spikes (> 5MB/s)
        if bytes_recv > 5_000_000:
            alerts.append({
                "type": "NET_SPIKE",
                "msg": f"High Inbound Traffic: {bytes_recv/1024/1024:.1f} MB/s",
                "level": "warning"
            })
            
        # 3. CONNECTION TRACKING (Active Packet Flows)
        current_conns = set()
        try:
            # Need permissions for all connections, this covers user-owned
            for c in psutil.net_connections(kind='inet'):
                if c.status == 'ESTABLISHED':
                    key = f"{c.laddr.ip}:{c.laddr.port}->{c.raddr.ip}:{c.raddr.port}" if c.raddr else str(c)
                    current_conns.add(key)
                    
                    if key not in self.known_conns:
                        # Flag suspicious ports (Basic Heuristic)
                        port = c.raddr.port if c.raddr else 0
                        level = "info"
                        if port not in [80, 443, 53, 22]:
                             level = "warning" # Non-standard web ports
                        
                        r_ip = c.raddr.ip if c.raddr else "unknown"
                        alerts.append({
                            "type": "CONNECTION",
                            "msg": f"New Conn: {r_ip}:{port}",
                            "level": level
                        })
        except: pass
        self.known_conns = current_conns

        # Add alerts to event feed
        for alert in alerts:
            self.events.insert(0, {
                "time": timestamp,
                "type": alert['type'],
                "msg": alert['msg'],
                "level": alert['level']
            })
            
        # Keep last 50 events
        self.events = self.events[:50]
        
        return {
            "events": self.events,
            "net_stats": {
                "sent_sec": f"{bytes_sent/1024:.1f} KB/s",
                "recv_sec": f"{bytes_recv/1024:.1f} KB/s",
                "total_conns": len(current_conns)
            }
        }

monitor = SecurityMonitor()

@app.route('/api/security')
def get_security():
    data = monitor.scan()
    return jsonify(data)

# ... (Logs and Message routes remain unchanged) ...

@app.route('/api/logs')
def get_logs():
    logs = []
    try:
        if LOG_FILE.exists():
            with open(LOG_FILE) as f:
                logs.extend([l.strip() for l in f.readlines()[-20:]])
    except: pass
    return jsonify({"logs": logs})

@app.route('/api/messages', methods=['GET', 'POST'])
def handle_messages():
    try:
        with open(MESSAGES_FILE, 'r') as f:
            msgs = json.load(f)
    except: msgs = []

    if request.method == 'POST':
        data = request.json
        text = data.get('text', '').strip()
        new_msg = {
            "role": "user",
            "text": text,
            "timestamp": time.time()
        }
        msgs.append(new_msg)
        
        # Command Processing
        response_text = "Message logged."
        
        if text.startswith('/exec '):
            cmd = text[6:]
            response_text = f"Executing: {cmd}..."
            try:
                import subprocess
                subprocess.Popen(cmd, shell=True)
                response_text = f"🚀 Executed: {cmd}"
            except Exception as e:
                response_text = f"❌ Execution failed: {str(e)}"
                
        elif text == '/scan':
            monitor.known_pids = set() # Reset baseline to re-scan
            response_text = "🔄 Security baseline reset. Re-scanning..."
            
        elif text.startswith('/log '):
            entry = text[5:]
            with open(SYSTEM_LOG, 'a') as f:
                f.write(f"[MANUAL USER ENTRY] {entry}\n")
            response_text = "✅ Entry saved to system logs."

        msgs.append({
            "role": "jarvis",
            "text": response_text,
            "timestamp": time.time()
        })
        
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(msgs, f)
        
        return jsonify({"success": True})
        
    return jsonify(msgs)

if __name__ == '__main__':
    print("ECOSYSTEM DASHBOARD STARTING ON PORT 5001...")
    # Refresh connection baseline on start
    monitor.scan()
    app.run(host='0.0.0.0', port=5001, debug=False)

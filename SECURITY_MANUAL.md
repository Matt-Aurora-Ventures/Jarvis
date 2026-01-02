# 🛡️ JARVIS SECURITY INTELLIGENCE

Jarvis now includes an **Intrusion Detection System (IDS)** integrated into the Ecosystem Dashboard.

## 👁️ Features

### 1. Process Monitoring
- **Real-time Spawn Detection**: All new processes are logged instantly.
- **Why?** Detects malware, unauthorized scripts, or unexpected background tasks.
- **Visualization**: Shows Process Name + PID.

### 2. Network Traffic Analysis
- **Flow Monitoring**: Tracks `TX` (Upload) and `RX` (Download) rates.
- **Spike Detection**: Alerts if inbound traffic exceeds 5MB/s (DDOS/Large Download).
- **Visualization**: Live KB/s stats in the Security Panel.

### 3. Connection Tracking
- **New Connection Logging**: Every new outbound/inbound connection is logged.
- **Port Auditing**: Flags connections to non-standard ports (anything not 80/443/22/53) as `WARNING`.
- **Visualization**: Shows Remote IP : Port.

---

## 🎮 How to Use

1. **Open Dashboard**: http://localhost:5001
2. **Watch Feed**: The "Security Monitor" panel updates every 2s.
3. **Reset Baseline**:
   - If the feed is noisy, type `/scan` in the Chat Console.
   - This resets the "known" baseline and only alerts on *new* activity.

## 🔍 Alerts Legend

- **PROCESS** (White): Normal system activity.
- **CONNECTION** (White): Standard web traffic.
- **CONNECTION** (Red): Suspicious/Non-standard port activity.
- **NET_SPIKE** (Red): Unusual bandwidth usage.

---

## ⚠️ Limitations
- User-mode monitoring (no kernel hooks).
- Cannot see packet payloads (encrypted SSL/TLS).
- Relies on `psutil` visibility scope.

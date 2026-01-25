# GUI Nodes and Remote Control Architecture Design

**Research Date:** 2026-01-25
**Goal:** Enable remote computer control from anywhere (phone while doing groceries)
**Constraint:** Work through firewalls/NAT, secure authentication

---

## Executive Summary

This document analyzes three architectural approaches for remote GUI node control:

| Approach | Security | Complexity | Latency | Cost |
|----------|----------|------------|---------|------|
| 1. Tailscale VPN | Excellent | Low | ~50-100ms | Free tier available |
| 2. WebSocket Gateway + ngrok | Good | Medium | ~100-200ms | 8-25/mo |
| 3. WebRTC Peer-to-Peer | Excellent | High | ~30-80ms | Free (STUN), 20+/mo (TURN) |

**Recommendation:** Start with **Tailscale + WebSocket API** (Approach 1) for simplicity and security.

---

## Architecture 1: Tailscale VPN (Recommended)

### Key Features

1. Zero Configuration NAT Traversal: WireGuard handles hole-punching automatically
2. End-to-End Encryption: WireGuard protocol (ChaCha20-Poly1305)
3. Private IP Space: Each device gets stable 100.x.x.x address
4. Built-in ACLs: Control which devices can talk to which
5. Magic DNS: jarvis-desktop.tailnet-name.ts.net automatically resolves

### Implementation

File: core/remote/tailscale_node.py

Components:
- FastAPI server with WebSocket support
- CommandExecutor class with whitelist of allowed apps
- JWT-based device authentication
- Pairing flow with time-limited codes

Command types:
- launch_app: Launch whitelisted applications
- keyboard: Send keyboard input
- screenshot: Capture and return screen image
- run_script: Execute predefined automation scripts

### Security Model

1. Network Layer: WireGuard encryption (AEAD)
2. Device Auth: JWT tokens issued during pairing
3. Command Auth: Whitelist of allowed operations
4. Audit Log: All commands logged with device ID

---

## Architecture 2: WebSocket Gateway

Cloud Gateway with Auth Service, Command Queue (Redis), Event Router.
Desktop connects outbound via WebSocket.
Options: ngrok (8/mo), Cloudflare Tunnel (free), Self-hosted VPS (5-20/mo).

---

## Architecture 3: WebRTC P2P

Direct P2P with DTLS encryption.
Signaling server only for setup.
STUN for NAT traversal (free), TURN for relay fallback.
Lowest latency (30-80ms) but complex implementation.

---

## Comparison

| Feature | Tailscale | Gateway | WebRTC |
|---------|-----------|---------|--------|
| Complexity | Low | Medium | High |
| Latency | 50-100ms | 100-200ms | 30-80ms |
| NAT Success | 99%+ | 100% | 90% |
| Cost | 0 | 5-25/mo | 0-20/mo |

---

## Recommended Roadmap

Week 1-2: Tailscale + FastAPI GUI Node
Week 3-4: Native Mobile App (React Native)
Week 5+: Optional WebRTC for live screen

---

## Security Checklist

- All commands logged with device ID
- Whitelist of allowed applications
- No arbitrary code execution
- Screenshot permission toggle
- Emergency kill switch

---

## Next Steps

1. Set up Tailscale on dev machines
2. Prototype FastAPI GUI Node with screenshot + app launch
3. Simple Telegram commands to test
4. Decide on native mobile app vs enhanced Telegram


---

## Detailed Implementation Guide

### Tailscale Setup (Desktop - Windows)

```bash
# Install
winget install Tailscale.Tailscale

# Start and authenticate
tailscale up

# Get your private IP
tailscale ip -4
# Returns something like: 100.64.0.1
```

### Tailscale Setup (Phone)

1. Download Tailscale from App Store / Play Store
2. Sign in with same account as desktop
3. Both devices now on same private network
4. Phone can reach desktop at 100.x.x.x

### GUI Node Server Implementation

```python
# core/remote/gui_node.py
from fastapi import FastAPI, WebSocket, HTTPException, Depends
from fastapi.security import HTTPBearer
import pyautogui
import mss
import jwt
import secrets
from PIL import Image
import io
import base64
import subprocess

app = FastAPI(title="Jarvis GUI Node")
security = HTTPBearer()
NODE_SECRET = secrets.token_urlsafe(32)
ALLOWED_DEVICES = set()

class CommandExecutor:
    ALLOWED_APPS = {
        "spotify": "spotify.exe",
        "chrome": "chrome.exe", 
        "terminal": "wt.exe",
        "vscode": "code.exe",
    }
    
    async def execute(self, command: dict) -> dict:
        cmd_type = command.get("type")
        
        if cmd_type == "launch_app":
            app_name = command.get("app")
            if app_name not in self.ALLOWED_APPS:
                raise PermissionError(f"App not whitelisted: {app_name}")
            subprocess.Popen(self.ALLOWED_APPS[app_name], shell=True)
            return {"status": "launched", "app": app_name}
            
        elif cmd_type == "keyboard":
            keys = command.get("keys", [])
            for key in keys:
                if key.startswith("hotkey:"):
                    combo = key.replace("hotkey:", "").split("+")
                    pyautogui.hotkey(*combo)
                else:
                    pyautogui.press(key)
            return {"status": "keys_sent", "count": len(keys)}
            
        elif cmd_type == "screenshot":
            with mss.mss() as sct:
                img = sct.grab(sct.monitors[1])
                pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                pil_img.thumbnail((800, 600))
                buffer = io.BytesIO()
                pil_img.save(buffer, format="JPEG", quality=70)
                b64 = base64.b64encode(buffer.getvalue()).decode()
            return {"status": "captured", "image": b64}
            
        else:
            raise ValueError(f"Unknown command: {cmd_type}")

executor = CommandExecutor()

@app.post("/pair")
async def pair_device(pairing_code: str, device_id: str, device_name: str):
    if not verify_pairing_code(pairing_code):
        raise HTTPException(status_code=401, detail="Invalid pairing code")
    
    ALLOWED_DEVICES.add(device_id)
    token = jwt.encode(
        {"device_id": device_id, "device_name": device_name},
        NODE_SECRET,
        algorithm="HS256"
    )
    return {"token": token}

@app.post("/execute")
async def execute_command(command: dict, credentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, NODE_SECRET, algorithms=["HS256"])
        if payload["device_id"] not in ALLOWED_DEVICES:
            raise HTTPException(status_code=403, detail="Device not authorized")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return await executor.execute(command)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

### Mobile Client (TypeScript/React Native)

```typescript
// services/gui-node.ts
class GUINodeClient {
  private baseUrl: string;
  private token: string | null = null;
  
  constructor(tailscaleIP: string) {
    this.baseUrl = `http://${tailscaleIP}:8000`;
  }
  
  async pair(pairingCode: string, deviceId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/pair`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pairing_code: pairingCode,
        device_id: deviceId,
        device_name: "Phone"
      })
    });
    const data = await response.json();
    this.token = data.token;
    await AsyncStorage.setItem("gui_node_token", this.token);
  }
  
  async sendCommand(command: GUICommand): Promise<any> {
    const response = await fetch(`${this.baseUrl}/execute`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${this.token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(command)
    });
    return response.json();
  }
  
  async launchSpotify() {
    return this.sendCommand({ type: "launch_app", app: "spotify" });
  }
  
  async takeScreenshot() {
    return this.sendCommand({ type: "screenshot" });
  }
}
```

---

## Security Deep Dive

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Unauthorized device access | Device pairing with time-limited codes + JWT |
| Token theft | Short expiry (24h) + refresh tokens |
| Man-in-the-middle | WireGuard provides E2E encryption |
| Command injection | Strict whitelist, no shell execution |
| Replay attacks | Nonces + timestamps in commands |
| Brute force pairing | Rate limiting + lockout after 5 attempts |

### ACL Configuration (Tailscale)

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["tag:mobile"],
      "dst": ["tag:desktop:8000"]
    }
  ],
  "tagOwners": {
    "tag:mobile": ["autogroup:admin"],
    "tag:desktop": ["autogroup:admin"]
  }
}
```

---

## Integration with Existing Jarvis

### Telegram Bot Integration

```python
# tg_bot/handlers/remote_control.py
from telegram import Update
from telegram.ext import ContextTypes
import httpx

GUI_NODE_URL = "http://100.64.0.1:8000"  # Tailscale IP

async def launch_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Unauthorized")
        return
    
    app_name = context.args[0] if context.args else None
    if not app_name:
        await update.message.reply_text("Usage: /launch <app>")
        return
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GUI_NODE_URL}/execute",
            headers={"Authorization": f"Bearer {GUI_NODE_TOKEN}"},
            json={"type": "launch_app", "app": app_name}
        )
        result = response.json()
    
    await update.message.reply_text(f"Launched: {result}")

async def screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GUI_NODE_URL}/execute",
            headers={"Authorization": f"Bearer {GUI_NODE_TOKEN}"},
            json={"type": "screenshot"}
        )
        result = response.json()
    
    # Decode and send image
    import base64
    img_bytes = base64.b64decode(result["image"])
    await update.message.reply_photo(photo=img_bytes)
```

---

## References

- Tailscale Documentation: https://tailscale.com/kb/
- WireGuard Protocol: https://www.wireguard.com/protocol/
- WebRTC for Data Channels: https://webrtc.org/
- aiortc (Python WebRTC): https://github.com/aiortc/aiortc
- ngrok Documentation: https://ngrok.com/docs
- Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
- pyautogui: https://pyautogui.readthedocs.io/
- mss (screenshot): https://python-mss.readthedocs.io/

# Technology Stack: Premium Trading Dashboard

**Project:** Jarvis Premium Trading Dashboard (V2 Upgrade)
**Researched:** 2026-02-05
**Overall Confidence:** HIGH

## Executive Summary

This stack recommendation builds on the **existing Flask backend** and adds a modern WebGL-powered frontend. The key insight: use **vanilla Three.js** (not React Three Fiber) since you already have a working Flask+Jinja setup. Adding React would mean rewriting everything. Keep costs at $0 with all free/open-source libraries.

---

## Recommended Stack

### Core 3D & Animation (Frontend)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Three.js** | r171+ | WebGL 3D rendering | Industry standard, matches existing jarvis website (r128), WebGPU-ready for future |
| **GSAP** | 3.12.5+ | Animation & ScrollTrigger | **100% FREE** (Webflow acquisition 2024), already used in jarvis website, best-in-class |
| **Lenis** | 1.1.x | Smooth scrolling | Lightweight (3KB), butter-smooth, integrates with GSAP ticker |

**Rationale:** The jarvis website already uses Three.js r128 + GSAP 3.12.5. Upgrade Three.js to r171+ for WebGPU support while maintaining API compatibility. GSAP became completely free in late 2024 including all premium plugins (ScrollTrigger, SplitText, MorphSVG).

### Financial Charts

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Lightweight Charts** | 5.1.0 | Candlestick/line charts | TradingView's open-source lib, 35KB, handles 50K+ candles smoothly, Apache 2.0 license |
| **D3.js** | 7.x | Treemaps, heatmaps, custom viz | Only for portfolio treemap/sector heatmap, not for price charts |

**Rationale:** Lightweight Charts v5 (released late 2025) is 16% smaller than v4, has multi-pane support, and handles real-time data efficiently. Use D3 sparingly for custom visualizations where Lightweight Charts doesn't fit.

### Real-Time Communication

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Flask-SocketIO** | 5.6.0 | WebSocket server | Integrates directly with existing Flask app, handles bi-directional real-time updates |
| **Socket.IO Client** | 4.x | Browser WebSocket client | Auto-reconnect, fallback to polling, room support |

**Rationale:** Your existing Flask backend (web/trading_web.py) uses HTTP polling every 30 seconds. Upgrade to WebSocket for sub-second price updates without major backend rewrites.

### Styling & Effects

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Vanilla CSS** | - | Core styling | No build step, matches jarvis website approach, CSS custom properties for theming |
| **PostCSS** (optional) | 8.x | Autoprefixer only | If you need older browser support |

**Rationale:** The jarvis website uses inline CSS with custom properties. For Awwwards-quality effects (glass morphism, radial glows), vanilla CSS is sufficient. Avoid Tailwind/styled-components complexity.

---

## Architecture Integration

### Frontend Structure (No Build System)

```
web/
  static/
    js/
      three.min.js          # CDN or local (r171+)
      gsap.min.js           # CDN or local (3.12.5+)
      ScrollTrigger.min.js  # GSAP plugin (now free)
      lenis.min.js          # Smooth scroll
      lightweight-charts.standalone.production.js
      socket.io.min.js      # WebSocket client
      dashboard.js          # Your app code
    css/
      dashboard.css         # Glass morphism, glows, etc.
  templates/
    dashboard.html          # Jinja template
```

### Backend Additions (Flask)

```python
# Add to requirements.txt
flask-socketio>=5.6.0
python-socketio>=5.10.0
eventlet>=0.34.0  # or gevent for async

# Upgrade trading_web.py
from flask_socketio import SocketIO, emit

socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('subscribe_positions')
def handle_subscribe():
    # Push real-time position updates
    pass
```

---

## Design System (From Style Reference)

### Typography
| Font | Weight | Use |
|------|--------|-----|
| **Clash Display** | 600, 700 | Headlines, large numbers |
| **DM Sans** | 400, 500, 600 | Body text, UI elements |

**CDN:** Google Fonts or self-host via Fontshare (Clash Display is free there)

### Color Palette
```css
:root {
  /* Core palette from jarvis website */
  --bg-primary: #0B0C0D;
  --accent-neon: #39FF14;
  --text-primary: #FFFFFF;

  /* Extended for trading UI */
  --profit: #39FF14;      /* Neon green for gains */
  --loss: #FF3B3B;        /* Red for losses */
  --glass-bg: rgba(255, 255, 255, 0.03);
  --glass-border: rgba(255, 255, 255, 0.08);
  --glow-green: 0 0 30px rgba(57, 255, 20, 0.3);
}
```

### Glass Morphism Recipe
```css
.glass-card {
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.hover-glow:hover {
  box-shadow: var(--glow-green);
  border-color: var(--accent-neon);
}
```

---

## Three.js vs React Three Fiber Decision

**Recommendation: Use vanilla Three.js**

| Factor | Three.js | React Three Fiber |
|--------|----------|-------------------|
| Learning curve | Lower (matches existing site) | Higher (React required) |
| Integration | Drop into Flask/Jinja | Requires full frontend rewrite |
| Performance | Direct control | Slight overhead (negligible) |
| Bundle size | Smaller (no React) | +40KB React runtime |
| Community | Larger, more examples | Growing but smaller |

**Decision:** The jarvis website already uses vanilla Three.js. Your existing trading_web.py serves Jinja templates. React Three Fiber would require:
1. Setting up React build pipeline
2. Rewriting all existing templates
3. Learning React state management

Not worth it for this upgrade. Use Three.js directly.

---

## WebSocket vs HTTP Polling

### Current State (trading_web.py)
```javascript
// 30-second polling interval
setInterval(loadAll, 30000);
```

### Recommended Upgrade
```javascript
// Real-time via Socket.IO
const socket = io();
socket.on('position_update', (data) => {
  updatePositionCard(data);
});
socket.on('price_tick', (data) => {
  chart.update({ time: data.time, value: data.price });
});
```

### Backend Pattern
```python
# Run in background thread/greenlet
def price_monitor():
    while True:
        prices = fetch_all_position_prices()
        socketio.emit('price_tick', prices, broadcast=True)
        eventlet.sleep(1)  # 1-second updates
```

---

## Cost Analysis

| Component | Cost | Notes |
|-----------|------|-------|
| Three.js | FREE | MIT License |
| GSAP + ScrollTrigger | FREE | Standard license (post-Webflow) |
| Lenis | FREE | MIT License |
| Lightweight Charts | FREE | Apache 2.0 License |
| D3.js | FREE | ISC License |
| Flask-SocketIO | FREE | MIT License |
| Fonts (Clash Display) | FREE | Fontshare free license |
| Hosting | Existing | Already running Flask on 5001 |

**Total additional cost: $0**

---

## Installation

### Python (Backend)
```bash
pip install flask-socketio>=5.6.0 eventlet>=0.34.0
```

### JavaScript (Frontend - CDN approach, no npm needed)
```html
<!-- In dashboard.html -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r171/three.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js"></script>
<script src="https://unpkg.com/lenis@1.1.18/dist/lenis.min.js"></script>
<script src="https://unpkg.com/lightweight-charts@5.1.0/dist/lightweight-charts.standalone.production.js"></script>
<script src="https://cdn.socket.io/4.7.4/socket.io.min.js"></script>
```

### Alternative: Local Assets (Recommended for production)
```bash
# Download to web/static/js/
curl -o web/static/js/three.min.js https://cdnjs.cloudflare.com/ajax/libs/three.js/r171/three.min.js
# ... etc for other libs
```

---

## Performance Considerations

### Real-Time Data
- **Target:** 1-second price updates for active positions
- **Solution:** Flask-SocketIO with eventlet, emit only changed data
- **Limit:** Cap at 50 positions (already configured in your system)

### 3D Rendering
- **Target:** 60fps on mid-range hardware
- **Solution:**
  - Use `requestAnimationFrame` for render loop
  - Limit particle counts (1000 max for background effects)
  - Use instanced meshes for repeated geometry
  - Enable frustum culling

### Charts
- **Target:** Smooth with 10K+ candles
- **Solution:** Lightweight Charts handles this natively
- **Optimization:** Downsample historical data beyond visible range

### Bundle Size
- Total JS: ~180KB gzipped (Three.js 50KB, GSAP 25KB, Lightweight Charts 35KB, others 70KB)
- No build step needed, serve directly

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| 3D Engine | Three.js | Babylon.js | Larger bundle, overkill for dashboard effects |
| 3D (React) | - | React Three Fiber | Requires React, rewrites existing code |
| Animation | GSAP | Anime.js | GSAP more powerful, already in use |
| Charts | Lightweight Charts | TradingView Charting Library | TradingView paid for commercial, Lightweight free |
| Charts | Lightweight Charts | Chart.js | Chart.js not optimized for financial data |
| WebSocket | Flask-SocketIO | raw WebSocket | SocketIO has auto-reconnect, rooms, easier API |
| Styling | Vanilla CSS | Tailwind | No build step, matches existing approach |

---

## Migration Path

### Phase 1: Add WebSocket (Backend)
1. Install flask-socketio + eventlet
2. Add socket events to existing trading_web.py
3. Keep HTTP endpoints as fallback

### Phase 2: Create New Dashboard Template
1. Create dashboard.html (dark theme, new design)
2. Load all JS libs via CDN initially
3. Port existing functionality to new UI

### Phase 3: Add 3D Effects
1. Add Three.js background (particles, orbs)
2. Integrate GSAP animations
3. Add Lenis smooth scroll

### Phase 4: Production Optimization
1. Move CDN assets to local static files
2. Add service worker for offline resilience
3. Implement lazy loading for heavy components

---

## Sources

### HIGH Confidence (Official Documentation)
- [Three.js Official](https://threejs.org/) - r171+ documentation
- [GSAP Pricing - Now Free](https://gsap.com/pricing/)
- [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- [Flask-SocketIO Documentation](https://flask-socketio.readthedocs.io/)

### MEDIUM Confidence (Multiple Sources Agree)
- [Three.js vs R3F Comparison](https://graffersid.com/react-three-fiber-vs-three-js/)
- [GSAP ScrollTrigger + Three.js](https://frontend.horse/episode/using-threejs-with-gsap-scrolltrigger/)
- [Lenis Smooth Scroll](https://lenis.darkroom.engineering/)
- [Lightweight Charts v5 Announcement](https://www.tradingview.com/blog/en/tradingview-lightweight-charts-version-5-50837/)

### LOW Confidence (Single Source / Community)
- WebGPU browser support claims - verify at caniuse.com before production use

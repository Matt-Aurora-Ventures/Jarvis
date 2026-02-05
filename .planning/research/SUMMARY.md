# Project Research Summary

**Project:** Jarvis Premium Trading Dashboard (Web version of /demo Telegram bot)
**Domain:** WebGL-powered Solana Trading Terminal
**Researched:** 2026-02-05
**Confidence:** HIGH

## Executive Summary

This dashboard is a **premium web trading terminal** for Solana tokens, upgrading the existing Flask-based `/demo` bot to an Awwwards-quality WebGL experience. The research confirms the approach should leverage the **existing Flask backend** (web/trading_web.py) rather than starting fresh, adding WebSocket real-time capabilities and Three.js visual effects on top of what already works. The key architectural insight: use **vanilla Three.js** (not React Three Fiber) since the existing codebase is Flask+Jinja with no React infrastructure.

The recommended approach builds incrementally: first upgrade real-time data delivery (WebSocket via Flask-SocketIO), then apply visual polish (glassmorphism, GSAP animations), and finally add Three.js 3D effects. This avoids the common pitfall of "starting over" when 80% of the functionality already exists. The existing `core/bags_websocket.py` and `web_demo/backend/` FastAPI services provide production-ready WebSocket infrastructure that just needs frontend integration.

The primary risks are **WebGL memory leaks** (Three.js resources not disposed on component unmount) and **WebSocket race conditions** with rapid price updates. Both are well-documented with established mitigation patterns. A secondary risk is scope creep toward "cool 3D effects" that add visual noise without trading value. The research strongly recommends starting with **functional parity to /demo bot** before any 3D enhancements.

## Key Findings

### Recommended Stack

The stack builds on the existing Flask backend (port 5001) with WebSocket upgrade and modern frontend libraries served via CDN (no build system required).

**Core technologies:**
- **Three.js r171+**: WebGL 3D rendering for premium visual effects (particles, glows) - matches existing jarvislife.io site style
- **GSAP 3.12.5+**: Animation and ScrollTrigger for micro-interactions - **now 100% free** after Webflow acquisition
- **Lightweight Charts 5.1.0**: TradingView's open-source financial charting (35KB, handles 50K+ candles)
- **Flask-SocketIO 5.6.0**: WebSocket server integrated with existing Flask app - upgrades current 30s polling to sub-second updates
- **Vanilla CSS with custom properties**: Glass morphism, radial glows - no Tailwind/build system complexity

**Design system:**
- Fonts: Clash Display (headlines) + DM Sans (body) - from Fontshare (free)
- Colors: #0B0C0D background, #39FF14 neon accent, glass borders at rgba(255,255,255,0.08)
- Effects: backdrop-filter blur(20px), box-shadow glows on hover

**Total cost: $0** - All libraries are free/open-source.

### Expected Features

**Must have (table stakes - users expect these):**
- Portfolio overview card (balance, positions, win rate) - **exists, needs visual upgrade**
- Real-time price updates - **needs WebSocket upgrade from 30s polling**
- Position list with P&L - **exists**
- Buy/sell with mandatory TP/SL - **exists via bags.app API**
- Sentiment analysis display - **exists via Grok AI**
- Dark mode (90%+ of traders prefer) - **needs implementation**

**Should have (differentiators for award-quality):**
- Glassmorphism cards (frosted glass effect)
- Micro-interactions on buttons (hover lift, shadows)
- Animated number transitions (P&L changes feel alive)
- Skeleton loading states (perceived performance)
- Toast notifications (replace JavaScript alerts)
- Sentiment gauge visualization (radial/gradient 0-100)

**Defer (v2+):**
- Advanced TradingView charting integration
- Multiple wallet support
- Trade history export
- Price alerts system
- Portfolio analytics graphs

**Anti-features (explicitly avoid):**
- Overcrowded charts - keep single-purpose visualizations
- Gratuitous 3D effects - flat design with subtle depth
- Sound effects - silent by default
- Auto-refresh without warning - use badge for new data
- Modal abuse - prefer inline expansion

### Architecture Approach

The architecture uses the existing **two-tier backend** (FastAPI on port 8000 as API gateway, Flask on port 5001 for trade execution) with a new WebSocket relay for real-time prices. TanStack Query handles REST data caching while a dedicated Zustand store manages high-frequency price updates separately from UI state.

**Major components:**
1. **Flask Backend** (existing) - Trade execution via bags.app, position management, wallet operations
2. **FastAPI Gateway** (existing) - WebSocket relay from bags.fm, rate limiting, auth, sentiment caching
3. **Frontend Dashboard** (new) - Jinja template with vanilla JS, Three.js effects, Lightweight Charts
4. **BagsWebSocketClient** (existing in core/) - bags.fm price feed subscription with auto-reconnect

**Data flow pattern:**
- REST: Dashboard -> FastAPI proxy -> Flask backend -> bags.app/Jupiter
- Real-time: bags.fm WebSocket -> FastAPI WebSocketManager -> Browser -> UI update
- Sentiment: Cache in Redis (5-min TTL) to avoid repeated Grok API calls

### Critical Pitfalls

1. **Three.js Memory Leaks** - WebGL resources (textures, geometries, materials) must be explicitly disposed in cleanup callbacks. Use `renderer.info.memory` to monitor. Establish disposal patterns in Phase 1 before any 3D code.

2. **WebSocket Race Conditions** - Price updates arriving during React renders cause stale displays. Implement event cache pattern: buffer messages until component is mounted, then flush. After reconnection, always fetch fresh state to fill gaps.

3. **WebGL Context Loss** - Browsers revoke WebGL contexts under memory pressure (especially mobile). Add `webglcontextlost` and `webglcontextrestored` event handlers. Show fallback UI during recovery. **Critical for mobile users.**

4. **setState in Animation Loops** - Never use React state (useState, Zustand selectors) for values that update every frame. Use refs and direct mutation. Check for `useState` in `useFrame` callbacks during code review.

5. **Throttling Price Updates** - bags.fm can send 100+ updates/second. Throttle to 60fps max (16ms interval) using requestAnimationFrame batching. Without this, the render pipeline will be overwhelmed.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: WebSocket Foundation
**Rationale:** Real-time data is the critical upgrade over current 30s polling. Must be in place before visual work.
**Delivers:** Sub-second price updates, WebSocket connection management, reconnection with state sync
**Addresses:** Real-time updates (table stakes), connection status indicator
**Avoids:** WebSocket race conditions (Pitfall 3), reconnection state drift (Pitfall 8)
**Stack:** Flask-SocketIO 5.6.0, eventlet, Socket.IO client

### Phase 2: Visual Foundation
**Rationale:** Core trading UI before 3D enhancements. Establishes design system that all future components use.
**Delivers:** New dashboard template, dark mode, glassmorphism cards, design system CSS
**Addresses:** Dark mode (table stakes), glass cards (differentiator), color-coded P&L
**Avoids:** Scope creep to 3D before functional parity
**Stack:** Vanilla CSS, custom properties, Clash Display font

### Phase 3: Core Trading Parity
**Rationale:** Match all /demo bot functionality before any new features
**Delivers:** Portfolio overview, position list, buy/sell flows, sentiment display
**Addresses:** All table stakes features from FEATURES.md
**Uses:** Existing Flask endpoints (/api/status, /api/positions, /api/trade/*)
**Implements:** Toast notifications, skeleton loaders, animated number transitions

### Phase 4: Premium Animations
**Rationale:** Polish layer - GSAP micro-interactions, staggered animations, smooth transitions
**Delivers:** Button hover effects, card entrance animations, number counters, smooth scrolling
**Addresses:** Differentiators from FEATURES.md (micro-interactions, animations)
**Stack:** GSAP 3.12.5, Lenis smooth scroll
**Avoids:** Animation in state (Pitfall 2)

### Phase 5: Financial Charts
**Rationale:** After core trading works, add price visualization
**Delivers:** Candlestick/line charts for positions, real-time chart updates
**Stack:** Lightweight Charts 5.1.0
**Addresses:** Price visualization (competitive feature)

### Phase 6: Three.js Effects
**Rationale:** Last phase - 3D is enhancement, not core functionality
**Delivers:** Animated particle background, subtle orb effects, ambient movement
**Stack:** Three.js r171+
**Avoids:** Memory leaks (Pitfall 1), context loss (Pitfall 4), continuous render loop (Pitfall 10)
**Uses:** frameloop="demand" pattern, disposal in cleanup

### Phase Ordering Rationale

- **WebSocket before visual:** Real-time data infrastructure must be solid before building UI that depends on it
- **Design system before components:** CSS variables and patterns established once, used everywhere
- **Functional parity before features:** Match /demo bot first, then exceed it
- **3D last:** Visual candy should not delay core trading functionality

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 5 (Charts):** Lightweight Charts API for real-time updates, WebSocket integration pattern
- **Phase 6 (Three.js):** Memory management patterns, specific particle systems, performance profiling

Phases with standard patterns (skip research-phase):
- **Phase 1 (WebSocket):** Flask-SocketIO has excellent docs, existing bags_websocket.py as reference
- **Phase 2-3 (UI/Trading):** Existing endpoints verified, standard HTML/CSS/JS patterns
- **Phase 4 (GSAP):** GSAP documentation is excellent, existing jarvislife.io as reference

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Official docs verified, all libraries are mature and well-documented |
| Features | HIGH | Based on existing /demo bot functionality + industry standards |
| Architecture | HIGH | Existing codebase verified (Flask endpoints, FastAPI WebSocket, bags.fm client) |
| Pitfalls | HIGH | Official docs (React Three Fiber, Khronos WebGL wiki) + verified community patterns |

**Overall confidence:** HIGH

### Gaps to Address

- **Mobile performance:** Research recommends quality tiers for mobile, but specific thresholds need testing on real devices
- **bags.fm WebSocket rate limits:** Unknown if they throttle high-frequency subscriptions. Monitor during Phase 1.
- **Grok sentiment caching:** 5-min TTL assumed, but may need adjustment based on API costs

## Sources

### Primary (HIGH confidence)
- [Three.js Official Documentation](https://threejs.org/) - r171+ features, WebGPU roadmap
- [GSAP Pricing - Now Free](https://gsap.com/pricing/) - Webflow acquisition confirmed
- [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/) - v5 API reference
- [Flask-SocketIO Documentation](https://flask-socketio.readthedocs.io/) - Integration patterns
- [React Three Fiber: Performance Pitfalls](https://r3f.docs.pmnd.rs/advanced/pitfalls) - Memory and render loop patterns
- [Khronos WebGL Wiki: Context Loss](https://www.khronos.org/webgl/wiki/HandlingContextLost) - Recovery patterns

### Secondary (MEDIUM confidence)
- Existing Jarvis codebase (VERIFIED):
  - `core/bags_websocket.py` - BagsWebSocketClient with auto-reconnect
  - `web_demo/backend/app/services/websocket_manager.py` - WebSocketManager
  - `web/trading_web.py` - Flask trading endpoints (verified working)
- [TkDodo: Using WebSockets with React Query](https://tkdodo.eu/blog/using-web-sockets-with-react-query) - Invalidation pattern

### Tertiary (LOW confidence)
- WebGPU browser support claims - verify at caniuse.com before enabling
- Mobile WebGL performance benchmarks - need real device testing

---
*Research completed: 2026-02-05*
*Ready for roadmap: yes*

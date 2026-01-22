# Bags Intel - Intelligence Platform

Comprehensive intelligence platform for bags.fm token graduations with AI-powered recommendations, supervisor integration, and self-learning capabilities.

## 🎯 Vision

A self-correcting, self-adjusting intelligence system that learns from outcomes and shares insights across all JARVIS components via the supervisor, powered by Ollama/Claude AI.

## ✨ Core Features

### Real-Time Intelligence Feed
- **Twitter-style interface** - Familiar, easy-to-scan layout
- **WebSocket live updates** - New graduations appear instantly
- **AI-powered analysis** - Grok summaries for each token
- **Comprehensive scoring** - 5-component quality assessment (Bonding, Creator, Social, Market, Distribution)
- **Risk indicators** - Clear visual risk levels with color coding

### 🆕 Advanced Intelligence Features

#### 1. Token Comparison Mode
- **Side-by-side analysis** - Compare 2-4 tokens simultaneously
- **Metric highlighting** - Best metrics automatically highlighted
- **Winner detection** - Identifies highest-scoring token
- **10+ metrics compared** - Scores, liquidity, volume, market cap, holders, risk
- **Decision support** - Make informed choices between opportunities

#### 2. Portfolio Tracker
- **Investment tracking** - Monitor all your bags.fm positions
- **Real-time P&L** - Live profit/loss calculations
- **Position management** - Add, track, and remove positions
- **Performance metrics** - Total invested, current value, P&L %, holdings count
- **LocalStorage persistence** - Positions saved across sessions

#### 3. Custom Alerts System
- **Criteria-based alerts** - Set min score, max risk, min liquidity
- **Browser notifications** - Desktop notifications for matched tokens
- **Sound alerts** - Optional audio notifications
- **Active/inactive toggle** - Enable/disable alerts per rule
- **Trigger history** - Track recent alert activations
- **Real-time monitoring** - Checks every 10 seconds

#### 4. AI-Powered Recommendations
- **Ollama/Claude integration** - Local AI for privacy and speed
- **Natural language reasoning** - Explains WHY each recommendation makes sense
- **Confidence scores** - 30%-95% based on historical accuracy
- **Self-adjusting** - Learns from feedback to improve over time
- **4 recommendation levels**: strong_buy, buy, hold, avoid

#### 5. Supervisor Integration
- **Cross-component communication** - Shares intelligence with Treasury, Telegram, Twitter bots
- **Feedback loops** - Receives trading outcomes from Treasury bot
- **Continuous learning** - Adjusts recommendations based on actual results
- **Shared state** - All components access same intelligence
- **Prediction accuracy tracking** - Measures and displays performance

### Advanced Filtering & Search
- **🔍 Smart Search** - Search by token name or symbol with instant results
- **Advanced Filters Panel** - Filter by:
  - Score range (min/max)
  - Risk level (low/medium/high/extreme)
  - Market cap range
  - Time range (1h, 6h, 24h, 7d, all time)
- **Quality Filters** - Quick filter buttons for Exceptional, Strong, Average, Weak
- **Sorting Options** - Sort by:
  - Time (newest/oldest first)
  - Score (highest/lowest)
  - Market cap (highest/lowest)

### Interactive Features
- **Token Detail Modal** - Click "View" to see comprehensive token details
- **Share Functionality** - Native share or copy link to clipboard
- **Copy Contract Address** - One-click CA copying
- **Refresh Individual Cards** - Update token data without full reload

### Customization & Settings
- **Custom Notifications** - Choose when to be notified:
  - Exceptional tokens (80+ score)
  - Strong tokens (65+ score)
  - Sound alerts (optional)
- **Display Options**:
  - Auto-refresh toggle
  - Compact card view for faster scanning
- **Persistent Settings** - Saved to localStorage

### Stats & Analytics
- **Live Stats Summary**:
  - Currently showing count
  - Average score of displayed tokens
  - Total market cap
- **Real-time Updates** - Stats update as you filter

### Mobile-Optimized
- **Fully Responsive** - Works beautifully on all screen sizes
- **Touch-optimized** - 44px minimum touch targets
- **Mobile-friendly cards** - Adjusted padding and font sizes
- **Swipeable** - Natural mobile interactions

### Performance
- **Efficient Rendering** - Only renders visible cards
- **Skeleton Loading** - Smooth loading states
- **Optimized Animations** - Respects prefers-reduced-motion
- **Local Caching** - Settings and preferences cached

## 🎨 Design System

Built with the JARVIS LifeOS design language:

- **Color Palette**:
  - Dark background (#0B0C0D)
  - Electric green accent (#39FF14)
  - Pure white (#FFFFFF)
  - Risk colors (green/yellow/orange/red)
- **Typography**:
  - Clash Display (headings)
  - DM Sans (body)
  - JetBrains Mono (code/data)
- **Glassmorphism**: Blurred glass cards with subtle borders
- **Animations**: Smooth transitions and micro-interactions
- **Responsive**: Mobile-first design

## 🚀 Quick Start

### Easy Setup (Recommended)

**Windows:**
```bash
cd webapp/bags-intel
start.bat
```

**Linux/Mac:**
```bash
cd webapp/bags-intel
chmod +x start.sh
./start.sh
```

### Manual Setup

1. **Install Dependencies**
```bash
cd webapp/bags-intel
pip install -r requirements.txt
```

2. **Run WebSocket Server** (Recommended)
```bash
python websocket_server.py
```

Or run basic API server (no WebSocket):
```bash
python api.py
```

3. **Open Browser**
Navigate to: http://localhost:5000

### Enhanced Version

For the full enhanced experience with all features:

1. Open `index-enhanced.html` instead of `index.html`
2. Uses `app-enhanced.js` with advanced filtering, search, modals, etc.
3. Includes `styles-enhanced.css` for additional UI components

## 📡 API Endpoints

### Core Endpoints
- `GET /api/bags-intel/graduations` - Get all graduation events
- `GET /api/bags-intel/graduations/latest` - Get most recent graduation
- `POST /api/bags-intel/webhook` - Webhook to receive new events (auto-shares with supervisor)
- `GET /api/bags-intel/stats` - Get statistics
- `GET /api/health` - Health check (includes supervisor status)

### 🆕 Supervisor Integration Endpoints
- `POST /api/bags-intel/feedback` - Receive trading outcome feedback from Treasury bot
- `GET /api/bags-intel/supervisor/stats` - Get prediction accuracy and learning stats

**See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for detailed API documentation and examples.**

## 🔗 Integration with Bags Intel Service

### Method 1: Direct Integration

```python
from webapp.bags_intel.api import add_graduation_event

# In your intel_service.py, after scoring a graduation:
add_graduation_event(graduation_event)
```

### Method 2: Webhook (Recommended)

```python
from webapp.bags_intel.integration import notify_webapp

# In your intel_service.py:
if graduation_event.is_reportable:
    notify_webapp(graduation_event)
```

### Method 3: Import Module

```python
from webapp.bags_intel.integration import WebappIntegration

# Initialize
webapp = WebappIntegration()

# Check health
if webapp.check_health():
    # Send graduation event
    webapp.notify_graduation(graduation_event)
```

## 📂 File Structure

```
webapp/bags-intel/
├── index.html              # Basic HTML structure
├── index-enhanced.html     # Enhanced with all features
├── styles.css              # Core JARVIS design system
├── styles-enhanced.css     # Additional UI components
├── app.js                  # Basic frontend JavaScript
├── app-enhanced.js         # Full-featured JavaScript
├── app-websocket.js        # WebSocket version
├── api.py                  # Basic Flask API server
├── websocket_server.py     # WebSocket-enabled server
├── integration.py          # Integration helpers
├── events.json             # Persistent event storage
├── requirements.txt        # Python dependencies
├── start.bat              # Windows quick start
├── start.sh               # Linux/Mac quick start
└── README.md              # This file
```

## 🎯 Quality Tiers

- 🌟 **Exceptional** (80-100): Top 10% metrics, strong buy signals
- ✅ **Strong** (65-79): Above average, solid fundamentals
- ➖ **Average** (50-64): Meets baseline, moderate risk
- ⚠️ **Weak** (35-49): Below average, higher risk
- 🚨 **Poor** (<35): Multiple red flags, avoid

## ⚠️ Risk Levels

- 🟢 **Low**: Safe fundamentals, verified creator, strong metrics
- 🟡 **Medium**: Some caution advised, monitor closely
- 🟠 **High**: Significant concerns, high volatility risk
- 🔴 **Extreme**: Multiple red flags, very high risk

## 📊 Score Components

Each graduation is scored across 5 dimensions:

1. **Bonding Score** (25%): Duration, volume, buyer count, buy/sell ratio
2. **Creator Score** (20%): Twitter presence, account age, launch history
3. **Social Score** (15%): Linked socials, website, community engagement
4. **Market Score** (25%): Liquidity, price stability, 24h volume
5. **Distribution Score** (15%): Holder count, concentration, whale activity

## ⌨️ Keyboard Shortcuts

- `/` - Focus search bar
- `Esc` - Close modals
- `Ctrl/Cmd + K` - Open settings (coming soon)

## 🎮 User Guide

### Filtering Tokens

1. **Quick Filters**: Click quality badges (Exceptional, Strong, etc.)
2. **Search**: Type token name or symbol in search bar
3. **Advanced Filters**: Click "Filters" button for granular control
   - Set score range (e.g., 70-100 for high quality only)
   - Select risk levels to show
   - Filter by market cap
   - Choose time range

### Viewing Details

- Click the "View" button (eye icon) on any card
- See comprehensive breakdown of all metrics
- Quick links to Bags.fm and DexScreener
- Copy contract address

### Customizing Experience

1. Click settings icon (⚙️) in header
2. Configure notifications:
   - Enable alerts for high-quality tokens
   - Turn on/off sound notifications
3. Toggle display options:
   - Auto-refresh for real-time updates
   - Compact mode for more cards per screen

## 🔧 Mock Data

By default, the server generates 20 mock graduation events for testing across all quality tiers.

To use real data:
1. Integrate with `bots/bags_intel` service
2. Use webhook endpoint or direct integration
3. Events auto-populate from real bags.fm graduations

## 🚀 Performance Tips

- **Use WebSocket server** for real-time updates (websocket_server.py)
- **Enable auto-refresh** for latest data without manual reload
- **Use compact mode** when tracking many tokens
- **Filter aggressively** to reduce rendering load

## 🐛 Troubleshooting

### WebSocket not connecting?
- Make sure `websocket_server.py` is running (not `api.py`)
- Check console for connection errors
- Falls back to polling automatically

### Events not showing?
- Check `events.json` exists and has data
- Verify API server is running on port 5000
- Check browser console for errors

### Filters not working?
- Clear browser cache and reload
- Check advanced filters aren't too restrictive
- Reset filters with "Reset" button

## 📈 Roadmap

- [x] Real-time WebSocket updates
- [x] Advanced filtering
- [x] Search functionality
- [x] Sorting options
- [x] Token detail modal
- [x] Share functionality
- [x] Custom notifications
- [x] Settings persistence
- [x] Mobile optimization
- [ ] Chart visualizations (price/volume)
- [ ] User watchlists
- [ ] Export to CSV
- [ ] Historical data view
- [ ] Comparison mode (side-by-side)
- [ ] Dark/light mode toggle
- [ ] Database persistence (PostgreSQL)

## 📄 License

Part of JARVIS LifeOS

## 🙏 Credits

- Design inspired by jarvislife.io
- Twitter feed layout reference provided by user
- Built with Flask, Socket.IO, and vanilla JavaScript

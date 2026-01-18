"""
Comprehensive Help & Command Reference for Jarvis Treasury Bot

Organized reference for all commands, features, and capabilities.
"""

from telegram.constants import ParseMode


class HelpReference:
    """Treasury Bot help and command reference."""

    @staticmethod
    def get_quick_start() -> str:
        """Get quick start guide."""
        return """👑 <b>JARVIS TREASURY BOT - QUICK START</b>

Welcome to the most advanced Telegram trading interface. Here's how to get started:

<b>Step 1: Dashboard</b>
/treasury_dashboard - See live portfolio metrics in real-time

<b>Step 2: Monitor Positions</b>
/treasury_positions - View all open trades with P&L

<b>Step 3: Performance</b>
/treasury_report - Analyze trading performance over time

<b>Step 4: Alerts</b>
/treasury_settings → Enable price/profit alerts → Stay updated automatically

<i>💡 Tip: Use inline buttons for quick navigation between screens</i>
"""

    @staticmethod
    def get_full_commands() -> str:
        """Get all available commands."""
        return """📚 <b>COMPLETE COMMAND REFERENCE</b>

<b>━ DASHBOARD & MONITORING ━</b>

/treasury_dashboard
  └─ Live portfolio dashboard with real-time metrics
     • Total balance and deployed capital
     • Total P&L and daily returns
     • Open positions summary
     • Win rate and trading stats
     • Real-time updates every 30 seconds

/treasury_positions
  └─ Detailed breakdown of all open positions
     • Entry price, current price, current value
     • Unrealized P&L with percentage
     • Time held and position size
     • Take profit and stop loss levels
     • Position exposure percentage

/treasury_trades
  └─ Recent trade history with results
     • Last 15 closed trades
     • Entry → Exit price progression
     • Individual P&L for each trade
     • Trade duration
     • Cumulative returns

<b>━ PERFORMANCE & ANALYTICS ━</b>

/treasury_report
  └─ Comprehensive performance analysis
     • Select period: 7d, 30d, 90d, 1 year
     • Period returns and annualized returns
     • Risk metrics: Sharpe ratio, Sortino ratio
     • Maximum drawdown and volatility
     • Trade statistics: Win rate, profit factor
     • Best/worst day analysis

<b>━ CONFIGURATION & CONTROL ━</b>

/treasury_settings
  └─ Configuration menu
     • Toggle between Live Trading and Dry Run mode
     • Adjust risk level (Conservative/Moderate/Aggressive/Degen)
     • Position sizing by risk level
     • Enable/disable features
     • Admin-only controls

<b>━ MARKET DATA ━</b>

/market_overview
  └─ Current market conditions
     • BTC, ETH, SOL prices and 24h changes
     • Market cap and Bitcoin dominance
     • 24h volume and Fear & Greed index
     • Top gainers and losers

/market_sentiment
  └─ Sentiment analysis by asset
     • Grok sentiment scores
     • Twitter sentiment tracking
     • News sentiment analysis
     • Onchain analysis
     • Key drivers and catalysts

/market_liquidations
  └─ Liquidation heatmap
     • BTC liquidation levels
     • ETH liquidation levels
     • SOL liquidation levels
     • Critical watch levels
     • Liquidation risk assessment

/market_volume
  └─ Trading volume analysis
     • 24h volume leaders
     • Volume trends (spike detection)
     • Buying vs selling pressure
     • Exchange flows (inflow/outflow)
     • Whale activity tracking

/market_trending
  └─ Trending tokens and social sentiment
     • Rising tokens by volume
     • Community favorites
     • Upcoming catalysts
     • Risk warnings

<b>━ ALERTS & NOTIFICATIONS ━</b>

/alerts_subscribe <type>
  └─ Subscribe to alerts
     • price_alert - Price movement alerts
     • profit_alert - Profit target alerts
     • stoploss_alert - Stop loss alerts
     • risk_alert - Portfolio risk alerts
     • all - All alerts

/alerts_unsubscribe <type>
  └─ Unsubscribe from alerts

/alerts_manage
  └─ View active subscriptions and configure alert thresholds

<b>━ HELP & REFERENCE ━</b>

/treasury_help
  └─ Full command reference (this message)

/help_keyboard_shortcuts
  └─ Learn keyboard shortcut buttons

/help_features
  └─ Overview of all features

<b>━ ADMIN COMMANDS ━</b>

/admin_toggle_live
  └─ [Admin] Switch between live and dry run mode

/admin_set_risk <level>
  └─ [Admin] Set risk level for all trades

/admin_export_report
  └─ [Admin] Export performance report as CSV

/admin_force_close_position <symbol>
  └─ [Admin] Force close a specific position

/admin_settings
  └─ [Admin] View detailed system settings

<i>💡 Tip: Most commands also have buttons for easier access</i>
"""

    @staticmethod
    def get_feature_overview() -> str:
        """Get feature overview."""
        return """🌟 <b>FEATURE OVERVIEW</b>

<b>PORTFOLIO MANAGEMENT</b>
  ✅ Real-time dashboard with live P&L tracking
  ✅ Position-by-position analysis
  ✅ Multi-timeframe performance reports
  ✅ Risk metrics and analytics
  ✅ Trade history tracking
  ✅ Exposure analysis by asset

<b>TRADING EXECUTION</b>
  ✅ One-click trade execution from dashboard
  ✅ Configurable position sizing
  ✅ Automatic stop loss placement
  ✅ Take profit management
  ✅ Risk-based entry sizing
  ✅ Support for memecoins, bluechips, altcoins

<b>ALERTS & MONITORING</b>
  ✅ Real-time price alerts
  ✅ Profit milestone notifications
  ✅ Stop loss triggers
  ✅ Portfolio risk warnings
  ✅ Market volatility alerts
  ✅ Sentiment shift alerts
  ✅ Liquidation zone warnings

<b>MARKET INTELLIGENCE</b>
  ✅ Market overview with major assets
  ✅ Multi-source sentiment analysis
  ✅ Liquidation heatmaps
  ✅ Volume and whale tracking
  ✅ Trending tokens detection
  ✅ Macro economic indicators

<b>VISUALIZATION</b>
  ✅ Portfolio performance charts
  ✅ Price action with moving averages
  ✅ Drawdown analysis
  ✅ Trade distribution histograms
  ✅ Position allocation pie charts
  ✅ Risk/return scatter plots
  ✅ Sentiment heatmaps

<b>AUTOMATION</b>
  ✅ Automatic position monitoring
  ✅ Stop loss enforcement
  ✅ Cooldown management
  ✅ Error recovery and retry logic
  ✅ Background alert monitoring
  ✅ Live dashboard updates

<b>SECURITY</b>
  ✅ Admin-only access
  ✅ Two-factor verification ready
  ✅ Audit trail logging
  ✅ Wallet integration
  ✅ Secure credential management

<b>PERFORMANCE TRACKING</b>
  ✅ Win rate calculation
  ✅ Profit factor analysis
  ✅ Sharpe ratio measurement
  ✅ Maximum drawdown tracking
  ✅ Cumulative returns
  ✅ Best/worst trade analysis
"""

    @staticmethod
    def get_keyboard_shortcuts() -> str:
        """Get keyboard shortcut guide."""
        return """⌨️ <b>KEYBOARD SHORTCUTS & BUTTONS</b>

<b>Navigation</b>
  🔄 Refresh - Update current view instantly
  ← Back - Return to previous menu
  ↩️ Main Menu - Go to main dashboard

<b>Dashboard Controls</b>
  📊 Details - Expand position details
  📈 Report - View performance report
  ⚙️ Settings - Open settings menu

<b>Position Management</b>
  🎯 Close - Close selected position
  📋 History - View position history
  🔔 Alerts - Configure alerts

<b>Market Data</b>
  📊 Overview - Market overview
  🧠 Sentiment - Sentiment analysis
  🔥 Liquidations - Liquidation levels
  ⚡ Volume - Volume analysis
  🚀 Trending - Trending tokens

<b>Quick Access</b>
  Just tap the button for instant navigation
  All buttons update in real-time
  Supports on/off toggles for settings

<b>Inline Menus</b>
  Select from options shown in message
  No need to type commands
  Instant feedback after selection
"""

    @staticmethod
    def get_faq() -> str:
        """Get frequently asked questions."""
        return """❓ <b>FREQUENTLY ASKED QUESTIONS</b>

<b>Getting Started</b>

Q: How do I start trading?
A: /treasury_dashboard to see your portfolio, then use the trade button

Q: What's the difference between Live and Dry Run?
A: Dry Run = paper trading (no real money). Live = real trading. Admins can toggle.

Q: How often is the dashboard updated?
A: Every 30 seconds automatically. Tap Refresh for instant update.

<b>Trading</b>

Q: What risk levels are available?
A: Conservative (1%), Moderate (2%), Aggressive (5%), Degen (10%)

Q: What's the maximum position size?
A: Depends on risk level and portfolio value. System validates before execution.

Q: Can I set custom stop loss/take profit?
A: Yes, all positions support both TP and SL with customizable levels.

Q: How is P&L calculated?
A: Real-time based on current prices. Includes both realized and unrealized P&L.

<b>Performance</b>

Q: What metrics do you track?
A: Win rate, Sharpe ratio, max drawdown, volatility, profit factor, average trade duration

Q: How far back do reports go?
A: 1 year of data available. Reports available for 7d, 30d, 90d, and 1y periods.

Q: What's Sharpe ratio?
A: Risk-adjusted return metric. Higher is better (>1.0 is good, >2.0 is excellent).

<b>Alerts</b>

Q: How do I enable alerts?
A: /treasury_settings → Enable notifications → Choose alert types

Q: Do alerts trigger outside trading hours?
A: Yes! Alerts work 24/7 across all timeframes.

Q: What's the minimum alert delay?
A: 60 seconds between identical alerts (prevents spam).

<b>Market Data</b>

Q: How often is market data updated?
A: Every minute for prices, every 5 minutes for sentiment, real-time for liquidations

Q: Where does data come from?
A: Jupiter (prices), GlassNode (liquidations), Grok/Twitter (sentiment), CoinGlass (volumes)

Q: Is data real-time?
A: Yes, streamed live from APIs with latency < 1 second

<b>Technical</b>

Q: What happens if the bot disconnects?
A: Supervisor auto-restarts within 30 seconds

Q: Are my positions safe?
A: Yes! Positions managed by Jarvis treasury wallet with multi-sig security

Q: Can I export my data?
A: Yes, /admin_export_report generates CSV for all trades
"""

    @staticmethod
    def get_tips_and_tricks() -> str:
        """Get tips and tricks."""
        return """💡 <b>TIPS & TRICKS</b>

<b>Dashboard Mastery</b>

1️⃣ Pin the dashboard message for quick access
   • Tap the three dots menu → Pin message
   • Quick access from channel topic

2️⃣ Use refresh frequently for latest data
   • New alerts only show on refresh
   • Volume changes update instantly

3️⃣ Check "Duration" column to identify old positions
   • Positions held 1+ week = consider taking profit
   • Positions held < 1 hour = monitor closely

<b>Position Management</b>

1️⃣ Always set stop loss on entry
   • Recommended: 15-20% below entry for memecoins
   • Recommended: 8-10% below entry for bluechips

2️⃣ Scale into profits with partial closes
   • Close 50% at 50% profit
   • Let runners run for bigger gains

3️⃣ Watch the Risk/Return ratio
   • Aim for 1:2 risk/reward minimum
   • Better positions are 1:3 or higher

<b>Market Timing</b>

1️⃣ Check sentiment before entering
   • Grok score > 70 = strong buy signal
   • Grok score < 40 = avoid entry

2️⃣ Watch liquidation zones
   • Buy near support (liquidation floors)
   • Sell near resistance (liquidation ceilings)

3️⃣ Monitor whale activity
   • Net positive whale flow = bullish
   • Check before major entries

<b>Risk Management</b>

1️⃣ Never risk more than 1-2% on single trade
   • System enforces this, but be aware

2️⃣ Keep 30% in cash/stablecoin
   • Reserve for buying dips
   • Prevents over-leveraging

3️⃣ Check Sharpe ratio weekly
   • > 1.0 = good
   • < 0.5 = re-evaluate strategy

<b>Alerts Pro Tips</b>

1️⃣ Subscribe to profit alerts
   • Get notified when positions hit 10%+ gains
   • Discipline to take profits

2️⃣ Enable volatility alerts
   • Prep for market moves
   • Adjust positions before major moves

3️⃣ Watch liquidation alerts
   • Major liquidations = buy opportunity
   • Or cover shorts before dump

<b>Charting</b>

1️⃣ Request charts via /chart <symbol>
   • Includes MA, entry/exit points
   • Updates hourly

2️⃣ Analyze the allocation pie chart
   • Ideally 5-8% per position max
   • Over 20% = concentration risk

3️⃣ Track drawdown over time
   • Healthy systems have < 15% max drawdown
   • > 25% = systemic issue
"""

    @staticmethod
    def get_troubleshooting() -> str:
        """Get troubleshooting guide."""
        return """🔧 <b>TROUBLESHOOTING</b>

<b>Dashboard Issues</b>

❌ Dashboard not updating?
✅ Solution: Tap Refresh button, or wait 30 seconds for auto-update

❌ Positions showing old prices?
✅ Solution: Force close the message and request /treasury_dashboard again

❌ P&L seems wrong?
✅ Solution: P&L is real-time based on spot prices. Check Jupiter for current prices.

<b>Trading Issues</b>

❌ Trade rejected?
✅ Check: Sufficient balance? Position limit reached? Risk too high?

❌ Position won't close?
✅ Solution: Wait for pending transaction to complete, try again in 30s

❌ Stop loss not triggered?
✅ Solution: Position monitoring runs every 60s. Check stop loss level is correct.

<b>Alert Issues</b>

❌ Not receiving alerts?
✅ Check: Are you subscribed to alert type? /alerts_manage to verify

❌ Too many alerts?
✅ Solution: Some alerts have 60s cooldown to prevent spam

❌ Alerts delayed?
✅ Telegram delivery can be slow. Refresh dashboard to check status.

<b>Performance Issues</b>

❌ Bot is slow?
✅ Solution: Close old messages, start fresh with /treasury_dashboard

❌ Charts not loading?
✅ Solution: System is generating chart (takes 5-10s). Check size limits.

❌ Report generation slow?
✅ Solution: Large report takes time. For 1-year reports allow 30-60 seconds.

<b>Data Issues</b>

❌ Market data seems outdated?
✅ Solution: Data refreshes every minute. Wait 60s and refresh.

❌ Sentiment scores not matching?
✅ Solution: Different sources update at different times. Average gives best picture.

❌ Liquidation levels suspicious?
✅ Solution: From GlassNode API. May be delayed 1-5 minutes during high volume.

<b>Contact & Support</b>

Need help?
1. Check this help guide: /treasury_help
2. Review FAQ: /help_faq
3. Contact admin directly with screenshot of issue

Admin command for status:
/admin_system_status - See bot health and error logs
"""

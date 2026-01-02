# API Requirements Tracker
# Last Updated: 2026-01-01 20:09:00

## 🔑 PENDING API KEYS & INTEGRATIONS

### HIGH PRIORITY

#### 1. BirdEye API Key (Solana Scanner)
**Status:** ❌ NEEDED  
**Purpose:** Scan top 50 high-volume Solana tokens  
**Where to get:** https://birdeye.so/  
**How to add:**
```bash
# Add to secrets/keys.json
{
  "birdeye_api_key": "YOUR_KEY_HERE"
}

# Or set environment variable
export BIRDEYE_API_KEY="YOUR_KEY_HERE"
```
**Impact:** Without this, can't scan real Solana token data
**User reminder:** ASK AGAIN SOON

---

#### 2. HyperLiquid API Credentials
**Status:** ❌ NEEDED  
**Purpose:** Fetch 3 months of historical trading data (90 days)  
**Note:** HyperLiquid API has 30-day max interval, need 3 concurrent fetches  
**Where to get:** https://hyperliquid.xyz/  
**How to add:**
```bash
# Add to secrets/keys.json
{
  "hyperliquid_api_key": "YOUR_KEY_HERE",
  "hyperliquid_secret": "YOUR_SECRET_HERE"
}
```
**Impact:** Without this, can't backtest on real 3-month data
**User reminder:** ASK AGAIN SOON

---

#### 3. NotebookLM Integration
**Status:** 🔍 RESEARCH NEEDED  
**Purpose:** Enable Jarvis to perform autonomous research cycles  
**Requirements:**
- Check for MCP (Model Context Protocol) integration
- Check for official API
- Deep integration with source-of-truth filtering
- Ask user for confirmation when needed

**Next Steps:**
1. Research NotebookLM API/MCP availability
2. Design integration architecture
3. Implement source filtering system
4. Add to Jarvis research workflow

**User reminder:** ASK AGAIN SOON

---

### MEDIUM PRIORITY

#### 4. OpenAI API Key (Optional - Premium Voice)
**Status:** ⚠️ OPTIONAL  
**Purpose:** Premium TTS (currently using free macOS "say")  
**Cost:** ~$2/month for heavy voice use  
**Where to get:** https://platform.openai.com/api-keys  
**How to add:**
```bash
# Add to secrets/keys.json
{
  "openai_api_key": "sk-YOUR_KEY_HERE"
}
```
**Current Workaround:** Using free macOS voice + Minimax text enhancement
**User reminder:** Only if premium voice quality needed

---

### COMPLETED ✅

- ✅ Groq API Key (already configured)
- ✅ OpenRouter API Key (already configured)
- ✅ System architecture for all integrations

---

## 📋 REMINDER SCHEDULE

**Next Check-In:** Soon (user requested)
**What to Ask:**
1. "Do you have a BirdEye API key yet? Need it for Solana token scanning"
2. "Ready to set up HyperLiquid for 3-month backtests?"
3. "Should I start researching NotebookLM integration (MCP/API)?"

---

## 🎯 IMMEDIATE IMPACT

**WITH BirdEye Key:**
- ✅ Scan real top 50 Solana tokens
- ✅ Get actual volume/liquidity data
- ✅ Run real trading pipeline

**WITH HyperLiquid:**
- ✅ Pull 3 months of historical data
- ✅ Run comprehensive 90-day backtests
- ✅ Test all 50 strategies properly

**WITH NotebookLM:**
- ✅ Autonomous research capabilities
- ✅ Source-based knowledge generation
- ✅ Smart filtering with user confirmation

---

## 📝 NOTES

- User wants to be reminded "soon" about these requirements
- Focus on BirdEye first (quick win for Solana scanning)
- NotebookLM integration is a bigger project
- HyperLiquid needs careful implementation (3×30-day concurrent fetches)

**AUTO-REMINDER ENABLED** 🔔

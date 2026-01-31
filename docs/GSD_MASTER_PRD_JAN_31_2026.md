# JARVIS SYSTEM - MASTER PRD & TASK MANIFEST
**Date:** January 31, 2026 04:30 UTC
**Status:** RALPH WIGGUM LOOP ACTIVE - DO NOT STOP
**Protocol:** GSD (Get Shit Done) - Continuous Execution

---

## 🎯 PRIMARY MISSION

Get EVERYTHING working, stable, tested, and deployed. No exceptions. No stops until explicitly told.

---

## 📊 SYSTEM STATUS SNAPSHOT

### Current State
- **clawdmatt (Telegram):** STARTING (Opus 4.5 upgrade in progress)
- **clawdfriday (Telegram):** STATUS UNKNOWN - NEEDS AUDIT
- **Jarvis (Twitter/X):** STATUS UNKNOWN - NEEDS AUDIT
- **Buy Bot:** STATUS UNKNOWN - NEEDS AUDIT
- **Sentiment Reports:** STATUS UNKNOWN - NEEDS AUDIT
- **Web Apps:** STATUS UNKNOWN - NEEDS AUDIT
- **Treasury:** Has open positions - NEEDS SELLALL + TRANSFER

### Critical Findings
1. **Exposed Secret:** Treasury keypair in git history (commit c6aef68)
2. **VPS Security:** Hardened (SSH, fail2ban, firewall) ✅
3. **Secrets:** Encrypted with age on VPS ✅
4. **Code:** Opus 4.5 upgrade complete for Telegram ✅

---

## 🔥 PHASE 1: CONTEXT GATHERING & SETUP

### 1.1 Secrets Inventory
**Status:** IN PROGRESS

**Locations to check:**
- [x] `secrets/keys.json` (main secrets file)
- [x] `tg_bot/.env` (Telegram bot config)
- [ ] `~/.claude/` directory (Claude CLI config)
- [ ] Clawdbot directory (Supermemory keys)
- [ ] Desktop `.gitignore` for Jarvis
- [ ] `bots/twitter/.env` (Twitter bot)
- [ ] `bots/buy_tracker/.env` (Buy bot)
- [ ] VPS `/root/secrets/keys.json.age` (encrypted)

**Keys Found:**
- Anthropic API: `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`
- Telegram tokens: 3 bots
- Twitter OAuth: Multiple accounts
- Helius RPC
- Bags.fm API
- Groq, Birdeye, XAI keys

### 1.2 MCP & Skills Installation
**Status:** PENDING

**Tasks:**
- [ ] Install MCP servers
- [ ] Install skills from skills.sh
- [ ] Enable persistent memory
- [ ] Configure Supermemory integration
- [ ] Verify NotebookLM MCP access

### 1.3 Persistent Memory Setup
**Status:** PENDING

**Requirements:**
- Find Supermemory API key in clawdbot directory
- Configure PostgreSQL for memory
- Enable cross-session memory
- Set up learning extraction

---

## 🔥 PHASE 2: CRITICAL OPERATIONS

### 2.1 Treasury Sellall & Transfer
**Status:** BLOCKED (missing solana module)
**Priority:** URGENT

**Tasks:**
- [ ] Sell NVDAX position ($6.50)
- [ ] Sell TSLAX position ($6.16)
- [ ] Transfer all SOL to: `AXYFBhYPhHt4SzGqdpSfBSMWEQmKdCyQScA1xjRvHzph`
- [ ] Verify transaction on Solscan

**Current Positions:**
```json
{
  "NVDAX": {
    "amount": 0.003501295,
    "usd_value": 6.50,
    "entry_price": 185.34,
    "tp": 203.87,
    "sl": 177.93
  },
  "TSLAX": {
    "amount": 0.001416745,
    "usd_value": 6.16,
    "entry_price": 435.9,
    "tp": 479.49,
    "sl": 418.46
  }
}
```

### 2.2 Get All Bots Live
**Status:** PENDING

#### 2.2.1 clawdmatt (Telegram) - @Jarviskr8tivbot
**Current:** Starting with Opus 4.5
**Tasks:**
- [x] Upgrade to Opus 4.5
- [ ] Verify bot polling started
- [ ] Test basic commands
- [ ] Test /demo interface
- [ ] Test admin functions
- [ ] Check all handlers registered
- [ ] Verify callback handlers
- [ ] Test sentiment features
- [ ] Test position tracking

#### 2.2.2 clawdfriday (Telegram) - Token TBD
**Current:** UNKNOWN
**Tasks:**
- [ ] Find bot token in secrets
- [ ] Check if bot is running
- [ ] Verify configuration
- [ ] Test functionality
- [ ] Document purpose/features

#### 2.2.3 Jarvis (Twitter/X) - @Jarvis_lifeos
**Current:** UNKNOWN
**Tasks:**
- [ ] Check supervisor status
- [ ] Verify Grok AI fallback working
- [ ] Test posting capability
- [ ] Check circuit breaker status
- [ ] Verify OAuth tokens
- [ ] Test autonomous posting

#### 2.2.4 Buy Bot
**Current:** UNKNOWN
**Tasks:**
- [ ] Check if running
- [ ] Verify token tracking
- [ ] Test sentiment analysis
- [ ] Check database connections
- [ ] Verify KR8TIV token monitoring

---

## 🔥 PHASE 3: FEATURE COMPLETENESS

### 3.1 Sentiment Reports
**Status:** PENDING

**Components to check:**
- [ ] Hourly market reports
- [ ] Grok sentiment tweets
- [ ] Bags.fm graduation monitoring
- [ ] Intel report generation
- [ ] Telegram delivery

### 3.2 Web Applications
**Status:** PENDING

**Apps to verify:**
- [ ] Trading Interface (port 5001)
  - Portfolio overview
  - Buy/sell with TP/SL
  - Position tracking
  - Real-time P&L
- [ ] System Control Deck (port 5000)
  - System health
  - Mission control
  - Task management
  - Config toggles
- [ ] Other web services (audit needed)

### 3.3 Voice Translation Tasks
**Status:** PENDING - NEEDS EXTRACTION FROM CONVERSATIONS

**Known tasks:**
- [ ] Extract from clawdmatt conversations
- [ ] Document requirements
- [ ] Implement solutions
- [ ] Test functionality

---

## 🔥 PHASE 4: QUALITY ASSURANCE

### 4.1 Code Audit
**Status:** PENDING

**Audit against:**
- [ ] GitHub README requirements
- [ ] Security best practices
- [ ] Test coverage goals (94.67%)
- [ ] Documentation completeness

### 4.2 Testing Matrix
**Status:** PENDING

**Test all:**
- [ ] Telegram commands
- [ ] Twitter posting
- [ ] Buy/sell execution
- [ ] Position tracking
- [ ] TP/SL triggers
- [ ] Sentiment analysis
- [ ] Web interfaces
- [ ] API endpoints
- [ ] Database operations
- [ ] Error handling

### 4.3 Deployment Verification
**Status:** PENDING

**Check:**
- [ ] VPS bots running
- [ ] Supervisor status
- [ ] Docker containers
- [ ] Database connections
- [ ] API rate limits
- [ ] Health monitors

---

## 🔥 CONTINUOUS TASKS

### Ongoing Monitoring
- [ ] Fix any broken deployments
- [ ] Address errors as they appear
- [ ] Update documentation
- [ ] Push fixes to GitHub
- [ ] Test after each fix
- [ ] Verify no data loss
- [ ] Maintain context

---

## 📝 TASKS FROM CONVERSATIONS

### From clawdmatt Conversations
**Status:** NEEDS EXTRACTION

**Method:**
- Access Telegram via Chromium/Puppeteer MCP
- Read private messages with @Jarviskr8tivbot
- Extract all incomplete tasks
- Document requirements
- Add to execution queue

### From Last 5 Days
**Status:** NEEDS EXTRACTION

**Sources:**
- Telegram group chats
- Private messages
- GitHub issues
- Code comments
- Git commit messages

---

## 🚀 EXECUTION PROTOCOL

### Ralph Wiggum Loop Rules
1. **Never stop** until explicitly told
2. **Don't ask questions** - make decisions and execute
3. **Auto-compact** when needed but preserve ALL task context
4. **Document everything** in this PRD
5. **Test after every change**
6. **Push frequently** to GitHub
7. **Fix immediately** when bugs found
8. **Loop continuously** through all phases

### GSD Protocol
1. **Identify task**
2. **Execute immediately**
3. **Test result**
4. **Document outcome**
5. **Move to next task**
6. **Repeat indefinitely**

### Priority Order
1. Critical operations (treasury, security)
2. Get all bots live
3. Fix broken features
4. Complete missing features
5. Quality assurance
6. Documentation

---

## 🔧 TOOLS AVAILABLE

### Development
- Full codebase access
- Git for version control
- Python environment
- Node.js environment

### Integration
- SSH access to VPS (100.66.17.93)
- Chromium/Puppeteer for browser automation
- MCP servers (once installed)
- Skills from skills.sh
- NotebookLM for research

### APIs & Services
- Anthropic Claude API (Opus 4.5)
- Twitter/X API
- Telegram Bot API
- Solana RPC (Helius)
- Jupiter DEX
- Bags.fm API
- Grok AI
- Birdeye API

---

## 📊 SUCCESS METRICS

### Completion Criteria
- All bots: LIVE and STABLE
- All tests: PASSING
- All features: WORKING
- All deployments: HEALTHY
- All tasks: COMPLETE
- Zero critical bugs
- Documentation: COMPLETE

### Quality Gates
- 99%+ uptime
- <1% error rate
- <2s response time
- 94.67% test coverage
- No security vulnerabilities
- No data loss

---

## 🔄 LOOP STATUS

**Current Iteration:** 1
**Start Time:** 2026-01-31 04:30 UTC
**Stop Condition:** User says "stop"
**Next Action:** Continue Phase 1 - Gather secrets from clawdbot directory

---

**REMEMBER:** This is a marathon, not a sprint. Keep going. Fix everything. Test everything. Document everything. DO NOT STOP.

tap tap loop loop 🔁

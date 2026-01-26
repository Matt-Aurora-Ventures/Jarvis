# MCP Server Setup Guide for Jarvis (Solana + Telegram Trading Bot)

## 🎯 Purpose
This guide configures Model Context Protocol (MCP) servers to enhance AI-assisted development for Solana blockchain and Telegram bot integration, with focus on:
- **Sequential Thinking**: Enhanced reasoning for complex trading logic
- **Extended Memory**: Persistent context across sessions
- **Performance Optimization**: Faster development with specialized tools

---

## 📦 Installed MCP Servers

### 1. **Sequential Thinking Server** ⭐ (CRITICAL)
**Purpose**: Dynamic, reflective problem-solving through thought sequences  
**Benefits for Solana Development**:
- Complex DEX trading logic decomposition
- Multi-step transaction planning
- Risk analysis and edge case handling
- Architecture decision reasoning

**Package**: `@modelcontextprotocol/server-sequential-thinking`  
**Status**: ✅ Auto-installed via npx

### 2. **Memory Server** ⭐ (CRITICAL)
**Purpose**: Knowledge graph-based persistent memory system  
**Benefits**:
- Remembers project architecture decisions
- Retains Solana program ABIs and contract addresses
- Stores trading strategy patterns and configurations
- Maintains context across coding sessions

**Package**: `@modelcontextprotocol/server-memory`  
**Status**: ✅ Auto-installed via npx

### 3. **Filesystem Server** ✅
**Purpose**: Secure file operations within allowed directories  
**Scope**: `C:\Users\lucid\OneDrive\Desktop\Projects`  
**Status**: ✅ Active

### 4. **Context7 Server** ✅
**Purpose**: Up-to-date documentation for libraries/frameworks  
**Key Libraries Available**:
- Python (standard library)
- aiogram (Telegram bot framework)
- python-telegram-bot
- FastAPI/Flask (for webhook servers)
- Web3/blockchain libraries

**Status**: ✅ Active

### 5. **Brave Search Server** ⚠️ (NEEDS CONFIGURATION)
**Purpose**: Real-time web search for latest docs  
**Status**: ⚠️ Requires API key

**Setup**:
1. Get free API key: https://brave.com/search/api/
2. Update `.mcp.json`:
   ```json
   "BRAVE_API_KEY": "your_actual_key_here"
   ```

### 6. **GitHub Server** 🔧 (OPTIONAL - RECOMMENDED)
**Purpose**: Direct repository access for examples  
**Benefits**:
- Access Solana program examples
- Review Jupiter/Raydium SDK implementations
- Study trading bot patterns

**Setup**:
1. Generate token: https://github.com/settings/tokens
2. Permissions needed: `repo`, `read:org`
3. Update `.mcp.json`:
   ```json
   "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_token_here"
   ```

### 7. **PostgreSQL Server** 🔧 (IF USING POSTGRES)
**Purpose**: Database schema and query assistance  
**Setup**: Update connection string in `.mcp.json`

### 8. **SQLite Server** ✅
**Purpose**: Local database operations  
**Path**: `C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\database.db`  
**Status**: ✅ Configured for your existing DB

### 9. **NotebookLM Server** ✅
**Purpose**: Google NotebookLM integration for AI research and documentation  
**Benefits**:
- Query NotebookLM notebooks directly from AI
- Create and manage notebooks programmatically
- Add sources (URLs, text, Google Drive docs)
- Generate audio overviews and summaries
- Get citation-backed answers from your documentation

**Package**: `notebooklm-mcp@latest`  
**Status**: ✅ Active

**Key Features**:
- **Research Assistant**: Ask AI to search your NotebookLM knowledge base
- **Documentation Management**: Create notebooks from your Solana/Telegram docs
- **Audio Summaries**: Generate podcast-style overviews of technical docs
- **Citation-Backed**: All answers include source citations
- **Browser Automation**: Uses Playwright for seamless integration

**Authentication**: First time use will open browser for Google login, then maintains persistent session.


---

## 🚀 Quick Start

### Restart Your AI Environment
After updating `.mcp.json`, restart your AI coding assistant (Claude Desktop, Cursor, etc.) to load the new servers.

### Verify Installation
The AI should now have access to these capabilities:
- ✅ Sequential thinking for complex problems
- ✅ Memory persistence across sessions
- ✅ Library documentation (Context7)
- ✅ NotebookLM research and documentation
- ✅ File operations
- ✅ SQLite database access

---

## 📚 Recommended Additional MCP Servers for Solana/Telegram

### For Solana Development

1. **Helius MCP Server** (Solana-specific)
   ```json
   "helius": {
     "command": "npx",
     "args": ["-y", "@helius/mcp-server"],
     "env": {
       "HELIUS_API_KEY": "your_helius_key"
     },
     "type": "stdio"
   }
   ```
   - Provides Solana RPC documentation
   - Enhanced blockchain query tools
   - Get key: https://helius.dev/

2. **Web Scraper Server** (for DEX documentation)
   ```json
   "puppeteer": {
     "command": "npx",
     "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
     "type": "stdio"
   }
   ```
   - Scrape Jupiter, Raydium, Meteora docs
   - Extract trading pair data
   - Monitor DEX interfaces

### For Telegram Bots

3. **Fetch Server** (API testing)
   ```json
   "fetch": {
     "command": "npx",
     "args": ["-y", "@modelcontextprotocol/server-fetch"],
     "type": "stdio"
   }
   ```
   - Test Telegram Bot API endpoints
   - Verify BAGS.fm API responses
   - Debug webhook integrations

### For Trading Logic

4. **Python Execution Server**
   ```json
   "python": {
     "command": "npx",
     "args": ["-y", "mcp-server-python"],
     "type": "stdio"
   }
   ```
   - Execute Python backtests
   - Test trading algorithms
   - Validate calculations

---

## 🎯 Usage Examples

### Sequential Thinking for Trading Logic
```
"Design a Solana trading bot that monitors Jupiter for arbitrage opportunities 
between SOL/USDC pools on different DEXs, considering gas fees, slippage, and MEV."
```
The sequential thinking server will break this down into:
1. Architecture analysis
2. DEX connection patterns
3. Price feed integration
4. Transaction simulation
5. Profitability calculation
6. Risk mitigation strategies

### Memory for Project Context
```
"Remember that our Jarvis bot uses aiogram for Telegram, solana-py for RPC calls,
and connects to Helius for fast transaction sending. We prioritize Jupiter for swaps
and use program subscriptions for real-time token launches."
```
The memory server stores this context permanently, so you won't need to re-explain in future sessions.

### Context7 for Library Help
```
"Show me how to use aiogram's FSM (Finite State Machine) for multi-step 
user interactions in the /swap command"
```
Gets latest aiogram documentation and examples.

### NotebookLM for Research
```
"Search my NotebookLM notebooks for Solana transaction retry patterns"
"Create a NotebookLM notebook from the Jupiter V6 API documentation"
"Generate an audio overview of my trading strategy notebook"
```
Query your documentation knowledge base and get citation-backed answers.


---

## 🔧 Performance Optimization Tips

### 1. Use Sequential Thinking for Complex Tasks
- Multi-step trading strategies
- Smart contract interaction planning
- Error handling architecture

### 2. Leverage Memory Server
- Store frequently used Solana addresses (program IDs, token mints)
- Save tested transaction patterns
- Remember discovered edge cases

### 3. Context7 for Accurate Docs
- Always verify library usage with Context7
- Check for deprecated methods in solana-py
- Get latest Telegram Bot API features

### 4. GitHub Server for Examples
- Study proven trading bot implementations
- Review secure key management patterns
- Find optimized transaction builders

---

## 🐛 Troubleshooting

### MCP Server Not Loading
1. Restart AI environment completely
2. Verify Node.js/npm is installed: `node --version`
3. Check `.mcp.json` syntax (valid JSON)

### Brave Search 422 Error
- Invalid/expired API key
- Get new key from https://brave.com/search/api/

### Sequential Thinking Not Available
- Ensure `@modelcontextprotocol/server-sequential-thinking` is listed
- Verify npx can install packages: `npx --version`

### Memory Not Persisting
- Memory server creates local storage automatically
- Check disk permissions in project directory
- Verify server is running (no startup errors)

---

## 📖 Key Documentation References

### MCP Core
- Official Docs: https://modelcontextprotocol.io/
- Server List: https://github.com/modelcontextprotocol/servers
- Community Servers: https://github.com/wong2/awesome-mcp-servers

### Solana MCP
- Helius MCP: https://helius.dev/
- QuickNode Guide: https://www.quicknode.com/guides/other-chains/solana/how-to-build-a-solana-mcp-server

### Your Tech Stack Docs
- aiogram: https://aiogram.dev/
- solana-py: https://michaelhly.github.io/solana-py/
- Jupiter API: https://hub.jup.ag/docs/apis/swap-api
- Telegram Bot API: https://core.telegram.org/bots/api

---

## ✅ Next Steps

1. **Restart your AI environment** to load new MCP servers
2. **Test Sequential Thinking**: Ask for a complex trading strategy breakdown
3. **Test Memory**: Store your Solana program IDs and token addresses
4. **Optional**: Add Brave API key for enhanced search
5. **Optional**: Add GitHub token for direct repo access
6. **Consider**: Helius MCP for Solana-specific tools

---

## 💡 Pro Tips for Solana Development

### Use Memory Server for:
```
store:
- BAGS_PROGRAM_ID = "BAG..."
- JUPITER_V6_API = "https://quote-api.jup.ag/v6"
- HELIUS_RPC = "https://..."
- Common token mints (SOL, USDC, BONK)
```

### Use Sequential Thinking for:
- "Design error recovery for failed Solana transactions"
- "Plan upgrade path from solana-py 0.30 to 0.31"
- "Architect rate limiting for Telegram webhook handlers"

### Use Context7 for:
- "How to use aiogram.types.InlineKeyboardMarkup"
- "Show solana-py transaction simulation examples"
- "Latest Telegram Bot API updates"

---

**Last Updated**: 2026-01-25  
**Compatible With**: Claude Desktop, Cursor, Windsurf, Cline, any MCP-compatible AI coding assistant

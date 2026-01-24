# Phase 4: bags.fm API Investigation

**Date**: 2026-01-24
**Status**: ⏸️ BLOCKED - Awaiting API Documentation
**Next Action**: Contact bags.fm support or review SDK source code

---

## Investigation Summary

**Problem**: All bags.fm API endpoints returning 404 Not Found

**Sources Checked**:
1. [Bags API Documentation](https://docs.bags.fm/) - Authentication guide only, no endpoint details
2. [Bags.fm LLM Documentation](https://docs.bags.fm/llms.txt) - Endpoint descriptions but no REST paths
3. [bags-sdk GitHub](https://github.com/bagsfm/bags-sdk) - TypeScript SDK, source code not visible in README

**Findings**:
- ✅ Base URL confirmed: `https://public-api-v2.bags.fm/api/v1/`
- ✅ Authentication: `x-api-key` header (not query param)
- ✅ SDK exists: `@bagsfm/bags-sdk` (TypeScript/Node.js)
- ❌ Specific REST endpoint paths not documented publicly
- ❌ Python API client not available

---

## Available Endpoint Descriptions

From [bags.fm LLM docs](https://docs.bags.fm/llms.txt):

### Trading
- **Get Trade Quote** - "Retrieves swap quotes with output amount, price impact, slippage, and route details"
- **Create Swap Transaction** - "Create a swap transaction from a trade quote"

### Partner
- **Get Partner Stats** - "Retrieve partner statistics including claimed and unclaimed fees for a given partner"
- **Create Partner Config** - "Generates partner keys for fee sharing"

### Token
- **Get Token Launch Creators** - "Returns token deployer information"
- **Get Token Lifetime Fees** - "Calculates total accumulated fees for tokens"

---

## Current Implementation Issues

**File**: [core/trading/bags_client.py](../../core/trading/bags_client.py)

**Endpoints We're Trying** (all return 404):
```python
BASE_URL = "https://public-api-v2.bags.fm/api/v1"

# GET /quote?from={mint}&to={mint}&amount={amount}&slippage={bps}
# GET /token/{mint}
# GET /tokens/trending
# GET /partner/stats?partner_key={key}
```

**Possible Issues**:
1. REST paths may be different (e.g., `/trade/quote` instead of `/quote`)
2. Authentication may be failing silently (wrong header format)
3. API version may have changed (v1 → v2?)
4. Endpoints may require POST instead of GET

---

## Next Steps (Priority Order)

### Option 1: TypeScript SDK Review (RECOMMENDED)
**Action**: Clone bags-sdk and review source code for actual endpoint paths
```bash
git clone https://github.com/bagsfm/bags-sdk.git
cd bags-sdk
# Review src/services/ for actual API calls
```

**Effort**: 2-4 hours
**Success Probability**: HIGH (source code has the answers)

### Option 2: Contact bags.fm Support
**Action**: Open support ticket via bags.fm Discord or dev.bags.fm contact form

**Questions to Ask**:
1. What is the correct REST path for getting swap quotes?
2. Is there a Python SDK or official Python examples?
3. Has the API structure changed recently?
4. Are the endpoint paths documented somewhere?

**Effort**: 1-2 days (waiting for response)
**Success Probability**: MEDIUM (depends on support responsiveness)

### Option 3: Network Traffic Analysis
**Action**: Use bags.fm web app and capture API calls via browser DevTools

**Steps**:
1. Open https://bags.fm/swap in browser
2. Open DevTools → Network tab
3. Execute a swap
4. Capture actual API endpoint and request format
5. Replicate in Python

**Effort**: 1-2 hours
**Success Probability**: HIGH (reverse engineering)

### Option 4: Defer to V1.1
**Action**: Launch V1 with Jupiter-only, revisit bags.fm integration in V1.1

**Impact**:
- No partner fee collection until fixed
- Core trading functionality unaffected (Jupiter works)
- Reduces V1 timeline pressure

**Effort**: 0 hours (defer decision)
**Success Probability**: N/A (postponed)

---

## Recommendation

**Short-term (This Week)**:
1. Try Option 3 (Network Traffic Analysis) - fastest path to working implementation
2. Document actual API calls from browser
3. Update bags_client.py with correct endpoints

**Medium-term (Next Week)**:
1. Clone and review bags-sdk source code (Option 1)
2. Implement TypeScript proxy if Python API too complex
3. Add comprehensive tests

**Long-term (V1.1)**:
1. Request Python SDK from bags.fm team
2. Contribute Python client to bags.fm if interest

---

## V1 Launch Decision

**Question**: Can we launch V1 without bags.fm API working?

**Answer**: YES

**Justification**:
1. ✅ Jupiter DEX fallback is fully functional
2. ✅ All trading operations work via Jupiter
3. ✅ TP/SL functionality is independent of swap provider
4. ⚠️ Only impact: No partner fee collection until fixed
5. ✅ Can add bags.fm in V1.1 without breaking changes

**Recommendation**: Proceed with V1 launch using Jupiter, document bags.fm as "Coming Soon" feature

---

## Current Status: BLOCKED

**Blocker**: Cannot determine correct API endpoint paths from public documentation

**Unblock Options**:
- Network traffic analysis (2 hours)
- SDK source code review (4 hours)
- Support ticket (1-2 days)
- Defer to V1.1 (0 hours)

**Recommended Path**: Network traffic analysis → SDK review → V1 launch with Jupiter

---

**Sources**:
- [Bags API Documentation](https://docs.bags.fm/)
- [Bags API for LLMs](https://docs.bags.fm/llms.txt)
- [bags-sdk GitHub Repository](https://github.com/bagsfm/bags-sdk)
- [Bitquery bags.fm API Docs](https://docs.bitquery.io/docs/blockchain/Solana/bags-fm-api/)

**Document Version**: 1.0
**Author**: Claude Sonnet 4.5
**Next Action**: Network traffic analysis or SDK source review

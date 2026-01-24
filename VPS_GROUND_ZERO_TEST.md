# VPS Ground Zero Test Plan

**Date**: 2026-01-24
**Purpose**: Systematic testing of EVERY component from installation to working bot

---

## Test 1: VPS Basic Connectivity ✅
- [ ] SSH access works
- [ ] Internet connectivity from VPS
- [ ] Python installed and accessible

## Test 2: Ollama AI Installation ✅
- [ ] Ollama service running
- [ ] qwen3-coder model loaded
- [ ] Can generate completions
- [ ] Anthropic-compatible endpoint working

## Test 3: Bot Process Status
- [ ] Supervisor service running
- [ ] Telegram bot process alive
- [ ] Treasury bot process alive
- [ ] No duplicate processes

## Test 4: Environment Configuration
- [ ] Correct tokens set
- [ ] AI endpoints configured
- [ ] Wallet password correct
- [ ] Chat IDs configured

## Test 5: Telegram API Connectivity
- [ ] Bot can call getMe (verify identity)
- [ ] Bot can receive updates (no polling conflicts)
- [ ] Bot can send messages to admin
- [ ] Bot can send messages to group

## Test 6: Bot Handler Registration
- [ ] /start command registered
- [ ] /demo command registered
- [ ] Message handlers active
- [ ] Callback handlers active

## Test 7: AI Integration
- [ ] Bot can call Ollama API
- [ ] Bot receives AI responses
- [ ] Responses are coherent
- [ ] No timeout errors

## Test 8: Wallet Integration
- [ ] Correct wallet loaded (BFhTj4TGKC77C7s3HLnLbCiVd6dXQSqGvtD8sJY5egVR)
- [ ] Can query balance
- [ ] Balance matches on-chain
- [ ] Wallet operations work

## Test 9: End-to-End Bot Test
- [ ] User sends /start → Bot responds
- [ ] User sends /demo → Bot shows UI
- [ ] User clicks button → Bot handles callback
- [ ] Bot can execute AI-powered features

---

## Execution Plan

We'll run these tests IN ORDER, documenting results after each one.

When a test FAILS, we STOP and FIX before proceeding.

Each test will produce VISIBLE CONFIRMATION (message sent, output shown, etc.)

NO ASSUMPTIONS - Everything must be verified with evidence.

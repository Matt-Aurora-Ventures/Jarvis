# Claude Opus 4.5 Ingest Prompt Guide

## Purpose
This guide shows how to prompt Claude Opus 4.5 to ingest and understand large documents
(PRDs, technical specs, codebases) for implementation work.

---

## Core Principles

1) Context first, tasks second
Always establish the full context before asking for action. Claude needs a clear mental model.

2) Explicit structure recognition
Tell Claude what kind of document it is and what to extract.

3) Multi-pass processing
For large documents (>1000 lines), use multiple prompts: understand -> validate -> plan -> execute.

4) Goal-oriented framing
State the end goal upfront so Claude can prioritize information accordingly.

---

## The Ingest Prompt Formula

[CONTEXT] + [DOCUMENT TYPE] + [WHAT TO EXTRACT] + [EXPECTED OUTPUT] + [CONSTRAINTS]

---

## Example 1: PRD Ingest for Implementation

Bad prompt:
```
Here's the PRD. Build this.
```
Why it fails: No structure, unclear expectations, no validation step.

Good prompt:
```
I'm providing a Product Requirements Document (PRD) for a Telegram trading bot enhancement.

Your task in this first pass:
1. Read and understand the full PRD structure
2. Identify all user stories (US-XXX format)
3. Extract technical dependencies (APIs, services, files mentioned)
4. Note any ambiguities or missing information
5. Create a high-level implementation roadmap

Document characteristics:
- Format: Markdown with numbered user stories
- Length: ~1800 lines
- Sections: Problem Statement, Goals, User Stories, Technical Details
- Priority markers: P0 (blocker), P1 (critical), P2 (nice-to-have)

What I need back:
- Summary of the core product vision (2-3 sentences)
- List of all user stories with priorities
- Technical architecture overview (what systems/APIs are involved)
- Critical path: which user stories MUST be done first
- Questions or gaps you identified

Constraints:
- Don't start writing code yet
- Focus on understanding, not implementation
- Flag contradictions or unclear requirements

---

[PASTE PRD HERE]

---

After you've analyzed this, I'll ask you to plan the implementation in priority order.
```

---

## Example 2: Codebase Ingest for Refactoring

```
I need you to understand a Python trading bot codebase before we refactor it.

Context:
- Project: Jarvis trading bot (Solana/Telegram integration)
- Language: Python 3.11, async/await heavy
- Structure: ~50 files across bots/, core/, tg_bot/ directories
- Problem: Code duplication between treasury bot and demo bot

Your task (Phase 1 - Understanding):
1. Identify all files that handle trading execution
2. Map out the data flow: user action -> API call -> position storage
3. Find duplicated logic between treasury and demo implementations
4. Note dependencies: which files import which modules
5. Identify integration points: APIs, databases, external services

What I'll provide:
- File tree structure (via tldr or ls -R)
- Key files you should read in full
- Specific functions/classes to focus on

What I need back:
- Architecture diagram (text-based, using boxes/arrows)
- List of duplicated code with file locations
- Refactoring candidates (what could be shared/merged)
- Risk assessment (what breaks if we refactor X)

Constraints:
- Don't propose solutions yet, just map the landscape
- Use file:line references for all claims (example: trading.py:142)
- If you're uncertain, mark with ? INFERRED

---

Let me know when you're ready, and I'll provide the file tree.
```

---

## Example 3: Multi-Step Ingest for Large PRDs

Phase 1: High-level understanding
```
I'm sharing a 1800-line PRD for a trading bot. This is PHASE 1: High-Level Understanding.

Read for:
- Overall product vision and goals
- Major features/capabilities being added
- Success metrics
- Any showstopper technical constraints

Output:
- 3-sentence product vision summary
- Top 5 features ranked by impact
- Key technical challenges you foresee
- Whether this PRD is ready for implementation (yes/no + why)

[PASTE PRD]
```

Phase 2: Deep dive - user stories
```
Now that you understand the vision, let's extract actionable user stories.

From the same PRD:
- List all user stories (US-XXX format)
- For each: title, priority (P0/P1/P2), acceptance criteria count, files modified
- Create a dependency graph (which US blocks which)
- Identify the critical path (minimum set to launch)

Output format:
US-001: [Title] - P0
  - Blocks: US-004, US-007
  - Acceptance Criteria: 12
  - Files: tg_bot/bot.py, tg_bot/handlers/demo.py
  - Estimated Complexity: Medium (existing handler, just needs registration)

...
```

Phase 3: Technical planning
```
Final pass: Create an implementation plan.

Using the user stories from Phase 2:
- Group into logical work packages (example: Buy Flow, Sentiment Hub, Order Management)
- Sequence the packages (what order to build in)
- For each package: list user stories, files touched, external dependencies (APIs)
- Estimate risk level (Low/Medium/High) based on unknowns

Output:
1. Work Package 1: [Name]
   - User Stories: US-001, US-002, US-003
   - Files: [list]
   - APIs/Services: bags.fm API, Grok AI
   - Risk: Medium (bags.fm API not tested yet)

2. Work Package 2: ...

Critical Path Validation:
Which packages MUST be done before others? Show dependency arrows.
```

---

## Best Practices for Ingest Prompts

1) Use structure markers
```
Context: ...
Task: ...
Output: ...
Constraints: ...
```

2) Provide document metadata
```
Document Type: Product Requirements Document (PRD)
Format: Markdown, user stories in US-XXX format
Length: ~1800 lines (~85KB)
Author/Date: Internal, 2026-01-24
Audience: Engineering team
Status: Draft v2 (expect changes)
```

3) Set explicit boundaries
```
Do NOT:
- Write code yet
- Make assumptions about missing info
- Propose solutions before understanding the problem

Do:
- Ask clarifying questions
- Flag ambiguities
- Validate your understanding before proceeding
```

4) Request validation checkpoints
```
Before proceeding to implementation:
1. Summarize your understanding of the goal
2. List assumptions you're making
3. Ask me to confirm: Is this correct?
Only after I say yes, move to planning.
```

5) Use the claim verification pattern
```
When making claims about the codebase, use:
- VERIFIED (you read the file and confirmed)
- INFERRED (based on grep/search, needs verification)
- UNCERTAIN (haven't checked, just guessing)

Example:
- The buy handler is registered in tg_bot/bot.py:181 (VERIFIED)
- There's probably a wallet initialization function (INFERRED)
- Jupiter API might be faster than bags.fm (UNCERTAIN)
```

6) Provide success criteria
```
How I'll judge success:
- You identified all 15 user stories (not missing any)
- Dependency graph is accurate (I can follow it visually)
- File locations are precise (file:line format)
- You flagged the 3 ambiguities I know exist
- No hallucinated features (only what's in the PRD)
```

---

## Common Pitfalls

Pitfall 1: Just read this PRD and implement it
Problem: Too vague. Claude will either ask to break it down or start too early.
Fix: Use the phased approach (understand -> validate -> plan -> execute).

Pitfall 2: Pasting 2000 lines with no framing
Problem: Claude doesn't know what to prioritize.
Fix: Say: Here is a 2000-line PRD. First read it for context. Then I will ask questions.

Pitfall 3: Asking for code before understanding
Problem: Code is based on partial context.
Fix: Phase 1 (understanding), Phase 2 (planning), Phase 3 (execution).

Pitfall 4: No validation loop
Problem: Wrong assumptions persist.
Fix: Ask for a summary and confirm before moving on.

---

## Template: Full Ingest Workflow

I'm providing a [DOCUMENT TYPE] for [PROJECT/FEATURE NAME].

Context:
- Project: [Name and brief description]
- Domain: [example: Solana trading bot]
- Current State: [what exists today]
- Goal: [what we're building/fixing]

Document Details:
- Format: [Markdown, PDF, code files, etc.]
- Length: [~X lines or pages]
- Structure: [Sections, user stories, API specs, etc.]
- Priority Markers: [P0/P1/P2, or other system]

Your Task (Multi-Phase):

Phase 1: Understanding (this message)
1. Read the full document
2. Identify: [key sections, user stories, technical dependencies]
3. Extract: [specific things you need]
4. Output: [summary, lists, questions]

Phase 2: Validation (next message)
- I'll review your understanding
- You'll clarify any ambiguities
- We'll confirm the critical path

Phase 3: Planning (after validation)
- Create implementation plan
- Sequence work packages
- Identify risks

Phase 4: Execution (after plan approval)
- Write code
- Run tests
- Iterate on feedback

Output Format for Phase 1:
[Be specific about what you want back - bullets, tables, summaries, etc.]

Constraints:
- Don't jump ahead to later phases
- Flag ambiguities, don't assume
- Use VERIFIED / INFERRED / UNCERTAIN for claims
- Ask clarifying questions before making decisions

Success Criteria:
[How will you know Claude understood correctly?]

---

[PASTE DOCUMENT HERE]

---

Let me know when you're ready to proceed to Phase 2.

---

## Special Case: Brownfield Codebase Ingest

Step 1: Provide the map
```
Before reading code, here's the lay of the land:

Project Structure:
- bots/ - Bot implementations (treasury, sentiment, demo)
- core/ - Shared utilities (trading, API clients)
- tg_bot/ - Telegram bot handlers and UI
- scripts/ - One-off automation scripts

Key Files (READ THESE FIRST):
- bots/supervisor.py - Main orchestrator
- bots/treasury/trading.py - Real money trading engine
- tg_bot/handlers/demo.py - Demo bot handlers
- core/bags_api.py - bags.fm API client (doesn't exist yet, needs creation)

Your Task:
1. Read the 4 key files above (I'll provide them)
2. Understand: What does the demo bot currently do?
3. Identify: What's broken? (hints: message handler not registered, wallet not initialized)
4. Map dependencies: What does demo.py import? What does it call?

After this, I'll share the PRD for what we're building.
```

Step 2: Provide files sequentially
```
Here's bots/supervisor.py (the orchestrator):

[PASTE FILE]

Questions before I share the next file?
```

---

## Advanced: Using TLDR CLI for Ingest

If the tldr CLI is installed, use structured analysis:

1. `tldr tree bots/ --ext .py` - See all bot files
2. `tldr structure tg_bot/handlers/ --lang python` - Get code structure
3. `tldr calls bots/` - Show cross-file dependencies
4. `tldr imports tg_bot/handlers/demo.py` - What does demo.py import?

---

## Summary

The key to effective ingest:
1. Context first (what, why, current state)
2. Phased approach (understand -> validate -> plan -> execute)
3. Explicit output format (don't make the model guess)
4. Validation checkpoints (summarize back before proceeding)
5. Claim verification (VERIFIED / INFERRED / UNCERTAIN)

Remember:
- Large documents (>1000 lines) need multiple passes
- Structure your prompt like you're onboarding a new engineer
- Validate understanding before action
- Use the existing .claude/rules patterns if available

---

## Next Steps

1. Copy the template above
2. Fill in your specific context
3. Paste your PRD/document
4. Let Claude do Phase 1 (understanding)
5. Review and validate
6. Move to Phase 2 (planning)
7. Only then: Phase 3 (execution)

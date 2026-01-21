# AI-Researcher Integration (HKUDS)

## Overview
Jarvis integrates **AI-Researcher** (HKUDS) as a research-job subsystem to continuously produce:
- Finance/Crypto research digests (daily)
- AI/ML upgrade scouting (daily) + deep dives (weekly)
- Structured artifacts: reports, claim sets, evaluation plans, and change proposals

Jarvis does **not** auto-merge or auto-deploy changes based on research output. Research produces proposals that are gated by tests and human approval.

## Upstream Project
- Upstream: https://github.com/HKUDS/AI-Researcher
- Paper: https://arxiv.org/abs/2505.18705
- License: MIT

We preserve upstream licensing and attribution in:
- `/vendor/ai-researcher/` (includes upstream LICENSE)
- `THIRD_PARTY_NOTICES.md`
- README “Third-Party Credits”

## Repository Layout
- `/vendor/ai-researcher/` — vendored upstream project (git subtree)
- `/services/researcher/` — Jarvis wrapper service
- `/core/artifacts/` — artifact registry (FS implementation initially)
- `/schemas/` — schemas for artifacts (report, claim set, proposal, eval plan)
- `/jobs/` — scheduled job runners (cron or queue)
- `/docs/CHANGE_PROPOSAL_TEMPLATE.md` — required format for system changes

## Artifact Types
Each job run must produce these artifacts under:
`/artifacts/<job_type>/<timestamp>/`

### 1) ResearchReport
Human-readable markdown:
- sources reviewed
- summaries
- key takeaways
- “what would change my mind”
- next research questions

### 2) ClaimSet (JSON)
Machine-readable claims:
- claim_id
- claim_text
- evidence (URL/DOI/arXiv)
- confidence (0–1)
- applicability (0–1)
- assumptions

### 3) ChangeProposal (JSON) [optional]
Only created if the research supports a concrete change:
- title
- motivation
- proposed change
- risk analysis
- rollback plan
- evaluation plan reference
- status = PROPOSED

### 4) EvaluationPlan (JSON) [required if ChangeProposal exists]
- datasets
- baselines
- metrics
- acceptance thresholds
- reproducibility instructions

## Execution Model
We run AI-Researcher as a contained job and normalize outputs.

### Option A: Docker (preferred)
Pros: reproducible, consistent CI.
- Build image once
- Run jobs with a mounted output folder

### Option B: Python venv
Pros: simplest locally
Cons: dependency drift in CI

We prefer Docker for production CI consistency.

## How to run (Docker-first)
1) Configure environment variables:
   - `AI_RESEARCHER_IMAGE` (upstream Docker image)
   - `AI_RESEARCHER_OUTPUT_DIR` (host output directory)
   - `AI_RESEARCHER_PROVIDER`, `AI_RESEARCHER_MODEL`, `AI_RESEARCHER_API_KEY` as required by upstream
2) Install dependencies:
   - `cd services/researcher && npm install`
3) Run a job:
   - `npm run research:finance`

## Scheduling
We run three schedules:
1) Daily Finance Scan (crypto/finance)
2) Daily AI/ML Scan (auto-upgrade scout)
3) Weekly Deep Dive (AI/ML)

Scheduling is implemented as:
- `jobs/run-finance-research.ts`
- `jobs/run-aiml-scan.ts`
- `jobs/run-weekly-deepdive.ts`
- `jobs/run-research-iteration.ts`

If you already have a scheduler/queue, wire these entrypoints into it.

## Iteration Loop

Use `jobs/run-research-iteration.ts` to run **finance + AI/ML scans in sequence** for multiple passes.
Control the number of iterations with `JARVIS_RESEARCH_ITERATIONS` (default: 2).

## Safety / Gating Rules
Research output is never directly applied to production.
- Any ChangeProposal remains `PROPOSED`
- To enact a change, create a PR using `/docs/CHANGE_PROPOSAL_TEMPLATE.md`
- PR must include: citations, evaluation plan, tests, rollback, feature flag (if applicable)

## Updating the Vendored Dependency (git subtree)
To add initially:
- See “Subtree Commands” in the root README or below.

To pull upstream updates later:
1) Add upstream as a remote if needed
2) Run subtree pull:
`git subtree pull --prefix vendor/ai-researcher upstream main --squash`

(Replace `main` with the upstream default branch.)

## Troubleshooting
- If outputs are missing citations, mark artifacts as INCOMPLETE and rerun with a narrower mission prompt.
- If upstream changes break our wrapper, pin a commit and file an internal issue before pulling further.

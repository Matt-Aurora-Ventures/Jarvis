# Multi-Agent Reliability + GSD-Orchestrated Mission Control Design

Date: 2026-02-24
Status: Approved
Owner: lucid

## 1. Objectives

Primary objective is to make the OpenClaw-based team production-grade for both personal and business use:

- Keep the four Telegram agent containers continuously available on VPS.
- Guarantee automated recovery within 2 minutes when an agent degrades or fails.
- Make task assignment deterministic, health-aware, and capability-aware.
- Enforce GSD spec-driven execution on every Mission Control task.
- Enforce Mission Control as the sole task ingress and orchestration control plane.
- Support hot skill ingestion so newly dropped skills become executable without manual drift.
- Keep always-on task listeners for Telegram and WhatsApp group channels.
- Support dual operation modes: team deployment and individual agent deployment.
- Make deployment GitHub-first with a single canonical infra pipeline.
- Keep repository truth synchronized across operational repos.

## 2. Scope and Canonical Repositories

### 2.1 In-scope runtime services

- openclaw-arsenal
- openclaw-edith
- openclaw-jocasta
- openclaw-ydy8-openclaw-1
- kr8tiv-mission-control stack (frontend/backend/db/redis/webhook-worker)

### 2.2 Canonical source responsibilities

- team-setup-and-organization:
  - Canonical Docker service definitions/templates.
  - Runtime topology and container composition contracts.
- kr8tiv-team-execution-resilience:
  - Canonical deployment and self-healing automation.
  - GitHub Actions workflow, health gate, rollback/recovery routines.
  - Orchestrator routing policy and capability matrix versions.
- kr8tivclaw, kr8tiv-mission-control:
  - Application logic only.
  - No unsourced manual production infra drift.

## 3. Reliability Architecture

### 3.1 Deployment model

- GitHub-driven deployment pipeline is canonical.
- Merge to protected branch in kr8tiv-team-execution-resilience triggers deployment workflow.
- Workflow applies production compose/config artifacts on VPS and performs controlled restart/update.
- Post-deploy health gate is mandatory before marking deployment successful.

### 3.2 Self-healing layers

Layer A (Container-level):
- Docker restart policy set to unless-stopped on all agent and mission-control critical services.
- Healthchecks defined per service.

Layer B (Watchdog-level):
- VPS watchdog runs every 30 seconds.
- For unhealthy/down services:
  - Immediate targeted restart.
  - Health recheck.
  - Escalate to project-level restart if required.

Layer C (Assignment-level):
- Degraded/down agents are removed from normal routing pools.
- Tasks are rerouted to healthy capable agents.

Target RTO:
- <= 2 minutes from failure detection to assignable healthy state.

### 3.3 No-drift operational policy

- Hostinger UI manual edits are emergency-only.
- Any emergency change must be backported to kr8tiv-team-execution-resilience the same day.
- Pipeline validation rejects deployments that diverge from canonical config schema.

## 4. Health, Failover, and Assignment Model

### 4.1 Health levels

- L0: Container health (running + healthcheck pass).
- L1: Agent process health (Telegram polling/webhook loop live).
- L2: Functional health (can claim and execute a synthetic test task).

### 4.2 Failure handling policy

- L0 failure:
  - Restart container immediately.
- L1 failure with L0 healthy:
  - Restart internal process, then container if unresolved.
- L2 failure:
  - Mark agent degraded.
  - Route non-critical tasks elsewhere.
  - Keep incident open until synthetic task passes.

### 4.3 Assignment policy

Assignment decision factors:
- task type capability
- current health level and score
- active load
- risk tier compatibility
- latency/cost budget

Queue protections:
- Unclaimed timeout triggers requeue+routing retry.
- Max retry limit routes to dead-letter queue with evidence.
- Deterministic fallback ensures no black-hole queue.

## 5. Multi-LLM Team Orchestration

### 5.1 Hierarchical control

- Global Orchestrator (single decision authority):
  - Dispatch, conflict resolution, policy enforcement.
  - Final approval for high-impact tasks.
- Specialist agents (arsenal/edith/jocasta/ydy8):
  - Execute within declared capability and risk bounds.
- Standby Orchestrator:
  - Takes over when primary orchestrator degrades.

### 5.2 Engine/capability abstraction

Each agent profile includes:
- engine_profile (provider/model/version)
- capabilities (supported task types)
- risk_tier (allowed autonomous action class)

Routing policy:
- High-impact/ambiguous tasks route to highest-caliber reasoning profile.
- Low-risk repetitive tasks route to lower-cost specialists.
- Optional second-opinion vote can be required for designated actions.

### 5.3 Deployment validation rules

Before deploy success:
- Every active task type has at least one healthy capable agent.
- Orchestrator and standby orchestrator are both reachable.
- Capability matrix has no orphan mappings.

## 6. GSD Protocol Embedded in Mission Control (Fork)

### 6.1 Mandatory per-task state machine

Task lifecycle:
- intake -> context -> spec -> plan -> execute -> verify -> done

Hard gates:
- execute is blocked unless spec and plan artifacts exist.
- High-risk tasks require orchestrator approval before execute.
- verify failure automatically returns task to plan with evidence.

Mode policy:
- team_mode:
  - Orchestrator approval gates apply for high-risk tasks.
- individual_mode:
  - No orchestrator dependency.
  - High-risk tasks require explicit owner approval before execute.

### 6.2 Mission Control schema additions

Required task fields:
- gsd_stage
- spec_doc_ref
- plan_doc_ref
- verification_ref
- approval_required
- risk_tier

### 6.3 UI/board behavior

Required views:
- By GSD Stage
- Blocked by Missing Spec/Plan
- Verification Failed

Dispatch behavior:
- Only execute-stage tasks are eligible for agent dispatch.
- Agents may draft spec/plan; policy engine controls stage transitions.

### 6.4 Skill hot-ingestion and execution

Mission Control must treat skills as dynamic runtime capabilities:
- New skills dropped into the approved skill registry are detected by watcher.
- Skill metadata is validated (schema, risk tier, allowed channels).
- Capability matrix is refreshed without manual service drift.
- Orchestrator can assign tasks to agents only after skill validation completes.

Safety rules:
- Unvalidated skills are quarantined and non-routable.
- High-risk skills require explicit orchestrator approval policy.
- Skill version and checksum are recorded for auditability.

### 6.5 Always-on channel listeners (group mode)

Mission Control owns channel ingress for team collaboration channels:
- Telegram group listener always-on (day-1 mandatory).
- WhatsApp group listener phase-2 after Telegram hardening.
- Message normalization to a shared task/event schema.
- De-duplication and idempotency to avoid duplicate task creation.
- Channel ack/receipt logged to support troubleshooting and SLA reporting.

Routing behavior:
- New inbound group task messages are converted to Mission Control tasks.
- Tasks immediately enter GSD lifecycle and are routed by orchestrator policy.
- Agent replies are posted back to the originating group channel with task context.

### 6.6 Individual agent operating model

Individual agents run the same framework without orchestration dependency:
- Same Mission Control task board and GSD lifecycle.
- Same skill ingestion, validation, and capability registry.
- NotebookLM available as optional enhanced-research path per task.
- Owner onboarding flow includes NotebookLM account linking prompt.
- NotebookLM usage is optional per task and policy-driven, not mandatory.

Approval policy in individual_mode:
- High-risk actions require owner_approval_required = true.
- Lower-risk actions may auto-execute per policy tier.

## 7. CI/CD and Secrets Baseline

Current local assessment:
- team-setup-and-organization (local copy): no .github/workflows currently present.
- kr8tiv-team-execution-resilience (local copy): no deploy workflow currently present.

Design implication:
- Build GitHub Actions deploy workflow from clean baseline in kr8tiv-team-execution-resilience.
- Add required repository secrets for SSH-based VPS deployment.
- Remove any dependence on local machine-only deployment state.

## 8. Observability and Incident Handling

Minimum telemetry:
- Agent status: healthy/degraded/down with last successful task timestamp.
- Queue stats: unclaimed age, retries, dead-letter count.
- Recovery stats: MTTR, restart counts, repeated failures.
- Deployment stats: success/failure reason and rollback events.

Incident policy:
- Every auto-remediation action is logged with timestamp and root cause classification.
- Repeat failures trigger escalation and temporary assignment suppression.

## 9. Testing and Verification Strategy

### 9.1 Reliability tests

- Kill one agent container -> verify recovery <= 2 min.
- Inject healthcheck failure -> verify reroute and recovery path.
- Simulate orchestrator failure -> verify standby takeover.

### 9.2 Assignment tests

- Mixed workload with capability constraints.
- Degraded agent exclusion and deterministic fallback.
- Dead-letter path after retry exhaustion.

### 9.3 GSD workflow tests

- Stage transition guards enforce spec/plan/verify gating.
- execute blocked without prerequisites.
- verify fail bounce-back to plan validated.

### 9.4 Deployment tests

- Pipeline deploy from GitHub to VPS.
- Health gate fail triggers rollback/fail-safe behavior.
- Drift detection validates canonical config integrity.

## 10. Risks and Mitigations

Risk: Config drift from Hostinger manual edits.
Mitigation: no-drift policy + mandatory backport + pipeline checks.

Risk: Heterogeneous LLM behavior inconsistency.
Mitigation: capability/risk matrix + orchestrator authority + policy validation.

Risk: Queue starvation when multiple agents degrade.
Mitigation: reroute logic + dead-letter queue + escalating recovery actions.

Risk: Incomplete secret/config setup for GitHub-first deploy.
Mitigation: explicit baseline bootstrap checklist in implementation plan.

## 11. Acceptance Criteria

- All four OpenClaw agent containers remain continuously managed with auto-recovery.
- Any single agent failure recovers to healthy assignable state within <= 2 minutes.
- Task assignment follows health/capability/risk policy and avoids black-hole queues.
- Mission Control enforces GSD stage gates on every task type.
- Mission Control is the canonical ingress/orchestration layer for all team tasks.
- New skills can be ingested and routed safely without manual container drift.
- Telegram and WhatsApp group listeners remain active and can create/route tasks continuously.
  - Delivery policy: Telegram day-1, WhatsApp after Telegram stability gate passes.
- Individual agents can run end-to-end GSD lifecycle without orchestrator dependency.
- In individual mode, high-risk actions are blocked until explicit owner approval.
- Deployment is GitHub-driven from kr8tiv-team-execution-resilience.
- Production configuration remains synchronized and auditable across repos.

## 12. Approved Decisions Summary

- First remediation milestone: Agent reliability first.
- Runtime model: Docker-based containers per agent.
- Canonical deployment mode: GitHub-driven.
- Canonical pipeline owner repo: kr8tiv-team-execution-resilience.
- Recovery target: <= 2 minutes.
- Team architecture: global orchestrator + standby + heterogeneous specialist agents.
- Task governance: GSD protocol integrated directly into Mission Control task lifecycle.
- Channel operations: always-on Telegram and WhatsApp group task listeners.
  - Rollout: WhatsApp enabled in phase-2 after Telegram hardening and stability verification.
- Skill operations: validated hot skill ingestion with policy-gated execution.
- Individual mode: no orchestrator gate, but same framework with owner approval on high-risk actions.

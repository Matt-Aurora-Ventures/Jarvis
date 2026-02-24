# Phase 04: CI/CD & Production Push Automation - Research

## 1. Context & Objectives
The final Phase 4 of the Jarvis development roadmap dictates the need for "CI/CD & Production Push Automation". Specifically, we must implement strict push-to-live pipelines that trigger deployments seamlessly when algorithmic models and sniper scripts hit validated targets.

The objective references two targets:
1. `kr8tiv.web.app`: This relates to the Next.js frontend deployed via Firebase Hosting.
2. `jarvislife.cloud`: This appears to be tied to the `deploy.yml` pipeline managing a `docker-compose` staging/production environment via Docker Hub and remote SSH scripting.

## 2. Existing Infrastructure Analysis
By investigating `.github/workflows`, we have identified three critical pipeline files:
1. `jarvis-sniper-firebase-deploy.yml`: Pushes `jarvis-sniper` directly to Firebase on `kr8tiv.web.app`. Currently it triggers on `push` to `main`, but Phase 4 implies tying this to backtesting outcomes or stricter quality gates.
2. `deploy.yml`: A dual staging/production pipeline pushing Docker containers. Currently, production deployments are blocked exclusively via manual dispatch or explicit GitHub `release` tags. The deployment commands utilize Docker Buildx and trigger a remote script `cd /opt/jarvis && docker compose up -d`.
3. `sniper-algo-loop.yml`: This loop continuously re-tunes strategies on a 17th-minute cron. It creates automated PR branches containing updated strategies (e.g. `automation/algo-loop/{run_id}`).

## 3. Required Implementation for Phase 4
### A. Tying Deployment to Algo Status
We need a bridging github actions workflow that recognizes when an `algo-tuning` branch is merged into `main`. The strategy needs to be:
- The bot tunes standard settings in `sniper-algo-loop.yml` and raises an `algo-tuning` PR.
- Assuming tests pass and humans (or higher-tier agents) merge the PR safely to `main`.
- We trigger `deploy.yml` automatically to production to release the algorithms into PyTorch nodes and UI.

### B. CI Gates & Matrix Testing
To fulfill "strict push-to-live pipelines seamlessly", Pytest and Next.js testing phases must strictly run inside a gating workflow. Let's create `ci.yml` enhancements guaranteeing the Python Backtesting (Phase 1) and Open Claw integrations (Phase 2 & 3) do not degrade the execution logic upon push.

## 4. Execution Plan Strategy
- `04-01-PLAN.md`: Revise the Firebase and Docker deployment workflows to safely auto-trigger the release based strictly on passing tests and PyTorch artifacts merging into `main`.
- `04-02-PLAN.md`: Implement a comprehensive `ci.yml` or Python testing step that prevents bad python codes from proceeding down the `jarvislife.cloud` pipeline.

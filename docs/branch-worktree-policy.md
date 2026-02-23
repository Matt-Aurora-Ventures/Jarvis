# Branch and Worktree Policy

## Goal
Prevent dual-agent drift and parallel surface divergence.

## Policy
1. Use one protected integration branch for release-bound work.
2. Use short-lived feature branches for isolated changes.
3. Use git worktrees for independent tasks that do not share mutable state.
4. Rebase or merge integration branch daily for long-running branches.
5. Do not ship directly from prototype branches.
6. Do not modify canonical and prototype surfaces in the same PR unless required.

## Required Checks Before Merge
1. P0 gate workflows pass.
2. Canonical surface guard passes (or explicit override label is present).
3. Tests for changed runtime paths pass in CI and locally.

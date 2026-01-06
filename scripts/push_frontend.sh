#!/usr/bin/env bash
# Helper script to create a branch, commit frontend changes, and push to origin.
# Run this locally from the repository root: `bash ./scripts/push_frontend.sh`

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

BRANCH=${1:-frontend/premium-refactor}
COMMIT_MSG=${2:-"chore(frontend): wire refactor + roadmap + styles"}

if ! command -v git >/dev/null 2>&1; then
  echo "git not found. Install git and run this script again." >&2
  exit 1
fi

echo "Repository: $REPO_ROOT"
echo "Creating branch: $BRANCH"

git fetch origin

if git show-ref --verify --quiet refs/heads/$BRANCH; then
  echo "Branch $BRANCH already exists locally. Checking it out."
  git checkout $BRANCH
else
  # create new branch from current HEAD
  git checkout -b $BRANCH
fi

echo "Staging frontend changes..."
git add frontend || true

if git diff --cached --quiet; then
  echo "No staged changes detected after adding frontend. Nothing to commit." >&2
  echo "If you intended to push, make sure changes are saved and try again." >&2
  exit 1
fi

echo "Committing with message: $COMMIT_MSG"
git commit -m "$COMMIT_MSG"

echo "Pushing to origin/$BRANCH"
git push -u origin $BRANCH

echo "Push complete. Create a PR from $BRANCH on GitHub if desired."

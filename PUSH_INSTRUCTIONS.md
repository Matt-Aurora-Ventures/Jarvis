# Push Frontend Changes (No automated terminal run)

This repository now contains a helper script to prepare and push the frontend changes to GitHub without me running commands on your machine.

Files added:
- `scripts/push_frontend.sh` — helper script to create branch, commit `frontend/` changes, and push to `origin`.

How to use (run locally):

1. From repository root run:

```bash
bash ./scripts/push_frontend.sh
```

2. To specify a branch name and commit message:

```bash
bash ./scripts/push_frontend.sh my-branch-name "my commit message"
```

What the script does:
- Fetches `origin`.
- Creates or checks out the branch (default `frontend/premium-refactor`).
- Stages the `frontend/` folder, commits with a default message, and pushes to origin.

If you prefer not to run the script, here are the exact commands to run manually:

```bash
git fetch origin
git checkout -b frontend/premium-refactor
git add frontend
git commit -m "chore(frontend): wire refactor + roadmap + styles"
git push -u origin frontend/premium-refactor
```

If you want me to open a pull request automatically (via GitHub API) I can prepare a small script for that, but I will not run it — you must run the push first or give explicit remote permissions.

Notes & safety:
- The script exits if no staged changes are detected after adding `frontend/` to avoid empty commits.
- It will stop and print instructions if `git` is not installed.

If you want, I can also prepare a GitHub Actions workflow that opens a PR automatically when a branch is pushed.

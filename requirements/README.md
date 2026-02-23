# Dependency Profiles

Profiles in this directory are the source of truth for host-scoped dependency boundaries.

- `signer.in` / `signer.txt`: Zone C signer host (minimal execution surface)
- `core.in` / `core.txt`: Zone B strategy + risk + journal
- `ai.in` / `ai.txt`: optional Zone A AI macro services
- `ci.in` / `ci.txt`: CI guardrail tooling
- `dev.in` / `dev.txt`: local development tooling

## Canonical Commands

```bash
python scripts/freeze_deps.py
python scripts/verify_deps.py
```

`freeze_deps.py` compiles lockfiles with hashes and refreshes `requirements/lockfile.sha256`.
`verify_deps.py` enforces lock drift checks, checksum integrity, and signer forbidden-package policy.

## Signer Constraints

Signer profile must remain minimal and must not include AI, web framework, or ML libraries.

- Maximum direct package count: `10`
- Forbidden package policy enforced by `scripts/verify_deps.py`

Do not install `core` or `ai` profiles on the signer host.

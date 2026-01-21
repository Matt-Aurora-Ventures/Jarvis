# Anchor Program ID Status - 2026-01-20

## Summary
All Solana smart contracts use **placeholder** program IDs. No deployments detected.

## Contracts Status

| Contract | Location | Program ID | Status |
|----------|----------|------------|--------|
| staking | `contracts/staking/` | `StakeXXXX...` | Placeholder |
| data-marketplace | `contracts/data-marketplace/` | `DmktXXXX...` | Placeholder |
| kr8tiv-staking | `contracts/kr8tiv-staking/` | `Fg6PaFpo...` | Default Anchor ID |

## Files Using Placeholders

1. **Anchor.toml** (all 3 contracts) - `[programs.localnet/devnet/mainnet]`
2. **lib.rs** (all 3 contracts) - `declare_id!(...)`
3. **Environment** - `STAKING_PROGRAM_ID` defaults to `111...111`

## Required Before Deployment

1. Generate program keypairs: `solana-keygen new -o target/deploy/<program>-keypair.json`
2. Build with Anchor: `anchor build`
3. Get program ID: `solana address -k target/deploy/<program>-keypair.json`
4. Update `declare_id!()` in lib.rs
5. Update Anchor.toml for each network
6. Set `STAKING_PROGRAM_ID` in environment

## Note
The Codex session was attempting to assess/update these IDs but hit usage limits.
These remain as placeholders until actual deployment occurs.

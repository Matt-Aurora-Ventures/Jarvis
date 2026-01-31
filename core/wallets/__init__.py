"""Compatibility shim.

Some older modules reference `core.wallets.*`.
The canonical implementation lives in `core.security.key_manager`.

Keep this thin to avoid future drift.
"""

"""
Jupiter Perps execution stack - Python 3.11, AnchorPy-based.

Zone C (Signer Host) startup sequence:
    1. integrity.verify_idl() - fail if IDL tampered
    2. Load signer keypair (live mode only)
    3. Start ExecutionService
    4. Start reconciliation_loop()

This package must NOT import anything from:
    - ai/, langgraph, openai, anthropic
    - web/, flask, fastapi, uvicorn
    - bots/twitter, bots/buy_tracker
    - ML stack (xgboost, scikit-learn, pandas)
"""

from core.jupiter_perps.integrity import verify_idl

__all__ = ["verify_idl"]

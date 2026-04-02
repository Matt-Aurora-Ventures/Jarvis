"""
API v1 Routes

Version 1 of the JARVIS API.
These are wrappers around existing routes with /api/v1 prefix.
"""

from fastapi import APIRouter
from api.versioning import create_versioned_router

# Import existing routers
try:
    from api.routes.staking import router as staking_base
    HAS_STAKING = True
except ImportError:
    HAS_STAKING = False

try:
    from api.routes.credits import router as credits_base
    HAS_CREDITS = True
except ImportError:
    HAS_CREDITS = False

try:
    from api.routes.rewards import router as rewards_base
    HAS_REWARDS = True
except ImportError:
    HAS_REWARDS = False

try:
    from api.routes.treasury_reports import router as treasury_base
    HAS_TREASURY = True
except ImportError:
    HAS_TREASURY = False

try:
    from api.routes.health import router as health_base
    HAS_HEALTH = True
except ImportError:
    HAS_HEALTH = False


def create_v1_routers() -> list[APIRouter]:
    """
    Create all v1 routers.

    Returns versioned copies of existing routes with /api/v1 prefix.
    """
    routers = []

    # Staking v1
    if HAS_STAKING:
        staking_v1 = create_versioned_router(
            version="v1",
            prefix="/staking",
            tags=["Staking"],
        )
        # Copy routes from base router
        for route in staking_base.routes:
            staking_v1.routes.append(route)
        routers.append(staking_v1)

    # Credits v1
    if HAS_CREDITS:
        credits_v1 = create_versioned_router(
            version="v1",
            prefix="/credits",
            tags=["Credits"],
        )
        for route in credits_base.routes:
            credits_v1.routes.append(route)
        routers.append(credits_v1)

    # Rewards v1
    if HAS_REWARDS:
        rewards_v1 = create_versioned_router(
            version="v1",
            prefix="/rewards",
            tags=["Rewards"],
        )
        for route in rewards_base.routes:
            rewards_v1.routes.append(route)
        routers.append(rewards_v1)

    # Treasury Reports v1
    if HAS_TREASURY:
        treasury_v1 = create_versioned_router(
            version="v1",
            prefix="/treasury/reports",
            tags=["Treasury"],
        )
        for route in treasury_base.routes:
            treasury_v1.routes.append(route)
        routers.append(treasury_v1)

    # Health v1
    if HAS_HEALTH:
        health_v1 = create_versioned_router(
            version="v1",
            prefix="/health",
            tags=["Health"],
        )
        for route in health_base.routes:
            health_v1.routes.append(route)
        routers.append(health_v1)

    return routers


__all__ = ["create_v1_routers"]

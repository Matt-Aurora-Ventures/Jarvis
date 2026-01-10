"""
Data Consent API Routes.

FastAPI endpoints for GDPR-compliant data consent management:
- View and update consent preferences
- Request data export (DSAR)
- Request data deletion
- Consent history
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from .models import ConsentTier, DataCategory
from .manager import ConsentManager, get_consent_manager

logger = logging.getLogger("jarvis.data_consent.routes")

router = APIRouter(prefix="/api/consent", tags=["Data Consent"])


# =============================================================================
# Request/Response Models
# =============================================================================


class ConsentPreferences(BaseModel):
    """User's current consent preferences."""
    user_id: str
    tier: str = Field(..., description="Current consent tier (TIER_0, TIER_1, TIER_2)")
    categories: Dict[str, bool] = Field(
        default_factory=dict,
        description="Category-specific consent flags",
    )
    last_updated: Optional[str] = Field(None, description="Last update timestamp")


class UpdateConsentRequest(BaseModel):
    """Request to update consent preferences."""
    tier: Optional[str] = Field(None, description="New consent tier")
    categories: Optional[Dict[str, bool]] = Field(
        None,
        description="Category-specific consent updates",
    )


class ConsentHistoryItem(BaseModel):
    """Single consent change record."""
    timestamp: str
    action: str
    previous_tier: Optional[str] = None
    new_tier: Optional[str] = None
    category: Optional[str] = None
    granted: Optional[bool] = None


class ConsentHistoryResponse(BaseModel):
    """Consent history response."""
    user_id: str
    history: List[ConsentHistoryItem] = Field(default_factory=list)


class DataExportRequest(BaseModel):
    """Request for data export (DSAR)."""
    categories: Optional[List[str]] = Field(
        None,
        description="Specific categories to export (None = all)",
    )
    format: str = Field(default="json", description="Export format: json, csv")


class DataExportResponse(BaseModel):
    """Data export response."""
    request_id: str
    status: str
    estimated_completion: Optional[str] = None
    download_url: Optional[str] = None


class DeletionRequest(BaseModel):
    """Request for data deletion."""
    categories: Optional[List[str]] = Field(
        None,
        description="Specific categories to delete (None = all)",
    )
    confirm: bool = Field(
        False,
        description="Must be True to confirm deletion",
    )


class DeletionResponse(BaseModel):
    """Data deletion response."""
    request_id: str
    status: str
    categories_deleted: List[str] = Field(default_factory=list)
    message: str


class AvailableOptionsResponse(BaseModel):
    """Available consent tiers and categories."""
    tiers: List[Dict[str, Any]]
    categories: List[Dict[str, Any]]


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/options", response_model=AvailableOptionsResponse)
async def get_consent_options():
    """Get available consent tiers and data categories."""
    return AvailableOptionsResponse(
        tiers=[
            {
                "id": ConsentTier.TIER_0.value,
                "name": "Essential Only",
                "description": "Only data essential for basic functionality",
            },
            {
                "id": ConsentTier.TIER_1.value,
                "name": "Standard",
                "description": "Essential + analytics for service improvement",
            },
            {
                "id": ConsentTier.TIER_2.value,
                "name": "Full",
                "description": "All data collection for personalized experience",
            },
        ],
        categories=[
            {
                "id": DataCategory.ESSENTIAL.value,
                "name": "Essential",
                "description": "Required for core functionality",
                "required": True,
            },
            {
                "id": DataCategory.ANALYTICS.value,
                "name": "Analytics",
                "description": "Usage patterns and performance data",
                "required": False,
            },
            {
                "id": DataCategory.PERSONALIZATION.value,
                "name": "Personalization",
                "description": "Data for personalized recommendations",
                "required": False,
            },
            {
                "id": DataCategory.TRADING.value,
                "name": "Trading",
                "description": "Trading history and preferences",
                "required": False,
            },
            {
                "id": DataCategory.MARKETING.value,
                "name": "Marketing",
                "description": "Marketing and promotional communications",
                "required": False,
            },
        ],
    )


@router.get("/preferences/{user_id}", response_model=ConsentPreferences)
async def get_consent_preferences(
    user_id: str,
    manager: ConsentManager = Depends(get_consent_manager),
):
    """Get user's current consent preferences."""
    try:
        consent = manager.get_consent(user_id)

        if not consent:
            # Return default (no consent yet)
            return ConsentPreferences(
                user_id=user_id,
                tier=ConsentTier.TIER_0.value,
                categories={},
                last_updated=None,
            )

        return ConsentPreferences(
            user_id=user_id,
            tier=consent.tier.value,
            categories={cat.value: True for cat in consent.categories},
            last_updated=consent.updated_at.isoformat() if consent.updated_at else None,
        )
    except Exception as e:
        logger.error(f"Error fetching consent: {e}")
        raise HTTPException(500, str(e))


@router.put("/preferences/{user_id}", response_model=ConsentPreferences)
async def update_consent_preferences(
    user_id: str,
    request: UpdateConsentRequest,
    manager: ConsentManager = Depends(get_consent_manager),
):
    """Update user's consent preferences."""
    try:
        # Determine new tier and categories
        tier = ConsentTier.TIER_0
        categories = []

        if request.tier:
            try:
                tier = ConsentTier(request.tier)
            except ValueError:
                raise HTTPException(400, f"Invalid tier: {request.tier}")

        # Build categories list from request
        if request.categories:
            for category_str, granted in request.categories.items():
                if granted:
                    try:
                        category = DataCategory(category_str)
                        categories.append(category)
                    except ValueError:
                        logger.warning(f"Invalid category: {category_str}")

        # Record the updated consent
        manager.record_consent(user_id, tier, categories)

        # Return updated preferences
        consent = manager.get_consent(user_id)

        return ConsentPreferences(
            user_id=user_id,
            tier=consent.tier.value if consent else ConsentTier.TIER_0.value,
            categories={cat.value: True for cat in (consent.categories if consent else [])},
            last_updated=consent.updated_at.isoformat() if consent and consent.updated_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating consent: {e}")
        raise HTTPException(500, str(e))


@router.get("/history/{user_id}", response_model=ConsentHistoryResponse)
async def get_consent_history(
    user_id: str,
    limit: int = 50,
    manager: ConsentManager = Depends(get_consent_manager),
):
    """Get user's consent change history."""
    try:
        history = manager.get_consent_history(user_id, limit=limit)

        return ConsentHistoryResponse(
            user_id=user_id,
            history=[
                ConsentHistoryItem(
                    timestamp=record["timestamp"],
                    action=record["action"],
                    previous_tier=record.get("old_tier"),
                    new_tier=record.get("new_tier"),
                    category=None,
                    granted=None,
                )
                for record in history
            ],
        )
    except Exception as e:
        logger.error(f"Error fetching consent history: {e}")
        raise HTTPException(500, str(e))


@router.post("/export/{user_id}", response_model=DataExportResponse)
async def request_data_export(
    user_id: str,
    request: DataExportRequest,
    manager: ConsentManager = Depends(get_consent_manager),
):
    """Request a data export (GDPR DSAR)."""
    try:
        import uuid

        # Parse categories
        categories = None
        if request.categories:
            try:
                categories = [DataCategory(c) for c in request.categories]
            except ValueError as e:
                raise HTTPException(400, f"Invalid category: {e}")

        # Create export request
        request_id = f"export_{uuid.uuid4().hex[:12]}"

        # In production, this would queue an async job
        # For now, we return a pending status
        return DataExportResponse(
            request_id=request_id,
            status="pending",
            estimated_completion=(
                datetime.now(timezone.utc).isoformat()
            ),
            download_url=None,  # Would be populated when ready
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating export request: {e}")
        raise HTTPException(500, str(e))


@router.post("/delete/{user_id}", response_model=DeletionResponse)
async def request_data_deletion(
    user_id: str,
    request: DeletionRequest,
    manager: ConsentManager = Depends(get_consent_manager),
):
    """Request data deletion (GDPR right to be forgotten)."""
    try:
        if not request.confirm:
            raise HTTPException(
                400,
                "Must set confirm=true to confirm data deletion",
            )

        # Parse categories
        categories = None
        if request.categories:
            try:
                categories = [DataCategory(c) for c in request.categories]
            except ValueError as e:
                raise HTTPException(400, f"Invalid category: {e}")

        # Create and execute deletion request
        deletion_request = manager.request_deletion(user_id, categories=categories)

        # Mark as completed immediately (in production, this would be async)
        manager.complete_deletion(deletion_request.id, success=True)

        return DeletionResponse(
            request_id=str(deletion_request.id),
            status="completed",
            categories_deleted=[c.value for c in (categories or [])],
            message="Data deletion request processed successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing deletion request: {e}")
        raise HTTPException(500, str(e))


@router.delete("/preferences/{user_id}")
async def revoke_all_consent(
    user_id: str,
    manager: ConsentManager = Depends(get_consent_manager),
):
    """Revoke all consent and reset to TIER_0."""
    try:
        manager.revoke_consent(user_id)

        return {
            "success": True,
            "message": "All consent revoked, reset to TIER_0",
        }
    except Exception as e:
        logger.error(f"Error revoking consent: {e}")
        raise HTTPException(500, str(e))

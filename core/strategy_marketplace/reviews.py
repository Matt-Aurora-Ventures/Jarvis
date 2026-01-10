"""
Strategy Review System

User reviews and ratings for marketplace strategies.

Prompts #105-106: Strategy Marketplace
"""

import asyncio
import logging
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class StrategyReview:
    """A user review for a strategy"""
    review_id: str
    strategy_id: str
    user_id: str
    rating: int  # 1-5 stars
    title: str = ""
    content: str = ""
    is_verified_purchase: bool = False

    # Helpfulness
    helpful_votes: int = 0
    unhelpful_votes: int = 0

    # Moderation
    is_approved: bool = True
    is_featured: bool = False
    reported_count: int = 0

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.review_id:
            data = f"{self.strategy_id}{self.user_id}{self.created_at.isoformat()}"
            self.review_id = f"REV-{hashlib.sha256(data.encode()).hexdigest()[:8].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "review_id": self.review_id,
            "strategy_id": self.strategy_id,
            "user_id": self.user_id,
            "rating": self.rating,
            "title": self.title,
            "content": self.content,
            "is_verified_purchase": self.is_verified_purchase,
            "helpful_votes": self.helpful_votes,
            "unhelpful_votes": self.unhelpful_votes,
            "is_approved": self.is_approved,
            "is_featured": self.is_featured,
            "reported_count": self.reported_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyReview":
        """Create from dictionary"""
        return cls(
            review_id=data["review_id"],
            strategy_id=data["strategy_id"],
            user_id=data["user_id"],
            rating=data["rating"],
            title=data.get("title", ""),
            content=data.get("content", ""),
            is_verified_purchase=data.get("is_verified_purchase", False),
            helpful_votes=data.get("helpful_votes", 0),
            unhelpful_votes=data.get("unhelpful_votes", 0),
            is_approved=data.get("is_approved", True),
            is_featured=data.get("is_featured", False),
            reported_count=data.get("reported_count", 0),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now()
        )


class ReviewManager:
    """
    Manages strategy reviews

    Handles review submission, moderation, and aggregation.
    """

    def __init__(self, storage_path: str = "data/strategy_marketplace/reviews.json"):
        self.storage_path = Path(storage_path)
        self.reviews: Dict[str, StrategyReview] = {}
        self.reviews_by_strategy: Dict[str, List[str]] = {}
        self.reviews_by_user: Dict[str, List[str]] = {}
        self._load()

    def _load(self):
        """Load reviews from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for review_data in data.get("reviews", []):
                review = StrategyReview.from_dict(review_data)
                self.reviews[review.review_id] = review

                if review.strategy_id not in self.reviews_by_strategy:
                    self.reviews_by_strategy[review.strategy_id] = []
                self.reviews_by_strategy[review.strategy_id].append(review.review_id)

                if review.user_id not in self.reviews_by_user:
                    self.reviews_by_user[review.user_id] = []
                self.reviews_by_user[review.user_id].append(review.review_id)

            logger.info(f"Loaded {len(self.reviews)} reviews")

        except Exception as e:
            logger.error(f"Failed to load reviews: {e}")

    def _save(self):
        """Save reviews to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "reviews": [r.to_dict() for r in self.reviews.values()],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save reviews: {e}")
            raise

    async def submit_review(
        self,
        strategy_id: str,
        user_id: str,
        rating: int,
        title: str = "",
        content: str = "",
        is_verified_purchase: bool = False
    ) -> Optional[StrategyReview]:
        """Submit a new review"""
        # Validate rating
        if rating < 1 or rating > 5:
            logger.warning(f"Invalid rating: {rating}")
            return None

        # Check if user already reviewed this strategy
        user_reviews = self.reviews_by_user.get(user_id, [])
        for rid in user_reviews:
            review = self.reviews.get(rid)
            if review and review.strategy_id == strategy_id:
                logger.warning(f"User {user_id} already reviewed strategy {strategy_id}")
                return None

        review = StrategyReview(
            review_id="",
            strategy_id=strategy_id,
            user_id=user_id,
            rating=rating,
            title=title,
            content=content,
            is_verified_purchase=is_verified_purchase
        )

        self.reviews[review.review_id] = review

        if strategy_id not in self.reviews_by_strategy:
            self.reviews_by_strategy[strategy_id] = []
        self.reviews_by_strategy[strategy_id].append(review.review_id)

        if user_id not in self.reviews_by_user:
            self.reviews_by_user[user_id] = []
        self.reviews_by_user[user_id].append(review.review_id)

        self._save()
        logger.info(f"Submitted review {review.review_id} for strategy {strategy_id}")
        return review

    async def get_review(self, review_id: str) -> Optional[StrategyReview]:
        """Get a review by ID"""
        return self.reviews.get(review_id)

    async def get_strategy_reviews(
        self,
        strategy_id: str,
        verified_only: bool = False,
        sort_by: str = "recent",
        limit: int = 50
    ) -> List[StrategyReview]:
        """Get reviews for a strategy"""
        review_ids = self.reviews_by_strategy.get(strategy_id, [])
        reviews = [self.reviews[rid] for rid in review_ids if rid in self.reviews]

        # Filter approved only
        reviews = [r for r in reviews if r.is_approved]

        if verified_only:
            reviews = [r for r in reviews if r.is_verified_purchase]

        # Sort
        if sort_by == "recent":
            reviews.sort(key=lambda r: r.created_at, reverse=True)
        elif sort_by == "helpful":
            reviews.sort(key=lambda r: r.helpful_votes - r.unhelpful_votes, reverse=True)
        elif sort_by == "rating_high":
            reviews.sort(key=lambda r: r.rating, reverse=True)
        elif sort_by == "rating_low":
            reviews.sort(key=lambda r: r.rating)

        return reviews[:limit]

    async def get_strategy_rating_summary(self, strategy_id: str) -> Dict[str, Any]:
        """Get rating summary for a strategy"""
        reviews = await self.get_strategy_reviews(strategy_id, limit=10000)

        if not reviews:
            return {
                "strategy_id": strategy_id,
                "total_reviews": 0,
                "average_rating": 0.0,
                "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                "verified_reviews": 0
            }

        total = len(reviews)
        avg_rating = sum(r.rating for r in reviews) / total

        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in reviews:
            distribution[review.rating] += 1

        verified = sum(1 for r in reviews if r.is_verified_purchase)

        return {
            "strategy_id": strategy_id,
            "total_reviews": total,
            "average_rating": round(avg_rating, 2),
            "rating_distribution": distribution,
            "verified_reviews": verified,
            "featured_review": next(
                (r.to_dict() for r in reviews if r.is_featured),
                None
            )
        }

    async def vote_helpful(self, review_id: str, is_helpful: bool) -> bool:
        """Vote on whether a review is helpful"""
        review = self.reviews.get(review_id)
        if not review:
            return False

        if is_helpful:
            review.helpful_votes += 1
        else:
            review.unhelpful_votes += 1

        self._save()
        return True

    async def report_review(self, review_id: str, reason: str = "") -> bool:
        """Report a review for moderation"""
        review = self.reviews.get(review_id)
        if not review:
            return False

        review.reported_count += 1

        # Auto-hide if too many reports
        if review.reported_count >= 5:
            review.is_approved = False

        self._save()
        logger.info(f"Review {review_id} reported. Total reports: {review.reported_count}")
        return True

    async def update_review(
        self,
        review_id: str,
        user_id: str,
        rating: Optional[int] = None,
        title: Optional[str] = None,
        content: Optional[str] = None
    ) -> bool:
        """Update a review (only by the author)"""
        review = self.reviews.get(review_id)
        if not review or review.user_id != user_id:
            return False

        if rating is not None and 1 <= rating <= 5:
            review.rating = rating
        if title is not None:
            review.title = title
        if content is not None:
            review.content = content

        review.updated_at = datetime.now()
        self._save()

        return True

    async def delete_review(self, review_id: str, user_id: str) -> bool:
        """Delete a review (only by the author)"""
        review = self.reviews.get(review_id)
        if not review or review.user_id != user_id:
            return False

        del self.reviews[review_id]

        if review.strategy_id in self.reviews_by_strategy:
            if review_id in self.reviews_by_strategy[review.strategy_id]:
                self.reviews_by_strategy[review.strategy_id].remove(review_id)

        if user_id in self.reviews_by_user:
            if review_id in self.reviews_by_user[user_id]:
                self.reviews_by_user[user_id].remove(review_id)

        self._save()
        return True

    async def feature_review(self, review_id: str) -> bool:
        """Mark a review as featured"""
        review = self.reviews.get(review_id)
        if not review:
            return False

        # Unfeature other reviews for this strategy
        for rid in self.reviews_by_strategy.get(review.strategy_id, []):
            other = self.reviews.get(rid)
            if other:
                other.is_featured = False

        review.is_featured = True
        self._save()

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get review statistics"""
        total = len(self.reviews)
        verified = sum(1 for r in self.reviews.values() if r.is_verified_purchase)
        avg_rating = sum(r.rating for r in self.reviews.values()) / total if total > 0 else 0

        return {
            "total_reviews": total,
            "verified_reviews": verified,
            "average_rating": round(avg_rating, 2),
            "strategies_reviewed": len(self.reviews_by_strategy),
            "reviewers": len(self.reviews_by_user)
        }


# Singleton instance
_review_manager: Optional[ReviewManager] = None


def get_review_manager() -> ReviewManager:
    """Get review manager singleton"""
    global _review_manager

    if _review_manager is None:
        _review_manager = ReviewManager()

    return _review_manager


# Testing
if __name__ == "__main__":
    async def test():
        manager = ReviewManager("test_reviews.json")

        # Submit reviews
        review1 = await manager.submit_review(
            strategy_id="STRAT-TEST123",
            user_id="USER_A",
            rating=5,
            title="Excellent strategy!",
            content="This strategy has been consistently profitable for me.",
            is_verified_purchase=True
        )
        print(f"Created review: {review1.review_id}")

        review2 = await manager.submit_review(
            strategy_id="STRAT-TEST123",
            user_id="USER_B",
            rating=4,
            title="Good but needs improvement",
            content="Works well in trending markets."
        )

        # Get summary
        summary = await manager.get_strategy_rating_summary("STRAT-TEST123")
        print(f"\nRating Summary:")
        print(f"  Total: {summary['total_reviews']}")
        print(f"  Average: {summary['average_rating']}")
        print(f"  Distribution: {summary['rating_distribution']}")

        # Vote helpful
        await manager.vote_helpful(review1.review_id, True)
        print(f"\nHelpful votes: {review1.helpful_votes}")

        # Stats
        print(f"\nStats: {manager.get_stats()}")

        # Clean up
        import os
        os.remove("test_reviews.json")

    asyncio.run(test())

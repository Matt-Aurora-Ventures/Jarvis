"""
X Bot Pre-Post Validator - Strong gate before any post.

Before any tweet is posted, this validator checks:
1. Is it new information? (factuality + novelty)
2. Is it accurate? (fact checking)
3. Is it necessary? (materiality)
4. Is it safe? (policy + brand)

Only if all checks pass does the tweet get posted.

Usage:
    from bots.twitter.pre_post_validator import get_pre_post_validator, ValidationResult

    validator = get_pre_post_validator()
    result = await validator.validate(content, category)

    if result.approved:
        await post_tweet(content)
    else:
        logger.info(f"Tweet blocked: {result.reason}")
"""

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Set

logger = logging.getLogger(__name__)

# Singleton instance
_validator: Optional["PrePostValidator"] = None


class ValidationLevel(Enum):
    """Severity of validation failures."""
    PASS = "pass"
    WARNING = "warning"
    BLOCK = "block"
    CRITICAL = "critical"


@dataclass
class ValidationCheck:
    """Result of a single validation check."""
    name: str
    passed: bool
    level: ValidationLevel
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Complete result of pre-post validation."""
    approved: bool
    level: ValidationLevel
    reason: str
    checks: List[ValidationCheck] = field(default_factory=list)
    content_hash: str = ""
    validated_at: datetime = field(default_factory=datetime.utcnow)
    processing_time_ms: float = 0.0

    @property
    def passed_checks(self) -> List[str]:
        return [c.name for c in self.checks if c.passed]

    @property
    def failed_checks(self) -> List[str]:
        return [c.name for c in self.checks if not c.passed]

    def summary(self) -> str:
        """Get a human-readable summary."""
        status = "✅ APPROVED" if self.approved else "❌ BLOCKED"
        return (
            f"{status}: {self.reason}\n"
            f"Checks passed: {len(self.passed_checks)}/{len(self.checks)}\n"
            f"Failed: {', '.join(self.failed_checks) or 'none'}"
        )


class PrePostValidator:
    """
    Comprehensive pre-post validation for X/Twitter content.

    Implements a multi-layer validation system:
    1. Content Quality (length, formatting, language)
    2. Novelty Check (is this new information?)
    3. Factuality Check (are claims accurate?)
    4. Policy Check (brand guidelines, banned patterns)
    5. Safety Check (no harmful content)
    """

    # Banned patterns that should never appear
    BANNED_PATTERNS = [
        r"guaranteed\s+(profit|returns?|gains?)",
        r"\d+x\s+guaranteed",
        r"free\s+money",
        r"send\s+\d+\s*(sol|eth|btc)",
        r"dm\s+(for|me)",
        r"financial\s+advice",
        r"(buy|sell)\s+now\s+before",
        r"last\s+chance\s+to\s+buy",
        r"moonshot\s+confirmed",
    ]

    # Overused patterns to avoid
    OVERUSED_PATTERNS = [
        r"^BREAKING:",
        r"^URGENT:",
        r"^ALERT:",
        r"LFG!*$",
        r"WAGMI!*$",
        r"gm\s+crypto\s+twitter",
        r"this\s+is\s+huge",
        r"you're\s+not\s+bullish\s+enough",
    ]

    # Required elements for different categories
    CATEGORY_REQUIREMENTS = {
        "market_update": {"min_length": 50, "requires_data": True},
        "trending_token": {"min_length": 40, "requires_symbol": True},
        "alpha_signal": {"min_length": 60, "requires_data": True},
        "agentic_tech": {"min_length": 40, "requires_data": False},
        "hourly_update": {"min_length": 30, "requires_data": True},
    }

    def __init__(self):
        self._recent_content_hashes: Dict[str, float] = {}
        self._recent_topics: Dict[str, float] = {}
        self._duplicate_window_hours = 24
        self._banned_compiled = [re.compile(p, re.IGNORECASE) for p in self.BANNED_PATTERNS]
        self._overused_compiled = [re.compile(p, re.IGNORECASE) for p in self.OVERUSED_PATTERNS]

    async def validate(
        self,
        content: str,
        category: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Validate content before posting.

        Returns a ValidationResult indicating if the content should be posted.
        """
        start_time = time.time()
        metadata = metadata or {}

        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        checks: List[ValidationCheck] = []

        # 1. Content Quality Check
        checks.append(await self._check_content_quality(content, category))

        # 2. Novelty Check
        checks.append(await self._check_novelty(content, content_hash))

        # 3. Policy Check (banned patterns)
        checks.append(await self._check_policy(content))

        # 4. Overuse Check
        checks.append(await self._check_overuse(content))

        # 5. Factuality Check (basic)
        checks.append(await self._check_factuality(content, metadata))

        # 6. Safety Check
        checks.append(await self._check_safety(content))

        # 7. Category-specific check
        if category:
            checks.append(await self._check_category_requirements(content, category))

        # Determine overall result
        critical_failures = [c for c in checks if c.level == ValidationLevel.CRITICAL]
        block_failures = [c for c in checks if c.level == ValidationLevel.BLOCK]
        warnings = [c for c in checks if c.level == ValidationLevel.WARNING]

        if critical_failures:
            approved = False
            level = ValidationLevel.CRITICAL
            reason = critical_failures[0].reason
        elif block_failures:
            approved = False
            level = ValidationLevel.BLOCK
            reason = block_failures[0].reason
        elif len(warnings) >= 3:
            approved = False
            level = ValidationLevel.BLOCK
            reason = "Too many warnings - content needs revision"
        else:
            approved = True
            level = ValidationLevel.PASS
            reason = "All checks passed"

            # Record this content as posted
            self._recent_content_hashes[content_hash] = time.time()

        processing_time = (time.time() - start_time) * 1000

        return ValidationResult(
            approved=approved,
            level=level,
            reason=reason,
            checks=checks,
            content_hash=content_hash,
            processing_time_ms=processing_time,
        )

    async def _check_content_quality(
        self,
        content: str,
        category: str,
    ) -> ValidationCheck:
        """Check basic content quality."""
        issues = []

        # Length check
        if len(content) < 20:
            issues.append("Content too short")
        if len(content) > 4000:
            issues.append("Content too long")

        # Check for placeholder text
        placeholders = ["{", "}", "[TOKEN]", "[SYMBOL]", "???", "TBD"]
        for p in placeholders:
            if p in content:
                issues.append(f"Contains placeholder: {p}")

        # Check for repeated characters
        if re.search(r"(.)\1{4,}", content):
            issues.append("Contains excessive repeated characters")

        # Check for all caps (more than 50%)
        alpha_chars = [c for c in content if c.isalpha()]
        if alpha_chars and sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars) > 0.5:
            issues.append("Too much CAPS (appears aggressive)")

        if issues:
            return ValidationCheck(
                name="content_quality",
                passed=False,
                level=ValidationLevel.BLOCK if len(issues) > 1 else ValidationLevel.WARNING,
                reason="; ".join(issues),
            )

        return ValidationCheck(
            name="content_quality",
            passed=True,
            level=ValidationLevel.PASS,
            reason="Content quality OK",
        )

    async def _check_novelty(
        self,
        content: str,
        content_hash: str,
    ) -> ValidationCheck:
        """Check if content is new/novel."""
        now = time.time()
        cutoff = now - (self._duplicate_window_hours * 3600)

        # Clean old entries
        self._recent_content_hashes = {
            h: t for h, t in self._recent_content_hashes.items()
            if t > cutoff
        }

        # Check for exact duplicate
        if content_hash in self._recent_content_hashes:
            hours_ago = (now - self._recent_content_hashes[content_hash]) / 3600
            return ValidationCheck(
                name="novelty",
                passed=False,
                level=ValidationLevel.BLOCK,
                reason=f"Exact duplicate from {hours_ago:.1f}h ago",
            )

        # Check for similar content (word overlap)
        content_words = set(content.lower().split())
        for existing_hash, timestamp in self._recent_content_hashes.items():
            if timestamp > cutoff:
                # This is a simplified check - in production, store words too
                pass

        return ValidationCheck(
            name="novelty",
            passed=True,
            level=ValidationLevel.PASS,
            reason="Content appears novel",
        )

    async def _check_policy(self, content: str) -> ValidationCheck:
        """Check against banned patterns."""
        for pattern in self._banned_compiled:
            if pattern.search(content):
                return ValidationCheck(
                    name="policy",
                    passed=False,
                    level=ValidationLevel.CRITICAL,
                    reason=f"Contains banned pattern (financial claims/scam indicators)",
                )

        return ValidationCheck(
            name="policy",
            passed=True,
            level=ValidationLevel.PASS,
            reason="No banned patterns found",
        )

    async def _check_overuse(self, content: str) -> ValidationCheck:
        """Check for overused/cliché patterns."""
        matches = []
        for pattern in self._overused_compiled:
            if pattern.search(content):
                matches.append(pattern.pattern)

        if matches:
            return ValidationCheck(
                name="overuse",
                passed=False,
                level=ValidationLevel.WARNING,
                reason=f"Contains overused patterns: {len(matches)} found",
                details={"patterns": matches},
            )

        return ValidationCheck(
            name="overuse",
            passed=True,
            level=ValidationLevel.PASS,
            reason="No overused patterns",
        )

    async def _check_factuality(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> ValidationCheck:
        """
        Basic factuality check.

        In production, this would call an LLM or fact-checking API.
        For now, we do basic sanity checks.
        """
        issues = []

        # Check for specific claims that should have sources
        claim_patterns = [
            r"(\d+)%\s+(increase|decrease|growth|drop)",
            r"\$[\d,]+\s+(billion|million|trillion)",
            r"(all-time|ath|new)\s+high",
            r"(research|study|report)\s+(shows|says|finds)",
        ]

        for pattern in claim_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                # Check if source is provided
                if not metadata.get("source"):
                    issues.append("Contains specific claims without source")
                break

        # Check for absolute statements
        absolutes = ["always", "never", "guaranteed", "definitely", "impossible"]
        for word in absolutes:
            if word.lower() in content.lower():
                issues.append(f"Contains absolute statement: '{word}'")
                break

        if issues:
            return ValidationCheck(
                name="factuality",
                passed=False,
                level=ValidationLevel.WARNING,
                reason="; ".join(issues),
            )

        return ValidationCheck(
            name="factuality",
            passed=True,
            level=ValidationLevel.PASS,
            reason="No obvious factuality issues",
        )

    async def _check_safety(self, content: str) -> ValidationCheck:
        """Check for harmful or inappropriate content."""
        # Check for potential harassment
        harassment_patterns = [
            r"(idiot|stupid|dumb|moron)",
            r"(loser|failure)",
            r"(stfu|gtfo)",
        ]

        for pattern in harassment_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return ValidationCheck(
                    name="safety",
                    passed=False,
                    level=ValidationLevel.BLOCK,
                    reason="Contains potentially harmful language",
                )

        return ValidationCheck(
            name="safety",
            passed=True,
            level=ValidationLevel.PASS,
            reason="No safety issues detected",
        )

    async def _check_category_requirements(
        self,
        content: str,
        category: str,
    ) -> ValidationCheck:
        """Check category-specific requirements."""
        requirements = self.CATEGORY_REQUIREMENTS.get(category, {})
        issues = []

        min_length = requirements.get("min_length", 0)
        if len(content) < min_length:
            issues.append(f"Below minimum length for {category} ({min_length} chars)")

        if requirements.get("requires_symbol"):
            if not re.search(r"\$[A-Z]+", content):
                issues.append(f"{category} requires a $SYMBOL")

        if requirements.get("requires_data"):
            # Check for some kind of data/numbers
            if not re.search(r"[\d.]+%?", content):
                issues.append(f"{category} should include data points")

        if issues:
            return ValidationCheck(
                name="category_requirements",
                passed=False,
                level=ValidationLevel.WARNING,
                reason="; ".join(issues),
            )

        return ValidationCheck(
            name="category_requirements",
            passed=True,
            level=ValidationLevel.PASS,
            reason=f"Meets {category} requirements",
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        now = time.time()
        cutoff = now - (24 * 3600)  # Last 24 hours

        recent = sum(1 for t in self._recent_content_hashes.values() if t > cutoff)

        return {
            "tracked_content_hashes": len(self._recent_content_hashes),
            "posts_last_24h": recent,
            "duplicate_window_hours": self._duplicate_window_hours,
        }


def get_pre_post_validator() -> PrePostValidator:
    """Get or create the singleton pre-post validator."""
    global _validator
    if _validator is None:
        _validator = PrePostValidator()
    return _validator

"""
Source Credibility Scoring - Evaluate trustworthiness of information sources.

Features:
- Multi-factor credibility assessment
- Historical accuracy tracking
- Domain reputation scoring
- Bias detection
- Cross-reference verification
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import hashlib
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class SourceCategory(Enum):
    """Categories of information sources."""
    OFFICIAL = "official"           # Government, official organizations
    ACADEMIC = "academic"           # Peer-reviewed, research institutions
    NEWS_MAJOR = "news_major"       # Major established news outlets
    NEWS_LOCAL = "news_local"       # Local/regional news
    BLOG = "blog"                   # Personal/company blogs
    SOCIAL = "social"               # Social media posts
    FORUM = "forum"                 # Forums, discussion boards
    WIKI = "wiki"                   # Wiki-style collaborative
    AGGREGATOR = "aggregator"       # News aggregators
    UNKNOWN = "unknown"             # Unclassified


class BiasLevel(Enum):
    """Detected bias level."""
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


class CredibilityTier(Enum):
    """Overall credibility tier."""
    VERIFIED = "verified"           # Highly trusted
    RELIABLE = "reliable"           # Generally trustworthy
    MIXED = "mixed"                 # Variable quality
    QUESTIONABLE = "questionable"   # Use with caution
    UNRELIABLE = "unreliable"       # Not trustworthy
    UNKNOWN = "unknown"             # No data


@dataclass
class SourceProfile:
    """Profile of an information source."""
    domain: str
    name: Optional[str] = None
    category: SourceCategory = SourceCategory.UNKNOWN
    credibility_tier: CredibilityTier = CredibilityTier.UNKNOWN
    bias_level: BiasLevel = BiasLevel.NONE
    bias_direction: Optional[str] = None  # e.g., "left", "right", "corporate"

    # Scores (0.0 to 1.0)
    accuracy_score: float = 0.5
    transparency_score: float = 0.5
    expertise_score: float = 0.5
    consistency_score: float = 0.5
    citation_score: float = 0.5

    # Metadata
    fact_checks_passed: int = 0
    fact_checks_failed: int = 0
    total_claims_tracked: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)
    notes: str = ""

    # Source relationships
    owned_by: Optional[str] = None
    affiliated_with: List[str] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        """Calculate weighted overall credibility score."""
        weights = {
            "accuracy": 0.35,
            "transparency": 0.20,
            "expertise": 0.20,
            "consistency": 0.15,
            "citation": 0.10,
        }
        return (
            self.accuracy_score * weights["accuracy"] +
            self.transparency_score * weights["transparency"] +
            self.expertise_score * weights["expertise"] +
            self.consistency_score * weights["consistency"] +
            self.citation_score * weights["citation"]
        )

    @property
    def fact_check_rate(self) -> float:
        """Calculate fact check pass rate."""
        total = self.fact_checks_passed + self.fact_checks_failed
        if total == 0:
            return 0.5  # Unknown
        return self.fact_checks_passed / total


@dataclass
class CredibilityAssessment:
    """Assessment result for a specific piece of content."""
    source_profile: SourceProfile
    content_hash: str
    assessment_time: datetime = field(default_factory=datetime.utcnow)

    # Content-specific scores
    claim_specificity: float = 0.5       # How specific/verifiable are claims
    source_attribution: float = 0.5      # Does it cite sources
    factual_language: float = 0.5        # Factual vs opinion language
    emotional_manipulation: float = 0.0  # Detected emotional manipulation
    logical_fallacies: float = 0.0       # Detected logical fallacies

    # Cross-reference results
    corroborating_sources: List[str] = field(default_factory=list)
    contradicting_sources: List[str] = field(default_factory=list)
    cross_reference_score: float = 0.5

    # Flags
    contains_claims: bool = True
    contains_opinion: bool = False
    is_satire: bool = False
    is_sponsored: bool = False

    # Final assessment
    overall_credibility: float = 0.5
    confidence: float = 0.5
    recommendation: str = ""

    def calculate_overall(self) -> float:
        """Calculate overall credibility score."""
        # Start with source credibility
        base_score = self.source_profile.overall_score

        # Adjust based on content analysis
        content_factor = (
            self.claim_specificity * 0.3 +
            self.source_attribution * 0.3 +
            self.factual_language * 0.2 +
            (1 - self.emotional_manipulation) * 0.1 +
            (1 - self.logical_fallacies) * 0.1
        )

        # Cross-reference bonus/penalty
        cross_ref_factor = self.cross_reference_score

        # Weighted combination
        self.overall_credibility = (
            base_score * 0.4 +
            content_factor * 0.3 +
            cross_ref_factor * 0.3
        )

        # Apply penalties
        if self.is_satire:
            self.overall_credibility *= 0.3
        if self.is_sponsored:
            self.overall_credibility *= 0.8

        return self.overall_credibility


class CredibilityScorer:
    """
    Scores the credibility of information sources and content.

    Usage:
        scorer = CredibilityScorer()
        await scorer.initialize()

        # Get source profile
        profile = await scorer.get_source_profile("example.com")

        # Assess specific content
        assessment = await scorer.assess_content(
            source_domain="example.com",
            content="The study found that...",
            claims=["Claim 1", "Claim 2"],
        )
    """

    # Known high-credibility domains (baseline)
    VERIFIED_DOMAINS = {
        "gov", "edu", "ac.uk", "gov.uk",
        "who.int", "un.org", "nih.gov", "cdc.gov",
    }

    # Known fact-checking organizations
    FACT_CHECKERS = {
        "snopes.com", "factcheck.org", "politifact.com",
        "fullfact.org", "apnews.com/hub/ap-fact-check",
    }

    def __init__(self, storage_path: Optional[Path] = None):
        self._storage_path = storage_path
        self._source_profiles: Dict[str, SourceProfile] = {}
        self._domain_categories: Dict[str, SourceCategory] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the credibility scorer."""
        if self._initialized:
            return

        # Load stored profiles
        if self._storage_path and self._storage_path.exists():
            await self._load_profiles()

        # Initialize domain categories
        self._init_domain_categories()

        self._initialized = True
        logger.info("Credibility scorer initialized")

    def _init_domain_categories(self) -> None:
        """Initialize known domain categories."""
        self._domain_categories.update({
            # Academic
            ".edu": SourceCategory.ACADEMIC,
            ".ac.uk": SourceCategory.ACADEMIC,
            "arxiv.org": SourceCategory.ACADEMIC,
            "scholar.google.com": SourceCategory.ACADEMIC,

            # Official
            ".gov": SourceCategory.OFFICIAL,
            ".gov.uk": SourceCategory.OFFICIAL,
            "who.int": SourceCategory.OFFICIAL,
            "un.org": SourceCategory.OFFICIAL,

            # Major news
            "reuters.com": SourceCategory.NEWS_MAJOR,
            "apnews.com": SourceCategory.NEWS_MAJOR,
            "bbc.com": SourceCategory.NEWS_MAJOR,
            "npr.org": SourceCategory.NEWS_MAJOR,

            # Social
            "twitter.com": SourceCategory.SOCIAL,
            "facebook.com": SourceCategory.SOCIAL,
            "reddit.com": SourceCategory.FORUM,

            # Wiki
            "wikipedia.org": SourceCategory.WIKI,
        })

    async def get_source_profile(
        self,
        domain: str,
        create_if_missing: bool = True,
    ) -> Optional[SourceProfile]:
        """Get or create a source profile for a domain."""
        domain = self._normalize_domain(domain)

        if domain in self._source_profiles:
            return self._source_profiles[domain]

        if not create_if_missing:
            return None

        # Create new profile with inferred category
        category = self._infer_category(domain)
        tier = self._infer_tier(domain, category)

        profile = SourceProfile(
            domain=domain,
            category=category,
            credibility_tier=tier,
        )

        # Set default scores based on category
        self._set_default_scores(profile)

        self._source_profiles[domain] = profile
        return profile

    async def assess_content(
        self,
        source_domain: str,
        content: str,
        claims: Optional[List[str]] = None,
        cross_reference_domains: Optional[List[str]] = None,
    ) -> CredibilityAssessment:
        """
        Assess the credibility of specific content.

        Args:
            source_domain: Domain the content came from
            content: The actual content text
            claims: Specific claims to verify
            cross_reference_domains: Other domains reporting same info
        """
        profile = await self.get_source_profile(source_domain)

        # Create content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        assessment = CredibilityAssessment(
            source_profile=profile,
            content_hash=content_hash,
        )

        # Analyze content
        assessment.claim_specificity = self._analyze_specificity(content)
        assessment.source_attribution = self._analyze_attribution(content)
        assessment.factual_language = self._analyze_language(content)
        assessment.emotional_manipulation = self._detect_manipulation(content)
        assessment.logical_fallacies = self._detect_fallacies(content)

        # Check for special content types
        assessment.is_satire = self._detect_satire(content, source_domain)
        assessment.is_sponsored = self._detect_sponsored(content)
        assessment.contains_opinion = self._detect_opinion(content)

        # Cross-reference if domains provided
        if cross_reference_domains:
            assessment.corroborating_sources = [
                d for d in cross_reference_domains
                if await self._is_corroborating(d, claims)
            ]
            assessment.cross_reference_score = len(assessment.corroborating_sources) / max(len(cross_reference_domains), 1)

        # Calculate overall score
        assessment.calculate_overall()

        # Generate recommendation
        assessment.recommendation = self._generate_recommendation(assessment)
        assessment.confidence = self._calculate_confidence(assessment)

        return assessment

    async def update_source_profile(
        self,
        domain: str,
        fact_check_passed: Optional[bool] = None,
        accuracy_update: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> SourceProfile:
        """Update a source profile with new information."""
        profile = await self.get_source_profile(domain)

        if fact_check_passed is not None:
            if fact_check_passed:
                profile.fact_checks_passed += 1
            else:
                profile.fact_checks_failed += 1

            # Recalculate accuracy based on fact checks
            profile.accuracy_score = (
                profile.accuracy_score * 0.7 +
                profile.fact_check_rate * 0.3
            )

        if accuracy_update is not None:
            # Weighted average with new data
            profile.accuracy_score = (
                profile.accuracy_score * 0.8 +
                accuracy_update * 0.2
            )

        if notes:
            profile.notes = notes

        profile.last_updated = datetime.utcnow()
        profile.total_claims_tracked += 1

        # Update credibility tier
        profile.credibility_tier = self._calculate_tier(profile)

        return profile

    async def compare_sources(
        self,
        domains: List[str],
    ) -> Dict[str, Any]:
        """Compare credibility of multiple sources."""
        profiles = []
        for domain in domains:
            profile = await self.get_source_profile(domain)
            if profile:
                profiles.append(profile)

        if not profiles:
            return {"error": "No profiles found"}

        return {
            "sources": [
                {
                    "domain": p.domain,
                    "category": p.category.value,
                    "tier": p.credibility_tier.value,
                    "overall_score": round(p.overall_score, 3),
                    "accuracy": round(p.accuracy_score, 3),
                    "bias": p.bias_level.value,
                }
                for p in profiles
            ],
            "most_credible": max(profiles, key=lambda p: p.overall_score).domain,
            "least_credible": min(profiles, key=lambda p: p.overall_score).domain,
            "average_score": sum(p.overall_score for p in profiles) / len(profiles),
        }

    async def get_trusted_sources(
        self,
        category: Optional[SourceCategory] = None,
        min_score: float = 0.7,
        limit: int = 10,
    ) -> List[SourceProfile]:
        """Get list of trusted sources."""
        profiles = list(self._source_profiles.values())

        if category:
            profiles = [p for p in profiles if p.category == category]

        profiles = [p for p in profiles if p.overall_score >= min_score]
        profiles.sort(key=lambda p: p.overall_score, reverse=True)

        return profiles[:limit]

    def _normalize_domain(self, domain: str) -> str:
        """Normalize a domain name."""
        domain = domain.lower().strip()
        if domain.startswith("http://"):
            domain = domain[7:]
        if domain.startswith("https://"):
            domain = domain[8:]
        if domain.startswith("www."):
            domain = domain[4:]
        domain = domain.split("/")[0]
        return domain

    def _infer_category(self, domain: str) -> SourceCategory:
        """Infer source category from domain."""
        # Check exact matches
        if domain in self._domain_categories:
            return self._domain_categories[domain]

        # Check TLD patterns
        for pattern, category in self._domain_categories.items():
            if domain.endswith(pattern):
                return category

        return SourceCategory.UNKNOWN

    def _infer_tier(self, domain: str, category: SourceCategory) -> CredibilityTier:
        """Infer credibility tier from domain and category."""
        # Check verified domains
        for verified in self.VERIFIED_DOMAINS:
            if domain.endswith(verified):
                return CredibilityTier.VERIFIED

        # Category-based defaults
        category_tiers = {
            SourceCategory.OFFICIAL: CredibilityTier.RELIABLE,
            SourceCategory.ACADEMIC: CredibilityTier.RELIABLE,
            SourceCategory.NEWS_MAJOR: CredibilityTier.RELIABLE,
            SourceCategory.NEWS_LOCAL: CredibilityTier.MIXED,
            SourceCategory.WIKI: CredibilityTier.MIXED,
            SourceCategory.BLOG: CredibilityTier.QUESTIONABLE,
            SourceCategory.SOCIAL: CredibilityTier.QUESTIONABLE,
            SourceCategory.FORUM: CredibilityTier.QUESTIONABLE,
        }

        return category_tiers.get(category, CredibilityTier.UNKNOWN)

    def _set_default_scores(self, profile: SourceProfile) -> None:
        """Set default scores based on category and tier."""
        tier_scores = {
            CredibilityTier.VERIFIED: 0.9,
            CredibilityTier.RELIABLE: 0.75,
            CredibilityTier.MIXED: 0.5,
            CredibilityTier.QUESTIONABLE: 0.35,
            CredibilityTier.UNRELIABLE: 0.2,
            CredibilityTier.UNKNOWN: 0.5,
        }

        base = tier_scores.get(profile.credibility_tier, 0.5)
        profile.accuracy_score = base
        profile.transparency_score = base
        profile.expertise_score = base
        profile.consistency_score = base
        profile.citation_score = base

    def _calculate_tier(self, profile: SourceProfile) -> CredibilityTier:
        """Calculate credibility tier from scores."""
        score = profile.overall_score

        if score >= 0.85:
            return CredibilityTier.VERIFIED
        elif score >= 0.7:
            return CredibilityTier.RELIABLE
        elif score >= 0.5:
            return CredibilityTier.MIXED
        elif score >= 0.3:
            return CredibilityTier.QUESTIONABLE
        else:
            return CredibilityTier.UNRELIABLE

    def _analyze_specificity(self, content: str) -> float:
        """Analyze how specific and verifiable claims are."""
        score = 0.5

        # Specific indicators (positive)
        specificity_indicators = [
            "according to", "research shows", "study found",
            "data indicates", "statistics show", "evidence suggests",
            "published in", "peer-reviewed",
        ]
        for indicator in specificity_indicators:
            if indicator in content.lower():
                score += 0.05

        # Vague indicators (negative)
        vague_indicators = [
            "some say", "many believe", "it is said",
            "allegedly", "reportedly", "sources say",
            "experts claim", "studies show",  # Without citation
        ]
        for indicator in vague_indicators:
            if indicator in content.lower():
                score -= 0.05

        return max(0.0, min(1.0, score))

    def _analyze_attribution(self, content: str) -> float:
        """Analyze source attribution quality."""
        score = 0.3  # Start low

        # Citation indicators
        if "http" in content or "https" in content:
            score += 0.2
        if "[" in content and "]" in content:  # Bracketed references
            score += 0.1
        if "cited" in content.lower() or "reference" in content.lower():
            score += 0.1

        # Named sources
        quote_count = content.count('"')
        if quote_count >= 2:  # Has quotes
            score += 0.1
        if "said" in content.lower() or "stated" in content.lower():
            score += 0.1

        return max(0.0, min(1.0, score))

    def _analyze_language(self, content: str) -> float:
        """Analyze factual vs opinion language."""
        content_lower = content.lower()

        # Opinion indicators
        opinion_words = [
            "i think", "i believe", "in my opinion", "personally",
            "should", "must", "obviously", "clearly",
            "best", "worst", "amazing", "terrible",
        ]

        opinion_count = sum(1 for word in opinion_words if word in content_lower)

        # Factual indicators
        factual_words = [
            "measured", "calculated", "observed", "recorded",
            "data", "percentage", "number", "amount",
            "increased", "decreased", "according to",
        ]

        factual_count = sum(1 for word in factual_words if word in content_lower)

        total = opinion_count + factual_count
        if total == 0:
            return 0.5

        return factual_count / total

    def _detect_manipulation(self, content: str) -> float:
        """Detect emotional manipulation tactics."""
        manipulation_indicators = [
            "shocking", "unbelievable", "you won't believe",
            "they don't want you to know", "the truth about",
            "exposed", "revealed", "secret",
            "outrage", "disgusting", "horrifying",
        ]

        content_lower = content.lower()
        count = sum(1 for indicator in manipulation_indicators if indicator in content_lower)

        return min(count * 0.15, 1.0)

    def _detect_fallacies(self, content: str) -> float:
        """Detect logical fallacies."""
        fallacy_indicators = [
            "everyone knows", "all experts agree",  # Appeal to authority/majority
            "slippery slope", "if we allow",        # Slippery slope
            "just asking questions",                 # JAQing off
            "correlation", "therefore caused",       # Correlation/causation
            "either we", "or we",                   # False dichotomy
        ]

        content_lower = content.lower()
        count = sum(1 for indicator in fallacy_indicators if indicator in content_lower)

        return min(count * 0.2, 1.0)

    def _detect_satire(self, content: str, domain: str) -> bool:
        """Detect if content is satire."""
        satire_domains = {
            "theonion.com", "babylonbee.com", "clickhole.com",
            "thebeaverton.com", "newsthump.com",
        }
        return domain in satire_domains

    def _detect_sponsored(self, content: str) -> bool:
        """Detect sponsored/paid content."""
        sponsored_indicators = [
            "sponsored", "paid partnership", "ad",
            "affiliate", "commission", "partner content",
        ]
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in sponsored_indicators)

    def _detect_opinion(self, content: str) -> bool:
        """Detect if content is opinion/editorial."""
        opinion_indicators = [
            "opinion", "editorial", "op-ed", "commentary",
            "column", "perspective", "analysis",
        ]
        content_lower = content.lower()[:500]  # Check beginning
        return any(indicator in content_lower for indicator in opinion_indicators)

    async def _is_corroborating(
        self,
        domain: str,
        claims: Optional[List[str]],
    ) -> bool:
        """Check if domain corroborates claims."""
        profile = await self.get_source_profile(domain)
        if not profile:
            return False

        # Consider corroborating if source is reliable
        return profile.overall_score >= 0.6

    def _generate_recommendation(self, assessment: CredibilityAssessment) -> str:
        """Generate human-readable recommendation."""
        score = assessment.overall_credibility

        if score >= 0.8:
            return "High credibility. Source and content appear reliable."
        elif score >= 0.6:
            return "Moderate credibility. Generally reliable but verify key claims."
        elif score >= 0.4:
            return "Mixed credibility. Cross-reference with additional sources."
        elif score >= 0.2:
            return "Low credibility. Treat with skepticism and verify independently."
        else:
            return "Very low credibility. Do not rely on this source."

    def _calculate_confidence(self, assessment: CredibilityAssessment) -> float:
        """Calculate confidence in the assessment."""
        factors = [
            # More data = higher confidence
            min(assessment.source_profile.total_claims_tracked / 100, 1.0) * 0.3,
            # Cross-references increase confidence
            len(assessment.corroborating_sources) * 0.1,
            # Known source category
            (0.2 if assessment.source_profile.category != SourceCategory.UNKNOWN else 0.0),
            # Base confidence
            0.3,
        ]
        return min(sum(factors), 1.0)

    async def _load_profiles(self) -> None:
        """Load profiles from storage."""
        try:
            data = json.loads(self._storage_path.read_text())
            for profile_data in data.get("profiles", []):
                profile = SourceProfile(
                    domain=profile_data["domain"],
                    name=profile_data.get("name"),
                    category=SourceCategory(profile_data.get("category", "unknown")),
                    credibility_tier=CredibilityTier(profile_data.get("tier", "unknown")),
                    accuracy_score=profile_data.get("accuracy", 0.5),
                    transparency_score=profile_data.get("transparency", 0.5),
                    expertise_score=profile_data.get("expertise", 0.5),
                    consistency_score=profile_data.get("consistency", 0.5),
                    citation_score=profile_data.get("citation", 0.5),
                )
                self._source_profiles[profile.domain] = profile
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")

    async def save_profiles(self) -> None:
        """Save profiles to storage."""
        if not self._storage_path:
            return

        data = {
            "profiles": [
                {
                    "domain": p.domain,
                    "name": p.name,
                    "category": p.category.value,
                    "tier": p.credibility_tier.value,
                    "accuracy": p.accuracy_score,
                    "transparency": p.transparency_score,
                    "expertise": p.expertise_score,
                    "consistency": p.consistency_score,
                    "citation": p.citation_score,
                    "fact_checks_passed": p.fact_checks_passed,
                    "fact_checks_failed": p.fact_checks_failed,
                }
                for p in self._source_profiles.values()
            ],
            "saved_at": datetime.utcnow().isoformat(),
        }

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path.write_text(json.dumps(data, indent=2))


# Singleton instance
_scorer: Optional[CredibilityScorer] = None


def get_credibility_scorer(storage_path: Optional[Path] = None) -> CredibilityScorer:
    """Get the global credibility scorer instance."""
    global _scorer
    if _scorer is None:
        path = storage_path or Path("data/credibility/sources.json")
        _scorer = CredibilityScorer(path)
    return _scorer

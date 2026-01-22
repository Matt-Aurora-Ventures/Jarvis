#!/usr/bin/env python3
"""
Bags Intel - Founder & Token Research Module
Deep due diligence on token creators and product-market fit analysis
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import aiohttp

logger = logging.getLogger("jarvis.bags_intel.founder_research")


@dataclass
class FounderProfile:
    """Comprehensive founder profile from research"""
    twitter_handle: Optional[str] = None
    twitter_verified: bool = False
    twitter_followers: int = 0
    twitter_account_age_days: int = 0

    linkedin_url: Optional[str] = None
    linkedin_found: bool = False
    linkedin_experience_years: int = 0
    linkedin_companies: List[str] = None

    github_username: Optional[str] = None
    github_repos: int = 0
    github_stars: int = 0

    website_url: Optional[str] = None
    website_professional: bool = False

    # Doxxed status
    is_doxxed: bool = False
    doxx_confidence: float = 0.0  # 0-1
    identity_signals: List[str] = None

    # Social interaction analysis
    interacts_with_known_devs: bool = False
    network_quality_score: float = 0.0  # 0-100
    influential_connections: List[str] = None

    # Experience signals
    past_projects: List[Dict[str, Any]] = None
    technical_background: bool = False
    business_experience: bool = False
    previous_successes: int = 0
    previous_failures: int = 0

    # Risk signals
    red_flags: List[str] = None
    green_flags: List[str] = None

    def __post_init__(self):
        if self.linkedin_companies is None:
            self.linkedin_companies = []
        if self.identity_signals is None:
            self.identity_signals = []
        if self.influential_connections is None:
            self.influential_connections = []
        if self.past_projects is None:
            self.past_projects = []
        if self.red_flags is None:
            self.red_flags = []
        if self.green_flags is None:
            self.green_flags = []


@dataclass
class ProductMarketFit:
    """Product-market fit analysis for token"""
    token_utility: str = "Unknown"  # "Utility", "Meme", "Governance", "Payment", etc.
    utility_score: float = 0.0  # 0-100

    target_market: str = "Unknown"
    market_size_estimate: str = "Unknown"  # "Small", "Medium", "Large", "Massive"

    competition_level: str = "Unknown"  # "None", "Low", "Medium", "High", "Saturated"
    competitive_advantage: str = ""

    demand_signals: List[str] = None
    traction_metrics: Dict[str, Any] = None

    # Community analysis
    community_size: int = 0
    community_engagement: str = "Low"  # "Low", "Medium", "High"
    organic_growth: bool = False

    # Market timing
    market_timing_score: float = 0.0  # 0-100
    timing_rationale: str = ""

    pmf_score: float = 0.0  # Overall 0-100 score

    def __post_init__(self):
        if self.demand_signals is None:
            self.demand_signals = []
        if self.traction_metrics is None:
            self.traction_metrics = {}


class FounderResearcher:
    """
    Researches token founders and product-market fit
    Uses multiple sources to build comprehensive intelligence
    """

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

        # Known dev/influencer Twitter handles (could be loaded from config)
        self.known_devs = {
            "murad_ben", "0xRacer", "ansem", "blknoiz06", "degentradingLSD",
            "cryptocobain", "DeFi_Made_Here", "0xWizard", "teddycleps"
        }

    async def research_founder(
        self,
        twitter_handle: Optional[str] = None,
        wallet_address: Optional[str] = None
    ) -> FounderProfile:
        """
        Comprehensive founder research

        Args:
            twitter_handle: Twitter/X handle
            wallet_address: Solana wallet address

        Returns:
            FounderProfile with all research findings
        """
        profile = FounderProfile()

        if not twitter_handle and not wallet_address:
            logger.warning("No founder identifiers provided")
            return profile

        # Twitter research
        if twitter_handle:
            await self._research_twitter(twitter_handle, profile)
            await self._analyze_social_network(twitter_handle, profile)

        # LinkedIn search (by name extracted from Twitter bio)
        if profile.twitter_handle:
            await self._search_linkedin(profile)

        # GitHub search
        if profile.twitter_handle:
            await self._search_github(profile)

        # Website analysis
        # TODO: Extract from token metadata or Twitter bio

        # Doxxed verification
        self._calculate_doxx_status(profile)

        # Calculate network quality
        self._calculate_network_quality(profile)

        # Identify red/green flags
        self._identify_signals(profile)

        return profile

    async def _research_twitter(self, handle: str, profile: FounderProfile):
        """Research Twitter profile"""
        profile.twitter_handle = handle.lstrip('@')

        # TODO: Use Twitter API to get:
        # - Verified status
        # - Follower count
        # - Account creation date
        # - Tweet history
        # - Bio information

        # Placeholder logic (would use real API)
        profile.twitter_verified = False  # Check blue checkmark
        profile.twitter_followers = 0  # Get follower count
        profile.twitter_account_age_days = 0  # Calculate age

        logger.info(f"Researched Twitter: @{handle}")

    async def _analyze_social_network(self, handle: str, profile: FounderProfile):
        """Analyze who founder interacts with"""

        # TODO: Use Twitter API to analyze:
        # - Who they follow
        # - Who they reply to frequently
        # - Quote tweets
        # - Mentions

        # Check if they interact with known devs
        # (Placeholder - would use real interaction data)
        profile.interacts_with_known_devs = False
        profile.influential_connections = []

        logger.info(f"Analyzed social network for @{handle}")

    async def _search_linkedin(self, profile: FounderProfile):
        """Search for LinkedIn profile"""

        # TODO: LinkedIn search by name/handle
        # Would require:
        # - LinkedIn API access or scraping
        # - Name extraction from Twitter bio
        # - Profile matching

        # Extract potential name from Twitter handle or bio
        # Search LinkedIn
        # If found, extract:
        # - Work experience
        # - Education
        # - Skills
        # - Connections

        profile.linkedin_found = False
        profile.linkedin_url = None
        profile.linkedin_experience_years = 0
        profile.linkedin_companies = []

        logger.info("LinkedIn search performed")

    async def _search_github(self, profile: FounderProfile):
        """Search for GitHub profile"""

        # TODO: GitHub API search
        # Try common username variations
        # If found, analyze:
        # - Repository count
        # - Stars received
        # - Contribution history
        # - Language expertise

        profile.github_username = None
        profile.github_repos = 0
        profile.github_stars = 0

        logger.info("GitHub search performed")

    def _calculate_doxx_status(self, profile: FounderProfile):
        """Calculate if founder is doxxed and confidence level"""

        confidence_signals = []
        confidence_score = 0.0

        # LinkedIn found with real name
        if profile.linkedin_found:
            confidence_signals.append("LinkedIn profile found")
            confidence_score += 0.4

        # Twitter verified
        if profile.twitter_verified:
            confidence_signals.append("Twitter verified")
            confidence_score += 0.2

        # Professional website
        if profile.website_professional:
            confidence_signals.append("Professional website")
            confidence_score += 0.15

        # GitHub profile
        if profile.github_username:
            confidence_signals.append("GitHub profile")
            confidence_score += 0.1

        # Twitter account age > 1 year
        if profile.twitter_account_age_days > 365:
            confidence_signals.append("Established Twitter account")
            confidence_score += 0.1

        # Substantial follower count
        if profile.twitter_followers > 1000:
            confidence_signals.append("Significant following")
            confidence_score += 0.05

        profile.is_doxxed = confidence_score >= 0.5
        profile.doxx_confidence = min(1.0, confidence_score)
        profile.identity_signals = confidence_signals

    def _calculate_network_quality(self, profile: FounderProfile):
        """Calculate quality of founder's network"""

        score = 0.0

        # Interacts with known devs
        if profile.interacts_with_known_devs:
            score += 40

        # Has influential connections
        if len(profile.influential_connections) > 0:
            score += min(30, len(profile.influential_connections) * 10)

        # Follower quality (verified followers, devs, etc.)
        # TODO: Analyze follower list

        # Engagement quality (meaningful conversations vs spam)
        # TODO: Analyze tweet content

        profile.network_quality_score = min(100, score)

    def _identify_signals(self, profile: FounderProfile):
        """Identify red and green flags"""

        # Green flags
        if profile.is_doxxed:
            profile.green_flags.append("✅ Founder is doxxed")

        if profile.linkedin_found:
            profile.green_flags.append("✅ LinkedIn profile found")

        if profile.github_username:
            profile.green_flags.append("✅ Active on GitHub")

        if profile.twitter_account_age_days > 365:
            profile.green_flags.append("✅ Established Twitter presence")

        if profile.interacts_with_known_devs:
            profile.green_flags.append("✅ Connected to known developers")

        if profile.previous_successes > 0:
            profile.green_flags.append(f"✅ {profile.previous_successes} previous successful projects")

        # Red flags
        if not profile.twitter_handle:
            profile.red_flags.append("⚠️ No Twitter presence")

        if profile.twitter_account_age_days < 90:
            profile.red_flags.append("⚠️ Very new Twitter account")

        if profile.twitter_followers < 100:
            profile.red_flags.append("⚠️ Low follower count")

        if not profile.linkedin_found and not profile.github_username:
            profile.red_flags.append("⚠️ No professional profiles found")

        if profile.previous_failures > 2:
            profile.red_flags.append(f"⚠️ {profile.previous_failures} previous failed projects")

        if not profile.is_doxxed:
            profile.red_flags.append("⚠️ Anonymous founder")


class ProductMarketFitAnalyzer:
    """
    Analyzes product-market fit for tokens
    Evaluates utility, market demand, competition, and timing
    """

    async def analyze_pmf(
        self,
        token_name: str,
        token_description: str,
        token_website: Optional[str] = None,
        social_links: Optional[Dict[str, str]] = None
    ) -> ProductMarketFit:
        """
        Analyze product-market fit

        Args:
            token_name: Name of token
            token_description: Description from token metadata
            token_website: Website URL
            social_links: Social media links

        Returns:
            ProductMarketFit analysis
        """
        pmf = ProductMarketFit()

        # Classify token utility
        await self._classify_utility(token_name, token_description, pmf)

        # Analyze target market
        await self._analyze_market(token_description, pmf)

        # Assess competition
        await self._assess_competition(token_name, token_description, pmf)

        # Identify demand signals
        await self._identify_demand_signals(social_links, pmf)

        # Analyze community
        await self._analyze_community(social_links, pmf)

        # Calculate overall PMF score
        self._calculate_pmf_score(pmf)

        return pmf

    async def _classify_utility(self, name: str, description: str, pmf: ProductMarketFit):
        """Classify token utility type"""

        desc_lower = description.lower()
        name_lower = name.lower()

        # Pattern matching for utility type
        if any(word in desc_lower for word in ["game", "gaming", "play", "nft"]):
            pmf.token_utility = "Gaming/NFT"
            pmf.utility_score = 70
        elif any(word in desc_lower for word in ["defi", "swap", "lend", "stake", "yield"]):
            pmf.token_utility = "DeFi"
            pmf.utility_score = 80
        elif any(word in desc_lower for word in ["govern", "vote", "dao", "proposal"]):
            pmf.token_utility = "Governance"
            pmf.utility_score = 60
        elif any(word in desc_lower for word in ["pay", "payment", "transfer", "currency"]):
            pmf.token_utility = "Payment"
            pmf.utility_score = 50
        elif any(word in desc_lower for word in ["meme", "fun", "community"]):
            pmf.token_utility = "Meme/Community"
            pmf.utility_score = 30
        else:
            pmf.token_utility = "Unknown"
            pmf.utility_score = 20

    async def _analyze_market(self, description: str, pmf: ProductMarketFit):
        """Analyze target market size"""

        # TODO: Use AI to extract target market from description
        # TODO: Research market size for that category

        pmf.target_market = "Unknown"
        pmf.market_size_estimate = "Unknown"

    async def _assess_competition(self, name: str, description: str, pmf: ProductMarketFit):
        """Assess competition level"""

        # TODO: Search for similar tokens
        # TODO: Analyze feature differentiation

        pmf.competition_level = "Unknown"
        pmf.competitive_advantage = ""

    async def _identify_demand_signals(self, social_links: Optional[Dict], pmf: ProductMarketFit):
        """Identify signals of market demand"""

        # TODO: Analyze:
        # - Social media engagement
        # - Community growth rate
        # - Search volume
        # - Similar project success

        pmf.demand_signals = []

    async def _analyze_community(self, social_links: Optional[Dict], pmf: ProductMarketFit):
        """Analyze community size and engagement"""

        # TODO: Aggregate followers from all platforms
        # TODO: Analyze engagement rates
        # TODO: Check for organic vs bot activity

        pmf.community_size = 0
        pmf.community_engagement = "Low"
        pmf.organic_growth = False

    def _calculate_pmf_score(self, pmf: ProductMarketFit):
        """Calculate overall PMF score"""

        score = 0.0

        # Utility score contribution (30%)
        score += pmf.utility_score * 0.3

        # Market size (20%)
        market_size_map = {
            "Massive": 100,
            "Large": 80,
            "Medium": 60,
            "Small": 40,
            "Unknown": 20
        }
        score += market_size_map.get(pmf.market_size_estimate, 20) * 0.2

        # Competition (15% - lower is better)
        competition_map = {
            "None": 100,
            "Low": 80,
            "Medium": 60,
            "High": 40,
            "Saturated": 20,
            "Unknown": 50
        }
        score += competition_map.get(pmf.competition_level, 50) * 0.15

        # Community (20%)
        engagement_map = {
            "High": 100,
            "Medium": 60,
            "Low": 30
        }
        community_score = engagement_map.get(pmf.community_engagement, 30)
        if pmf.organic_growth:
            community_score = min(100, community_score * 1.2)
        score += community_score * 0.2

        # Demand signals (15%)
        demand_score = min(100, len(pmf.demand_signals) * 20)
        score += demand_score * 0.15

        pmf.pmf_score = min(100, score)


# Global instances
founder_researcher = FounderResearcher()
pmf_analyzer = ProductMarketFitAnalyzer()


async def research_token_comprehensive(
    token_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Comprehensive research on token and founder

    Args:
        token_data: Token graduation event data

    Returns:
        Dict with founder_profile and product_market_fit
    """
    twitter_handle = token_data.get("creator_twitter")
    wallet_address = token_data.get("creator_wallet")

    # Research founder
    founder_profile = await founder_researcher.research_founder(
        twitter_handle=twitter_handle,
        wallet_address=wallet_address
    )

    # Analyze PMF
    pmf = await pmf_analyzer.analyze_pmf(
        token_name=token_data.get("token_name", ""),
        token_description=token_data.get("description", ""),
        token_website=token_data.get("website"),
        social_links=token_data.get("social_links", {})
    )

    return {
        "founder_profile": asdict(founder_profile),
        "product_market_fit": asdict(pmf),
        "research_timestamp": datetime.now().isoformat()
    }

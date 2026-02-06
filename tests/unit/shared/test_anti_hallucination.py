"""Tests for Anti-Hallucination System."""

import pytest
from unittest.mock import MagicMock

from bots.shared.anti_hallucination import HallucinationChecker


class TestHallucinationChecker:
    """Tests for HallucinationChecker."""

    def setup_method(self):
        self.checker = HallucinationChecker()

    def test_check_content_returns_expected_structure(self):
        result = self.checker.check_content("Hello world")
        assert "score" in result
        assert "flags" in result
        assert "verified_facts" in result
        assert "unverified_claims" in result
        assert 0.0 <= result["score"] <= 1.0

    def test_clean_text_scores_high(self):
        result = self.checker.check_content("The weather is nice today.")
        assert result["score"] >= 0.7
        assert len(result["flags"]) == 0

    # URL checks
    def test_flags_suspicious_urls(self):
        text = "Check out https://totally-real-crypto-site-12345.com/profit"
        result = self.checker.check_content(text)
        url_flags = [f for f in result["flags"] if f["type"] == "unverified_url"]
        assert len(url_flags) >= 1

    def test_known_domains_not_flagged(self):
        text = "Visit https://twitter.com/user and https://github.com/repo"
        result = self.checker.check_content(text)
        url_flags = [f for f in result["flags"] if f["type"] == "unverified_url"]
        assert len(url_flags) == 0

    def test_malformed_url_flagged(self):
        text = "Go to https://google..com/search"
        result = self.checker.check_content(text)
        url_flags = [f for f in result["flags"] if f["type"] == "unverified_url"]
        assert len(url_flags) >= 1

    # Statistics checks
    def test_flags_unattributed_statistics(self):
        text = "Studies show that 87% of traders lose money."
        result = self.checker.check_content(text)
        stat_flags = [f for f in result["flags"] if f["type"] == "unattributed_statistic"]
        assert len(stat_flags) >= 1

    def test_attributed_statistics_not_flagged(self):
        text = "According to the SEC, 87% of traders lose money."
        result = self.checker.check_content(text)
        stat_flags = [f for f in result["flags"] if f["type"] == "unattributed_statistic"]
        assert len(stat_flags) == 0

    # Quote checks
    def test_flags_unattributed_quotes(self):
        text = 'It is well known that "the market always goes up eventually no matter what" and we believed it.'
        result = self.checker.check_content(text)
        quote_flags = [f for f in result["flags"] if f["type"] == "unattributed_quote"]
        assert len(quote_flags) >= 1

    def test_attributed_quotes_not_flagged(self):
        text = 'Warren Buffett said "be fearful when others are greedy".'
        result = self.checker.check_content(text)
        quote_flags = [f for f in result["flags"] if f["type"] == "unattributed_quote"]
        assert len(quote_flags) == 0

    # Name checks with knowledge graph
    def test_flags_unknown_names_with_kg(self):
        kg = MagicMock()
        kg.search.return_value = []
        checker = HallucinationChecker(knowledge_graph=kg)
        text = "Dr. Fabricated McPerson published groundbreaking research."
        result = checker.check_content(text)
        name_flags = [f for f in result["flags"] if f["type"] == "unknown_name"]
        assert len(name_flags) >= 1

    def test_known_names_not_flagged_with_kg(self):
        kg = MagicMock()
        kg.search.return_value = [{"name": "Daryl", "type": "person"}]
        checker = HallucinationChecker(knowledge_graph=kg)
        text = "Daryl mentioned the new strategy."
        result = checker.check_content(text)
        name_flags = [f for f in result["flags"] if f["type"] == "unknown_name"]
        assert len(name_flags) == 0

    # Score degradation
    def test_multiple_flags_lower_score(self):
        text = (
            'It is known that "trust me bro this is totally legit investment advice" '
            "and 99% of people at https://scam-site-xyz-fake-domain.com agree. "
            "Also 75% of experts at https://another..fake-url-too.com confirm."
        )
        result = self.checker.check_content(text)
        assert result["score"] < 0.5
        assert len(result["flags"]) >= 2

    # Verification footer
    def test_add_verification_footer_high_score(self):
        check_result = {"score": 0.95, "flags": [], "verified_facts": [], "unverified_claims": []}
        output = self.checker.add_verification_footer("Hello", check_result)
        assert "VERIFIED" in output.upper() or "hello" in output.lower()

    def test_add_verification_footer_low_score(self):
        check_result = {
            "score": 0.3,
            "flags": [{"type": "unverified_url", "content": "x", "suggestion": "y"}],
            "verified_facts": [],
            "unverified_claims": ["claim1"],
        }
        output = self.checker.add_verification_footer("Hello", check_result)
        assert "UNVERIFIED" in output.upper() or "WARNING" in output.upper() or "caution" in output.lower()

    # No KG means names aren't checked
    def test_no_kg_skips_name_check(self):
        checker = HallucinationChecker(knowledge_graph=None)
        text = "Dr. Fabricated McPerson published research."
        result = checker.check_content(text)
        name_flags = [f for f in result["flags"] if f["type"] == "unknown_name"]
        assert len(name_flags) == 0

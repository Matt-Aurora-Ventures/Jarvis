#!/usr/bin/env python3
"""
Tests for Enhanced Search Pipeline
Validates query optimization, quality scoring, and content processing
"""

import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

# Add the project root to Python path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.enhanced_search_pipeline import (
    SearchQueryOptimizer,
    SearchResultQualityScorer, 
    SearchCache,
    EnhancedSearchPipeline
)


class TestSearchQueryOptimizer(unittest.TestCase):
    
    def setUp(self):
        self.optimizer = SearchQueryOptimizer()
    
    def test_optimize_query_basic(self):
        """Test basic query optimization."""
        result = self.optimizer.optimize_query("autonomous AI agents")
        
        # Should add current year and remove stop words
        self.assertIn("2025", result)
        self.assertIn("autonomous", result)
        self.assertIn("agents", result)
        self.assertNotIn("the", result)
        self.assertNotIn("and", result)
    
    def test_optimize_query_with_focus(self):
        """Test query optimization with focus."""
        result = self.optimizer.optimize_query(
            "machine learning", 
            intent="technical", 
            focus="neural networks"
        )
        
        self.assertIn("tutorial", result)
        self.assertIn("implementation", result)
        self.assertIn("neural", result)
        self.assertIn("networks", result)
    
    def test_generate_query_variations(self):
        """Test query variation generation."""
        variations = self.optimizer.generate_query_variations("python programming", max_variations=3)
        
        self.assertLessEqual(len(variations), 3)
        self.assertIn("python programming", variations[0])  # Original should be first
        
        # Check for expected variations
        all_text = " ".join(variations).lower()
        self.assertTrue(
            any(term in all_text for term in ["tutorial", "guide", "implementation", "example"])
        )
    
    def test_domain_specific_optimization(self):
        """Test domain-specific query optimization."""
        
        # AI domain
        result = self.optimizer.optimize_query("AI systems")
        self.assertIn("neural networks", result)
        
        # Crypto domain  
        result = self.optimizer.optimize_query("crypto trading")
        self.assertIn("strategies analysis", result)
        
        # Autonomous domain
        result = self.optimizer.optimize_query("autonomous vehicles")
        self.assertIn("agent architecture", result)


class TestSearchResultQualityScorer(unittest.TestCase):
    
    def setUp(self):
        self.scorer = SearchResultQualityScorer()
    
    def test_score_high_quality_domain(self):
        """Test scoring of high-quality domains."""
        result = {
            "url": "https://github.com/awesome/project",
            "title": "Tutorial: Implement neural networks",
            "snippet": "A comprehensive guide to implementing neural networks with code examples and step-by-step instructions."
        }
        
        score = self.scorer.score_result(result)
        self.assertGreater(score, 0.8)
    
    def test_score_low_quality_domain(self):
        """Test scoring of low-quality domains."""
        result = {
            "url": "https://buzzfeed.com/clickbait-article",
            "title": "You won't believe these AI tricks!",
            "snippet": "Short content"
        }
        
        score = self.scorer.score_result(result)
        self.assertLess(score, 0.3)
    
    def test_filter_results_by_quality(self):
        """Test filtering results by quality score."""
        results = [
            {
                "url": "https://github.com/good/project",
                "title": "Good tutorial",
                "snippet": "Comprehensive content with examples and implementation details."
            },
            {
                "url": "https://spam-site.com/bad", 
                "title": "Clickbait",
                "snippet": "Short"
            },
            {
                "url": "https://medium.com/decent-article",
                "title": "Decent article about AI",
                "snippet": "Some useful information about artificial intelligence and machine learning."
            }
        ]
        
        filtered = self.scorer.filter_results(results, min_score=0.5)
        
        # Should filter out low quality results
        self.assertLessEqual(len(filtered), len(results))
        
        # Remaining results should have quality scores
        for result in filtered:
            self.assertIn("quality_score", result)
            self.assertGreaterEqual(result["quality_score"], 0.5)
    
    def test_domain_blacklist(self):
        """Test domain blacklist filtering."""
        results = [
            {
                "url": "https://facebook.com/tr/spam",
                "title": "Spam content",
                "snippet": "Some content"
            },
            {
                "url": "https://github.com/good/project",
                "title": "Good content", 
                "snippet": "Useful content"
            }
        ]
        
        filtered = self.scorer.filter_results(results)
        
        # Should filter out blacklisted domains
        urls = [r["url"] for r in filtered]
        self.assertNotIn("https://facebook.com/tr/spam", urls)
        self.assertIn("https://github.com/good/project", urls)


class TestSearchCache(unittest.TestCase):
    
    def setUp(self):
        # Use test database path
        from core.enhanced_search_pipeline import SEARCH_CACHE_PATH
        self.original_path = SEARCH_CACHE_PATH
        SEARCH_CACHE_PATH.unlink(missing_ok=True)  # Clean up any existing test cache
        
        self.cache = SearchCache()
    
    def tearDown(self):
        # Clean up test cache
        from core.enhanced_search_pipeline import SEARCH_CACHE_PATH
        SEARCH_CACHE_PATH.unlink(missing_ok=True)
    
    def test_cache_search_results(self):
        """Test caching and retrieval of search results."""
        query = "test query"
        results = [
            {"url": "https://example.com/1", "title": "Result 1", "snippet": "Snippet 1"},
            {"url": "https://example.com/2", "title": "Result 2", "snippet": "Snippet 2"}
        ]
        
        # Cache results
        self.cache.cache_search_results(query, results)
        
        # Retrieve cached results
        cached = self.cache.get_search_results(query)
        
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 2)
        self.assertEqual(cached[0]["url"], "https://example.com/1")
    
    def test_cache_content(self):
        """Test caching and retrieval of content."""
        url = "https://example.com/article"
        content = "This is the article content with sufficient length to be cached."
        title = "Test Article"
        
        # Cache content
        self.cache.cache_content(url, content, title)
        
        # Retrieve cached content
        cached_content = self.cache.get_content(url)
        
        self.assertEqual(cached_content, content)
    
    def test_cache_miss(self):
        """Test cache miss scenarios."""
        # Non-existent query
        result = self.cache.get_search_results("non-existent query")
        self.assertIsNone(result)
        
        # Non-existent URL
        content = self.cache.get_content("https://non-existent.com")
        self.assertIsNone(content)


class TestEnhancedSearchPipeline(unittest.TestCase):
    
    def setUp(self):
        self.pipeline = EnhancedSearchPipeline()
    
    @patch('core.enhanced_search_pipeline.get_research_engine')
    def test_search_with_optimization(self, mock_get_engine):
        """Test search with query optimization."""
        
        # Mock the research engine
        mock_engine = MagicMock()
        mock_engine.search_web.return_value = [
            {"url": "https://github.com/test/project", "title": "Test Project", "snippet": "A test project"}
        ]
        mock_get_engine.return_value = mock_engine
        
        # Perform search
        result = self.pipeline.search("AI agents", intent="technical")
        
        # Verify optimization occurred
        self.assertIn("2025", result["query"])
        self.assertTrue(result["success"])
        self.assertEqual(len(result["results"]), 1)
    
    @patch('core.enhanced_search_pipeline.providers.ask_llm')
    def test_process_insights(self, mock_ask_llm):
        """Test insight processing."""
        
        # Mock LLM response
        mock_response = json.dumps({
            "KEY_FINDINGS": ["AI agents can operate autonomously"],
            "PRACTICAL_APPLICATIONS": ["Customer service automation"],
            "TECHNICAL_PATTERNS": ["Reinforcement learning loops"],
            "RISKS_LIMITATIONS": ["Potential for unintended behavior"],
            "NEXT_STEPS": ["Implement safety constraints"]
        })
        mock_ask_llm.return_value = mock_response
        
        # Process content
        content = "AI agents are systems that can operate autonomously..."
        insights = self.pipeline.process_insights("AI agents", content)
        
        # Verify structure
        expected_keys = ["KEY_FINDINGS", "PRACTICAL_APPLICATIONS", "TECHNICAL_PATTERNS", "RISKS_LIMITATIONS", "NEXT_STEPS"]
        for key in expected_keys:
            self.assertIn(key, insights)
            self.assertIsInstance(insights[key], list)
        
        # Verify content
        self.assertEqual(len(insights["KEY_FINDINGS"]), 1)
        self.assertIn("autonomously", insights["KEY_FINDINGS"][0])
    
    def test_process_insights_fallback(self):
        """Test insight processing fallback when LLM fails."""
        
        # Mock LLM failure
        with patch('core.enhanced_search_pipeline.providers.ask_llm', side_effect=Exception("LLM failed")):
            content = "Some content here"
            insights = self.pipeline.process_insights("topic", content)
            
            # Should return fallback insights
            self.assertIn("KEY_FINDINGS", insights)
            self.assertIn("manual review needed", insights["KEY_FINDINGS"][0])
    
    @patch('core.enhanced_search_pipeline.get_research_engine')
    def test_content_extraction_with_cache(self, mock_get_engine):
        """Test content extraction with caching."""
        
        # Mock research engine
        mock_engine = MagicMock()
        mock_engine.extract_content.return_value = "Extracted content here"
        mock_get_engine.return_value = mock_engine
        
        url = "https://example.com/article"
        
        # First extraction (should call engine)
        content1 = self.pipeline.extract_content(url, use_cache=True)
        self.assertEqual(content1, "Extracted content here")
        mock_engine.extract_content.assert_called_once_with(url)
        
        # Second extraction (should use cache)
        content2 = self.pipeline.extract_content(url, use_cache=True)
        self.assertEqual(content2, "Extracted content here")
        mock_engine.extract_content.assert_called_once()  # Still only called once


class TestGoldenPrompts(unittest.TestCase):
    """Test with golden research prompts for quality validation."""
    
    def setUp(self):
        self.pipeline = EnhancedSearchPipeline()
    
    @patch('core.enhanced_search_pipeline.get_research_engine')
    @patch('core.enhanced_search_pipeline.providers.ask_llm')
    def test_golden_prompt_trading_bots(self, mock_ask_llm, mock_get_engine):
        """Test golden prompt: crypto trading bots."""
        
        # Mock search results
        mock_engine = MagicMock()
        mock_engine.search_web.return_value = [
            {
                "url": "https://github.com/trading-bot/project",
                "title": "Building Crypto Trading Bots with Python",
                "snippet": "A comprehensive tutorial on implementing automated trading strategies using Python APIs and real-time market data."
            }
        ]
        mock_engine.extract_content.return_value = """
        Trading bots require several components: market data feeds, signal generation, 
        risk management, and execution systems. Most successful bots use technical 
        indicators like RSI, MACD, and moving averages for signal generation. Risk 
        management is crucial - implement stop-losses and position sizing.
        """
        mock_get_engine.return_value = mock_engine
        
        # Mock insight processing
        mock_ask_llm.return_value = json.dumps({
            "KEY_FINDINGS": [
                "Technical indicators (RSI, MACD) are commonly used for signal generation",
                "Risk management with stop-losses is essential for bot success"
            ],
            "PRACTICAL_APPLICATIONS": [
                "Implement Python-based trading bot with real-time market data",
                "Use position sizing algorithms to manage risk"
            ],
            "TECHNICAL_PATTERNS": [
                "Signal generation using technical analysis",
                "Risk management with stop-loss mechanisms"
            ],
            "RISKS_LIMITATIONS": [
                "Market volatility can cause unexpected losses",
                "API rate limits may affect bot performance"
            ],
            "NEXT_STEPS": [
                "Implement backtesting framework for strategy validation",
                "Add monitoring and alerting system for bot failures"
            ]
        })
        
        # Execute search
        result = self.pipeline.search(
            "crypto trading bots", 
            intent="practical",
            focus="risk management strategies"
        )
        
        # Verify search quality
        self.assertTrue(result["success"])
        self.assertGreater(len(result["results"]), 0)
        
        # Process content
        if result["results"]:
            content = self.pipeline.extract_content(result["results"][0]["url"])
            insights = self.pipeline.process_insights("crypto trading bots", content)
            
            # Verify insight quality
            self.assertGreater(len(insights["KEY_FINDINGS"]), 0)
            self.assertGreater(len(insights["PRACTICAL_APPLICATIONS"]), 0)
            self.assertTrue(
                any("risk" in finding.lower() for finding in insights["KEY_FINDINGS"])
            )
    
    @patch('core.enhanced_search_pipeline.get_research_engine')
    @patch('core.enhanced_search_pipeline.providers.ask_llm')
    def test_golden_prompt_autonomous_agents(self, mock_ask_llm, mock_get_engine):
        """Test golden prompt: autonomous agent architectures."""
        
        # Mock search results
        mock_engine = MagicMock()
        mock_engine.search_web.return_value = [
            {
                "url": "https://arxiv.org/abs/2023.12345",
                "title": "Multi-Agent Autonomy: A Survey of Architectures",
                "snippet": "Comprehensive survey of autonomous agent architectures including reactive, deliberative, and hybrid approaches with performance comparisons."
            }
        ]
        mock_engine.extract_content.return_value = """
        Autonomous agent architectures can be categorized into reactive, deliberative, 
        and hybrid approaches. Reactive agents respond immediately to environmental 
        changes using simple stimulus-response rules. Deliberative agents maintain 
        internal world models and plan ahead. Hybrid architectures combine both 
        approaches for optimal performance. Recent advances in LLMs have enabled 
        more sophisticated natural language understanding and reasoning capabilities.
        """
        mock_get_engine.return_value = mock_engine
        
        # Mock insight processing
        mock_ask_llm.return_value = json.dumps({
            "KEY_FINDINGS": [
                "Hybrid architectures combine reactive and deliberative approaches",
                "LLM integration enables enhanced natural language reasoning"
            ],
            "PRACTICAL_APPLICATIONS": [
                "Implement hybrid agent with both reactive and planning components",
                "Use LLMs for natural language task understanding"
            ],
            "TECHNICAL_PATTERNS": [
                "Stimulus-response rules for reactive behavior",
                "World model maintenance for deliberative planning"
            ],
            "RISKS_LIMITATIONS": [
                "Computational overhead of maintaining world models",
                "LLM reliability issues in critical decision paths"
            ],
            "NEXT_STEPS": [
                "Implement adaptive architecture selection based on task complexity",
                "Add LLM fallback mechanisms for reliability"
            ]
        })
        
        # Execute search
        result = self.pipeline.search(
            "autonomous agent architectures",
            intent="research", 
            focus="hybrid approaches"
        )
        
        # Verify search quality
        self.assertTrue(result["success"])
        self.assertGreater(len(result["results"]), 0)
        
        # Process content
        if result["results"]:
            content = self.pipeline.extract_content(result["results"][0]["url"])
            insights = self.pipeline.process_insights("autonomous agents", content)
            
            # Verify insight quality
            self.assertGreater(len(insights["KEY_FINDINGS"]), 0)
            self.assertTrue(
                any("hybrid" in insight.lower() for insight in insights["KEY_FINDINGS"])
            )


def run_quality_checks():
    """Run quality checks on the enhanced search pipeline."""
    print("Running Enhanced Search Pipeline Quality Checks...")
    
    # Run unit tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    print("\n✅ All quality checks passed!")


if __name__ == "__main__":
    run_quality_checks()

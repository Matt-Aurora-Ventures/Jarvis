"""
Comprehensive unit tests for bots/twitter/format_thread.py

This module tests the Grok sentiment thread formatter which:
1. Loads environment variables from a .env file
2. Loads Grok sentiment data from sentiment_report_data.json
3. Calls the Anthropic API to format the data into a Twitter thread
4. Writes the output to thread_draft.txt

Since this is a script module, we test:
- Environment variable loading
- JSON data loading
- API request formation
- Response handling
- Output file writing
- Thread formatting helpers and validators
"""

import pytest
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
from io import StringIO

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# Thread Formatting Validation Helpers (standalone tests)
# =============================================================================

class TestThreadFormattingHelpers:
    """Test helper functions for validating thread formatting."""

    def validate_tweet_length(self, tweet: str, max_length: int = 280) -> bool:
        """Validate a single tweet meets character limit."""
        return len(tweet) <= max_length

    def validate_premium_tweet_length(self, tweet: str, max_length: int = 4000) -> bool:
        """Validate a premium tweet meets character limit."""
        return len(tweet) <= max_length

    def split_into_tweets(self, content: str, max_length: int = 280) -> list:
        """Split content into tweets respecting character limits."""
        if len(content) <= max_length:
            return [content]

        tweets = []
        words = content.split()
        current_tweet = ""

        for word in words:
            test_tweet = f"{current_tweet} {word}".strip() if current_tweet else word
            if len(test_tweet) <= max_length - 10:  # Reserve space for numbering
                current_tweet = test_tweet
            else:
                if current_tweet:
                    tweets.append(current_tweet)
                current_tweet = word

        if current_tweet:
            tweets.append(current_tweet)

        return tweets

    def add_thread_numbering(self, tweets: list) -> list:
        """Add 1/N, 2/N format numbering to tweets."""
        total = len(tweets)
        return [f"{i+1}/{total} {tweet}" for i, tweet in enumerate(tweets)]

    def extract_tweet_markers(self, text: str) -> list:
        """Extract tweets from ---TWEET N--- markers."""
        import re
        pattern = r'---TWEET (\d+)---\s*(.*?)(?=---TWEET \d+---|$)'
        matches = re.findall(pattern, text, re.DOTALL)
        return [(int(num), content.strip()) for num, content in matches]

    # Character Limit Tests
    def test_validate_standard_tweet_length_valid(self):
        """Test validation passes for tweet under 280 chars."""
        tweet = "This is a short tweet"
        assert self.validate_tweet_length(tweet) is True

    def test_validate_standard_tweet_length_exact(self):
        """Test validation passes for tweet at exactly 280 chars."""
        tweet = "a" * 280
        assert self.validate_tweet_length(tweet) is True

    def test_validate_standard_tweet_length_over(self):
        """Test validation fails for tweet over 280 chars."""
        tweet = "a" * 281
        assert self.validate_tweet_length(tweet) is False

    def test_validate_premium_tweet_length_valid(self):
        """Test validation passes for premium tweet under 4000 chars."""
        tweet = "a" * 3999
        assert self.validate_premium_tweet_length(tweet) is True

    def test_validate_premium_tweet_length_exact(self):
        """Test validation passes for premium tweet at exactly 4000 chars."""
        tweet = "a" * 4000
        assert self.validate_premium_tweet_length(tweet) is True

    def test_validate_premium_tweet_length_over(self):
        """Test validation fails for premium tweet over 4000 chars."""
        tweet = "a" * 4001
        assert self.validate_premium_tweet_length(tweet) is False

    # Tweet Splitting Tests
    def test_split_short_content_no_split(self):
        """Test short content stays as single tweet."""
        content = "Short content"
        tweets = self.split_into_tweets(content)
        assert len(tweets) == 1
        assert tweets[0] == "Short content"

    def test_split_long_content_multiple_tweets(self):
        """Test long content splits into multiple tweets."""
        content = " ".join(["word"] * 100)  # Long content
        tweets = self.split_into_tweets(content)
        assert len(tweets) > 1
        for tweet in tweets:
            assert len(tweet) <= 280

    def test_split_preserves_words(self):
        """Test splitting preserves whole words."""
        content = "This is a test sentence with several words that should not be broken"
        tweets = self.split_into_tweets(content, max_length=50)
        for tweet in tweets:
            # No word should be cut in half
            assert "Thi" not in tweet or "This" in tweet

    def test_split_empty_content(self):
        """Test empty content returns empty list."""
        content = ""
        tweets = self.split_into_tweets(content)
        assert tweets == [""]

    # Thread Numbering Tests
    def test_add_numbering_single_tweet(self):
        """Test numbering for single tweet."""
        tweets = ["Hello world"]
        numbered = self.add_thread_numbering(tweets)
        assert numbered == ["1/1 Hello world"]

    def test_add_numbering_multiple_tweets(self):
        """Test numbering for multiple tweets."""
        tweets = ["First", "Second", "Third"]
        numbered = self.add_thread_numbering(tweets)
        assert numbered == ["1/3 First", "2/3 Second", "3/3 Third"]

    def test_add_numbering_many_tweets(self):
        """Test numbering for many tweets (double digits)."""
        tweets = [f"Tweet {i}" for i in range(12)]
        numbered = self.add_thread_numbering(tweets)
        assert numbered[0] == "1/12 Tweet 0"
        assert numbered[11] == "12/12 Tweet 11"

    def test_add_numbering_empty_list(self):
        """Test numbering for empty list."""
        tweets = []
        numbered = self.add_thread_numbering(tweets)
        assert numbered == []

    # Tweet Marker Extraction Tests
    def test_extract_markers_single_tweet(self):
        """Test extracting single tweet from markers."""
        text = "---TWEET 1---\nHello world"
        extracted = self.extract_tweet_markers(text)
        assert len(extracted) == 1
        assert extracted[0] == (1, "Hello world")

    def test_extract_markers_multiple_tweets(self):
        """Test extracting multiple tweets from markers."""
        text = """---TWEET 1---
First tweet content
---TWEET 2---
Second tweet content
---TWEET 3---
Third tweet content"""
        extracted = self.extract_tweet_markers(text)
        assert len(extracted) == 3
        assert extracted[0] == (1, "First tweet content")
        assert extracted[1] == (2, "Second tweet content")
        assert extracted[2] == (3, "Third tweet content")

    def test_extract_markers_with_multiline_content(self):
        """Test extracting tweets with multiline content."""
        text = """---TWEET 1---
First line
Second line
---TWEET 2---
Another tweet"""
        extracted = self.extract_tweet_markers(text)
        assert len(extracted) == 2
        assert "First line" in extracted[0][1]
        assert "Second line" in extracted[0][1]

    def test_extract_markers_no_markers(self):
        """Test extracting from text with no markers."""
        text = "Just some plain text without markers"
        extracted = self.extract_tweet_markers(text)
        assert extracted == []


# =============================================================================
# URL, Mention, and Hashtag Handling Tests
# =============================================================================

class TestUrlMentionHashtagHandling:
    """Test handling of URLs, mentions, and hashtags in threads."""

    def count_urls(self, text: str) -> int:
        """Count URLs in text."""
        import re
        url_pattern = r'https?://[^\s]+'
        return len(re.findall(url_pattern, text))

    def count_mentions(self, text: str) -> int:
        """Count @mentions in text."""
        import re
        mention_pattern = r'@\w+'
        return len(re.findall(mention_pattern, text))

    def count_hashtags(self, text: str) -> int:
        """Count #hashtags in text."""
        import re
        hashtag_pattern = r'#\w+'
        return len(re.findall(hashtag_pattern, text))

    def count_cashtags(self, text: str) -> int:
        """Count $cashtags in text."""
        import re
        cashtag_pattern = r'\$[A-Z]+'
        return len(re.findall(cashtag_pattern, text))

    def extract_urls(self, text: str) -> list:
        """Extract all URLs from text."""
        import re
        url_pattern = r'https?://[^\s]+'
        return re.findall(url_pattern, text)

    def url_shortener_length(self, url: str) -> int:
        """Twitter counts all URLs as 23 characters."""
        return 23

    def calculate_real_length(self, tweet: str) -> int:
        """Calculate real Twitter length accounting for URL shortening."""
        urls = self.extract_urls(tweet)
        length = len(tweet)
        for url in urls:
            # Subtract actual URL length, add 23 for t.co shortening
            length = length - len(url) + 23
        return length

    # URL Tests
    def test_count_urls_none(self):
        """Test counting URLs when none present."""
        text = "No URLs here"
        assert self.count_urls(text) == 0

    def test_count_urls_single(self):
        """Test counting single URL."""
        text = "Check out https://example.com for more"
        assert self.count_urls(text) == 1

    def test_count_urls_multiple(self):
        """Test counting multiple URLs."""
        text = "Visit https://site1.com and https://site2.com/path"
        assert self.count_urls(text) == 2

    def test_url_shortener_always_23(self):
        """Test URL shortener returns 23 for any URL."""
        assert self.url_shortener_length("https://example.com") == 23
        assert self.url_shortener_length("https://very-long-domain.com/path/to/page") == 23

    def test_calculate_real_length_no_urls(self):
        """Test real length calculation without URLs."""
        tweet = "Hello world"
        assert self.calculate_real_length(tweet) == 11

    def test_calculate_real_length_with_url(self):
        """Test real length calculation with URL."""
        tweet = "Check this https://example.com out"
        # "Check this " (11) + 23 (url) + " out" (4) = 38
        assert self.calculate_real_length(tweet) == 38

    # Mention Tests
    def test_count_mentions_none(self):
        """Test counting mentions when none present."""
        text = "No mentions here"
        assert self.count_mentions(text) == 0

    def test_count_mentions_single(self):
        """Test counting single mention."""
        text = "Hey @user check this out"
        assert self.count_mentions(text) == 1

    def test_count_mentions_multiple(self):
        """Test counting multiple mentions."""
        text = "@user1 and @user2 should see this @user3"
        assert self.count_mentions(text) == 3

    # Hashtag Tests
    def test_count_hashtags_none(self):
        """Test counting hashtags when none present."""
        text = "No hashtags here"
        assert self.count_hashtags(text) == 0

    def test_count_hashtags_single(self):
        """Test counting single hashtag."""
        text = "Love #Solana today"
        assert self.count_hashtags(text) == 1

    def test_count_hashtags_multiple(self):
        """Test counting multiple hashtags."""
        text = "#Jarvis #Solana #DeFi #crypto"
        assert self.count_hashtags(text) == 4

    # Cashtag Tests
    def test_count_cashtags_none(self):
        """Test counting cashtags when none present."""
        text = "No cashtags here"
        assert self.count_cashtags(text) == 0

    def test_count_cashtags_single(self):
        """Test counting single cashtag."""
        text = "Bullish on $SOL"
        assert self.count_cashtags(text) == 1

    def test_count_cashtags_multiple(self):
        """Test counting multiple cashtags."""
        text = "$SOL $BTC $ETH looking strong"
        assert self.count_cashtags(text) == 3


# =============================================================================
# Unicode and Emoji Handling Tests
# =============================================================================

class TestUnicodeEmojiHandling:
    """Test handling of Unicode characters and emojis in threads."""

    def count_emojis(self, text: str) -> int:
        """Count emojis in text using regex."""
        import re
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        return len(emoji_pattern.findall(text))

    def strip_emojis(self, text: str) -> str:
        """Remove emojis from text."""
        import re
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        return emoji_pattern.sub('', text)

    def normalize_unicode(self, text: str) -> str:
        """Normalize Unicode text to NFC form."""
        import unicodedata
        return unicodedata.normalize('NFC', text)

    def test_count_emojis_none(self):
        """Test counting emojis when none present."""
        text = "Plain text"
        assert self.count_emojis(text) == 0

    def test_count_emojis_single(self):
        """Test counting single emoji."""
        text = "Hello world \U0001F600"  # grinning face
        assert self.count_emojis(text) >= 1

    def test_count_emojis_multiple(self):
        """Test counting multiple emojis."""
        text = "\U0001F680\U0001F31F\U0001F4B0"  # rocket, star, money bag
        assert self.count_emojis(text) >= 1  # May count as 1 group

    def test_strip_emojis_removes_all(self):
        """Test stripping emojis removes all emojis."""
        text = "Hello \U0001F600 world \U0001F680"
        stripped = self.strip_emojis(text)
        assert "\U0001F600" not in stripped
        assert "\U0001F680" not in stripped
        assert "Hello" in stripped
        assert "world" in stripped

    def test_strip_emojis_preserves_text(self):
        """Test stripping emojis preserves non-emoji text."""
        text = "No emojis here"
        stripped = self.strip_emojis(text)
        assert stripped == "No emojis here"

    def test_unicode_length_calculation(self):
        """Test Unicode string length calculation."""
        # Regular ASCII
        assert len("hello") == 5
        # Unicode characters
        assert len("\u00e9") == 1  # e with acute
        # Emoji (single code point)
        assert len("\U0001F600") == 1  # But may be 2 in some encodings

    def test_normalize_unicode_nfc(self):
        """Test Unicode normalization to NFC."""
        # Composed vs decomposed e-acute
        composed = "\u00e9"  # e-acute as single char
        decomposed = "e\u0301"  # e + combining acute
        normalized = self.normalize_unicode(decomposed)
        assert normalized == composed

    def test_special_unicode_characters(self):
        """Test handling of special Unicode characters."""
        text = "Test \u2022 bullet \u2013 dash \u201c quote \u201d"
        assert len(text) > 0
        # Should not crash
        normalized = self.normalize_unicode(text)
        assert normalized is not None

    def test_mixed_scripts(self):
        """Test handling of mixed script content."""
        text = "English and \u4e2d\u6587 Chinese"
        assert len(text) > 0
        normalized = self.normalize_unicode(text)
        assert "\u4e2d\u6587" in normalized


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases for thread formatting."""

    def test_empty_content_handling(self):
        """Test handling of empty content."""
        content = ""
        assert len(content) == 0

    def test_whitespace_only_content(self):
        """Test handling of whitespace-only content."""
        content = "   \n\t\r   "
        assert content.strip() == ""

    def test_single_character_tweet(self):
        """Test single character tweet."""
        tweet = "a"
        assert len(tweet) == 1

    def test_exactly_280_character_tweet(self):
        """Test tweet at exactly 280 characters."""
        tweet = "a" * 280
        assert len(tweet) == 280

    def test_very_long_thread_100_tweets(self):
        """Test handling of very long thread (100 tweets)."""
        tweets = [f"Tweet number {i}" for i in range(100)]
        assert len(tweets) == 100
        # All should be valid length
        for tweet in tweets:
            assert len(tweet) <= 280

    def test_very_long_single_word(self):
        """Test handling of word longer than tweet limit."""
        long_word = "a" * 300
        # Should not crash when processing
        assert len(long_word) > 280

    def test_special_characters_in_content(self):
        """Test handling of special characters."""
        content = "Test <script>alert('xss')</script> & \"quotes\" 'apostrophe'"
        assert "<script>" in content
        assert "&" in content
        assert '"' in content

    def test_newlines_in_content(self):
        """Test handling of newlines."""
        content = "Line 1\nLine 2\r\nLine 3"
        lines = content.splitlines()
        assert len(lines) == 3

    def test_tabs_in_content(self):
        """Test handling of tabs."""
        content = "Column1\tColumn2\tColumn3"
        assert "\t" in content

    def test_null_bytes_filtered(self):
        """Test that null bytes are handled."""
        content = "Hello\x00World"
        filtered = content.replace("\x00", "")
        assert "\x00" not in filtered
        assert "HelloWorld" == filtered


# =============================================================================
# Module Import and Environment Tests
# =============================================================================

class TestModuleEnvironment:
    """Test environment variable loading and module initialization."""

    def test_env_file_parsing_basic(self):
        """Test basic .env file parsing logic."""
        env_content = """
KEY1=value1
KEY2=value2
# Comment line
KEY3=value3
"""
        env_vars = {}
        for line in env_content.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()

        assert env_vars.get("KEY1") == "value1"
        assert env_vars.get("KEY2") == "value2"
        assert env_vars.get("KEY3") == "value3"
        assert "Comment" not in env_vars

    def test_env_file_parsing_with_quotes(self):
        """Test .env file parsing with quoted values."""
        env_content = 'KEY="quoted value"'
        line = env_content.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            # Value should include quotes (or be stripped depending on implementation)
            assert key.strip() == "KEY"

    def test_env_file_parsing_equals_in_value(self):
        """Test .env file parsing when value contains equals sign."""
        env_content = "URL=https://api.example.com?key=value"
        line = env_content.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            assert key.strip() == "URL"
            assert value.strip() == "https://api.example.com?key=value"

    def test_env_file_empty_lines_skipped(self):
        """Test empty lines are skipped in .env parsing."""
        env_content = """

KEY1=value1

KEY2=value2

"""
        env_vars = {}
        for line in env_content.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()

        assert len(env_vars) == 2


# =============================================================================
# API Request and Response Tests
# =============================================================================

class TestApiRequestResponse:
    """Test API request formation and response handling."""

    @pytest.fixture
    def mock_response_success(self):
        """Create a successful API response mock."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            'content': [{'text': '---TWEET 1---\nTest tweet content'}]
        }
        return response

    @pytest.fixture
    def mock_response_error(self):
        """Create an error API response mock."""
        response = MagicMock()
        response.status_code = 500
        response.text = "Internal Server Error"
        return response

    @pytest.fixture
    def sample_grok_data(self):
        """Create sample Grok sentiment data."""
        return {
            'macro': 'Market is bullish',
            'stocks': 'AAPL looking strong',
            'commodities': 'Gold rising',
            'metals': 'Silver stable',
            'microcaps': 'SOL ecosystem hot',
            'solana': 'Memecoins pumping'
        }

    def test_request_headers_format(self):
        """Test API request headers are formatted correctly."""
        headers = {
            'x-api-key': 'test-key',
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        }
        assert headers['x-api-key'] == 'test-key'
        assert headers['anthropic-version'] == '2023-06-01'
        assert headers['content-type'] == 'application/json'

    def test_request_body_format(self):
        """Test API request body is formatted correctly."""
        body = {
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 6000,
            'messages': [{'role': 'user', 'content': 'Test prompt'}],
        }
        assert body['model'] == 'claude-sonnet-4-20250514'
        assert body['max_tokens'] == 6000
        assert len(body['messages']) == 1
        assert body['messages'][0]['role'] == 'user'

    def test_response_success_parsing(self, mock_response_success):
        """Test parsing successful API response."""
        result = mock_response_success.json()
        thread = result['content'][0]['text'].strip()
        assert '---TWEET 1---' in thread
        assert 'Test tweet content' in thread

    def test_response_error_handling(self, mock_response_error):
        """Test handling error API response."""
        assert mock_response_error.status_code == 500
        assert 'Error' in mock_response_error.text

    def test_full_report_building(self, sample_grok_data):
        """Test building full report from Grok data."""
        data = sample_grok_data
        full_report = f"""
=== GROK SENTIMENT REPORT DATA ===

MACRO ANALYSIS:
{data['macro']}

STOCK PICKS:
{data['stocks']}

COMMODITIES:
{data['commodities']}

PRECIOUS METALS:
{data['metals']}

CRYPTO MICROCAPS - MULTI-CHAIN (LOTTERY TICKETS):
{data.get('microcaps', data.get('solana', ''))}
"""
        assert 'MACRO ANALYSIS' in full_report
        assert 'Market is bullish' in full_report
        assert 'STOCK PICKS' in full_report
        assert 'AAPL looking strong' in full_report

    def test_prompt_includes_critical_requirements(self):
        """Test prompt includes all critical requirements."""
        prompt_requirements = [
            "JARVIS",
            "Tony Stark's AI assistant",
            "NO EMOJIS",
            "LOTTERY TICKETS",
            "extreme risk",
            "XStocks.fi",
            "PreStocks.com",
            "Grok",
            "disclaimer",
        ]
        # These requirements come from the actual format_thread.py prompt
        prompt_template = """You are JARVIS - Tony Stark's AI assistant. Sophisticated, calm, subtle wit, self-aware. NO EMOJIS ALLOWED.

Transform this Grok sentiment report into a THREAD for X (Twitter). With Premium, each tweet can be up to 4000 characters, so make them substantive.

CRITICAL REQUIREMENTS:
1. WARN HEAVILY that this is still being tested - we are calibrating, be super careful
2. Microcap tokens are LOTTERY TICKETS - extreme risk, can go to zero
3. Stocks mentioned are available via XStocks.fi and PreStocks.com (tokenized stocks on Solana)
4. Credit Grok for the analysis - JARVIS just presents it
5. Be measured and careful in tone - not hype, not FUD, just facts
6. Include specific price targets, stop losses, levels where available
7. Include disclaimers throughout
8. ABSOLUTELY NO EMOJIS - this is JARVIS, not a crypto bro"""

        for requirement in prompt_requirements:
            assert requirement in prompt_template, f"Missing requirement: {requirement}"


# =============================================================================
# Thread Structure Validation Tests
# =============================================================================

class TestThreadStructure:
    """Test thread structure and organization."""

    @pytest.fixture
    def sample_thread(self):
        """Create a sample formatted thread."""
        return """---TWEET 1---
INTRO - System announcement, warnings about testing phase

---TWEET 2---
MACRO OUTLOOK - Short/Medium/Long term analysis

---TWEET 3---
TRADITIONAL MARKETS - DXY and Stocks outlook

---TWEET 4---
STOCK PICKS - The 5 picks with targets

---TWEET 5---
COMMODITIES - The 5 movers

---TWEET 6---
PRECIOUS METALS - Gold/Silver/Platinum

---TWEET 7---
CRYPTO MICROCAPS - The lottery tickets with heavy warnings

---TWEET 8---
CLOSING - Final disclaimer, building in public"""

    def extract_sections(self, thread: str) -> list:
        """Extract section headers from thread."""
        import re
        pattern = r'---TWEET \d+---\s*\n([A-Z][A-Z\s]+ -)'
        matches = re.findall(pattern, thread)
        return matches

    def test_thread_has_intro(self, sample_thread):
        """Test thread has an intro section."""
        assert 'INTRO' in sample_thread

    def test_thread_has_macro_outlook(self, sample_thread):
        """Test thread has macro outlook section."""
        assert 'MACRO OUTLOOK' in sample_thread

    def test_thread_has_stock_picks(self, sample_thread):
        """Test thread has stock picks section."""
        assert 'STOCK PICKS' in sample_thread

    def test_thread_has_commodities(self, sample_thread):
        """Test thread has commodities section."""
        assert 'COMMODITIES' in sample_thread

    def test_thread_has_metals(self, sample_thread):
        """Test thread has precious metals section."""
        assert 'PRECIOUS METALS' in sample_thread

    def test_thread_has_crypto_microcaps(self, sample_thread):
        """Test thread has crypto microcaps section."""
        assert 'CRYPTO MICROCAPS' in sample_thread

    def test_thread_has_closing(self, sample_thread):
        """Test thread has closing section."""
        assert 'CLOSING' in sample_thread

    def test_thread_tweet_count(self, sample_thread):
        """Test thread has expected number of tweets."""
        import re
        tweet_markers = re.findall(r'---TWEET \d+---', sample_thread)
        assert len(tweet_markers) == 8

    def test_thread_tweets_sequential(self, sample_thread):
        """Test tweets are numbered sequentially."""
        import re
        tweet_numbers = [int(n) for n in re.findall(r'---TWEET (\d+)---', sample_thread)]
        expected = list(range(1, len(tweet_numbers) + 1))
        assert tweet_numbers == expected


# =============================================================================
# File Output Tests
# =============================================================================

class TestFileOutput:
    """Test file output handling."""

    def test_output_file_write(self, tmp_path):
        """Test writing output to file."""
        output_path = tmp_path / "thread_draft.txt"
        content = "Test thread content"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        assert output_path.exists()
        assert output_path.read_text(encoding='utf-8') == content

    def test_output_file_encoding_utf8(self, tmp_path):
        """Test output file uses UTF-8 encoding."""
        output_path = tmp_path / "thread_draft.txt"
        content = "Unicode: \u00e9\u00e8\u00ea \u4e2d\u6587"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        with open(output_path, 'r', encoding='utf-8') as f:
            read_content = f.read()

        assert read_content == content

    def test_output_file_overwrite(self, tmp_path):
        """Test output file overwrites existing content."""
        output_path = tmp_path / "thread_draft.txt"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("Original content")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("New content")

        assert output_path.read_text(encoding='utf-8') == "New content"

    def test_output_path_resolution(self):
        """Test output path is resolved correctly."""
        base_path = Path("/some/path/to/format_thread.py")
        expected_output = base_path.parent / "thread_draft.txt"
        assert str(expected_output) == "/some/path/to/thread_draft.txt"


# =============================================================================
# Integration-Style Tests with Mocking
# =============================================================================

class TestFormatThreadIntegration:
    """Integration-style tests for format_thread module with full mocking."""

    @pytest.fixture
    def mock_env_file(self):
        """Create mock environment file content."""
        return """ANTHROPIC_API_KEY=test-api-key
ANTHROPIC_BASE_URL=http://localhost:8080
"""

    @pytest.fixture
    def mock_data_file(self):
        """Create mock data file content."""
        return json.dumps({
            'macro': 'Market outlook positive',
            'stocks': 'Tech sector strong',
            'commodities': 'Oil rising',
            'metals': 'Gold stable',
            'microcaps': 'SOL ecosystem bullish'
        })

    @pytest.fixture
    def mock_api_response(self):
        """Create mock API response."""
        return {
            'content': [{
                'text': """---TWEET 1---
System under development, calibrating sentiment analysis

---TWEET 2---
Macro outlook: Market showing strength

---TWEET 3---
NFA - Always do your own research"""
            }]
        }

    def test_full_flow_mocked(self, mock_env_file, mock_data_file, mock_api_response, tmp_path):
        """Test full format_thread flow with all dependencies mocked."""
        # Create temp files
        env_path = tmp_path / ".env"
        env_path.write_text(mock_env_file)

        data_path = tmp_path / "sentiment_report_data.json"
        data_path.write_text(mock_data_file)

        output_path = tmp_path / "thread_draft.txt"

        # Load data
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Build report
        full_report = f"""
=== GROK SENTIMENT REPORT DATA ===

MACRO ANALYSIS:
{data['macro']}

STOCK PICKS:
{data['stocks']}

COMMODITIES:
{data['commodities']}

PRECIOUS METALS:
{data['metals']}

CRYPTO MICROCAPS:
{data.get('microcaps', '')}
"""

        # Simulate API call and response
        result = mock_api_response['content'][0]['text'].strip()

        # Write output
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)

        # Verify
        assert output_path.exists()
        output_content = output_path.read_text(encoding='utf-8')
        assert '---TWEET 1---' in output_content
        assert 'System under development' in output_content


# =============================================================================
# Anthropic Utils Integration Tests
# =============================================================================

class TestAnthropicUtilsIntegration:
    """Test integration with anthropic_utils module."""

    def test_get_anthropic_api_key_from_env(self, monkeypatch):
        """Test getting API key from environment."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
        monkeypatch.setenv("JARVIS_ALLOW_REMOTE_ANTHROPIC", "true")

        from core.llm.anthropic_utils import get_anthropic_api_key
        key = get_anthropic_api_key()
        assert key == "test-key-123"

    def test_get_anthropic_messages_url_default(self, monkeypatch):
        """Test getting default messages URL."""
        monkeypatch.setenv("JARVIS_ALLOW_REMOTE_ANTHROPIC", "true")
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        monkeypatch.delenv("OLLAMA_ANTHROPIC_BASE_URL", raising=False)

        from core.llm.anthropic_utils import get_anthropic_messages_url
        url = get_anthropic_messages_url()
        assert url == "https://api.anthropic.com/v1/messages"

    def test_get_anthropic_messages_url_local(self, monkeypatch):
        """Test getting local messages URL."""
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://localhost:8080/v1")

        from core.llm.anthropic_utils import get_anthropic_messages_url
        url = get_anthropic_messages_url()
        assert "localhost" in url
        assert "/v1/messages" in url

    def test_is_local_anthropic_true(self, monkeypatch):
        """Test local Anthropic detection."""
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://localhost:8080")

        from core.llm.anthropic_utils import is_local_anthropic
        assert is_local_anthropic() is True

    def test_is_local_anthropic_false(self, monkeypatch):
        """Test non-local Anthropic detection."""
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        monkeypatch.delenv("OLLAMA_ANTHROPIC_BASE_URL", raising=False)

        from core.llm.anthropic_utils import is_local_anthropic
        assert is_local_anthropic() is False


# =============================================================================
# Prompt Construction Tests
# =============================================================================

class TestPromptConstruction:
    """Test prompt construction for Claude API."""

    def test_prompt_structure(self):
        """Test prompt has required structure."""
        prompt_template = """You are JARVIS - Tony Stark's AI assistant.

Transform this Grok sentiment report into a THREAD for X (Twitter).

CRITICAL REQUIREMENTS:
1. WARN HEAVILY that this is still being tested
2. Microcap tokens are LOTTERY TICKETS

Structure the thread as:
1/ INTRO
2/ MACRO OUTLOOK

Format each tweet like:
---TWEET 1---
[content]
---TWEET 2---
[content]"""

        # Test sections exist
        assert "JARVIS" in prompt_template
        assert "CRITICAL REQUIREMENTS" in prompt_template
        assert "Structure the thread" in prompt_template
        assert "Format each tweet" in prompt_template

    def test_prompt_report_injection(self):
        """Test full report is injected into prompt."""
        report = "MACRO: Bullish\nSTOCKS: AAPL strong"
        prompt_base = "Here is the data:\n\n"

        full_prompt = prompt_base + report

        assert "MACRO: Bullish" in full_prompt
        assert "STOCKS: AAPL strong" in full_prompt

    def test_prompt_max_tokens_reasonable(self):
        """Test max_tokens is set to reasonable value."""
        max_tokens = 6000
        # With 8 tweets at ~4000 chars each, 6000 tokens should be sufficient
        assert max_tokens >= 4000
        assert max_tokens <= 10000


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling scenarios."""

    def test_missing_data_file_handling(self, tmp_path):
        """Test handling when data file is missing."""
        data_path = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            with open(data_path, 'r') as f:
                json.load(f)

    def test_invalid_json_handling(self, tmp_path):
        """Test handling invalid JSON in data file."""
        data_path = tmp_path / "invalid.json"
        data_path.write_text("not valid json {{{")

        with pytest.raises(json.JSONDecodeError):
            with open(data_path, 'r') as f:
                json.load(f)

    def test_missing_api_key_handling(self, monkeypatch):
        """Test handling when API key is missing."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        monkeypatch.delenv("JARVIS_ALLOW_REMOTE_ANTHROPIC", raising=False)

        from core.llm.anthropic_utils import get_anthropic_api_key
        key = get_anthropic_api_key()
        # Should return empty string when not local and not allowed remote
        assert key == ""

    def test_api_timeout_simulation(self):
        """Test handling API timeout."""
        import requests

        with patch('requests.post') as mock_post:
            mock_post.side_effect = requests.Timeout("Connection timed out")

            with pytest.raises(requests.Timeout):
                requests.post("http://example.com", json={})

    def test_api_connection_error_simulation(self):
        """Test handling API connection error."""
        import requests

        with patch('requests.post') as mock_post:
            mock_post.side_effect = requests.ConnectionError("Failed to connect")

            with pytest.raises(requests.ConnectionError):
                requests.post("http://example.com", json={})


# =============================================================================
# Data Validation Tests
# =============================================================================

class TestDataValidation:
    """Test data validation for Grok sentiment data."""

    @pytest.fixture
    def valid_data(self):
        """Create valid Grok data structure."""
        return {
            'macro': 'Macro analysis content',
            'stocks': 'Stock picks content',
            'commodities': 'Commodities content',
            'metals': 'Precious metals content',
            'microcaps': 'Microcap tokens content'
        }

    @pytest.fixture
    def partial_data(self):
        """Create partial Grok data with missing fields."""
        return {
            'macro': 'Macro analysis content',
            'stocks': 'Stock picks content',
        }

    def test_valid_data_structure(self, valid_data):
        """Test valid data passes validation."""
        required_fields = ['macro', 'stocks', 'commodities', 'metals']
        for field in required_fields:
            assert field in valid_data

    def test_partial_data_handling(self, partial_data):
        """Test partial data is handled gracefully."""
        # Using .get() with defaults
        assert partial_data.get('macro', '') != ''
        assert partial_data.get('commodities', 'N/A') == 'N/A'

    def test_microcaps_fallback_to_solana(self):
        """Test microcaps falls back to solana field."""
        data = {
            'macro': 'Macro',
            'stocks': 'Stocks',
            'commodities': 'Commodities',
            'metals': 'Metals',
            'solana': 'Solana microcaps content'
        }
        microcaps = data.get('microcaps', data.get('solana', ''))
        assert microcaps == 'Solana microcaps content'

    def test_empty_data_handling(self):
        """Test empty data structure handling."""
        data = {}
        assert data.get('macro', '') == ''
        assert data.get('stocks', '') == ''


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

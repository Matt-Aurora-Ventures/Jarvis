"""
Unit tests for bots.shared.utils module.

Tests cover:
- Time utilities: now_utc, format_duration, parse_time
- Text utilities: truncate, escape_markdown, extract_urls, sanitize_filename
- Data utilities: safe_json_loads, deep_merge, flatten_dict
- Network utilities: is_url_valid, get_ip_address
- File utilities: ensure_dir, atomic_write, read_json_file
"""

import pytest
import json
import tempfile
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

# Import module under test
from bots.shared.utils import (
    # Time utilities
    now_utc,
    format_duration,
    parse_time,
    # Text utilities
    truncate,
    escape_markdown,
    extract_urls,
    sanitize_filename,
    # Data utilities
    safe_json_loads,
    deep_merge,
    flatten_dict,
    # Network utilities
    is_url_valid,
    get_ip_address,
    # File utilities
    ensure_dir,
    atomic_write,
    read_json_file,
)


class TestTimeUtilities:
    """Tests for time-related utility functions."""

    def test_now_utc_returns_datetime(self):
        """now_utc should return a datetime object."""
        result = now_utc()
        assert isinstance(result, datetime)

    def test_now_utc_is_utc_timezone(self):
        """now_utc should return a UTC-aware datetime."""
        result = now_utc()
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_now_utc_is_current_time(self):
        """now_utc should return approximately the current time."""
        before = datetime.now(timezone.utc)
        result = now_utc()
        after = datetime.now(timezone.utc)
        assert before <= result <= after

    def test_format_duration_seconds_only(self):
        """format_duration should handle seconds < 60."""
        assert format_duration(30) == "30s"
        assert format_duration(59) == "59s"
        assert format_duration(0) == "0s"

    def test_format_duration_minutes_and_seconds(self):
        """format_duration should handle minutes properly."""
        assert format_duration(60) == "1m"
        assert format_duration(90) == "1m 30s"
        assert format_duration(120) == "2m"
        assert format_duration(3599) == "59m 59s"

    def test_format_duration_hours_minutes_seconds(self):
        """format_duration should handle hours properly."""
        assert format_duration(3600) == "1h"
        assert format_duration(3660) == "1h 1m"
        assert format_duration(3661) == "1h 1m 1s"
        assert format_duration(9000) == "2h 30m"

    def test_format_duration_days(self):
        """format_duration should handle days properly."""
        assert format_duration(86400) == "1d"
        assert format_duration(90000) == "1d 1h"
        assert format_duration(172800) == "2d"

    def test_format_duration_negative(self):
        """format_duration should handle negative values gracefully."""
        result = format_duration(-60)
        assert result == "0s" or result.startswith("-")

    def test_format_duration_float(self):
        """format_duration should handle float values."""
        assert format_duration(90.5) == "1m 30s"

    def test_parse_time_iso_format(self):
        """parse_time should parse ISO format strings."""
        result = parse_time("2026-02-02T14:30:00Z")
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 2
        assert result.hour == 14
        assert result.minute == 30

    def test_parse_time_date_only(self):
        """parse_time should parse date-only strings."""
        result = parse_time("2026-02-02")
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 2

    def test_parse_time_relative_minutes(self):
        """parse_time should handle relative time like '30m'."""
        before = datetime.now(timezone.utc)
        result = parse_time("30m")
        expected = before + timedelta(minutes=30)
        # Allow 1 second tolerance
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_time_relative_hours(self):
        """parse_time should handle relative time like '2h'."""
        before = datetime.now(timezone.utc)
        result = parse_time("2h")
        expected = before + timedelta(hours=2)
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_time_invalid_returns_none(self):
        """parse_time should return None for invalid input."""
        assert parse_time("invalid") is None
        assert parse_time("") is None
        assert parse_time(None) is None


class TestTextUtilities:
    """Tests for text manipulation utility functions."""

    def test_truncate_short_text_unchanged(self):
        """truncate should not modify text shorter than max_len."""
        assert truncate("hello", 10) == "hello"
        assert truncate("hello", 5) == "hello"

    def test_truncate_adds_ellipsis(self):
        """truncate should add ... when text exceeds max_len."""
        result = truncate("hello world", 5)
        assert result == "hello..."
        assert len(result) == 8

    def test_truncate_custom_max_len(self):
        """truncate should respect custom max_len."""
        result = truncate("this is a long string", max_len=10)
        assert result == "this is a ..."

    def test_truncate_empty_string(self):
        """truncate should handle empty strings."""
        assert truncate("", 10) == ""

    def test_truncate_none_returns_empty(self):
        """truncate should handle None gracefully."""
        assert truncate(None, 10) == ""

    def test_escape_markdown_special_chars(self):
        """escape_markdown should escape special Telegram markdown chars."""
        # Telegram MarkdownV2 special characters: _*[]()~`>#+-=|{}.!
        result = escape_markdown("Hello *world* _test_")
        assert "*" not in result or "\\*" in result
        assert "_" not in result or "\\_" in result

    def test_escape_markdown_preserves_normal_text(self):
        """escape_markdown should not alter normal text."""
        assert escape_markdown("hello world") == "hello world"

    def test_escape_markdown_empty_string(self):
        """escape_markdown should handle empty strings."""
        assert escape_markdown("") == ""

    def test_escape_markdown_none_returns_empty(self):
        """escape_markdown should handle None."""
        assert escape_markdown(None) == ""

    def test_extract_urls_single_url(self):
        """extract_urls should find a single URL."""
        text = "Check out https://example.com for more info"
        urls = extract_urls(text)
        assert "https://example.com" in urls

    def test_extract_urls_multiple_urls(self):
        """extract_urls should find multiple URLs."""
        text = "Visit https://example.com and http://test.org"
        urls = extract_urls(text)
        assert len(urls) == 2
        assert "https://example.com" in urls
        assert "http://test.org" in urls

    def test_extract_urls_no_urls(self):
        """extract_urls should return empty list when no URLs."""
        assert extract_urls("no urls here") == []

    def test_extract_urls_empty_string(self):
        """extract_urls should handle empty strings."""
        assert extract_urls("") == []

    def test_extract_urls_with_paths(self):
        """extract_urls should capture URL paths."""
        text = "See https://example.com/path/to/page?query=1"
        urls = extract_urls(text)
        assert "https://example.com/path/to/page?query=1" in urls

    def test_sanitize_filename_removes_illegal_chars(self):
        """sanitize_filename should remove illegal filename characters."""
        result = sanitize_filename("file<>:name|test?.txt")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert "|" not in result
        assert "?" not in result

    def test_sanitize_filename_preserves_valid_chars(self):
        """sanitize_filename should preserve valid filename characters."""
        result = sanitize_filename("valid_file-name.txt")
        assert result == "valid_file-name.txt"

    def test_sanitize_filename_replaces_spaces(self):
        """sanitize_filename should replace spaces with underscores."""
        result = sanitize_filename("file with spaces.txt")
        assert " " not in result
        assert "_" in result or "-" in result

    def test_sanitize_filename_handles_empty(self):
        """sanitize_filename should handle empty strings."""
        result = sanitize_filename("")
        assert result == "" or result == "unnamed"

    def test_sanitize_filename_limits_length(self):
        """sanitize_filename should limit filename length."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) <= 255


class TestDataUtilities:
    """Tests for data manipulation utility functions."""

    def test_safe_json_loads_valid_json(self):
        """safe_json_loads should parse valid JSON."""
        result = safe_json_loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_safe_json_loads_invalid_json_returns_default(self):
        """safe_json_loads should return default on invalid JSON."""
        result = safe_json_loads("not json", default={})
        assert result == {}

    def test_safe_json_loads_custom_default(self):
        """safe_json_loads should use custom default."""
        result = safe_json_loads("invalid", default={"error": True})
        assert result == {"error": True}

    def test_safe_json_loads_empty_string(self):
        """safe_json_loads should handle empty strings."""
        result = safe_json_loads("", default=[])
        assert result == []

    def test_safe_json_loads_none_returns_default(self):
        """safe_json_loads should handle None."""
        result = safe_json_loads(None, default={})
        assert result == {}

    def test_safe_json_loads_list(self):
        """safe_json_loads should parse JSON lists."""
        result = safe_json_loads('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_deep_merge_simple_dicts(self):
        """deep_merge should merge simple dictionaries."""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"c": 3}
        result = deep_merge(dict1, dict2)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_deep_merge_overlapping_keys(self):
        """deep_merge should override with dict2 values."""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 3, "c": 4}
        result = deep_merge(dict1, dict2)
        assert result["b"] == 3

    def test_deep_merge_nested_dicts(self):
        """deep_merge should recursively merge nested dicts."""
        dict1 = {"a": {"x": 1, "y": 2}}
        dict2 = {"a": {"y": 3, "z": 4}}
        result = deep_merge(dict1, dict2)
        assert result["a"]["x"] == 1
        assert result["a"]["y"] == 3
        assert result["a"]["z"] == 4

    def test_deep_merge_empty_dicts(self):
        """deep_merge should handle empty dictionaries."""
        assert deep_merge({}, {"a": 1}) == {"a": 1}
        assert deep_merge({"a": 1}, {}) == {"a": 1}
        assert deep_merge({}, {}) == {}

    def test_deep_merge_does_not_modify_originals(self):
        """deep_merge should not modify original dictionaries."""
        dict1 = {"a": 1}
        dict2 = {"b": 2}
        deep_merge(dict1, dict2)
        assert dict1 == {"a": 1}
        assert dict2 == {"b": 2}

    def test_flatten_dict_simple(self):
        """flatten_dict should flatten simple nested dicts."""
        nested = {"a": {"b": 1}}
        result = flatten_dict(nested)
        assert result == {"a.b": 1}

    def test_flatten_dict_multiple_levels(self):
        """flatten_dict should handle multiple nesting levels."""
        nested = {"a": {"b": {"c": 1}}}
        result = flatten_dict(nested)
        assert result == {"a.b.c": 1}

    def test_flatten_dict_mixed_content(self):
        """flatten_dict should handle mixed nested/flat content."""
        nested = {"a": 1, "b": {"c": 2, "d": {"e": 3}}}
        result = flatten_dict(nested)
        assert result["a"] == 1
        assert result["b.c"] == 2
        assert result["b.d.e"] == 3

    def test_flatten_dict_already_flat(self):
        """flatten_dict should handle already flat dicts."""
        flat = {"a": 1, "b": 2}
        result = flatten_dict(flat)
        assert result == {"a": 1, "b": 2}

    def test_flatten_dict_empty(self):
        """flatten_dict should handle empty dicts."""
        assert flatten_dict({}) == {}

    def test_flatten_dict_with_lists(self):
        """flatten_dict should preserve lists as values."""
        nested = {"a": {"b": [1, 2, 3]}}
        result = flatten_dict(nested)
        assert result["a.b"] == [1, 2, 3]


class TestNetworkUtilities:
    """Tests for network-related utility functions."""

    def test_is_url_valid_http(self):
        """is_url_valid should accept valid HTTP URLs."""
        assert is_url_valid("http://example.com") is True
        assert is_url_valid("http://example.com/path") is True

    def test_is_url_valid_https(self):
        """is_url_valid should accept valid HTTPS URLs."""
        assert is_url_valid("https://example.com") is True
        assert is_url_valid("https://sub.example.com/path?q=1") is True

    def test_is_url_valid_invalid_urls(self):
        """is_url_valid should reject invalid URLs."""
        assert is_url_valid("not a url") is False
        assert is_url_valid("ftp://example.com") is False  # Only http/https
        assert is_url_valid("") is False
        assert is_url_valid(None) is False

    def test_is_url_valid_missing_scheme(self):
        """is_url_valid should reject URLs without scheme."""
        assert is_url_valid("example.com") is False
        assert is_url_valid("www.example.com") is False

    def test_get_ip_address_returns_string(self):
        """get_ip_address should return a string."""
        result = get_ip_address()
        assert isinstance(result, str)

    def test_get_ip_address_valid_format(self):
        """get_ip_address should return valid IP format."""
        result = get_ip_address()
        # Should be valid IPv4 format or localhost
        parts = result.split(".")
        # Either IPv4 (4 parts) or could be a hostname
        if len(parts) == 4:
            assert all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)


class TestFileUtilities:
    """Tests for file-related utility functions."""

    def test_ensure_dir_creates_directory(self):
        """ensure_dir should create directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "new_subdir")
            assert not os.path.exists(new_dir)
            ensure_dir(new_dir)
            assert os.path.exists(new_dir)
            assert os.path.isdir(new_dir)

    def test_ensure_dir_nested_directories(self):
        """ensure_dir should create nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "a", "b", "c")
            ensure_dir(new_dir)
            assert os.path.exists(new_dir)

    def test_ensure_dir_existing_directory(self):
        """ensure_dir should not fail on existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ensure_dir(tmpdir)  # Should not raise
            assert os.path.exists(tmpdir)

    def test_ensure_dir_returns_path(self):
        """ensure_dir should return the path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "test")
            result = ensure_dir(new_dir)
            assert result == new_dir or str(result) == new_dir

    def test_atomic_write_creates_file(self):
        """atomic_write should create file with content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.txt")
            atomic_write(filepath, "hello world")
            assert os.path.exists(filepath)
            with open(filepath, "r") as f:
                assert f.read() == "hello world"

    def test_atomic_write_overwrites_existing(self):
        """atomic_write should overwrite existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.txt")
            with open(filepath, "w") as f:
                f.write("old content")
            atomic_write(filepath, "new content")
            with open(filepath, "r") as f:
                assert f.read() == "new content"

    def test_atomic_write_handles_dict(self):
        """atomic_write should handle dict content as JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.json")
            atomic_write(filepath, {"key": "value"})
            with open(filepath, "r") as f:
                content = json.load(f)
            assert content == {"key": "value"}

    def test_read_json_file_valid(self):
        """read_json_file should read valid JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.json")
            with open(filepath, "w") as f:
                json.dump({"key": "value"}, f)
            result = read_json_file(filepath)
            assert result == {"key": "value"}

    def test_read_json_file_missing_returns_default(self):
        """read_json_file should return default for missing files."""
        result = read_json_file("/nonexistent/path.json", default={})
        assert result == {}

    def test_read_json_file_custom_default(self):
        """read_json_file should use custom default."""
        result = read_json_file("/nonexistent/path.json", default={"error": True})
        assert result == {"error": True}

    def test_read_json_file_invalid_json_returns_default(self):
        """read_json_file should return default for invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "bad.json")
            with open(filepath, "w") as f:
                f.write("not valid json")
            result = read_json_file(filepath, default=[])
            assert result == []

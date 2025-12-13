"""
Unit tests for helpers module.

Tests utility functions for common operations.
"""

import json
import time

import pytest

from info_agent.utils.helpers import (
    bytes_to_human_readable,
    deep_merge,
    ensure_list,
    generate_prefixed_id,
    generate_uuid,
    get_current_timestamp,
    get_current_timestamp_iso,
    iso_to_timestamp,
    mask_sensitive_string,
    safe_json_dumps,
    safe_json_loads,
    timestamp_to_iso,
    truncate_string,
    validate_email_format,
)


class TestGenerateUUID:
    """Tests for UUID generation functions."""

    def test_generate_uuid_length(self) -> None:
        """Test UUID has correct length."""
        uid = generate_uuid()
        assert len(uid) == 32

    def test_generate_uuid_unique(self) -> None:
        """Test UUIDs are unique."""
        uuids = [generate_uuid() for _ in range(100)]
        assert len(set(uuids)) == 100

    def test_generate_uuid_alphanumeric(self) -> None:
        """Test UUID contains only alphanumeric characters."""
        uid = generate_uuid()
        assert uid.isalnum()

    def test_generate_prefixed_id(self) -> None:
        """Test prefixed ID generation."""
        task_id = generate_prefixed_id("task")
        assert task_id.startswith("task_")
        assert len(task_id) == 37  # "task_" (5) + UUID (32)

    def test_generate_prefixed_id_different_prefixes(self) -> None:
        """Test different prefixes."""
        wf_id = generate_prefixed_id("wf")
        email_id = generate_prefixed_id("email")

        assert wf_id.startswith("wf_")
        assert email_id.startswith("email_")


class TestTimestampFunctions:
    """Tests for timestamp functions."""

    def test_get_current_timestamp_returns_float(self) -> None:
        """Test current timestamp is a float."""
        ts = get_current_timestamp()
        assert isinstance(ts, float)

    def test_get_current_timestamp_reasonable(self) -> None:
        """Test timestamp is reasonable (after 2020)."""
        ts = get_current_timestamp()
        # Jan 1, 2020 = 1577836800
        assert ts > 1577836800

    def test_get_current_timestamp_iso_format(self) -> None:
        """Test ISO timestamp format."""
        ts = get_current_timestamp_iso()

        assert "T" in ts
        assert "+" in ts or "Z" in ts  # Has timezone info

    def test_timestamp_to_iso_conversion(self) -> None:
        """Test Unix timestamp to ISO conversion."""
        ts = 1700000000.0
        iso = timestamp_to_iso(ts)

        assert "2023-11-14" in iso
        assert "T" in iso

    def test_iso_to_timestamp_conversion(self) -> None:
        """Test ISO to Unix timestamp conversion."""
        iso = "2023-11-14T22:13:20+00:00"
        ts = iso_to_timestamp(iso)

        assert ts == 1700000000.0

    def test_timestamp_roundtrip(self) -> None:
        """Test timestamp conversion roundtrip."""
        original = get_current_timestamp()
        iso = timestamp_to_iso(original)
        back = iso_to_timestamp(iso)

        # Should be very close (within 1 second due to precision)
        assert abs(original - back) < 1


class TestTruncateString:
    """Tests for truncate_string function."""

    def test_short_string_unchanged(self) -> None:
        """Test short strings are not changed."""
        result = truncate_string("Hello", max_length=10)
        assert result == "Hello"

    def test_exact_length_unchanged(self) -> None:
        """Test strings at exact max length are not changed."""
        result = truncate_string("HelloWorld", max_length=10)
        assert result == "HelloWorld"

    def test_long_string_truncated(self) -> None:
        """Test long strings are truncated."""
        result = truncate_string("Hello World", max_length=8)
        assert result == "Hello..."
        assert len(result) == 8

    def test_custom_suffix(self) -> None:
        """Test custom suffix."""
        result = truncate_string("Hello World", max_length=9, suffix="[more]")
        assert result == "Hel[more]"

    def test_empty_string(self) -> None:
        """Test empty string."""
        result = truncate_string("", max_length=10)
        assert result == ""


class TestJsonFunctions:
    """Tests for JSON helper functions."""

    def test_safe_json_loads_valid(self) -> None:
        """Test parsing valid JSON."""
        result = safe_json_loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_safe_json_loads_invalid(self) -> None:
        """Test parsing invalid JSON returns default."""
        result = safe_json_loads("not json", default={})
        assert result == {}

    def test_safe_json_loads_none_input(self) -> None:
        """Test None input returns default."""
        result = safe_json_loads(None, default=[])  # type: ignore
        assert result == []

    def test_safe_json_loads_default_none(self) -> None:
        """Test default is None when not specified."""
        result = safe_json_loads("invalid")
        assert result is None

    def test_safe_json_dumps_valid(self) -> None:
        """Test serializing valid object."""
        result = safe_json_dumps({"key": "value"})
        assert result == '{"key": "value"}'

    def test_safe_json_dumps_invalid(self) -> None:
        """Test serializing invalid object returns default."""
        # Set type is not JSON serializable without default handler
        # But we use default=str, so it should work
        result = safe_json_dumps({1, 2, 3})
        # Should not be the default since we use default=str
        assert result != "{}"

    def test_safe_json_dumps_with_default_str(self) -> None:
        """Test objects are converted with str."""
        from datetime import datetime

        obj = {"date": datetime(2023, 1, 1)}
        result = safe_json_dumps(obj)

        # Should contain string representation
        assert "2023" in result


class TestMaskSensitiveString:
    """Tests for mask_sensitive_string function."""

    def test_mask_api_key(self) -> None:
        """Test masking API key."""
        test_string = "sk-abcdefghijklmnop"
        result = mask_sensitive_string(test_string, visible_chars=4)
        assert result.startswith("sk-a")
        assert len(result) == len(test_string)  # Same length as input
        assert result[4:] == "*" * (len(test_string) - 4)

    def test_mask_short_string(self) -> None:
        """Test masking short string."""
        result = mask_sensitive_string("abc", visible_chars=4)
        assert result == "***"

    def test_mask_exact_length(self) -> None:
        """Test masking string of exact visible length."""
        # When string length <= visible_chars, return all asterisks
        result = mask_sensitive_string("abcd", visible_chars=4)
        assert result == "****"

    def test_mask_longer_than_visible(self) -> None:
        """Test masking string longer than visible chars."""
        result = mask_sensitive_string("abcde", visible_chars=4)
        assert result == "abcd*"

    def test_mask_default_chars(self) -> None:
        """Test default visible chars."""
        result = mask_sensitive_string("secretvalue")
        assert result.startswith("secr")
        assert len(result) == len("secretvalue")


class TestValidateEmailFormat:
    """Tests for validate_email_format function."""

    def test_valid_email(self) -> None:
        """Test valid email addresses."""
        assert validate_email_format("user@example.com") is True
        assert validate_email_format("user.name@example.com") is True
        assert validate_email_format("user+tag@example.co.uk") is True

    def test_invalid_email_no_at(self) -> None:
        """Test email without @ is invalid."""
        assert validate_email_format("userexample.com") is False

    def test_invalid_email_no_domain(self) -> None:
        """Test email without domain is invalid."""
        assert validate_email_format("user@") is False

    def test_invalid_email_no_tld(self) -> None:
        """Test email without TLD is invalid."""
        assert validate_email_format("user@example") is False

    def test_invalid_email_empty(self) -> None:
        """Test empty string is invalid."""
        assert validate_email_format("") is False


class TestBytesToHumanReadable:
    """Tests for bytes_to_human_readable function."""

    def test_bytes(self) -> None:
        """Test bytes display."""
        assert bytes_to_human_readable(512) == "512.0 B"

    def test_kilobytes(self) -> None:
        """Test kilobytes display."""
        assert bytes_to_human_readable(1536) == "1.5 KB"

    def test_megabytes(self) -> None:
        """Test megabytes display."""
        assert bytes_to_human_readable(1572864) == "1.5 MB"

    def test_gigabytes(self) -> None:
        """Test gigabytes display."""
        assert bytes_to_human_readable(1610612736) == "1.5 GB"

    def test_zero_bytes(self) -> None:
        """Test zero bytes."""
        assert bytes_to_human_readable(0) == "0.0 B"


class TestEnsureList:
    """Tests for ensure_list function."""

    def test_list_unchanged(self) -> None:
        """Test list is returned unchanged."""
        result = ensure_list([1, 2, 3])
        assert result == [1, 2, 3]

    def test_single_value_wrapped(self) -> None:
        """Test single value is wrapped in list."""
        result = ensure_list("single")
        assert result == ["single"]

    def test_none_returns_empty_list(self) -> None:
        """Test None returns empty list."""
        result = ensure_list(None)
        assert result == []

    def test_dict_wrapped(self) -> None:
        """Test dict is wrapped in list."""
        result = ensure_list({"key": "value"})
        assert result == [{"key": "value"}]


class TestDeepMerge:
    """Tests for deep_merge function."""

    def test_simple_merge(self) -> None:
        """Test simple dict merge."""
        base = {"a": 1, "b": 2}
        override = {"b": 20, "c": 3}

        result = deep_merge(base, override)

        assert result == {"a": 1, "b": 20, "c": 3}

    def test_nested_merge(self) -> None:
        """Test nested dict merge."""
        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"b": 10}}

        result = deep_merge(base, override)

        assert result == {"a": {"b": 10, "c": 2}}

    def test_deep_nested_merge(self) -> None:
        """Test deeply nested merge."""
        base = {"level1": {"level2": {"level3": {"a": 1, "b": 2}}}}
        override = {"level1": {"level2": {"level3": {"a": 10}}}}

        result = deep_merge(base, override)

        assert result["level1"]["level2"]["level3"] == {"a": 10, "b": 2}

    def test_override_non_dict_with_dict(self) -> None:
        """Test overriding non-dict value with dict."""
        base = {"a": 1}
        override = {"a": {"nested": "value"}}

        result = deep_merge(base, override)

        assert result == {"a": {"nested": "value"}}

    def test_base_unchanged(self) -> None:
        """Test base dict is not modified."""
        base = {"a": {"b": 1}}
        override = {"a": {"b": 10}}

        deep_merge(base, override)

        assert base == {"a": {"b": 1}}

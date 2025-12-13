"""
Helper functions for Info-Agent.

This module provides common utility functions used throughout the system.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from info_agent.utils.logging import get_logger

logger = get_logger(__name__)


def generate_uuid() -> str:
    """
    Generate a unique identifier.

    Returns:
        str: A UUID4 string without hyphens.

    Example:
        >>> uid = generate_uuid()
        >>> len(uid)
        32
    """
    return uuid.uuid4().hex


def generate_prefixed_id(prefix: str) -> str:
    """
    Generate a prefixed unique identifier.

    Args:
        prefix: Prefix to prepend to the UUID (e.g., 'wf', 'task', 'email').

    Returns:
        str: Prefixed UUID string.

    Example:
        >>> task_id = generate_prefixed_id("task")
        >>> task_id.startswith("task_")
        True
    """
    return f"{prefix}_{generate_uuid()}"


def get_current_timestamp() -> float:
    """
    Get the current UTC timestamp as a float.

    Returns:
        float: Current Unix timestamp in seconds.

    Example:
        >>> ts = get_current_timestamp()
        >>> isinstance(ts, float)
        True
    """
    return datetime.now(timezone.utc).timestamp()


def get_current_timestamp_iso() -> str:
    """
    Get the current UTC timestamp in ISO 8601 format.

    Returns:
        str: Current timestamp in ISO format.

    Example:
        >>> ts = get_current_timestamp_iso()
        >>> "T" in ts  # ISO format includes T separator
        True
    """
    return datetime.now(timezone.utc).isoformat()


def timestamp_to_iso(timestamp: float) -> str:
    """
    Convert Unix timestamp to ISO 8601 format.

    Args:
        timestamp: Unix timestamp in seconds.

    Returns:
        str: ISO 8601 formatted string.

    Example:
        >>> timestamp_to_iso(1700000000.0)
        '2023-11-14T22:13:20+00:00'
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def iso_to_timestamp(iso_string: str) -> float:
    """
    Convert ISO 8601 string to Unix timestamp.

    Args:
        iso_string: ISO 8601 formatted string.

    Returns:
        float: Unix timestamp in seconds.

    Example:
        >>> iso_to_timestamp("2023-11-14T22:13:20+00:00")
        1700000000.0
    """
    dt = datetime.fromisoformat(iso_string)
    return dt.timestamp()


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length.

    Args:
        s: String to truncate.
        max_length: Maximum length (including suffix).
        suffix: Suffix to append if truncated.

    Returns:
        str: Truncated string with suffix if needed.

    Example:
        >>> truncate_string("Hello World", max_length=8)
        'Hello...'
    """
    if len(s) <= max_length:
        return s

    return s[: max_length - len(suffix)] + suffix


def safe_json_loads(s: Optional[str], default: Optional[Any] = None) -> Any:
    """
    Safely parse JSON string, returning default on failure.

    Args:
        s: JSON string to parse (can be None).
        default: Value to return if parsing fails.

    Returns:
        Parsed JSON value or default.

    Example:
        >>> safe_json_loads('{"key": "value"}')
        {'key': 'value'}
        >>> safe_json_loads('invalid', default={})
        {}
    """
    if s is None:
        return default

    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("json_parse_failed", error=str(e), input_preview=truncate_string(s, 50))
        return default


def safe_json_dumps(obj: Any, default: str = "{}") -> str:
    """
    Safely serialize object to JSON string.

    Args:
        obj: Object to serialize.
        default: Default string to return on failure.

    Returns:
        JSON string or default.

    Example:
        >>> safe_json_dumps({"key": "value"})
        '{"key": "value"}'
    """
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError) as e:
        logger.warning("json_dump_failed", error=str(e), obj_type=type(obj).__name__)
        return default


def mask_sensitive_string(s: str, visible_chars: int = 4) -> str:
    """
    Mask a sensitive string, showing only first few characters.

    Args:
        s: String to mask.
        visible_chars: Number of characters to keep visible.

    Returns:
        Masked string.

    Example:
        >>> mask_sensitive_string("sk-abcdefghijklmnop")
        'sk-a************'
    """
    if len(s) <= visible_chars:
        return "*" * len(s)

    return s[:visible_chars] + "*" * (len(s) - visible_chars)


def validate_email_format(email: str) -> bool:
    """
    Basic email format validation.

    Args:
        email: Email address to validate.

    Returns:
        bool: True if email appears valid.

    Note:
        This is a basic check, not RFC 5322 compliant.
    """
    import re

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def bytes_to_human_readable(num_bytes: int) -> str:
    """
    Convert bytes to human-readable string.

    Args:
        num_bytes: Number of bytes.

    Returns:
        Human-readable string (e.g., "1.5 MB").

    Example:
        >>> bytes_to_human_readable(1536)
        '1.5 KB'
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def ensure_list(value: Any) -> list:
    """
    Ensure value is a list.

    Args:
        value: Any value.

    Returns:
        Value as list (wraps non-list values).

    Example:
        >>> ensure_list("single")
        ['single']
        >>> ensure_list([1, 2, 3])
        [1, 2, 3]
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries.

    Args:
        base: Base dictionary.
        override: Dictionary with values to override.

    Returns:
        Merged dictionary.

    Example:
        >>> base = {"a": {"b": 1, "c": 2}}
        >>> override = {"a": {"b": 10}}
        >>> deep_merge(base, override)
        {'a': {'b': 10, 'c': 2}}
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result

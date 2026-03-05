"""
Shared utility functions for Alhazen skill CLI scripts.

Canonical implementations of escape_string, generate_id, get_timestamp.
Import these in skill scripts rather than copy-pasting.
"""

import uuid
from datetime import datetime, timezone


def escape_string(s: str) -> str:
    """Escape special characters for TypeQL string literals."""
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def generate_id(prefix: str) -> str:
    """Generate a unique ID with a domain prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def get_timestamp() -> str:
    """Return current UTC timestamp in TypeQL datetime format (no timezone suffix)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

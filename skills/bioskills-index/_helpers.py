"""
Standalone utility helpers for the bioskills-index skill.

Copied from src/skillful_alhazen/utils/skill_helpers.py so that
the skill does not depend on the skillful-alhazen package structure
when deployed from its own standalone repo.
"""

import os
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
    """Return current UTC timestamp in TypeQL datetime format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def should_cache(content) -> bool:
    """Return True if content exceeds the 50 KB inline storage threshold."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return len(content) >= 50 * 1024


def get_cache_dir():
    """Return (and create) the alhazen cache root directory."""
    import pathlib
    p = pathlib.Path(os.path.expanduser(os.getenv("ALHAZEN_CACHE_DIR", "~/.alhazen/cache")))
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_to_cache(artifact_id: str, content, mime_type: str) -> dict:
    """Save content to the file cache and return path metadata."""
    cache_root = get_cache_dir()
    type_map = {
        "text/html": ("html", "html"),
        "application/pdf": ("pdf", "pdf"),
        "application/json": ("json", "json"),
        "text/plain": ("text", "txt"),
        "text/markdown": ("text", "md"),
    }
    type_dir, ext = type_map.get(mime_type, ("other", "bin"))
    dir_path = cache_root / type_dir
    dir_path.mkdir(exist_ok=True)
    filename = f"{artifact_id}.{ext}"
    full_path = dir_path / filename
    if isinstance(content, str):
        content = content.encode("utf-8")
    full_path.write_bytes(content)
    return {
        "cache_path": f"{type_dir}/{filename}",
        "file_size": len(content),
        "full_path": str(full_path),
    }


def load_from_cache_text(cache_path: str, encoding: str = "utf-8") -> str:
    """Load text content from the file cache."""
    cache_root = get_cache_dir()
    full = cache_root / cache_path
    return full.read_text(encoding=encoding)

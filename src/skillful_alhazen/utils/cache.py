"""
Cache utility module for storing large artifacts externally.

Large files (PDFs, HTML, images) are stored in a file cache organized by content type.
Files under CACHE_THRESHOLD are stored inline in TypeDB; larger files go to the cache.

Cache Directory Structure:
    ~/.alhazen/cache/
      html/           # Web pages (job postings, company pages)
      pdf/            # Documents (papers, reports)
      image/          # Images (screenshots, diagrams)
      json/           # Structured data (API responses)
      text/           # Plain text files

Environment:
    ALHAZEN_CACHE_DIR - Override default cache location (default: ~/.alhazen/cache)
"""

import hashlib
import os
from pathlib import Path
from typing import Optional

# Cache threshold in bytes (50KB) - content smaller than this is stored inline
CACHE_THRESHOLD = 50 * 1024

# MIME type to directory and extension mapping
MIME_TYPE_MAP = {
    # HTML
    "text/html": ("html", "html"),
    "application/xhtml+xml": ("html", "html"),
    # PDF
    "application/pdf": ("pdf", "pdf"),
    # Images
    "image/png": ("image", "png"),
    "image/jpeg": ("image", "jpg"),
    "image/gif": ("image", "gif"),
    "image/webp": ("image", "webp"),
    "image/svg+xml": ("image", "svg"),
    # JSON
    "application/json": ("json", "json"),
    # Text
    "text/plain": ("text", "txt"),
    "text/markdown": ("text", "md"),
    "text/csv": ("text", "csv"),
    # XML
    "application/xml": ("text", "xml"),
    "text/xml": ("text", "xml"),
}

# Extension to MIME type mapping (for detection)
EXTENSION_MIME_MAP = {
    ".html": "text/html",
    ".htm": "text/html",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".xml": "application/xml",
}


def get_cache_dir() -> Path:
    """
    Get the cache directory path, creating it if necessary.

    Uses ALHAZEN_CACHE_DIR environment variable if set,
    otherwise defaults to ~/.alhazen/cache

    Returns:
        Path to the cache directory
    """
    cache_dir_env = os.getenv("ALHAZEN_CACHE_DIR")
    if cache_dir_env:
        cache_dir = Path(cache_dir_env).expanduser()
    else:
        cache_dir = Path.home() / ".alhazen" / "cache"

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_type_dir(mime_type: str) -> str:
    """
    Get the subdirectory name for a MIME type.

    Args:
        mime_type: MIME type string (e.g., "text/html")

    Returns:
        Directory name (e.g., "html")
    """
    if mime_type in MIME_TYPE_MAP:
        return MIME_TYPE_MAP[mime_type][0]
    # Default to "other" for unknown types
    return "other"


def guess_extension(mime_type: str) -> str:
    """
    Get the file extension for a MIME type.

    Args:
        mime_type: MIME type string (e.g., "application/pdf")

    Returns:
        File extension without dot (e.g., "pdf")
    """
    if mime_type in MIME_TYPE_MAP:
        return MIME_TYPE_MAP[mime_type][1]
    # Default extension
    return "bin"


def guess_mime_type(filename: Optional[str] = None, content: Optional[bytes] = None) -> str:
    """
    Detect MIME type from filename extension or content.

    Args:
        filename: Optional filename to check extension
        content: Optional content bytes for magic number detection

    Returns:
        MIME type string (defaults to "application/octet-stream")
    """
    # Try extension first
    if filename:
        ext = Path(filename).suffix.lower()
        if ext in EXTENSION_MIME_MAP:
            return EXTENSION_MIME_MAP[ext]

    # Try magic number detection for common formats
    if content and len(content) >= 4:
        # PDF
        if content[:4] == b"%PDF":
            return "application/pdf"
        # PNG
        if content[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        # JPEG
        if content[:2] == b"\xff\xd8":
            return "image/jpeg"
        # GIF
        if content[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        # HTML (check for DOCTYPE or opening tags)
        if content[:5].lower() == b"<!doc" or content[:5].lower() == b"<html":
            return "text/html"
        # JSON (starts with { or [)
        stripped = content.lstrip()
        if stripped and stripped[0:1] in (b"{", b"["):
            return "application/json"

    return "application/octet-stream"


def compute_content_hash(content: bytes | str) -> str:
    """
    Compute SHA-256 hash of content.

    Args:
        content: Content as bytes or string

    Returns:
        Hexadecimal hash string
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def should_cache(content: bytes | str) -> bool:
    """
    Determine if content should be stored in cache vs inline.

    Args:
        content: Content as bytes or string

    Returns:
        True if content exceeds CACHE_THRESHOLD
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    return len(content) >= CACHE_THRESHOLD


def save_to_cache(
    artifact_id: str,
    content: bytes | str,
    mime_type: str,
) -> dict:
    """
    Save content to the cache and return metadata.

    Args:
        artifact_id: The artifact ID (used in filename)
        content: Content as bytes or string
        mime_type: MIME type of the content

    Returns:
        Dictionary with:
            - cache_path: Relative path in cache (e.g., "html/artifact-abc123.html")
            - file_size: Size in bytes
            - content_hash: SHA-256 hash
            - full_path: Absolute path to file
    """
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content

    # Get directory and extension for this type
    type_dir = get_type_dir(mime_type)
    extension = guess_extension(mime_type)

    # Build paths
    cache_dir = get_cache_dir()
    type_path = cache_dir / type_dir
    type_path.mkdir(parents=True, exist_ok=True)

    filename = f"{artifact_id}.{extension}"
    full_path = type_path / filename
    cache_path = f"{type_dir}/{filename}"

    # Write file
    full_path.write_bytes(content_bytes)

    return {
        "cache_path": cache_path,
        "file_size": len(content_bytes),
        "content_hash": compute_content_hash(content_bytes),
        "full_path": str(full_path),
    }


def load_from_cache(cache_path: str) -> bytes:
    """
    Load content from cache as bytes.

    Args:
        cache_path: Relative path in cache (e.g., "html/artifact-abc123.html")

    Returns:
        Content as bytes

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    cache_dir = get_cache_dir()
    full_path = cache_dir / cache_path
    return full_path.read_bytes()


def load_from_cache_text(cache_path: str, encoding: str = "utf-8") -> str:
    """
    Load content from cache as text.

    Args:
        cache_path: Relative path in cache
        encoding: Text encoding (default: utf-8)

    Returns:
        Content as string

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    return load_from_cache(cache_path).decode(encoding)


def delete_from_cache(cache_path: str) -> bool:
    """
    Delete a file from the cache.

    Args:
        cache_path: Relative path in cache

    Returns:
        True if file was deleted, False if it didn't exist
    """
    cache_dir = get_cache_dir()
    full_path = cache_dir / cache_path
    if full_path.exists():
        full_path.unlink()
        return True
    return False


def get_cache_stats() -> dict:
    """
    Get statistics about the cache.

    Returns:
        Dictionary with:
            - cache_dir: Absolute path to cache directory
            - total_files: Total number of files
            - total_size: Total size in bytes
            - by_type: Dict mapping type dir to {count, size}
    """
    cache_dir = get_cache_dir()
    stats = {
        "cache_dir": str(cache_dir),
        "total_files": 0,
        "total_size": 0,
        "by_type": {},
    }

    if not cache_dir.exists():
        return stats

    for type_dir in cache_dir.iterdir():
        if type_dir.is_dir():
            type_name = type_dir.name
            type_stats = {"count": 0, "size": 0}

            for file_path in type_dir.iterdir():
                if file_path.is_file():
                    type_stats["count"] += 1
                    type_stats["size"] += file_path.stat().st_size

            if type_stats["count"] > 0:
                stats["by_type"][type_name] = type_stats
                stats["total_files"] += type_stats["count"]
                stats["total_size"] += type_stats["size"]

    return stats


def format_size(size_bytes: int) -> str:
    """
    Format byte size as human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable string (e.g., "1.5 MB")
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

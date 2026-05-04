#!/usr/bin/env python3
"""
Apply the rename map to files — replacing old type names with new ones.

For .tql files: renames type labels in definitions, sub clauses, owns, plays.
Roles names stay UNPREFIXED (they're scoped to their relation).
For .py/.ts/.tsx files: simple string replacement (longest match first).

Usage:
    uv run python scripts/apply_rename_map.py --map scripts/rename_map.json --files FILE [FILE ...]
    uv run python scripts/apply_rename_map.py --map scripts/rename_map.json --files FILE --dry-run
"""

import argparse
import json
import re
import sys
from pathlib import Path


def load_rename_map(path: str) -> dict[str, str]:
    with open(path) as f:
        return json.load(f)


def _find_inline_comment(line: str) -> int:
    """Find the position of an inline # comment, ignoring # inside quotes."""
    in_quote = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quote = not in_quote
        elif ch == '#' and not in_quote:
            return i
    return -1


def apply_to_text(text: str, rename_map: dict[str, str], skip_comments: bool = False) -> str:
    """Apply rename map to text using whole-word replacement.

    Sorts by length descending to prevent partial matches
    (e.g., 'note' matching inside 'note-threading').
    """
    # Sort by old name length descending (longest first to avoid partial matches)
    sorted_renames = sorted(rename_map.items(), key=lambda x: len(x[0]), reverse=True)

    if skip_comments:
        # Process line by line, skip comment portions
        lines = text.split('\n')
        result_lines = []
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith('#') or stripped.startswith('//'):
                result_lines.append(line)  # full comment line — keep unchanged
                continue
            # Split on inline comment (# not inside quotes)
            comment_idx = _find_inline_comment(line)
            if comment_idx >= 0:
                code_part = line[:comment_idx]
                comment_part = line[comment_idx:]
            else:
                code_part = line
                comment_part = ''
            for old_name, new_name in sorted_renames:
                pattern = r'(?<![a-zA-Z0-9_-])' + re.escape(old_name) + r'(?![a-zA-Z0-9_])'
                code_part = re.sub(pattern, new_name, code_part)
            result_lines.append(code_part + comment_part)
        return '\n'.join(result_lines)
    else:
        for old_name, new_name in sorted_renames:
            pattern = r'(?<![a-zA-Z0-9_-])' + re.escape(old_name) + r'(?![a-zA-Z0-9_])'
            text = re.sub(pattern, new_name, text)
        return text


def apply_to_file(filepath: str, rename_map: dict[str, str], dry_run: bool = False) -> dict:
    """Apply renames to a single file. Returns change summary."""
    path = Path(filepath)
    if not path.exists():
        return {"file": filepath, "status": "not_found"}

    original = path.read_text()
    skip_comments = path.suffix in ('.tql', '.typeql')
    modified = apply_to_text(original, rename_map, skip_comments=skip_comments)

    if original == modified:
        return {"file": filepath, "status": "unchanged"}

    # Count changes
    changes = 0
    for old_name in rename_map:
        old_count = original.count(old_name)
        new_count = modified.count(old_name)
        if old_count > new_count:
            changes += old_count - new_count

    if dry_run:
        # Show diff preview
        old_lines = original.splitlines()
        new_lines = modified.splitlines()
        diff_lines = []
        for i, (ol, nl) in enumerate(zip(old_lines, new_lines)):
            if ol != nl:
                diff_lines.append(f"  L{i+1}: {ol.strip()}")
                diff_lines.append(f"     → {nl.strip()}")
        return {
            "file": filepath,
            "status": "would_change",
            "changes": changes,
            "preview": diff_lines[:20],  # first 10 changes
        }

    path.write_text(modified)
    return {"file": filepath, "status": "changed", "changes": changes}


def main():
    parser = argparse.ArgumentParser(description="Apply rename map to files")
    parser.add_argument("--map", required=True, help="Path to rename_map.json")
    parser.add_argument("--files", nargs="+", required=True, help="Files to process")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    args = parser.parse_args()

    rename_map = load_rename_map(args.map)
    print(f"Loaded {len(rename_map)} renames from {args.map}", file=sys.stderr)

    results = []
    for filepath in args.files:
        result = apply_to_file(filepath, rename_map, args.dry_run)
        results.append(result)

        status = result["status"]
        if status == "changed":
            print(f"  ✓ {filepath} ({result['changes']} replacements)", file=sys.stderr)
        elif status == "would_change":
            print(f"  ~ {filepath} ({result['changes']} replacements)", file=sys.stderr)
            for line in result.get("preview", []):
                print(f"    {line}", file=sys.stderr)
        elif status == "unchanged":
            print(f"  - {filepath} (no changes)", file=sys.stderr)
        elif status == "not_found":
            print(f"  ✗ {filepath} (not found)", file=sys.stderr)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

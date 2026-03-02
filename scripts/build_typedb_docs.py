#!/usr/bin/env python3
"""
Build TypeDB 3.x reference documentation from official typedb-docs repo.

Usage:
    uv run python scripts/build_typedb_docs.py

Prerequisites:
    git clone --depth=1 --branch 3.x-development \
        https://github.com/typedb/typedb-docs /tmp/typedb-docs

Outputs:
    local_resources/typedb/typedb-3x-reference.md   — full assembled reference
"""

import re
import sys
from pathlib import Path

DOCS_DIR = Path("/tmp/typedb-docs")
OUT_DIR = Path(__file__).parent.parent / "local_resources" / "typedb"

# Priority files with section titles
SOURCE_FILES = [
    ("reference/modules/ROOT/pages/typedb-2-vs-3/diff.adoc", "TypeDB 2.x to 3.x: What Changed"),
    ("typeql-reference/modules/ROOT/pages/data-model.adoc", "Data Model"),
    ("typeql-reference/modules/ROOT/pages/schema/define.adoc", "Define Query"),
    ("typeql-reference/modules/ROOT/pages/schema/redefine.adoc", "Redefine Query"),
    ("typeql-reference/modules/ROOT/pages/schema/undefine.adoc", "Undefine Query"),
    ("core-concepts/modules/ROOT/pages/typeql/query-clauses.adoc", "Query Clauses"),
    ("typeql-reference/modules/ROOT/pages/pipelines/match.adoc", "Match Pipeline"),
    ("typeql-reference/modules/ROOT/pages/pipelines/fetch.adoc", "Fetch Pipeline"),
    ("typeql-reference/modules/ROOT/pages/pipelines/insert.adoc", "Insert Pipeline"),
    ("typeql-reference/modules/ROOT/pages/pipelines/delete.adoc", "Delete Pipeline"),
    ("typeql-reference/modules/ROOT/pages/pipelines/update.adoc", "Update Pipeline"),
    ("typeql-reference/modules/ROOT/pages/statements/isa.adoc", "Statement: isa"),
    ("typeql-reference/modules/ROOT/pages/statements/has.adoc", "Statement: has"),
    ("typeql-reference/modules/ROOT/pages/statements/sub.adoc", "Statement: sub"),
    ("typeql-reference/modules/ROOT/pages/statements/relates.adoc", "Statement: relates"),
    ("typeql-reference/modules/ROOT/pages/statements/owns.adoc", "Statement: owns"),
    ("typeql-reference/modules/ROOT/pages/statements/plays.adoc", "Statement: plays"),
    ("typeql-reference/modules/ROOT/pages/keywords.adoc", "TypeQL Keywords"),
]


def convert_adoc_to_md(content: str) -> str:
    """Convert AsciiDoc to markdown, stripping Antora-specific markup."""
    lines = content.split("\n")
    out = []
    skip_block = False
    in_source = False
    lang = ""

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip page attribute lines (:attribute: value)
        if re.match(r"^:[a-zA-Z0-9_-]+:.*$", line):
            i += 1
            continue

        # Skip test marker comments inside source blocks  (#!test[...])
        if re.match(r"^#!test\[", line.strip()):
            i += 1
            continue

        # Skip include:: directives
        if line.strip().startswith("include::"):
            i += 1
            continue

        # Handle NOTE/WARNING/TIP/IMPORTANT admonition blocks [NOTE]\n====\n...\n====
        if line.strip() in ("[NOTE]", "[WARNING]", "[TIP]", "[IMPORTANT]", "[CAUTION]"):
            kind = line.strip()[1:-1]
            i += 1
            # Check if next line opens a block
            if i < len(lines) and lines[i].strip() == "====":
                i += 1
                block_lines = []
                while i < len(lines) and lines[i].strip() != "====":
                    block_lines.append(lines[i])
                    i += 1
                i += 1  # skip closing ====
                # Emit as blockquote with kind prefix
                converted_inner = convert_adoc_to_md("\n".join(block_lines))
                for bl in converted_inner.split("\n"):
                    out.append(f"> {bl}" if bl else ">")
                out.append("")
                continue
            else:
                # Inline admonition
                out.append(f"> **{kind}:** {lines[i] if i < len(lines) else ''}")
                i += 1
                continue

        # Skip anchor lines [#_something]
        if re.match(r"^\[#[^\]]+\]$", line.strip()):
            i += 1
            continue

        # Handle source code blocks
        if re.match(r"^\[,?(\w+)?\]$", line.strip()) or re.match(r"^\[source,?(\w+)?\]$", line.strip()):
            m = re.match(r"^\[(?:source,?|,?)(\w+)?\]$", line.strip())
            lang = m.group(1) if m and m.group(1) else ""
            i += 1
            if i < len(lines) and lines[i].strip() == "----":
                i += 1
                code_lines = []
                while i < len(lines) and lines[i].strip() != "----":
                    code_lines.append(lines[i])
                    i += 1
                i += 1  # skip closing ----
                out.append(f"```{lang}")
                out.extend(code_lines)
                out.append("```")
                out.append("")
                continue
            continue

        # Raw code block ---- without preceding [,typeql]
        if line.strip() == "----" and not in_source:
            in_source = True
            out.append("```")
            i += 1
            continue
        if line.strip() == "----" and in_source:
            in_source = False
            out.append("```")
            out.append("")
            i += 1
            continue

        # AsciiDoc table — pass through as-is (it's still readable)
        # Convert headers: = Title -> # Title, == -> ##, === -> ###, etc.
        if re.match(r"^(={1,5})\s+(.+)$", line):
            m = re.match(r"^(={1,5})\s+(.+)$", line)
            level = len(m.group(1))
            title = m.group(2)
            out.append(f"{'#' * level} {title}")
            i += 1
            continue

        # Inline xref: strip to just the display text or the page name
        line = re.sub(r"xref:[^[]+\[([^\]]*)\]", lambda m: m.group(1) or "link", line)

        # Inline links: https://...[text] -> [text](url)
        line = re.sub(r"(https?://[^\[]+)\[([^\]]*)\]", lambda m: f"[{m.group(2) or m.group(1)}]({m.group(1)})", line)

        # Bold **text** stays as-is (already markdown)
        # AsciiDoc bold *text* -> **text**
        line = re.sub(r"\*([^*\n]+)\*", r"**\1**", line)

        # Inline code `text` -> `text` (already markdown)

        # Skip empty Antora tag comments
        if re.match(r"^//\s*(tag|end)::", line):
            i += 1
            continue

        # Skip regular comments
        if line.strip().startswith("//"):
            i += 1
            continue

        # AsciiDoc list item * -> -
        if re.match(r"^\*{1}\s+", line) and not re.match(r"^\*\*", line):
            line = re.sub(r"^\*\s+", "- ", line)
        elif re.match(r"^\*\*\s+", line):
            line = re.sub(r"^\*\*\s+", "  - ", line)
        elif re.match(r"^\*\*\*\s+", line):
            line = re.sub(r"^\*\*\*\s+", "    - ", line)

        # Numbered list . -> 1.
        if re.match(r"^\.\s+", line):
            line = re.sub(r"^\.\s+", "1. ", line)

        out.append(line)
        i += 1

    return "\n".join(out)


def build_full_reference() -> str:
    """Assemble all source files into a single markdown reference."""
    sections = []
    sections.append("# TypeDB 3.x Full Reference")
    sections.append("")
    sections.append(
        "> Generated from https://github.com/typedb/typedb-docs (branch: 3.x-development)"
    )
    sections.append("> Read `local_resources/typedb/llms.txt` for the quick reference cheat sheet.")
    sections.append("")

    missing = []
    for rel_path, section_title in SOURCE_FILES:
        src = DOCS_DIR / rel_path
        if not src.exists():
            missing.append(rel_path)
            print(f"  MISSING: {rel_path}", file=sys.stderr)
            continue

        print(f"  Processing: {rel_path}")
        raw = src.read_text(encoding="utf-8")
        converted = convert_adoc_to_md(raw)

        # Remove leading blank lines
        converted = converted.strip()

        sections.append(f"---")
        sections.append(f"")
        sections.append(f"# {section_title}")
        sections.append(f"")
        sections.append(converted)
        sections.append("")

    if missing:
        print(f"\nWARNING: {len(missing)} files not found. Check DOCS_DIR={DOCS_DIR}", file=sys.stderr)

    return "\n".join(sections)


def main():
    if not DOCS_DIR.exists():
        print(f"ERROR: typedb-docs not found at {DOCS_DIR}", file=sys.stderr)
        print("Run: git clone --depth=1 --branch 3.x-development https://github.com/typedb/typedb-docs /tmp/typedb-docs", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Building TypeDB 3.x full reference...")
    full_ref = build_full_reference()
    out_path = OUT_DIR / "typedb-3x-reference.md"
    out_path.write_text(full_ref, encoding="utf-8")
    size_kb = len(full_ref) / 1024
    print(f"Written: {out_path} ({size_kb:.1f} KB)")

    print("\nDone. llms.txt is hand-curated — edit local_resources/typedb/llms.txt directly.")


if __name__ == "__main__":
    main()

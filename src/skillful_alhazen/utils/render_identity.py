#!/usr/bin/env python3
"""
Render Identity Files — Generate OpenClaw identity files from TypeDB.

This script implements the "Structured Memory Provider" pattern: rendering
structured data from TypeDB into markdown files that OpenClaw can index
and search via its native memory_search infrastructure.

Usage:
    python src/skillful_alhazen/utils/render_identity.py <command> [options]

Commands:
    render-memory       Generate MEMORY.md (preserve pinned notes, regenerate briefing)
    render-heartbeat    Generate HEARTBEAT.md (monitoring tasks from collections)
    render-user         Merge static USER.md header + activity summary from TypeDB
    render-tools        Generate TOOLS.md with TypeDB status, cache stats
    render-agents       Generate skills inventory section of AGENTS.md
    render-collections  Render each collection as memory/<collection-slug>.md
    render-all          Run all renderers
    mark-dirty          Touch the .typedb-dirty flag

Environment:
    TYPEDB_HOST         TypeDB server host (default: localhost)
    TYPEDB_PORT         TypeDB server port (default: 1729)
    TYPEDB_DATABASE     Database name (default: alhazen_notebook)
    ALHAZEN_PROJECT_ROOT  Project root (default: auto-detected)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
_src_dir = Path(__file__).resolve().parent.parent.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

# Configuration
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alhazen_notebook")

# Project root detection
PROJECT_ROOT = os.getenv(
    "ALHAZEN_PROJECT_ROOT",
    str(Path(__file__).resolve().parent.parent.parent.parent),
)

TEMPLATES_DIR = Path(PROJECT_ROOT) / "local_resources" / "openclaw"
SKILLS_MANIFEST_DIR = Path(PROJECT_ROOT) / "local_resources" / "skills"

# Delimiters for preserving static sections
DYNAMIC_START = "<!-- DYNAMIC:"
DYNAMIC_END = "<!-- END DYNAMIC -->"
BRIEFING_START = "<!-- TYPEDB BRIEFING: auto-generated, do not edit below this line -->"
BRIEFING_END = "<!-- END TYPEDB BRIEFING -->"
AUTO_GEN_START = "<!-- AUTO-GENERATED:"
AUTO_GEN_END = "<!-- END AUTO-GENERATED -->"


# ---------------------------------------------------------------------------
# TypeDB connection helpers
# ---------------------------------------------------------------------------

def get_typedb_driver():
    """Get a TypeDB driver, or None if unavailable."""
    try:
        from typedb.driver import TypeDB
        return TypeDB.core_driver(f"{TYPEDB_HOST}:{TYPEDB_PORT}")
    except Exception:
        return None


def typedb_available() -> bool:
    """Check if TypeDB is reachable."""
    driver = get_typedb_driver()
    if driver is None:
        return False
    try:
        exists = driver.databases.contains(TYPEDB_DATABASE)
        driver.close()
        return exists
    except Exception:
        try:
            driver.close()
        except Exception:
            pass
        return False


def run_query(query: str, *, write: bool = False) -> list:
    """Run a TypeQL query and return results (for fetch queries)."""
    from typedb.driver import SessionType, TransactionType
    driver = get_typedb_driver()
    if driver is None:
        return []
    try:
        tx_type = TransactionType.WRITE if write else TransactionType.READ
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(tx_type) as tx:
                results = list(tx.query.fetch(query))
                if write:
                    tx.commit()
                return results
    except Exception as e:
        print(f"TypeDB query error: {e}", file=sys.stderr)
        return []
    finally:
        try:
            driver.close()
        except Exception:
            pass


def run_count_query(query: str) -> int:
    """Run a TypeQL match-aggregate count query."""
    from typedb.driver import SessionType, TransactionType
    driver = get_typedb_driver()
    if driver is None:
        return 0
    try:
        with driver.session(TYPEDB_DATABASE, SessionType.DATA) as session:
            with session.transaction(TransactionType.READ) as tx:
                result = tx.query.match_aggregate(query)
                if result and result.is_int():
                    return result.as_int()
                return 0
    except Exception as e:
        print(f"TypeDB count query error: {e}", file=sys.stderr)
        return 0
    finally:
        try:
            driver.close()
        except Exception:
            pass


def parse_fetch_result(result: dict) -> dict:
    """Parse a TypeDB fetch result into a flat dictionary."""
    parsed = {}
    for key, value in result.items():
        if isinstance(value, dict):
            for attr_name, attr_value in value.items():
                if attr_name != "type":
                    if isinstance(attr_value, list) and len(attr_value) == 1:
                        parsed[attr_name] = attr_value[0].get("value")
                    elif isinstance(attr_value, list) and len(attr_value) > 1:
                        parsed[attr_name] = [v.get("value") for v in attr_value]
                    elif isinstance(attr_value, dict):
                        parsed[attr_name] = attr_value.get("value")
        else:
            parsed[key] = value
    return parsed


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def query_collections() -> list[dict]:
    """Get all collections with member counts."""
    collections = run_query(
        "match $c isa collection; fetch $c: id, name, description, logical-query;"
    )
    result = []
    for c in collections:
        parsed = parse_fetch_result(c)
        cid = parsed.get("id", "")
        count = run_count_query(
            f'match $c isa collection, has id "{cid}"; '
            f'(collection: $c, member: $m) isa collection-membership; '
            f'get $m; count;'
        )
        parsed["member_count"] = count
        result.append(parsed)
    return result


def query_recent_notes(days: int = 7, limit: int = 20) -> list[dict]:
    """Get recent notes with their aboutness context."""
    # Get recent notes ordered by created-at
    notes = run_query(
        f"match $n isa note, has created-at $t; "
        f"fetch $n: id, content, confidence, created-at; "
        f"sort $t desc; limit {limit};"
    )
    result = []
    for n in notes:
        parsed = parse_fetch_result(n)
        nid = parsed.get("id", "")
        # Get what the note is about
        subjects = run_query(
            f'match $n isa note, has id "{nid}"; '
            f'(note: $n, subject: $s) isa aboutness; '
            f'fetch $s: id, name;'
        )
        parsed["subjects"] = [parse_fetch_result(s) for s in subjects]
        result.append(parsed)
    return result


def query_tagged_notes(tag_name: str, limit: int = 20) -> list[dict]:
    """Get notes with a specific tag."""
    notes = run_query(
        f'match $t isa tag, has name "{tag_name}"; '
        f'(tagged-entity: $n, tag: $t) isa tagging; '
        f'$n isa note; '
        f'fetch $n: id, content, confidence, created-at; '
        f'limit {limit};'
    )
    return [parse_fetch_result(n) for n in notes]


def query_user_questions(resolved: bool = False, limit: int = 10) -> list[dict]:
    """Get open user questions."""
    questions = run_query(
        f"match $q isa user-question; "
        f"fetch $q: id, content, created-at; "
        f"limit {limit};"
    )
    return [parse_fetch_result(q) for q in questions]


def query_collection_detail(collection_id: str) -> dict:
    """Get detailed collection info with members and notes."""
    collections = run_query(
        f'match $c isa collection, has id "{collection_id}"; '
        f'fetch $c: id, name, description, logical-query;'
    )
    if not collections:
        return {}

    info = parse_fetch_result(collections[0])

    # Get members
    members = run_query(
        f'match $c isa collection, has id "{collection_id}"; '
        f'(collection: $c, member: $m) isa collection-membership; '
        f'fetch $m: id, name, description; limit 50;'
    )
    info["members"] = [parse_fetch_result(m) for m in members]

    return info


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:60]


def format_datetime(dt_value) -> str:
    """Format a datetime value for display."""
    if isinstance(dt_value, str):
        try:
            dt = datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
            return dt.strftime("%b %d")
        except (ValueError, AttributeError):
            return str(dt_value)[:10]
    if isinstance(dt_value, datetime):
        return dt_value.strftime("%b %d")
    return str(dt_value)[:10] if dt_value else "unknown"


def truncate(text: str, max_len: int = 120) -> str:
    """Truncate text with ellipsis."""
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def preserve_static_section(
    existing_content: str,
    new_content: str,
    start_marker: str,
    end_marker: str,
) -> str:
    """Replace only the dynamic section, preserving static content above the marker."""
    if not existing_content:
        return new_content

    # Find the start marker in existing content
    start_idx = existing_content.find(start_marker)
    if start_idx == -1:
        # No marker found — append dynamic section
        return existing_content.rstrip() + "\n\n" + new_content

    # Everything before the start marker is static
    static_part = existing_content[:start_idx].rstrip()

    # Find the dynamic section in new content
    new_start_idx = new_content.find(start_marker)
    if new_start_idx == -1:
        dynamic_part = new_content
    else:
        dynamic_part = new_content[new_start_idx:]

    return static_part + "\n" + dynamic_part


def load_skill_manifests() -> list[dict]:
    """Load skill manifests from YAML files."""
    manifests = []
    if not SKILLS_MANIFEST_DIR.exists():
        return manifests

    for yaml_file in sorted(SKILLS_MANIFEST_DIR.glob("*.yaml")):
        manifest = {}
        with open(yaml_file) as f:
            for line in f:
                line = line.strip()
                if ":" in line and not line.startswith("#") and not line.startswith("-"):
                    key, _, val = line.partition(":")
                    key = key.strip()
                    val = val.strip().strip('"')
                    if key in ("name", "description"):
                        manifest[key] = val
        if manifest.get("name"):
            manifests.append(manifest)
    return manifests


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_memory(workspace: Path) -> None:
    """Render MEMORY.md: preserve pinned notes, regenerate briefing from TypeDB."""
    memory_path = workspace / "MEMORY.md"
    existing = memory_path.read_text() if memory_path.exists() else ""

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    available = typedb_available()

    # Build the briefing section
    lines = []
    lines.append(BRIEFING_START)
    lines.append(f"## Knowledge Briefing")
    lines.append(f"*Rendered: {now} from TypeDB*")
    lines.append("")

    if not available:
        lines.append("*TypeDB unavailable. Showing last known state or defaults.*")
        lines.append("")
    else:
        # Collections table
        collections = query_collections()
        if collections:
            lines.append("### Collections")
            lines.append("| Collection | Items | Description |")
            lines.append("|---|---|---|")
            for c in collections:
                name = c.get("name", "unnamed")
                count = c.get("member_count", 0)
                desc = truncate(c.get("description", ""), 60)
                lines.append(f"| {name} | {count} | {desc} |")
            lines.append("")

        # Recent notes
        notes = query_recent_notes(days=7, limit=20)
        if notes:
            lines.append("### Recent Notes")
            for n in notes:
                date = format_datetime(n.get("created-at"))
                content = truncate(n.get("content", ""), 100)
                confidence = n.get("confidence")
                subjects = n.get("subjects", [])
                subject_names = ", ".join(
                    s.get("name", s.get("id", "?"))[:40] for s in subjects[:2]
                )
                conf_str = f" (confidence: {confidence})" if confidence else ""
                re_str = f" re: {subject_names}" if subject_names else ""
                lines.append(f"- [{date}]{re_str} -- \"{content}\"{conf_str}")
            lines.append("")

        # Open questions
        questions = query_user_questions(resolved=False, limit=5)
        if questions:
            lines.append("### Open Questions")
            for q in questions:
                content = truncate(q.get("content", ""), 120)
                lines.append(f'- "{content}"')
            lines.append("")

        # Saved searches (collections with logical-query)
        saved = [c for c in collections if c.get("logical-query")]
        if saved:
            lines.append("### Saved Searches")
            for s in saved:
                name = s.get("name", "unnamed")
                query = s.get("logical-query", "")
                lines.append(f'- "{query}" -> collection: {name}')
            lines.append("")

    lines.append(BRIEFING_END)

    dynamic_section = "\n".join(lines)

    if existing:
        # Preserve everything before the briefing marker (pinned notes)
        result = preserve_static_section(
            existing, dynamic_section, BRIEFING_START, BRIEFING_END
        )
    else:
        # No existing file — use template
        template_path = TEMPLATES_DIR / "MEMORY.md.template"
        if template_path.exists():
            template = template_path.read_text()
            result = preserve_static_section(
                template, dynamic_section, BRIEFING_START, BRIEFING_END
            )
        else:
            result = "# MEMORY.md\n\n## Pinned Notes\n<!-- This section is yours to edit. It persists across renders. -->\n\n" + dynamic_section

    memory_path.write_text(result + "\n")
    print(f"Rendered {memory_path}", file=sys.stderr)


def render_heartbeat(workspace: Path) -> None:
    """Render HEARTBEAT.md from TypeDB saved searches and pending notes."""
    heartbeat_path = workspace / "HEARTBEAT.md"
    available = typedb_available()

    lines = []
    lines.append("# HEARTBEAT.md — Periodic Research Tasks")
    lines.append("<!-- Auto-generated from TypeDB saved searches and pending notes -->")
    lines.append("")

    # Paper monitoring: collections with logical-query
    lines.append("## Paper Monitoring")
    if available:
        collections = query_collections()
        saved = [c for c in collections if c.get("logical-query")]
        if saved:
            for s in saved:
                name = s.get("name", "unnamed")
                query = s.get("logical-query", "")
                lines.append(
                    f'- Check Europe PMC: "{query}" '
                    f"(collection: {name})"
                )
        else:
            lines.append("*No saved searches configured.*")
    else:
        lines.append("*TypeDB unavailable.*")
    lines.append("")

    # Pending follow-ups: notes tagged follow-up or todo
    lines.append("## Pending Follow-ups")
    if available:
        followups = query_tagged_notes("follow-up", limit=10)
        todos = query_tagged_notes("todo", limit=10)
        pending = followups + todos
        if pending:
            seen_ids = set()
            for n in pending:
                nid = n.get("id", "")
                if nid in seen_ids:
                    continue
                seen_ids.add(nid)
                content = truncate(n.get("content", ""), 100)
                date = format_datetime(n.get("created-at"))
                lines.append(f"- [{date}] {content}")
        else:
            lines.append("*No pending follow-ups.*")
    else:
        lines.append("*TypeDB unavailable.*")
    lines.append("")

    # Job Forager section (if job_forager.py exists)
    forager_script = Path(PROJECT_ROOT) / ".claude" / "skills" / "jobhunt" / "job_forager.py"
    if forager_script.exists():
        lines.append("## Job Forager (daily)")
        lines.append("")
        lines.append("Run the job forager heartbeat to discover new postings from configured sources.")
        lines.append("Only run once per day -- check memory/heartbeat-state.json for last run time.")
        lines.append("")
        lines.append("```bash")
        lines.append(
            f"uv run --project {PROJECT_ROOT} python {forager_script} "
            f"heartbeat --min-relevance 0.1"
        )
        lines.append("```")
        lines.append("")
        lines.append("After running:")
        lines.append("- If new candidates found, summarize them to the user (titles, companies, relevance scores)")
        lines.append('- Update memory/heartbeat-state.json with timestamp: {"job_forager": "YYYY-MM-DDTHH:MM:SS"}')
        lines.append("- If no sources configured yet, suggest running suggest-sources and mention add-source")
        lines.append("")

    # Maintenance section
    dirty_flag = workspace / ".typedb-dirty"
    lines.append("## Maintenance")
    lines.append(f"- Check `{dirty_flag}` -- if exists and MEMORY.md older than flag:")
    lines.append(
        f"  run: `uv run python {PROJECT_ROOT}/src/skillful_alhazen/utils/render_identity.py "
        f"render-all --workspace {workspace}`"
    )
    lines.append(f"  then: `rm {dirty_flag}`")
    lines.append("")

    heartbeat_path.write_text("\n".join(lines) + "\n")
    print(f"Rendered {heartbeat_path}", file=sys.stderr)


def render_user(workspace: Path) -> None:
    """Render USER.md: preserve static header, add activity from TypeDB."""
    user_path = workspace / "USER.md"
    existing = user_path.read_text() if user_path.exists() else ""
    available = typedb_available()

    # Build dynamic section
    dyn_lines = []
    dyn_lines.append(f"{DYNAMIC_START} auto-generated from TypeDB activity -- do not edit below this line -->")

    if available:
        collections = query_collections()
        if collections:
            dyn_lines.append("## Active Research Threads")
            for c in collections:
                name = c.get("name", "unnamed")
                count = c.get("member_count", 0)
                desc = c.get("description", "")
                dyn_lines.append(f"- \"{name}\" -- {count} items" + (f" ({desc})" if desc else ""))
        else:
            dyn_lines.append("## Active Research Threads")
            dyn_lines.append("*No collections found in TypeDB.*")
    else:
        dyn_lines.append("## Active Research Threads")
        dyn_lines.append("*TypeDB unavailable.*")

    dyn_lines.append(DYNAMIC_END)
    dynamic_section = "\n".join(dyn_lines)

    if existing:
        result = preserve_static_section(
            existing, dynamic_section, DYNAMIC_START, DYNAMIC_END
        )
    else:
        # Use template
        template_path = TEMPLATES_DIR / "USER.md.template"
        if template_path.exists():
            template = template_path.read_text()
            result = preserve_static_section(
                template, dynamic_section, DYNAMIC_START, DYNAMIC_END
            )
        else:
            result = "# USER.md\n\n" + dynamic_section

    user_path.write_text(result + "\n")
    print(f"Rendered {user_path}", file=sys.stderr)


def render_tools(workspace: Path) -> None:
    """Render TOOLS.md with environment state."""
    tools_path = workspace / "TOOLS.md"

    # Check TypeDB status
    available = typedb_available()
    typedb_status = "running" if available else "stopped"

    # Get cache stats
    try:
        from skillful_alhazen.utils.cache import get_cache_dir, get_cache_stats, format_size
        stats = get_cache_stats()
        cache_dir = stats["cache_dir"]
        cache_parts = []
        for type_name, type_stats in stats.get("by_type", {}).items():
            cache_parts.append(f"{type_stats['count']} {type_name}")
        cache_stats_str = ", ".join(cache_parts) if cache_parts else "empty"
        cache_stats_str += f" ({format_size(stats['total_size'])} total)"
    except Exception:
        cache_dir = str(Path.home() / ".alhazen" / "cache")
        cache_stats_str = "unable to read"

    # Detect loaded namespaces
    namespaces = []
    ns_dir = Path(PROJECT_ROOT) / "local_resources" / "typedb" / "namespaces"
    if ns_dir.exists():
        namespaces = [f.stem for f in sorted(ns_dir.glob("*.tql"))]

    content = f"""# TOOLS.md — Environment Notes

## TypeDB
- Host: {TYPEDB_HOST}:{TYPEDB_PORT}
- Database: {TYPEDB_DATABASE}
- Namespaces: {', '.join(namespaces) if namespaces else 'none'}
- Status: {typedb_status}

## Artifact Cache
- Location: {cache_dir}
- Stats: {cache_stats_str}

## CLI Pattern
All skills follow: `uv run python .claude/skills/<name>/<name>.py <subcommand> [args]`
Use `--help` on any script for available subcommands.

## Project Root
ALHAZEN_PROJECT_ROOT = {PROJECT_ROOT}
"""

    tools_path.write_text(content)
    print(f"Rendered {tools_path}", file=sys.stderr)


def render_agents(workspace: Path) -> None:
    """Update the auto-generated skills inventory in AGENTS.md."""
    agents_path = workspace / "AGENTS.md"

    if not agents_path.exists():
        # Copy template
        template_path = TEMPLATES_DIR / "AGENTS.md"
        if template_path.exists():
            import shutil
            shutil.copy2(template_path, agents_path)
        else:
            return

    existing = agents_path.read_text()

    # Build skills inventory from manifests
    manifests = load_skill_manifests()
    inv_lines = []
    inv_lines.append(f"{AUTO_GEN_START} skill inventory from manifests -->")
    inv_lines.append("<!-- Re-generated by: render_identity.py render-agents -->")
    for m in manifests:
        name = m.get("name", "unknown")
        desc = m.get("description", "")
        inv_lines.append(f"- /{name} -- {desc}")
    inv_lines.append(AUTO_GEN_END)

    inventory_section = "\n".join(inv_lines)
    result = preserve_static_section(
        existing, inventory_section, AUTO_GEN_START, AUTO_GEN_END
    )

    agents_path.write_text(result + "\n")
    print(f"Rendered {agents_path}", file=sys.stderr)


def render_collections(workspace: Path) -> None:
    """Render each collection as memory/<collection-slug>.md."""
    memory_dir = workspace / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    if not typedb_available():
        print("TypeDB unavailable, skipping collection rendering", file=sys.stderr)
        return

    collections = query_collections()
    for c in collections:
        cid = c.get("id", "")
        name = c.get("name", "unnamed")
        slug = slugify(name)
        if not slug:
            slug = cid

        detail = query_collection_detail(cid)
        members = detail.get("members", [])
        description = c.get("description", "")
        logical_query = c.get("logical-query", "")

        lines = []
        lines.append(f"# Collection: {name}")
        lines.append("")
        if description:
            lines.append(f"{description}")
            lines.append("")
        if logical_query:
            lines.append(f"**Saved search:** `{logical_query}`")
            lines.append("")

        lines.append(f"**Members:** {c.get('member_count', len(members))}")
        lines.append("")

        if members:
            lines.append("## Items")
            for m in members[:30]:  # Cap at 30 to keep files bounded
                mname = m.get("name", m.get("id", "?"))
                mdesc = truncate(m.get("description", ""), 80)
                lines.append(f"- **{mname}**" + (f" -- {mdesc}" if mdesc else ""))
            if len(members) > 30:
                lines.append(f"- ... and {len(members) - 30} more")
            lines.append("")

        # Get notes about collection members (sample)
        notes_for_collection = []
        for m in members[:10]:
            mid = m.get("id", "")
            if mid:
                member_notes = run_query(
                    f'match $s isa information-content-entity, has id "{mid}"; '
                    f'(note: $n, subject: $s) isa aboutness; '
                    f'fetch $n: id, content, confidence; limit 3;'
                )
                for n in member_notes:
                    parsed = parse_fetch_result(n)
                    parsed["about"] = m.get("name", mid)
                    notes_for_collection.append(parsed)

        if notes_for_collection:
            lines.append("## Key Notes")
            for n in notes_for_collection[:15]:
                content = truncate(n.get("content", ""), 100)
                about = n.get("about", "?")
                conf = n.get("confidence")
                conf_str = f" (confidence: {conf})" if conf else ""
                lines.append(f"- re: {about} -- \"{content}\"{conf_str}")
            lines.append("")

        file_path = memory_dir / f"collection-{slug}.md"
        file_path.write_text("\n".join(lines) + "\n")
        print(f"Rendered {file_path}", file=sys.stderr)


def render_all(workspace: Path) -> None:
    """Run all renderers."""
    workspace.mkdir(parents=True, exist_ok=True)

    # Copy SOUL.md (static, never changes)
    soul_src = TEMPLATES_DIR / "SOUL.md"
    soul_dst = workspace / "SOUL.md"
    if soul_src.exists() and not soul_dst.exists():
        soul_dst.write_text(soul_src.read_text())
        print(f"Copied {soul_dst}", file=sys.stderr)

    # Copy AGENTS.md template if not exists, then update
    agents_dst = workspace / "AGENTS.md"
    if not agents_dst.exists():
        agents_src = TEMPLATES_DIR / "AGENTS.md"
        if agents_src.exists():
            agents_dst.write_text(agents_src.read_text())
            print(f"Copied {agents_dst}", file=sys.stderr)

    # Copy USER.md template if not exists
    user_dst = workspace / "USER.md"
    if not user_dst.exists():
        user_src = TEMPLATES_DIR / "USER.md.template"
        if user_src.exists():
            user_dst.write_text(user_src.read_text())
            print(f"Copied {user_dst}", file=sys.stderr)

    render_agents(workspace)
    render_tools(workspace)
    render_user(workspace)
    render_memory(workspace)
    render_heartbeat(workspace)
    render_collections(workspace)

    print("All identity files rendered.", file=sys.stderr)


def mark_dirty(workspace: Path) -> None:
    """Touch the .typedb-dirty flag file."""
    dirty_path = workspace / ".typedb-dirty"
    dirty_path.touch()
    print(f"Touched {dirty_path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Render OpenClaw identity files from TypeDB"
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.home() / ".openclaw" / "workspace",
        help="OpenClaw workspace directory (default: ~/.openclaw/workspace)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("render-memory", help="Generate MEMORY.md")
    subparsers.add_parser("render-heartbeat", help="Generate HEARTBEAT.md")
    subparsers.add_parser("render-user", help="Generate USER.md")
    subparsers.add_parser("render-tools", help="Generate TOOLS.md")
    subparsers.add_parser("render-agents", help="Update skills in AGENTS.md")
    subparsers.add_parser("render-collections", help="Render collection files")
    subparsers.add_parser("render-all", help="Run all renderers")
    subparsers.add_parser("mark-dirty", help="Touch .typedb-dirty flag")

    args = parser.parse_args()
    workspace = args.workspace
    workspace.mkdir(parents=True, exist_ok=True)

    commands = {
        "render-memory": render_memory,
        "render-heartbeat": render_heartbeat,
        "render-user": render_user,
        "render-tools": render_tools,
        "render-agents": render_agents,
        "render-collections": render_collections,
        "render-all": render_all,
        "mark-dirty": mark_dirty,
    }

    func = commands[args.command]
    func(workspace)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Skill usage logger for Alhazen.

Serves two purposes:
1. PostToolUse Claude Code hook — reads JSON from stdin, detects skill
   invocations, estimates token counts, writes records to TypeDB.
2. CLI tool — query, label, and export logged invocations.

Usage as hook (configured in .claude/settings.json):
    uv run python local_resources/skilllog/skill_logger.py

Usage as CLI:
    uv run python local_resources/skilllog/skill_logger.py list-invocations [--skill NAME]
    uv run python local_resources/skilllog/skill_logger.py token-report [--skill NAME]
    uv run python local_resources/skilllog/skill_logger.py label --id INVOCATION_ID (--golden | --rejected | --unlabeled)
    uv run python local_resources/skilllog/skill_logger.py export-golden --skill NAME [--output FILE]
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Add project root to sys.path so config.py is importable
sys.path.insert(0, str(PROJECT_ROOT / "local_resources" / "skilllog"))
from config import (
    error_on_typedb_unavailable,
    get_disabled_skills,
    is_monitoring_enabled,
    is_skill_active,
)

# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """
    Estimate token count using tiktoken (cl100k_base encoding).
    Falls back to character / 4 heuristic if tiktoken is unavailable.
    """
    if not text:
        return 0
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Skill detection
# ---------------------------------------------------------------------------

# Patterns that identify a bash command as a skill invocation
SKILL_PATTERNS = [
    # Built-in skills: .claude/skills/<name>/<name>.py
    re.compile(r'\.claude/skills/(?P<skill>[^/]+)/\S+\.py\s+(?P<command>\S+)'),
    # External skills: local_skills/<name>/<name>.py
    re.compile(r'local_skills/(?P<skill>[^/]+)/\S+\.py\s+(?P<command>\S+)'),
]


def detect_skill_invocation(command: str) -> Optional[tuple[str, str]]:
    """
    Returns (skill_name, command_name) if the bash command is a skill call,
    else None.
    """
    for pattern in SKILL_PATTERNS:
        m = pattern.search(command)
        if m:
            return m.group("skill"), m.group("command")
    return None


# ---------------------------------------------------------------------------
# TypeDB helpers
# ---------------------------------------------------------------------------

def get_typedb_connection():
    """Return (client, session) connected to the configured TypeDB database."""
    try:
        from typedb.driver import TypeDB, SessionType, TransactionType
    except ImportError:
        raise RuntimeError("typedb-driver is not installed. Run: uv sync --all-extras")

    host = os.environ.get("TYPEDB_HOST", "localhost")
    port = int(os.environ.get("TYPEDB_PORT", "1729"))
    database = os.environ.get("TYPEDB_DATABASE", "alhazen_notebook")

    client = TypeDB.core_driver(f"{host}:{port}")
    session = client.session(database, SessionType.DATA)
    return client, session


def generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def escape_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def get_timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# Hook entry point (PostToolUse)
# ---------------------------------------------------------------------------

def run_hook():
    """
    Main hook handler. Reads Claude Code PostToolUse JSON from stdin.
    Exits 0 if monitoring disabled or command is not a skill invocation.
    Exits non-zero if TypeDB write fails (when error_on_typedb_unavailable is True).
    """
    if not is_monitoring_enabled():
        sys.exit(0)

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    # Only handle Bash tool calls
    if payload.get("tool_name") != "Bash":
        sys.exit(0)

    tool_input = payload.get("tool_input", {})
    tool_response = payload.get("tool_response", {})

    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    detected = detect_skill_invocation(command)
    if detected is None:
        sys.exit(0)

    skill_name, cmd_name = detected

    # Check if this skill is active
    if not is_skill_active(skill_name):
        sys.exit(0)

    # Collect output
    output_text = ""
    if isinstance(tool_response, dict):
        output_text = tool_response.get("output", "") or ""
        if not output_text:
            output_text = str(tool_response)
    elif isinstance(tool_response, str):
        output_text = tool_response

    exit_code = 0
    if isinstance(tool_response, dict):
        # Claude Code doesn't always expose exit code directly; try to infer
        if tool_response.get("is_error"):
            exit_code = 1

    input_tokens = estimate_tokens(command)
    output_tokens = estimate_tokens(output_text)
    total_tokens = input_tokens + output_tokens
    timestamp = get_timestamp()
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")

    invocation_id = generate_id("skilllog-inv")
    input_id = generate_id("skilllog-in")
    output_id = generate_id("skilllog-out")

    try:
        client, session = get_typedb_connection()
        from typedb.driver import TransactionType

        with session.transaction(TransactionType.WRITE) as tx:
            # Insert invocation entity
            tx.query.insert(f"""
                insert $inv isa skilllog-invocation,
                    has id "{invocation_id}",
                    has name "{escape_string(f'{skill_name}:{cmd_name}')}",
                    has skill-name "{escape_string(skill_name)}",
                    has command-name "{escape_string(cmd_name)}",
                    has session-id "{escape_string(session_id)}",
                    has exit-code {exit_code},
                    has input-tokens-estimate {input_tokens},
                    has output-tokens-estimate {output_tokens},
                    has total-tokens-estimate {total_tokens},
                    has evaluation-label "unlabeled",
                    has created-at {timestamp},
                    has provenance "skilllog-hook";
            """)

            # Insert input artifact (store inline — commands are always small)
            tx.query.insert(f"""
                insert $art isa skilllog-input,
                    has id "{input_id}",
                    has name "input:{invocation_id}",
                    has content "{escape_string(command)}",
                    has format "bash",
                    has created-at {timestamp},
                    has provenance "skilllog-hook";
            """)

            # Insert output artifact (truncate if very large)
            truncated_output = output_text[:8000] if len(output_text) > 8000 else output_text
            tx.query.insert(f"""
                insert $art isa skilllog-output,
                    has id "{output_id}",
                    has name "output:{invocation_id}",
                    has content "{escape_string(truncated_output)}",
                    has format "text",
                    has created-at {timestamp},
                    has provenance "skilllog-hook";
            """)

            # Link input artifact to invocation via representation relation
            tx.query.insert(f"""
                match
                    $inv isa skilllog-invocation, has id "{invocation_id}";
                    $art isa skilllog-input, has id "{input_id}";
                insert (referent: $inv, artifact: $art) isa representation;
            """)

            # Link output artifact to invocation
            tx.query.insert(f"""
                match
                    $inv isa skilllog-invocation, has id "{invocation_id}";
                    $art isa skilllog-output, has id "{output_id}";
                insert (referent: $inv, artifact: $art) isa representation;
            """)

            tx.commit()

        session.close()
        client.close()

    except Exception as e:
        if error_on_typedb_unavailable():
            print(f"[skilllog] ERROR: Failed to log invocation to TypeDB: {e}", file=sys.stderr)
            sys.exit(1)
        # If error_on_typedb_unavailable is False (not the default), silently pass
        sys.exit(0)


# ---------------------------------------------------------------------------
# CLI subcommands (Task #5)
# ---------------------------------------------------------------------------

def cmd_list_invocations(args):
    """List recent skill invocations from TypeDB."""
    try:
        client, session = get_typedb_connection()
        from typedb.driver import TransactionType

        skill_filter = f', has skill-name "{args.skill}"' if args.skill else ""
        limit = args.limit if hasattr(args, "limit") and args.limit else 50

        with session.transaction(TransactionType.READ) as tx:
            query = f"""
                match $inv isa skilllog-invocation{skill_filter},
                    has id $id,
                    has skill-name $skill,
                    has command-name $cmd,
                    has total-tokens-estimate $tokens,
                    has evaluation-label $label,
                    has created-at $ts;
                fetch $id; $skill; $cmd; $tokens; $label; $ts;
                limit {limit};
            """
            results = list(tx.query.fetch(query))

        session.close()
        client.close()

        rows = []
        for r in results:
            rows.append({
                "id": r["id"]["value"],
                "skill": r["skill"]["value"],
                "command": r["cmd"]["value"],
                "tokens": r["tokens"]["value"],
                "label": r["label"]["value"],
                "timestamp": r["ts"]["value"],
            })

        print(json.dumps(rows, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_token_report(args):
    """Summarize token usage by skill and command."""
    try:
        client, session = get_typedb_connection()
        from typedb.driver import TransactionType

        skill_filter = f', has skill-name "{args.skill}"' if args.skill else ""

        with session.transaction(TransactionType.READ) as tx:
            query = f"""
                match $inv isa skilllog-invocation{skill_filter},
                    has skill-name $skill,
                    has command-name $cmd,
                    has total-tokens-estimate $tokens;
                fetch $skill; $cmd; $tokens;
            """
            results = list(tx.query.fetch(query))

        session.close()
        client.close()

        # Aggregate
        from collections import defaultdict
        skill_totals: dict = defaultdict(lambda: {"total": 0, "count": 0, "commands": defaultdict(lambda: {"total": 0, "count": 0})})

        for r in results:
            skill = r["skill"]["value"]
            cmd = r["cmd"]["value"]
            tokens = r["tokens"]["value"]
            skill_totals[skill]["total"] += tokens
            skill_totals[skill]["count"] += 1
            skill_totals[skill]["commands"][cmd]["total"] += tokens
            skill_totals[skill]["commands"][cmd]["count"] += 1

        print("\nToken Usage Report")
        print("=" * 60)
        for skill, data in sorted(skill_totals.items(), key=lambda x: -x[1]["total"]):
            avg = data["total"] // data["count"] if data["count"] else 0
            print(f"\n{skill}: {data['total']:,} tokens total ({data['count']} calls, avg {avg:,})")
            for cmd, cdata in sorted(data["commands"].items(), key=lambda x: -x[1]["total"]):
                cavg = cdata["total"] // cdata["count"] if cdata["count"] else 0
                print(f"  {cmd:<30} {cdata['total']:>8,} tokens  ({cdata['count']} calls, avg {cavg:,})")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_label(args):
    """Set evaluation label on an invocation."""
    label = "golden" if args.golden else ("rejected" if args.rejected else "unlabeled")

    try:
        client, session = get_typedb_connection()
        from typedb.driver import TransactionType

        with session.transaction(TransactionType.WRITE) as tx:
            # Delete old label
            tx.query.delete(f"""
                match $inv isa skilllog-invocation, has id "{args.id}", has evaluation-label $old;
                delete $inv has evaluation-label $old;
            """)
            # Insert new label
            tx.query.insert(f"""
                match $inv isa skilllog-invocation, has id "{args.id}";
                insert $inv has evaluation-label "{label}";
            """)
            tx.commit()

        session.close()
        client.close()
        print(json.dumps({"success": True, "id": args.id, "label": label}))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_export_golden(args):
    """Export golden invocations as JSON for TextGrad consumption."""
    try:
        client, session = get_typedb_connection()
        from typedb.driver import TransactionType

        skill_filter = f', has skill-name "{args.skill}"' if args.skill else ""

        with session.transaction(TransactionType.READ) as tx:
            # Get golden invocations
            query = f"""
                match $inv isa skilllog-invocation{skill_filter},
                    has id $id,
                    has skill-name $skill,
                    has command-name $cmd,
                    has evaluation-label "golden",
                    has created-at $ts;
                fetch $id; $skill; $cmd; $ts;
            """
            inv_results = list(tx.query.fetch(query))

            records = []
            for r in inv_results:
                inv_id = r["id"]["value"]

                # Get input artifact
                in_q = f"""
                    match $inv isa skilllog-invocation, has id "{inv_id}";
                        $art isa skilllog-input, has content $c;
                        (referent: $inv, artifact: $art) isa representation;
                    fetch $c;
                """
                in_res = list(tx.query.fetch(in_q))
                input_content = in_res[0]["c"]["value"] if in_res else ""

                # Get output artifact
                out_q = f"""
                    match $inv isa skilllog-invocation, has id "{inv_id}";
                        $art isa skilllog-output, has content $c;
                        (referent: $inv, artifact: $art) isa representation;
                    fetch $c;
                """
                out_res = list(tx.query.fetch(out_q))
                output_content = out_res[0]["c"]["value"] if out_res else ""

                records.append({
                    "id": inv_id,
                    "skill": r["skill"]["value"],
                    "command": r["cmd"]["value"],
                    "timestamp": r["ts"]["value"],
                    "input": input_content,
                    "output": output_content,
                })

        session.close()
        client.close()

        output = json.dumps(records, indent=2)
        if args.output:
            Path(args.output).write_text(output)
            print(f"Exported {len(records)} golden invocations to {args.output}")
        else:
            print(output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def main():
    # If stdin has data (hook mode) and no CLI args given, run as hook
    if len(sys.argv) == 1 and not sys.stdin.isatty():
        run_hook()
        return

    parser = argparse.ArgumentParser(
        description="Skill usage logger for Alhazen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list-invocations
    p_list = sub.add_parser("list-invocations", help="List logged skill invocations")
    p_list.add_argument("--skill", help="Filter by skill name")
    p_list.add_argument("--limit", type=int, default=50, help="Max results (default 50)")
    p_list.set_defaults(func=cmd_list_invocations)

    # token-report
    p_report = sub.add_parser("token-report", help="Token usage summary by skill and command")
    p_report.add_argument("--skill", help="Filter by skill name")
    p_report.set_defaults(func=cmd_token_report)

    # label
    p_label = sub.add_parser("label", help="Set evaluation label on an invocation")
    p_label.add_argument("--id", required=True, help="Invocation ID")
    label_group = p_label.add_mutually_exclusive_group(required=True)
    label_group.add_argument("--golden", action="store_true", help="Mark as golden example")
    label_group.add_argument("--rejected", action="store_true", help="Mark as rejected")
    label_group.add_argument("--unlabeled", action="store_true", help="Reset to unlabeled")
    p_label.set_defaults(func=cmd_label)

    # export-golden
    p_export = sub.add_parser("export-golden", help="Export golden invocations for TextGrad")
    p_export.add_argument("--skill", help="Filter by skill name")
    p_export.add_argument("--output", help="Output file path (default: stdout)")
    p_export.set_defaults(func=cmd_export_golden)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

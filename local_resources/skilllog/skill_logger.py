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
    uv run python local_resources/skilllog/skill_logger.py context-trend [--skill NAME]
    uv run python local_resources/skilllog/skill_logger.py migrate-context-schema
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


def estimate_context_tokens() -> dict:
    """Estimate tokens in always-loaded context files."""
    context_files = {
        "claude_md": PROJECT_ROOT / "CLAUDE.md",
        "soul_md": PROJECT_ROOT / "local_resources/openclaw/SOUL.md",
        "agents_md": PROJECT_ROOT / "local_resources/openclaw/AGENTS.md",
        "memory_md": Path.home() / ".claude/projects/-Users-gullyburns-skillful-alhazen/memory/MEMORY.md",
    }
    # Also scan local_skills/*/SKILL.md (loaded into context)
    # and local_skills/*/USAGE.md (on-demand, NOT loaded into context)
    skill_md_total = 0
    usage_md_total = 0
    local_skills_dir = PROJECT_ROOT / "local_skills"
    if local_skills_dir.exists():
        for skill_md in local_skills_dir.glob("*/SKILL.md"):
            try:
                skill_md_total += estimate_tokens(skill_md.read_text(errors="replace"))
            except OSError:
                pass
        for usage_md in local_skills_dir.glob("*/USAGE.md"):
            try:
                usage_md_total += estimate_tokens(usage_md.read_text(errors="replace"))
            except OSError:
                pass

    totals = {}
    for name, path in context_files.items():
        if path.exists():
            try:
                totals[name] = estimate_tokens(path.read_text(errors="replace"))
            except OSError:
                pass
    totals["skill_mds"] = skill_md_total
    totals["total"] = sum(totals.values())
    # usage_mds is NOT included in total (on-demand, not loaded into context)
    totals["usage_mds"] = usage_md_total
    return totals


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


# ---------------------------------------------------------------------------
# Skill gap repo routing
# ---------------------------------------------------------------------------

CORE_SKILLS = {
    "typedb-notebook",
    "web-search",
    "curation-skill-builder",
    "tech-recon",
}

CORE_REPO = "GullyBurns/skillful-alhazen"
EXTERNAL_REPO = "sciknow-io/alhazen-skill-examples"

# Skills that live in their own repos (not core or alhazen-skill-examples)
SKILL_REPO_MAP: dict[str, str] = {
    "dismech": "sciknow-io/alhazen-skill-dismech",
}


def get_gap_repo(skill_name: str) -> str:
    """Route a skill name to the correct GitHub repo for gap issues."""
    if skill_name in SKILL_REPO_MAP:
        return SKILL_REPO_MAP[skill_name]
    return CORE_REPO if skill_name in CORE_SKILLS else EXTERNAL_REPO


# ---------------------------------------------------------------------------
# TypeDB schema error detection
# ---------------------------------------------------------------------------

# These error codes indicate schema representation failures — the schema
# doesn't have a type/attribute/relation that the skill tried to use.
TYPEDB_SCHEMA_ERROR_PATTERNS = [
    re.compile(r'\[SYR\d+\]'),   # Schema syntax / type not found
    re.compile(r'\[TYR\d+\]'),   # Type resolution errors
    re.compile(r'\[FEX\d+\]'),   # Fetch expression errors (often relation attribute access)
    re.compile(r'\[SVL\d+\]'),   # Schema validity errors (e.g., abstract supertype)
    re.compile(r'\[REP\d+\]'),   # Representation errors (entity comparison)
]


def detect_typedb_schema_error(text: str) -> Optional[str]:
    """
    Scan output text for TypeDB schema error codes.
    Returns the first matching error code string (e.g. '[SYR1]'), or None.
    These indicate ontological gaps — the schema lacks a type the skill needs.
    """
    for pattern in TYPEDB_SCHEMA_ERROR_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(0)
    return None


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
# TypeDB helpers (TypeDB 3.x)
# ---------------------------------------------------------------------------

def get_typedb_connection():
    """Return (driver, database) connected to the configured TypeDB database."""
    try:
        from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType
    except ImportError:
        raise RuntimeError("typedb-driver is not installed. Run: uv sync --all-extras")

    host = os.environ.get("TYPEDB_HOST", "localhost")
    port = int(os.environ.get("TYPEDB_PORT", "1729"))
    database = os.environ.get("TYPEDB_DATABASE", "alhazen_notebook")
    username = os.environ.get("TYPEDB_USERNAME", "admin")
    password = os.environ.get("TYPEDB_PASSWORD", "password")

    driver = TypeDB.driver(
        f"{host}:{port}",
        Credentials(username, password),
        DriverOptions(is_tls_enabled=False),
    )
    return driver, database


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

    # --- Schema gap detection -------------------------------------------
    # Check for TypeDB schema error codes in skill output.
    # These are ontological gap signals: the schema lacks a type the skill
    # tried to use. Print to stdout so Claude sees the hint.
    _schema_error = detect_typedb_schema_error(output_text)
    if _schema_error:
        _repo = get_gap_repo(skill_name)
        print(
            f"\n[SCHEMA-GAP-HINT] skill='{skill_name}' command='{cmd_name}' "
            f"encountered TypeDB schema error {_schema_error}.\n"
            f"This may mean the schema is missing an entity type, attribute, or relation.\n"
            f"File a schema gap issue:\n"
            f"  uv run python local_resources/skilllog/skill_logger.py file-schema-gap \\\n"
            f"    --skill {skill_name} \\\n"
            f"    --concept \"<what concept were you trying to represent?>\" \\\n"
            f"    --missing \"<what type/attribute/relation is absent in TypeDB?>\" \\\n"
            f"    --suggested \"<suggested TypeQL snippet>\"\n"
            f"Target repo: {_repo}\n"
            f"\n"
            f"If this gap affects EXISTING entity types (hierarchy changes, attribute moves),\n"
            f"use the schema evolution workflow:\n"
            f"  1. Save old schema: cp <schema.tql> local_resources/typedb/migration-rules/<name>/old_schema.tql\n"
            f"  2. Fix the schema\n"
            f"  3. Generate rules: uv run python src/skillful_alhazen/utils/schema_diff.py diff --old OLD --new NEW --generate-rules --rules-dir RULES/\n"
            f"  4. Test: make db-migrate-test RULES=RULES/\n"
            f"  See CLAUDE.md \"Schema Evolution\" section for full workflow.\n"
        )
    elif exit_code != 0:
        # Non-schema execution failure — still worth surfacing
        _repo = get_gap_repo(skill_name)
        print(
            f"\n[SKILL-GAP-HINT] skill='{skill_name}' command='{cmd_name}' "
            f"exited with code {exit_code}.\n"
            f"If this is a skill design problem, file a gap issue:\n"
            f"  gh issue create --repo {_repo} "
            f"--title \"Gap [moderate][entity-schema]: <summary>\" --label \"gap:open\"\n"
            f"  (Full template: see CLAUDE.md 'Schema Gap Reporting' section)\n"
        )
    # --- End schema gap detection ---------------------------------------

    input_tokens = estimate_tokens(command)
    output_tokens = estimate_tokens(output_text)
    total_tokens = input_tokens + output_tokens
    ctx = estimate_context_tokens()
    context_tokens = ctx.get("total", 0)
    claude_md_tokens = ctx.get("claude_md", 0)
    memory_md_tokens = ctx.get("memory_md", 0)
    skill_mds_tokens = ctx.get("skill_mds", 0)
    soul_md_tokens = ctx.get("soul_md", 0)
    agents_md_tokens = ctx.get("agents_md", 0)
    timestamp = get_timestamp()
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")

    invocation_id = generate_id("skilllog-inv")
    input_id = generate_id("skilllog-in")
    output_id = generate_id("skilllog-out")

    try:
        from typedb.driver import TransactionType

        driver, database = get_typedb_connection()

        with driver.transaction(database, TransactionType.WRITE) as tx:
            # Insert invocation entity
            tx.query(f"""
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
                    has context-tokens-estimate {context_tokens},
                    has claude-md-tokens {claude_md_tokens},
                    has memory-md-tokens {memory_md_tokens},
                    has skill-mds-tokens {skill_mds_tokens},
                    has soul-md-tokens {soul_md_tokens},
                    has agents-md-tokens {agents_md_tokens},
                    has evaluation-label "unlabeled",
                    has created-at {timestamp},
                    has provenance "skilllog-hook";
            """).resolve()

            # Insert input artifact (store inline — commands are always small)
            tx.query(f"""
                insert $art isa skilllog-input,
                    has id "{input_id}",
                    has name "input:{invocation_id}",
                    has content "{escape_string(command)}",
                    has format "bash",
                    has created-at {timestamp},
                    has provenance "skilllog-hook";
            """).resolve()

            # Insert output artifact (truncate if very large)
            truncated_output = output_text[:8000] if len(output_text) > 8000 else output_text
            tx.query(f"""
                insert $art isa skilllog-output,
                    has id "{output_id}",
                    has name "output:{invocation_id}",
                    has content "{escape_string(truncated_output)}",
                    has format "text",
                    has created-at {timestamp},
                    has provenance "skilllog-hook";
            """).resolve()

            # Link input artifact to invocation via representation relation
            tx.query(f"""
                match
                    $inv isa skilllog-invocation, has id "{invocation_id}";
                    $art isa skilllog-input, has id "{input_id}";
                insert (referent: $inv, artifact: $art) isa representation;
            """).resolve()

            # Link output artifact to invocation
            tx.query(f"""
                match
                    $inv isa skilllog-invocation, has id "{invocation_id}";
                    $art isa skilllog-output, has id "{output_id}";
                insert (referent: $inv, artifact: $art) isa representation;
            """).resolve()

            tx.commit()

        driver.close()

    except Exception as e:
        if error_on_typedb_unavailable():
            print(f"[skilllog] ERROR: Failed to log invocation to TypeDB: {e}", file=sys.stderr)
            sys.exit(1)
        # If error_on_typedb_unavailable is False (not the default), silently pass
        sys.exit(0)


# ---------------------------------------------------------------------------
# CLI subcommands
# ---------------------------------------------------------------------------

def cmd_list_invocations(args):
    """List recent skill invocations from TypeDB."""
    try:
        from typedb.driver import TransactionType

        driver, database = get_typedb_connection()
        skill_filter = f', has skill-name "{args.skill}"' if args.skill else ""
        limit = args.limit if hasattr(args, "limit") and args.limit else 50

        with driver.transaction(database, TransactionType.READ) as tx:
            query = f"""
                match $inv isa skilllog-invocation{skill_filter},
                    has id $id,
                    has skill-name $skill,
                    has command-name $cmd,
                    has total-tokens-estimate $tokens,
                    has evaluation-label $label,
                    has created-at $ts;
                limit {limit};
                fetch {{
                    "id": $id,
                    "skill": $skill,
                    "cmd": $cmd,
                    "tokens": $tokens,
                    "label": $label,
                    "ts": $ts
                }};
            """
            results = list(tx.query(query).resolve())

        driver.close()

        rows = []
        for r in results:
            rows.append({
                "id": r["id"],
                "skill": r["skill"],
                "command": r["cmd"],
                "tokens": r["tokens"],
                "label": r["label"],
                "timestamp": r["ts"],
            })

        print(json.dumps(rows, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_token_report(args):
    """Summarize token usage by skill and command, with static context baseline."""
    try:
        from typedb.driver import TransactionType

        driver, database = get_typedb_connection()
        skill_filter = f', has skill-name "{args.skill}"' if args.skill else ""

        with driver.transaction(database, TransactionType.READ) as tx:
            query = f"""
                match $inv isa skilllog-invocation{skill_filter},
                    has skill-name $skill,
                    has command-name $cmd,
                    has total-tokens-estimate $tokens,
                    has context-tokens-estimate $ctx;
                fetch {{
                    "skill": $skill,
                    "cmd": $cmd,
                    "tokens": $tokens,
                    "ctx": $ctx
                }};
            """
            results = list(tx.query(query).resolve())

        driver.close()

        # Aggregate
        from collections import defaultdict
        skill_totals: dict = defaultdict(lambda: {
            "total": 0, "count": 0, "ctx_total": 0,
            "commands": defaultdict(lambda: {"total": 0, "count": 0, "ctx_total": 0})
        })

        for r in results:
            skill = r["skill"]
            cmd = r["cmd"]
            tokens = r["tokens"]
            ctx = r.get("ctx", 0) or 0
            skill_totals[skill]["total"] += tokens
            skill_totals[skill]["count"] += 1
            skill_totals[skill]["ctx_total"] += ctx
            skill_totals[skill]["commands"][cmd]["total"] += tokens
            skill_totals[skill]["commands"][cmd]["count"] += 1
            skill_totals[skill]["commands"][cmd]["ctx_total"] += ctx

        # Show static context baseline from current filesystem
        current_ctx = estimate_context_tokens()
        print("\nStatic Context Baseline (current filesystem)")
        print("=" * 60)
        for name, tokens in current_ctx.items():
            if name not in ("total", "usage_mds"):
                print(f"  {name:<30} {tokens:>8,} tokens")
        print(f"  {'TOTAL':<30} {current_ctx['total']:>8,} tokens")
        if current_ctx.get("usage_mds"):
            print(f"  {'usage_mds (on-demand, not loaded)':<30} {current_ctx['usage_mds']:>8,} tokens")

        print("\nToken Usage Report (CLI I/O estimates)")
        print("=" * 60)
        if not skill_totals:
            print("  No invocations logged yet.")
        for skill, data in sorted(skill_totals.items(), key=lambda x: -x[1]["total"]):
            avg = data["total"] // data["count"] if data["count"] else 0
            avg_ctx = data["ctx_total"] // data["count"] if data["count"] else 0
            print(f"\n{skill}: {data['total']:,} CLI tokens total ({data['count']} calls, avg {avg:,})")
            print(f"  Static context at invocation time: avg {avg_ctx:,} tokens/call")
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
        from typedb.driver import TransactionType

        driver, database = get_typedb_connection()

        with driver.transaction(database, TransactionType.WRITE) as tx:
            # Delete old label
            tx.query(f"""
                match $inv isa skilllog-invocation, has id "{args.id}", has evaluation-label $old;
                delete has $old;
            """).resolve()
            # Insert new label
            tx.query(f"""
                match $inv isa skilllog-invocation, has id "{args.id}";
                insert $inv has evaluation-label "{label}";
            """).resolve()
            tx.commit()

        driver.close()
        print(json.dumps({"success": True, "id": args.id, "label": label}))

        if label == "golden":
            print(
                "\n[CONSOLIDATION-HINT] This invocation was marked golden. "
                "Consider crystallizing key outputs into long-term memory:\n"
                "  uv run python .claude/skills/agentic-memory/agentic_memory.py consolidate \\\n"
                "    --content \"<key finding or decision>\" \\\n"
                "    --subject <relevant-entity-id> \\\n"
                "    --fact-type knowledge|decision|goal \\\n"
                "    --source-episode <episode-id>",
                file=sys.stderr,
            )

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_token_report_llm(args):
    """Summarize real LLM token usage logged by the LiteLLM callback (OpenClaw)."""
    try:
        from typedb.driver import TransactionType
        from collections import defaultdict

        driver, database = get_typedb_connection()

        with driver.transaction(database, TransactionType.READ) as tx:
            query = """
                match $c isa skilllog-llm-call,
                    has llm-model $model,
                    has input-tokens-estimate $in_tok,
                    has output-tokens-estimate $out_tok,
                    has cache-creation-tokens $cc_tok,
                    has cache-read-tokens $cr_tok,
                    has cost-usd $cost,
                    has duration-ms $dur,
                    has exit-code $exit;
                fetch {
                    "model":    $model,
                    "in_tok":   $in_tok,
                    "out_tok":  $out_tok,
                    "cc_tok":   $cc_tok,
                    "cr_tok":   $cr_tok,
                    "cost":     $cost,
                    "dur":      $dur,
                    "exit":     $exit
                };
            """
            results = list(tx.query(query).resolve())

        driver.close()

        if not results:
            print("No LLM calls logged yet.")
            return

        total_calls = len(results)
        total_in    = sum(r["in_tok"] for r in results)
        total_out   = sum(r["out_tok"] for r in results)
        total_cc    = sum(r["cc_tok"] for r in results)
        total_cr    = sum(r["cr_tok"] for r in results)
        total_cost  = sum(r["cost"] for r in results)
        errors      = sum(1 for r in results if r["exit"] != 0)

        # Cache hit ratio: cache_read / (input + cache_read) avoids div-by-zero
        denom = total_in + total_cr
        cache_ratio = (total_cr / denom * 100) if denom else 0.0

        # Savings: tokens served from cache at ~10% of input rate
        # Rough estimate: saved = cache_read * (input_rate - cache_read_rate)
        saved_usd = total_cr * (3.0 - 0.30) / 1_000_000

        print("\nLLM Call Report (OpenClaw via LiteLLM)")
        print("=" * 60)
        print(f"  Total calls:          {total_calls:>8,}")
        print(f"  Errors:               {errors:>8,}")
        print(f"  Total cost:           ${total_cost:>11.4f}")
        print(f"  Cache savings est.:  ~${saved_usd:>11.4f}")
        print(f"  Input tokens:         {total_in:>8,}")
        print(f"  Output tokens:        {total_out:>8,}")
        print(f"  Cache create tokens:  {total_cc:>8,}")
        print(f"  Cache read tokens:    {total_cr:>8,}  ({cache_ratio:.1f}% of input+read)")

        # Aggregate by model
        by_model: dict = defaultdict(lambda: {"calls": 0, "cost": 0.0, "in": 0, "out": 0})
        for r in results:
            m = r["model"]
            by_model[m]["calls"] += 1
            by_model[m]["cost"]  += r["cost"]
            by_model[m]["in"]    += r["in_tok"]
            by_model[m]["out"]   += r["out_tok"]

        if len(by_model) > 1:
            print("\nBy model:")
            for model, d in sorted(by_model.items(), key=lambda x: -x[1]["cost"]):
                print(f"  {model:<35} {d['calls']:>5} calls  ${d['cost']:.4f}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------

def cmd_migrate_context_schema(args):
    """Add per-file context token attributes to live TypeDB database (non-destructive)."""
    try:
        from typedb.driver import TransactionType

        driver, database = get_typedb_connection()

        with driver.transaction(database, TransactionType.SCHEMA) as tx:
            tx.query("""
                define
                    attribute claude-md-tokens, value integer;
                    attribute memory-md-tokens, value integer;
                    attribute skill-mds-tokens, value integer;
                    attribute soul-md-tokens, value integer;
                    attribute agents-md-tokens, value integer;
                    entity skilllog-invocation
                        owns claude-md-tokens,
                        owns memory-md-tokens,
                        owns skill-mds-tokens,
                        owns soul-md-tokens,
                        owns agents-md-tokens;
            """).resolve()
            tx.commit()

        driver.close()
        print("Migration complete. Per-file context token attributes added to skilllog-invocation.")

    except Exception as e:
        msg = str(e)
        if "already" in msg.lower() or "exist" in msg.lower():
            print("Schema already up to date (attributes already defined).")
        else:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


# ---------------------------------------------------------------------------
# Context trend report
# ---------------------------------------------------------------------------

def cmd_context_trend(args):
    """Show context token trend over time, grouped by day."""
    from collections import defaultdict

    try:
        from typedb.driver import TransactionType

        driver, database = get_typedb_connection()
        skill_filter = f', has skill-name "{args.skill}"' if args.skill else ""

        with driver.transaction(database, TransactionType.READ) as tx:
            # All invocations with context total + timestamp
            results = list(tx.query(f"""
                match $inv isa skilllog-invocation{skill_filter},
                    has id $id,
                    has context-tokens-estimate $ctx,
                    has created-at $ts;
                fetch {{
                    "id": $id,
                    "ctx": $ctx,
                    "ts": $ts
                }};
            """).resolve())

            # Per-file breakdown — only present on records logged after migration
            try:
                breakdown_results = list(tx.query(f"""
                    match $inv isa skilllog-invocation{skill_filter},
                        has id $id,
                        has claude-md-tokens $claude,
                        has memory-md-tokens $mem,
                        has skill-mds-tokens $skills;
                    fetch {{
                        "id": $id,
                        "claude": $claude,
                        "mem": $mem,
                        "skills": $skills
                    }};
                """).resolve())
            except Exception:
                breakdown_results = []

        driver.close()

        # Build per-id breakdown map
        breakdown_map = {r["id"]: r for r in breakdown_results}

        # Group by day
        by_day: dict = defaultdict(lambda: {"count": 0, "ctx_total": 0, "breakdowns": []})
        for r in results:
            ts = str(r["ts"])
            day = ts[:10]
            by_day[day]["count"] += 1
            by_day[day]["ctx_total"] += r["ctx"]
            if r["id"] in breakdown_map:
                by_day[day]["breakdowns"].append(breakdown_map[r["id"]])

        # Print report
        current_ctx = estimate_context_tokens()
        print("\nContext Token Trend (by day)")
        print("=" * 72)
        print(f"{'Date':<12} {'Calls':>5}  {'Avg Context':>12}  {'Delta':>8}  {'CLAUDE.md':>10}  {'MEMORY.md':>10}  {'SKILL.mds':>10}")
        print("-" * 72)

        prev_avg = None
        for day in sorted(by_day.keys()):
            data = by_day[day]
            avg_ctx = data["ctx_total"] // data["count"]

            delta_str = "—"
            if prev_avg is not None:
                delta = avg_ctx - prev_avg
                delta_str = f"{'+' if delta >= 0 else ''}{delta:,}"
            prev_avg = avg_ctx

            if data["breakdowns"]:
                b = data["breakdowns"]
                avg_claude = sum(x["claude"] for x in b) // len(b)
                avg_mem = sum(x["mem"] for x in b) // len(b)
                avg_skills = sum(x["skills"] for x in b) // len(b)
                print(f"{day:<12} {data['count']:>5}  {avg_ctx:>12,}  {delta_str:>8}  {avg_claude:>10,}  {avg_mem:>10,}  {avg_skills:>10,}")
            else:
                print(f"{day:<12} {data['count']:>5}  {avg_ctx:>12,}  {delta_str:>8}  {'—':>10}  {'—':>10}  {'—':>10}")

        print()
        print("Current file sizes (snapshot now):")
        labels = {"claude_md": "CLAUDE.md", "memory_md": "MEMORY.md", "skill_mds": "SKILL.mds",
                  "soul_md": "SOUL.md", "agents_md": "AGENTS.md"}
        for key, tokens in current_ctx.items():
            if key not in ("total", "usage_mds"):
                print(f"  {labels.get(key, key):<12}  {tokens:>8,} tokens")
        print(f"  {'TOTAL':<12}  {current_ctx['total']:>8,} tokens")
        if current_ctx.get("usage_mds"):
            print(f"  {'USAGE.mds (on-demand)':<12}  {current_ctx['usage_mds']:>8,} tokens  [not loaded into context]")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# file-schema-gap subcommand
# ---------------------------------------------------------------------------

def cmd_file_schema_gap(args):
    """
    File a TypeDB schema gap as a GitHub issue.

    Schema gaps are ontological failures: Claude tried to represent a concept
    that has no place in the current TypeDB schema. Routes to the correct repo,
    checks for duplicate open issues, constructs a structured body matching
    gap-triage.yml parsing expectations, then runs `gh issue create`.
    """
    import subprocess

    skill = args.skill
    concept = args.concept
    missing = args.missing
    suggested = args.suggested or "(to be determined)"
    repo = get_gap_repo(skill)

    title = f"Schema gap [{skill}]: '{concept}' not representable in TypeDB"

    # Check for duplicate open issues before filing
    if not args.dry_run and not args.skip_dedup:
        try:
            check = subprocess.run(
                ["gh", "issue", "list", "--repo", repo,
                 "--label", "gap:open", "--json", "title", "--limit", "50"],
                capture_output=True, text=True, check=True,
            )
            existing = json.loads(check.stdout or "[]")
            for issue in existing:
                if concept.lower() in issue.get("title", "").lower():
                    print(json.dumps({
                        "success": False,
                        "duplicate": True,
                        "message": f"Likely duplicate found: {issue['title']}",
                        "hint": "Use --skip-dedup to file anyway",
                    }, indent=2))
                    return
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pass  # Dedup check failed — proceed to file

    # Build body matching gap-triage.yml parser expectations exactly:
    #   **Severity:** <value>   **Phase:** <value>   **Skill:** <value>
    pattern_line = (
        f"Any skill that needs to represent '{concept}' requires this schema extension. "
        f"Check for similar missing types when building related skills."
    )
    body_parts = [
        "## What was missing",
        f"The concept of '{concept}' is not representable in the TypeDB schema for `{skill}`.",
        "",
        "## What broke",
        missing,
        "",
        "## Suggested fix",
        f"Add to `{skill}/schema.tql`:",
        "```typeql",
        suggested,
        "```",
        "",
        "## Generalizable pattern",
        pattern_line,
        "",
        "---",
        f"**Skill:** {skill}",
        "**Phase:** entity-schema",
        "**Severity:** moderate",
    ]
    body = "\n".join(body_parts)

    cmd = [
        "gh", "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body", body,
        "--label", "gap:open",
    ]

    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "repo": repo,
            "title": title,
            "body": body,
            "command": " ".join(cmd),
        }, indent=2))
        return

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        issue_url = result.stdout.strip()
        print(json.dumps({
            "success": True,
            "issue_url": issue_url,
            "repo": repo,
            "title": title,
        }, indent=2))
    except subprocess.CalledProcessError as e:
        print(json.dumps({
            "success": False,
            "error": e.stderr.strip() or str(e),
            "repo": repo,
            "title": title,
        }, indent=2))
        sys.exit(1)
    except FileNotFoundError:
        print(json.dumps({
            "success": False,
            "error": "gh CLI not found. Install: https://cli.github.com/",
        }, indent=2))
        sys.exit(1)


# ---------------------------------------------------------------------------
# fix-gap subcommand
# ---------------------------------------------------------------------------

def cmd_fix_gap(args):
    """
    Start a local gap fix: create a branch, update issue labels, post a comment.

    Fetches the issue from GitHub, derives a branch name from the title,
    creates the branch locally, updates labels (gap:in-progress), and posts
    a "Fix started" comment on the issue.
    """
    import re
    import subprocess

    issue_num = args.issue
    repo = args.repo

    # Fetch issue details
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_num), "--repo", repo,
             "--json", "title,body,labels"],
            capture_output=True, text=True, check=True,
        )
        issue = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(json.dumps({"success": False, "error": f"Could not fetch issue #{issue_num}: {e}"}), file=sys.stdout)
        sys.exit(1)

    title = issue.get("title", "gap-fix")
    # Derive branch slug: kebab-case, max 40 chars
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
    branch = f"fix/gap-{issue_num}-{slug}"

    # Create local branch
    try:
        subprocess.run(["git", "checkout", "-b", branch], check=True)
    except subprocess.CalledProcessError as e:
        print(json.dumps({"success": False, "error": f"Could not create branch '{branch}': {e}"}), file=sys.stdout)
        sys.exit(1)

    # Update issue labels
    try:
        subprocess.run(
            ["gh", "issue", "edit", str(issue_num), "--repo", repo,
             "--add-label", "gap:in-progress", "--remove-label", "gap:open"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        pass  # Label update failure is non-fatal

    # Post "Fix started" comment
    comment_body = (
        f"Fix started on branch `{branch}`.\n\n"
        f"Implementing locally against running TypeDB. "
        f"Will open a draft PR via `submit-gap-pr` when validated."
    )
    try:
        subprocess.run(
            ["gh", "issue", "comment", str(issue_num), "--repo", repo, "--body", comment_body],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        pass  # Comment failure is non-fatal

    print(json.dumps({
        "success": True,
        "branch": branch,
        "issue": issue_num,
        "repo": repo,
        "next_step": f"Implement the fix, then run: submit-gap-pr --issue {issue_num} --repo {repo}",
    }, indent=2))


# ---------------------------------------------------------------------------
# submit-gap-pr subcommand
# ---------------------------------------------------------------------------

def cmd_submit_gap_pr(args):
    """
    After fixing a gap locally: run tests, open a draft PR, post PR link on issue.

    Confirms tests pass, builds a PR body from the issue title + decisions,
    opens a draft PR (not merged — human reviews and merges), posts the PR
    link as an issue comment, and updates labels to gap:pr-open.
    """
    import re
    import subprocess

    issue_num = args.issue
    repo = args.repo
    decisions = args.decisions or ""

    # Verify we're on a fix branch (not main)
    try:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        current_branch = branch_result.stdout.strip()
        if current_branch in ("main", "master"):
            print(json.dumps({
                "success": False,
                "error": "You are on 'main'. Run fix-gap first to create a fix branch.",
            }, indent=2))
            sys.exit(1)
    except subprocess.CalledProcessError:
        pass

    # Confirm there are commits ahead of main
    try:
        diff_result = subprocess.run(
            ["git", "log", "main..HEAD", "--oneline"],
            capture_output=True, text=True,
        )
        if not diff_result.stdout.strip():
            print(json.dumps({
                "success": False,
                "error": "No commits ahead of main on this branch. Implement and commit the fix first.",
            }, indent=2))
            sys.exit(1)
    except subprocess.CalledProcessError:
        pass

    # Run tests if a test suite exists
    test_status = "No test suite found — skipped."
    for test_cmd in [["uv", "run", "pytest", "--tb=short", "-q"], ["python", "-m", "pytest", "-q"]]:
        try:
            r = subprocess.run(test_cmd, capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                test_status = "All local tests passed."
                break
            elif r.returncode == 5:
                # pytest exit code 5 = no tests collected
                test_status = "No tests collected — skipped."
                break
            else:
                print(json.dumps({
                    "success": False,
                    "error": "Tests failed. Fix tests before opening a PR.",
                    "output": (r.stdout + r.stderr)[-2000:],
                }, indent=2))
                sys.exit(1)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # Fetch issue details
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_num), "--repo", repo,
             "--json", "title,comments"],
            capture_output=True, text=True, check=True,
        )
        issue = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(json.dumps({"success": False, "error": f"Could not fetch issue #{issue_num}: {e}"}))
        sys.exit(1)

    issue_title = issue.get("title", f"gap #{issue_num}")

    # Gather implementation decision comments (after the "Fix started" comment)
    if not decisions:
        comments = issue.get("comments", [])
        decision_lines = []
        past_started = False
        for c in comments:
            body = c.get("body", "")
            if "Fix started on branch" in body:
                past_started = True
                continue
            if past_started and body.strip():
                decision_lines.append(body.strip())
        decisions = "\n\n".join(decision_lines) if decision_lines else "(no implementation notes recorded)"

    # Derive skill name from branch (fix/gap-N-<slug>)
    skill_match = re.search(r"\*\*Skill:\*\*\s*([a-z0-9][a-z0-9-]*)", issue.get("title", ""), re.IGNORECASE)
    skill_name = skill_match.group(1) if skill_match else "skill"

    # Build PR title and body
    title_slug = re.sub(r"[^a-z0-9]+", "-", issue_title.lower()).strip("-")[:60]
    pr_title = f"fix({skill_name}): {title_slug} (closes #{issue_num})"

    pr_body = "\n".join([
        f"Closes #{issue_num}",
        "",
        "## Summary",
        issue_title,
        "",
        "## Implementation decisions",
        decisions,
        "",
        "## Test status",
        test_status,
        "",
        "---",
        "_Generated locally against running TypeDB. Review diff, promote from draft, and merge when satisfied._",
    ])

    # Push branch
    try:
        subprocess.run(["git", "push", "-u", "origin", "HEAD"], check=True)
    except subprocess.CalledProcessError as e:
        print(json.dumps({"success": False, "error": f"git push failed: {e}"}))
        sys.exit(1)

    # Create draft PR
    try:
        pr_result = subprocess.run(
            ["gh", "pr", "create",
             "--repo", repo,
             "--draft",
             "--title", pr_title,
             "--body", pr_body],
            capture_output=True, text=True, check=True,
        )
        pr_url = pr_result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(json.dumps({"success": False, "error": f"gh pr create failed: {e.stderr.strip()}"}))
        sys.exit(1)

    # Post PR link on issue
    try:
        subprocess.run(
            ["gh", "issue", "comment", str(issue_num), "--repo", repo,
             "--body", f"Draft PR opened: {pr_url}\n\nReview the diff, promote from draft, and merge when satisfied."],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        pass

    # Update issue labels
    try:
        subprocess.run(
            ["gh", "issue", "edit", str(issue_num), "--repo", repo,
             "--add-label", "gap:pr-open", "--remove-label", "gap:in-progress"],
            capture_output=True, text=True,
        )
    except subprocess.CalledProcessError:
        pass

    print(json.dumps({
        "success": True,
        "pr_url": pr_url,
        "pr_draft": True,
        "issue": issue_num,
        "test_status": test_status,
        "next_step": f"Review and merge at {pr_url}",
    }, indent=2))


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

    # token-report-llm
    p_llm = sub.add_parser("token-report-llm", help="Real LLM token usage from OpenClaw (LiteLLM callback)")
    p_llm.set_defaults(func=cmd_token_report_llm)

    # migrate-context-schema
    p_migrate = sub.add_parser("migrate-context-schema", help="Add per-file context token attributes to live DB (non-destructive)")
    p_migrate.set_defaults(func=cmd_migrate_context_schema)

    # context-trend
    p_trend = sub.add_parser("context-trend", help="Show context token size trend over time")
    p_trend.add_argument("--skill", help="Filter by skill name")
    p_trend.set_defaults(func=cmd_context_trend)

    # file-schema-gap
    p_sgap = sub.add_parser(
        "file-schema-gap",
        help="File a TypeDB schema gap issue (concept not representable in schema)",
    )
    p_sgap.add_argument("--skill", required=True,
                        help="Skill name (e.g. jobhunt, typedb-notebook)")
    p_sgap.add_argument("--concept", required=True,
                        help="The concept or relationship Claude tried to represent")
    p_sgap.add_argument("--missing", required=True,
                        help="What TypeDB entity/relation/attribute is absent")
    p_sgap.add_argument("--suggested", default="",
                        help="Suggested TypeQL snippet to add to schema.tql")
    p_sgap.add_argument("--skip-dedup", action="store_true",
                        help="Skip duplicate issue check and file anyway")
    p_sgap.add_argument("--dry-run", action="store_true",
                        help="Print the gh command without running it")
    p_sgap.set_defaults(func=cmd_file_schema_gap)

    # fix-gap
    p_fg = sub.add_parser(
        "fix-gap",
        help="Start a local gap fix: create branch, update labels, post comment",
    )
    p_fg.add_argument("--issue", required=True, type=int, help="GitHub issue number")
    p_fg.add_argument("--repo", required=True, help="GitHub repo slug (e.g. sciknow-io/alhazen-skill-dismech)")
    p_fg.set_defaults(func=cmd_fix_gap)

    # submit-gap-pr
    p_sgpr = sub.add_parser(
        "submit-gap-pr",
        help="Run tests, push branch, open a draft PR, post PR link on issue",
    )
    p_sgpr.add_argument("--issue", required=True, type=int, help="GitHub issue number")
    p_sgpr.add_argument("--repo", required=True, help="GitHub repo slug (e.g. sciknow-io/alhazen-skill-dismech)")
    p_sgpr.add_argument("--decisions", default="",
                        help="Implementation decisions to include in PR body (optional)")
    p_sgpr.set_defaults(func=cmd_submit_gap_pr)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

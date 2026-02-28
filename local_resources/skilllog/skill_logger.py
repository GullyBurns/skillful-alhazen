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


def cmd_export_golden(args):
    """Export golden invocations as JSON for TextGrad consumption."""
    try:
        from typedb.driver import TransactionType

        driver, database = get_typedb_connection()
        skill_filter = f', has skill-name "{args.skill}"' if args.skill else ""

        with driver.transaction(database, TransactionType.READ) as tx:
            # Get golden invocations
            query = f"""
                match $inv isa skilllog-invocation{skill_filter},
                    has id $id,
                    has skill-name $skill,
                    has command-name $cmd,
                    has evaluation-label "golden",
                    has created-at $ts;
                fetch {{
                    "id": $id,
                    "skill": $skill,
                    "cmd": $cmd,
                    "ts": $ts
                }};
            """
            inv_results = list(tx.query(query).resolve())

            records = []
            for r in inv_results:
                inv_id = r["id"]

                # Get input artifact
                in_q = f"""
                    match $inv isa skilllog-invocation, has id "{inv_id}";
                        $art isa skilllog-input, has content $c;
                        (referent: $inv, artifact: $art) isa representation;
                    fetch {{ "c": $c }};
                """
                in_res = list(tx.query(in_q).resolve())
                input_content = in_res[0]["c"] if in_res else ""

                # Get output artifact
                out_q = f"""
                    match $inv isa skilllog-invocation, has id "{inv_id}";
                        $art isa skilllog-output, has content $c;
                        (referent: $inv, artifact: $art) isa representation;
                    fetch {{ "c": $c }};
                """
                out_res = list(tx.query(out_q).resolve())
                output_content = out_res[0]["c"] if out_res else ""

                records.append({
                    "id": inv_id,
                    "skill": r["skill"],
                    "command": r["cmd"],
                    "timestamp": r["ts"],
                    "input": input_content,
                    "output": output_content,
                })

        driver.close()

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

    # export-golden
    p_export = sub.add_parser("export-golden", help="Export golden invocations for TextGrad")
    p_export.add_argument("--skill", help="Filter by skill name")
    p_export.add_argument("--output", help="Output file path (default: stdout)")
    p_export.set_defaults(func=cmd_export_golden)

    # migrate-context-schema
    p_migrate = sub.add_parser("migrate-context-schema", help="Add per-file context token attributes to live DB (non-destructive)")
    p_migrate.set_defaults(func=cmd_migrate_context_schema)

    # context-trend
    p_trend = sub.add_parser("context-trend", help="Show context token size trend over time")
    p_trend.add_argument("--skill", help="Filter by skill name")
    p_trend.set_defaults(func=cmd_context_trend)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

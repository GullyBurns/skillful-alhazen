#!/usr/bin/env python3
"""
TextGrad-powered skill optimizer for Alhazen.

Reads a skill's golden evaluation dataset from TypeDB, runs TextGrad
optimization on the skill's SKILL.md instruction sections and Python
script PROMPT_ constants, then creates a git branch and GitHub PR with
the suggested changes and textual gradient explanations.

Usage:
    uv run python local_resources/textgrad/skill_optimizer.py --skill SKILL_NAME
    uv run python local_resources/textgrad/skill_optimizer.py --skill jobhunt --create-pr
    uv run python local_resources/textgrad/skill_optimizer.py --skill jobhunt --dry-run

Invoked via Makefile:
    make optimize-skill SKILL=jobhunt
"""

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

sys.path.insert(0, str(PROJECT_ROOT / "local_resources" / "skilllog"))
from config import get_textgrad_backend, is_textgrad_enabled

CLAUDE_SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"
LOCAL_SKILLS_DIR = PROJECT_ROOT / "local_skills"


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

def check_dependencies():
    """Exit early with a helpful message if required packages are missing."""
    try:
        import textgrad  # noqa: F401
    except ImportError:
        print("Error: textgrad is not installed.", file=sys.stderr)
        print("Run: uv add textgrad  or  uv sync --extra textgrad", file=sys.stderr)
        sys.exit(1)

    if not is_textgrad_enabled():
        print("Error: TextGrad optimization is disabled in alhazen.yaml.", file=sys.stderr)
        print("Enable with:  make textgrad-on", file=sys.stderr)
        print("Or:           ALHAZEN_TEXTGRAD_ENABLED=true make optimize-skill SKILL=...", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Skill file discovery
# ---------------------------------------------------------------------------

def find_skill_dir(skill_name: str) -> Path:
    """Return the directory for the given skill name."""
    for base in [CLAUDE_SKILLS_DIR, LOCAL_SKILLS_DIR]:
        candidate = base / skill_name
        if candidate.is_dir() and (candidate / "SKILL.md").exists():
            return candidate
    raise FileNotFoundError(f"Skill '{skill_name}' not found in .claude/skills/ or local_skills/")


def extract_skill_md_sections(skill_md_path: Path) -> dict[str, str]:
    """
    Extract named sections from SKILL.md for optimization.

    Returns a dict of {section_name: section_content} for sections
    that contain LLM-facing instructions (not code blocks, not prereqs).
    """
    text = skill_md_path.read_text()
    sections = {}

    # Split into H2 sections
    parts = re.split(r'^## (.+)$', text, flags=re.MULTILINE)
    # parts = [preamble, section1_name, section1_body, section2_name, section2_body, ...]

    OPTIMIZE_SECTIONS = {
        "Sensemaking Workflow",
        "Philosophy",
        "Philosophy: The Curation Pattern",
        "Commands",
    }

    for i in range(1, len(parts) - 1, 2):
        section_name = parts[i].strip()
        section_body = parts[i + 1]
        if any(opt in section_name for opt in OPTIMIZE_SECTIONS):
            sections[section_name] = section_body

    return sections


def extract_python_prompts(script_path: Path) -> dict[str, str]:
    """
    Extract PROMPT_<NAME> string constants from a Python script.

    Convention: module-level string assignments of the form:
        PROMPT_FOO = \"\"\"...\"\"\"
    or:
        PROMPT_FOO = (
            \"some text\"
        )
    """
    text = script_path.read_text()
    prompts = {}

    # Match triple-quoted string assignments
    pattern = re.compile(
        r'^(PROMPT_\w+)\s*=\s*"""(.*?)"""',
        re.MULTILINE | re.DOTALL,
    )
    for m in pattern.finditer(text):
        prompts[m.group(1)] = m.group(2).strip()

    return prompts


# ---------------------------------------------------------------------------
# Evaluation dataset loading
# ---------------------------------------------------------------------------

def load_golden_examples(skill_name: str) -> list[dict]:
    """
    Load golden invocation examples from TypeDB via skill_logger export.
    Returns list of {input, output, command} dicts.
    Falls back to empty list if TypeDB is unavailable.
    """
    skill_logger = PROJECT_ROOT / "local_resources" / "skilllog" / "skill_logger.py"
    try:
        result = subprocess.run(
            ["uv", "run", "python", str(skill_logger),
             "export-golden", "--skill", skill_name],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            print(f"Warning: Could not load golden examples: {result.stderr.strip()}", file=sys.stderr)
            return []
        return json.loads(result.stdout) if result.stdout.strip() else []
    except Exception as e:
        print(f"Warning: Golden example export failed: {e}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# TextGrad optimization
# ---------------------------------------------------------------------------

def optimize_section(
    section_name: str,
    section_content: str,
    examples: list[dict],
    backend: str,
    max_iterations: int = 3,
) -> tuple[str, list[str]]:
    """
    Run TextGrad to optimize a SKILL.md section.

    Returns (optimized_content, list_of_gradient_explanations).
    """
    import textgrad as tg

    # Configure backward engine (the critic)
    engine = tg.get_engine(f"experimental:{backend}", cache=False)
    tg.set_backward_engine(engine, override=True)

    variable = tg.Variable(
        section_content,
        role_description=(
            f"Instructions in the '{section_name}' section of a SKILL.md file. "
            "These instructions guide an AI agent on how to perform a specific task. "
            "They should be clear, concise, and produce accurate results."
        ),
        requires_grad=True,
    )

    # Build loss description from examples
    if examples:
        example_summary = "\n".join(
            f"- Command: {ex['command']}, Expected output structure: {ex['output'][:200]}..."
            for ex in examples[:5]
        )
        loss_description = (
            f"Evaluate these instructions for the '{section_name}' section. "
            f"They should produce consistent, accurate outputs for skill commands like:\n"
            f"{example_summary}\n\n"
            "Are the instructions clear? Complete? Free of ambiguity? "
            "Do they correctly guide the AI agent through the task? "
            "Are there unnecessary words that inflate token usage? "
            "Provide specific, actionable feedback."
        )
    else:
        loss_description = (
            f"Evaluate these instructions for the '{section_name}' section of a SKILL.md file. "
            "Are they clear, complete, and unambiguous? "
            "Would an AI agent following these instructions produce accurate, consistent results? "
            "Are there unnecessary verbose phrases that could be shortened without losing meaning? "
            "Provide specific, actionable feedback."
        )

    loss_fn = tg.TextLoss(loss_description)
    optimizer = tg.TGD(parameters=[variable])
    gradients = []

    for iteration in range(max_iterations):
        loss = loss_fn(variable)
        loss.backward()
        gradient_text = variable.gradients[0].value if variable.gradients else ""
        if gradient_text:
            gradients.append(f"Iteration {iteration + 1}: {gradient_text[:500]}")
        optimizer.step()

    return variable.value, gradients


def optimize_prompt_constant(
    prompt_name: str,
    prompt_content: str,
    examples: list[dict],
    backend: str,
    max_iterations: int = 2,
) -> tuple[str, list[str]]:
    """
    Run TextGrad to optimize a Python PROMPT_ constant.

    Returns (optimized_content, list_of_gradient_explanations).
    """
    import textgrad as tg

    engine = tg.get_engine(f"experimental:{backend}", cache=False)
    tg.set_backward_engine(engine, override=True)

    variable = tg.Variable(
        prompt_content,
        role_description=(
            f"A prompt constant named {prompt_name} in a Python skill script. "
            "This prompt is sent to an LLM to perform a specific extraction or analysis task. "
            "It should be clear, specific, and produce structured, consistent outputs."
        ),
        requires_grad=True,
    )

    loss_fn = tg.TextLoss(
        f"Evaluate this LLM prompt ({prompt_name}). "
        "Does it clearly specify what the LLM should do? "
        "Does it define the expected output format precisely? "
        "Are there unnecessary instructions that increase token usage without improving accuracy? "
        "Would following this prompt produce consistent, parseable outputs? "
        "Provide specific, actionable improvement suggestions."
    )

    optimizer = tg.TGD(parameters=[variable])
    gradients = []

    for iteration in range(max_iterations):
        loss = loss_fn(variable)
        loss.backward()
        gradient_text = variable.gradients[0].value if variable.gradients else ""
        if gradient_text:
            gradients.append(f"Iteration {iteration + 1}: {gradient_text[:500]}")
        optimizer.step()

    return variable.value, gradients


# ---------------------------------------------------------------------------
# File patching
# ---------------------------------------------------------------------------

def patch_skill_md(skill_md_path: Path, section_name: str, new_content: str):
    """Replace a section body in SKILL.md with optimized content."""
    text = skill_md_path.read_text()
    # Find the section and replace its body up to the next H2 or end of file
    pattern = re.compile(
        r'(^## ' + re.escape(section_name) + r'$)(.*?)((?=^## )|\Z)',
        re.MULTILINE | re.DOTALL,
    )
    replacement = r'\g<1>\n' + new_content.strip() + '\n\n\g<3>'
    new_text, count = re.subn(pattern, replacement, text)
    if count:
        skill_md_path.write_text(new_text)
    return count > 0


def patch_python_prompts(script_path: Path, prompt_name: str, new_content: str):
    """Replace a PROMPT_ constant in a Python script."""
    text = script_path.read_text()
    pattern = re.compile(
        r'^(' + re.escape(prompt_name) + r'\s*=\s*""")(.*?)(""")',
        re.MULTILINE | re.DOTALL,
    )
    replacement = r'\g<1>' + '\n' + new_content.strip() + '\n' + r'\g<3>'
    new_text, count = re.subn(pattern, replacement, text)
    if count:
        script_path.write_text(new_text)
    return count > 0


# ---------------------------------------------------------------------------
# Git + PR workflow
# ---------------------------------------------------------------------------

def create_branch_and_pr(skill_name: str, changes: list[dict], dry_run: bool) -> str:
    """
    Create a git branch with the optimized changes and open a PR.

    changes = [{"file": path, "section": name, "gradients": [...]}]
    Returns the PR URL.
    """
    date_str = datetime.utcnow().strftime("%Y%m%d-%H%M")
    branch_name = f"textgrad/{skill_name}-{date_str}"

    if dry_run:
        print(f"\n[Dry run] Would create branch: {branch_name}")
        print(f"[Dry run] Would create PR for skill: {skill_name}")
        for change in changes:
            print(f"[Dry run]   Modified: {change['file']}")
            print(f"[Dry run]   Section:  {change['section']}")
        return "(dry run - no PR created)"

    # Create branch
    subprocess.check_call(["git", "checkout", "-b", branch_name], cwd=PROJECT_ROOT)

    # Stage changed files
    changed_files = list({str(c["file"]) for c in changes})
    subprocess.check_call(["git", "add"] + changed_files, cwd=PROJECT_ROOT)

    # Build commit message with gradient explanations
    gradient_summary = ""
    for change in changes:
        if change.get("gradients"):
            gradient_summary += f"\n### {change['section']}\n"
            for g in change["gradients"][:2]:
                gradient_summary += f"- {g[:300]}\n"

    commit_msg = textwrap.dedent(f"""\
        textgrad: optimize {skill_name} skill instructions

        Automated TextGrad optimization pass on {skill_name}/SKILL.md
        and Python prompt constants. Changes are suggestions — review
        carefully before merging.

        Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
    """)

    subprocess.check_call(
        ["git", "commit", "-m", commit_msg],
        cwd=PROJECT_ROOT,
    )

    # Push branch
    subprocess.check_call(
        ["git", "push", "-u", "origin", branch_name],
        cwd=PROJECT_ROOT,
    )

    # Build PR body
    sections_changed = ", ".join(c["section"] for c in changes)
    files_changed = "\n".join(f"- `{c['file']}`" for c in changes)

    pr_body = textwrap.dedent(f"""\
        ## TextGrad Optimization: `{skill_name}`

        Automated optimization pass using TextGrad (automatic differentiation via text).
        These are **suggestions** — please review, edit, and validate before merging.

        ### What changed
        - Sections optimized: {sections_changed}
        - Files modified:
        {files_changed}

        ### Textual gradient summaries (why changes were made)
        {gradient_summary or "(No gradient details available)"}

        ### How to review
        1. Read the diff carefully — does the new text convey the same intent more clearly?
        2. Test the skill manually: `/skill-name` in Claude Code
        3. If the changes look wrong, close this PR and adjust the evaluation criteria

        ---
        🤖 Generated with [TextGrad](https://textgrad.com/) via [Claude Code](https://claude.com/claude-code)
    """)

    # Create PR
    result = subprocess.run(
        ["gh", "pr", "create",
         "--title", f"textgrad: optimize {skill_name} skill instructions",
         "--body", pr_body,
         "--head", branch_name],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        print(f"Warning: PR creation failed: {result.stderr}", file=sys.stderr)
        return f"(PR creation failed — branch {branch_name} was pushed)"

    pr_url = result.stdout.strip()
    return pr_url


# ---------------------------------------------------------------------------
# Main optimization flow
# ---------------------------------------------------------------------------

def run_optimization(args):
    """Main entry point for optimization."""
    check_dependencies()

    skill_name = args.skill
    backend = get_textgrad_backend()
    dry_run = args.dry_run
    create_pr = args.create_pr

    print(f"Optimizing skill: {skill_name}")
    print(f"Backend: {backend}")
    print(f"Dry run: {dry_run}")

    # Find skill directory
    try:
        skill_dir = find_skill_dir(skill_name)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    skill_md = skill_dir / "SKILL.md"

    # Find Python script(s)
    python_scripts = list(skill_dir.glob("*.py"))

    # Load golden examples
    print(f"\nLoading golden examples for '{skill_name}'...")
    examples = load_golden_examples(skill_name)
    print(f"  Found {len(examples)} golden examples")
    if not examples:
        print("  Warning: No golden examples found. Optimization will use generic quality criteria.")
        print("  To build golden examples: label invocations with")
        print("    uv run python local_resources/skilllog/skill_logger.py label --id ID --golden")

    changes = []

    # Optimize SKILL.md sections
    print(f"\nOptimizing SKILL.md sections...")
    sections = extract_skill_md_sections(skill_md)
    if not sections:
        print("  No optimizable sections found (looking for: Sensemaking Workflow, Philosophy)")
    for section_name, section_content in sections.items():
        print(f"  Optimizing section: {section_name}")
        if dry_run:
            print(f"    [Dry run] Would optimize {len(section_content)} chars")
            changes.append({
                "file": str(skill_md.relative_to(PROJECT_ROOT)),
                "section": section_name,
                "gradients": ["(dry run)"],
            })
            continue

        try:
            optimized, gradients = optimize_section(
                section_name, section_content, examples, backend
            )
            if optimized.strip() != section_content.strip():
                patched = patch_skill_md(skill_md, section_name, optimized)
                if patched:
                    changes.append({
                        "file": str(skill_md.relative_to(PROJECT_ROOT)),
                        "section": section_name,
                        "gradients": gradients,
                    })
                    print(f"    ✓ Section optimized ({len(section_content)} → {len(optimized)} chars)")
            else:
                print(f"    → No changes needed for '{section_name}'")
        except Exception as e:
            print(f"    ✗ Failed to optimize '{section_name}': {e}", file=sys.stderr)

    # Optimize Python PROMPT_ constants
    for script_path in python_scripts:
        prompts = extract_python_prompts(script_path)
        if not prompts:
            continue
        print(f"\nOptimizing prompts in {script_path.name}...")
        for prompt_name, prompt_content in prompts.items():
            print(f"  Optimizing: {prompt_name}")
            if dry_run:
                print(f"    [Dry run] Would optimize {len(prompt_content)} chars")
                changes.append({
                    "file": str(script_path.relative_to(PROJECT_ROOT)),
                    "section": prompt_name,
                    "gradients": ["(dry run)"],
                })
                continue

            try:
                optimized, gradients = optimize_prompt_constant(
                    prompt_name, prompt_content, examples, backend
                )
                if optimized.strip() != prompt_content.strip():
                    patched = patch_python_prompts(script_path, prompt_name, optimized)
                    if patched:
                        changes.append({
                            "file": str(script_path.relative_to(PROJECT_ROOT)),
                            "section": prompt_name,
                            "gradients": gradients,
                        })
                        print(f"    ✓ Prompt optimized ({len(prompt_content)} → {len(optimized)} chars)")
                else:
                    print(f"    → No changes needed for {prompt_name}")
            except Exception as e:
                print(f"    ✗ Failed to optimize {prompt_name}: {e}", file=sys.stderr)

    if not changes:
        print("\nNo changes produced. Optimization complete (no improvements found).")
        return

    print(f"\nOptimization complete: {len(changes)} change(s) made.")

    if create_pr or dry_run:
        print("\nCreating git branch and PR...")
        pr_url = create_branch_and_pr(skill_name, changes, dry_run)
        print(f"\nPR: {pr_url}")
    else:
        print("\nChanges written to disk. Review with: git diff")
        print("To create a PR: make optimize-skill SKILL=" + skill_name + " (it creates PR automatically)")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="TextGrad-powered skill optimizer for Alhazen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              make optimize-skill SKILL=jobhunt
              uv run python local_resources/textgrad/skill_optimizer.py --skill jobhunt --dry-run
              ALHAZEN_TEXTGRAD_ENABLED=true uv run python ... --skill epmc-search --create-pr
        """),
    )
    parser.add_argument("--skill", required=True, help="Skill name to optimize")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be optimized without making changes")
    parser.add_argument("--create-pr", action="store_true",
                        help="Create a GitHub PR with the changes (default when run via make)")
    args = parser.parse_args()

    run_optimization(args)


if __name__ == "__main__":
    main()

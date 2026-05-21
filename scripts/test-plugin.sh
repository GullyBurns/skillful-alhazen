#!/usr/bin/env bash
# =============================================================================
# Alhazen Plugin Smoke Test
# =============================================================================
# Validates that a skill plugin is correctly structured and functional.
#
# Usage:
#   ./scripts/test-plugin.sh tech-recon        # Test tech-recon skill
#   ./scripts/test-plugin.sh jobhunt           # Test jobhunt skill
#   ./scripts/test-plugin.sh --all             # Test all skills
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed
# =============================================================================

set -uo pipefail

# --- Configuration -----------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

TYPEDB_HOST="${TYPEDB_HOST:-localhost}"
TYPEDB_PORT="${TYPEDB_PORT:-1729}"
TYPEDB_DATABASE="${TYPEDB_DATABASE:-alhazen_notebook}"

# --- Helpers -----------------------------------------------------------------

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'
BOLD='\033[1m'

PASS=0
FAIL=0
SKIP=0

check() {
    local label="$1"
    shift
    printf "  %-45s " "$label"
    if output=$("$@" 2>&1); then
        echo -e "${GREEN}PASS${NC}"
        PASS=$((PASS + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        # Show first 3 lines of error
        echo "$output" | head -3 | sed 's/^/    /'
        FAIL=$((FAIL + 1))
        return 1
    fi
}

skip() {
    local label="$1"
    local reason="$2"
    printf "  %-45s " "$label"
    echo -e "${YELLOW}SKIP${NC} ($reason)"
    SKIP=$((SKIP + 1))
}

header() {
    echo ""
    echo -e "${BOLD}=== $1 ===${NC}"
}

# --- Skill resolution --------------------------------------------------------

find_skill_dir() {
    local name="$1"
    if [ -d "skills/$name" ]; then
        echo "skills/$name"
    elif [ -d "local_skills/$name" ]; then
        echo "local_skills/$name"
    else
        echo ""
    fi
}

find_skill_script() {
    local skill_dir="$1"
    local name="$2"
    # Try common naming patterns
    for candidate in \
        "$skill_dir/${name}.py" \
        "$skill_dir/${name//-/_}.py" \
        "$skill_dir/$(echo "$name" | tr '-' '_').py"; do
        if [ -f "$candidate" ]; then
            echo "$candidate"
            return
        fi
    done
    # Fall back to first .py that isn't __init__ or test
    find "$skill_dir" -maxdepth 1 -name "*.py" \
        -not -name "__*" -not -name "test_*" -not -name "*_test.py" \
        -not -name "setup.py" | head -1
}

# --- Test functions ----------------------------------------------------------

test_plugin_structure() {
    local name="$1"
    local skill_dir="$2"

    header "Plugin Structure: $name"

    check "SKILL.md exists" test -f "$skill_dir/SKILL.md"
    check "skill.yaml exists" test -f "$skill_dir/skill.yaml"
    check ".claude-plugin/plugin.json exists" test -f "$skill_dir/.claude-plugin/plugin.json"
    check "skills/$name/SKILL.md exists (plugin loader)" test -f "$skill_dir/skills/$name/SKILL.md"
    check "skills/$name/SKILL.md resolves" test -s "$skill_dir/skills/$name/SKILL.md"
}

test_typedb_connection() {
    header "TypeDB Connectivity"

    check "TypeDB port reachable" bash -c "echo > /dev/tcp/$TYPEDB_HOST/$TYPEDB_PORT"

    check "TypeDB driver connects" uv run python -c "
from typedb.driver import TypeDB, Credentials, DriverOptions
import os
d = TypeDB.driver(
    os.getenv('TYPEDB_HOST','localhost') + ':' + os.getenv('TYPEDB_PORT','1729'),
    Credentials(os.getenv('TYPEDB_USERNAME','admin'), os.getenv('TYPEDB_PASSWORD','password')),
    DriverOptions(is_tls_enabled=False),
)
assert d.databases.contains(os.getenv('TYPEDB_DATABASE','alhazen_notebook')), 'Database not found'
d.close()
print('Connected')
"
}

test_skill_cli() {
    local name="$1"
    local script="$2"

    header "CLI: $name"

    if [ -z "$script" ]; then
        skip "CLI --help" "no Python script found"
        return
    fi

    check "CLI --help" uv run python "$script" --help
}

test_skill_read() {
    local name="$1"
    local script="$2"

    header "Read Operations: $name"

    if [ -z "$script" ]; then
        skip "Read query" "no Python script found"
        return
    fi

    case "$name" in
        tech-recon)
            check "list-investigations" uv run python "$script" list-investigations
            ;;
        jobhunt)
            check "list-pipeline" uv run python "$script" list-pipeline
            check "list-opportunities" uv run python "$script" list-opportunities
            ;;
        typedb-notebook)
            check "list-collections" uv run python "$script" list-collections
            ;;
        agentic-memory)
            check "describe-schema" uv run python "$script" describe-schema
            ;;
        web-search)
            skip "Web search" "requires SearXNG running"
            ;;
        *)
            skip "Read query" "no read test defined for $name"
            ;;
    esac
}

test_schema_loaded() {
    local name="$1"
    local skill_dir="$2"

    header "Schema: $name"

    if [ ! -f "$skill_dir/schema.tql" ]; then
        skip "Schema file" "no schema.tql"
        return
    fi

    check "schema.tql exists" test -f "$skill_dir/schema.tql"

    # Check that skill's namespace prefix appears in schema
    if [ -f "$skill_dir/skill.yaml" ]; then
        local ns
        ns=$(uv run python -c "
import yaml
with open('$skill_dir/skill.yaml') as f:
    cfg = yaml.safe_load(f)
print(cfg.get('schema', {}).get('namespace', ''))
" 2>/dev/null)
        if [ -n "$ns" ]; then
            check "Namespace '$ns' in schema.tql" grep -q "$ns" "$skill_dir/schema.tql"
        fi
    fi
}

# --- Main --------------------------------------------------------------------

run_skill_tests() {
    local name="$1"
    local skill_dir
    skill_dir=$(find_skill_dir "$name")

    if [ -z "$skill_dir" ]; then
        echo -e "${RED}Skill '$name' not found in skills/ or local_skills/${NC}"
        FAIL=$((FAIL + 1))
        return 1
    fi

    local script
    script=$(find_skill_script "$skill_dir" "$name")

    echo -e "\n${BOLD}Testing skill: $name${NC} ($skill_dir)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    test_plugin_structure "$name" "$skill_dir"
    test_schema_loaded "$name" "$skill_dir"
    test_typedb_connection
    test_skill_cli "$name" "$script"
    test_skill_read "$name" "$script"
}

# Parse arguments
SKILLS=()
if [ $# -eq 0 ]; then
    echo "Usage: $0 <skill-name> [<skill-name>...] | --all"
    exit 1
elif [ "$1" = "--all" ]; then
    for d in skills/*/; do
        name=$(basename "$d")
        [ "$name" = "_template" ] && continue
        SKILLS+=("$name")
    done
    for d in local_skills/*/; do
        name=$(basename "$d")
        # Skip if already tested as core skill
        [[ " ${SKILLS[*]} " =~ " $name " ]] && continue
        SKILLS+=("$name")
    done
else
    SKILLS=("$@")
fi

echo -e "${BOLD}Alhazen Plugin Smoke Test${NC}"
echo "Skills: ${SKILLS[*]}"

for skill in "${SKILLS[@]}"; do
    run_skill_tests "$skill"
done

# --- Summary -----------------------------------------------------------------

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BOLD}Results:${NC} ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}, ${YELLOW}${SKIP} skipped${NC}"

if [ $FAIL -gt 0 ]; then
    exit 1
else
    exit 0
fi

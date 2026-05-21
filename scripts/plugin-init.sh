#!/usr/bin/env bash
# =============================================================================
# Alhazen Plugin Init — Standalone TypeDB Bootstrap
# =============================================================================
# Starts TypeDB via Docker and loads core + skill schemas.
# Idempotent — safe to re-run. Reuses existing container if running.
#
# Usage:
#   ./scripts/plugin-init.sh                     # Core schema only
#   ./scripts/plugin-init.sh tech-recon           # Core + tech-recon schema
#   ./scripts/plugin-init.sh jobhunt tech-recon   # Core + multiple skills
#
# Environment (all optional — defaults match dev setup):
#   TYPEDB_HOST       default: localhost
#   TYPEDB_PORT       default: 1729
#   TYPEDB_DATABASE   default: alhazen_notebook
#   TYPEDB_USERNAME   default: admin
#   TYPEDB_PASSWORD   default: password
# =============================================================================

set -euo pipefail

# --- Configuration -----------------------------------------------------------

TYPEDB_IMAGE="typedb/typedb:3.8.0"
TYPEDB_CONTAINER="alhazen-typedb"
TYPEDB_HOST="${TYPEDB_HOST:-localhost}"
TYPEDB_PORT="${TYPEDB_PORT:-1729}"
TYPEDB_DATABASE="${TYPEDB_DATABASE:-alhazen_notebook}"
TYPEDB_USERNAME="${TYPEDB_USERNAME:-admin}"
TYPEDB_PASSWORD="${TYPEDB_PASSWORD:-password}"

# Resolve script directory and project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Helpers -----------------------------------------------------------------

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

info()  { echo -e "${BLUE}$*${NC}"; }
ok()    { echo -e "${GREEN}$*${NC}"; }
warn()  { echo -e "${YELLOW}$*${NC}"; }
fail()  { echo -e "${RED}$*${NC}" >&2; exit 1; }

# --- Step 1: Check Docker ----------------------------------------------------

command -v docker >/dev/null 2>&1 || fail "Docker is required but not installed. Install: https://docs.docker.com/get-docker/"
docker info >/dev/null 2>&1 || fail "Docker daemon is not running. Start Docker and try again."

# --- Step 2: Start TypeDB container (idempotent) ----------------------------

if docker ps --filter "name=$TYPEDB_CONTAINER" --filter "status=running" --format '{{.Names}}' | grep -q "$TYPEDB_CONTAINER"; then
    ok "TypeDB already running ($TYPEDB_CONTAINER)"
elif docker ps -a --filter "name=$TYPEDB_CONTAINER" --format '{{.Names}}' | grep -q "$TYPEDB_CONTAINER"; then
    info "Starting stopped TypeDB container..."
    docker start "$TYPEDB_CONTAINER"
else
    info "Creating TypeDB container ($TYPEDB_IMAGE)..."
    docker run -d \
        --name "$TYPEDB_CONTAINER" \
        -p "127.0.0.1:${TYPEDB_PORT}:1729" \
        -v typedb-data:/var/lib/typedb/data \
        --restart unless-stopped \
        "$TYPEDB_IMAGE"
fi

# --- Step 3: Wait for readiness ---------------------------------------------

info "Waiting for TypeDB to be ready on port $TYPEDB_PORT..."
TIMEOUT=60
ELAPSED=0
while ! timeout 2 bash -c "echo > /dev/tcp/$TYPEDB_HOST/$TYPEDB_PORT" 2>/dev/null; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [ $ELAPSED -ge $TIMEOUT ]; then
        fail "TypeDB failed to start within ${TIMEOUT}s"
    fi
    printf "."
done
echo ""
ok "TypeDB is ready at $TYPEDB_HOST:$TYPEDB_PORT"

# --- Step 4: Find core schema ------------------------------------------------

CORE_SCHEMA=""
# Dev mode: full repo has local_resources/typedb/
if [ -f "$PROJECT_ROOT/local_resources/typedb/alhazen_notebook.tql" ]; then
    CORE_SCHEMA="$PROJECT_ROOT/local_resources/typedb/alhazen_notebook.tql"
# Standalone: bundled with scripts
elif [ -f "$SCRIPT_DIR/core-schema.tql" ]; then
    CORE_SCHEMA="$SCRIPT_DIR/core-schema.tql"
# Plugin mode: check .claude-plugin directory
elif [ -f "$PROJECT_ROOT/.claude-plugin/core-schema.tql" ]; then
    CORE_SCHEMA="$PROJECT_ROOT/.claude-plugin/core-schema.tql"
else
    fail "Cannot find core schema (alhazen_notebook.tql). Expected in:\n  - local_resources/typedb/alhazen_notebook.tql\n  - scripts/core-schema.tql\n  - .claude-plugin/core-schema.tql"
fi

info "Core schema: $CORE_SCHEMA"

# --- Step 5: Find skill schemas ----------------------------------------------

SKILL_SCHEMAS=()
for skill_name in "$@"; do
    schema=""
    # Check local_skills/ first (dev mode after make build-skills)
    if [ -f "$PROJECT_ROOT/local_skills/$skill_name/schema.tql" ]; then
        schema="$PROJECT_ROOT/local_skills/$skill_name/schema.tql"
    # Check skills/ (core skills in dev mode)
    elif [ -f "$PROJECT_ROOT/skills/$skill_name/schema.tql" ]; then
        schema="$PROJECT_ROOT/skills/$skill_name/schema.tql"
    else
        warn "Warning: No schema.tql found for skill '$skill_name' — skipping"
        continue
    fi
    info "Skill schema: $schema"
    SKILL_SCHEMAS+=("$schema")
done

# --- Step 6: Load schemas via db_init.py ------------------------------------

# Check for uv (preferred) or fall back to python3
if command -v uv >/dev/null 2>&1; then
    PYTHON_CMD="uv run python"
else
    PYTHON_CMD="python3"
fi

# Check if db_init.py exists
DB_INIT="$PROJECT_ROOT/scripts/db_init.py"
if [ ! -f "$DB_INIT" ]; then
    fail "Cannot find scripts/db_init.py. This script must be run from the project root or a plugin that bundles it."
fi

info "Loading schemas into database '$TYPEDB_DATABASE'..."
SCHEMA_ARGS=("$CORE_SCHEMA")
for s in "${SKILL_SCHEMAS[@]+"${SKILL_SCHEMAS[@]}"}"; do
    SCHEMA_ARGS+=("$s")
done

TYPEDB_HOST="$TYPEDB_HOST" \
TYPEDB_PORT="$TYPEDB_PORT" \
TYPEDB_DATABASE="$TYPEDB_DATABASE" \
TYPEDB_USERNAME="$TYPEDB_USERNAME" \
TYPEDB_PASSWORD="$TYPEDB_PASSWORD" \
$PYTHON_CMD "$DB_INIT" "${SCHEMA_ARGS[@]}"

# --- Done --------------------------------------------------------------------

echo ""
ok "=== Plugin init complete ==="
echo "  Container:  $TYPEDB_CONTAINER"
echo "  Host:       $TYPEDB_HOST:$TYPEDB_PORT"
echo "  Database:   $TYPEDB_DATABASE"
echo "  Schemas:    core$([ ${#SKILL_SCHEMAS[@]} -gt 0 ] && echo " + ${#SKILL_SCHEMAS[@]} skill(s)" || echo "")"
echo ""
echo "Environment variables (already set to defaults):"
echo "  export TYPEDB_HOST=$TYPEDB_HOST"
echo "  export TYPEDB_PORT=$TYPEDB_PORT"
echo "  export TYPEDB_DATABASE=$TYPEDB_DATABASE"

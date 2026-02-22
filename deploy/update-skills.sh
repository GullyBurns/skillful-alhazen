#!/bin/bash
# update-skills.sh — Pull latest code and copy skills into a hardened workspace
#
# Usage:
#   ./update-skills.sh [BRANCH] [OPENCLAW_HOME]
#
# Defaults:
#   BRANCH:        main
#   OPENCLAW_HOME: /Users/openclaw  (macOS) or /home/openclaw (Linux)
#
# The script expects the Ansible-deployed directory layout:
#   OPENCLAW_HOME/
#   ├── skillful-alhazen/          # Git clone (shared)
#   └── openclaw-hardened/         # Hardened stack workspace
#       └── workspace/skills/      # Skills copied here
#
# After copying, restarts the agent container so it picks up new skills.

set -e

BRANCH="${1:-main}"

# Auto-detect OS for default openclaw home
if [ "$(uname)" = "Darwin" ]; then
    OPENCLAW_HOME="${2:-/Users/openclaw}"
else
    OPENCLAW_HOME="${2:-/home/openclaw}"
fi

REPO_DIR="$OPENCLAW_HOME/skillful-alhazen"

# Find the hardened workspace (openclaw-hardened or openclaw-docker)
if [ -d "$OPENCLAW_HOME/openclaw-hardened/workspace" ]; then
    WORKSPACE_DIR="$OPENCLAW_HOME/openclaw-hardened/workspace"
elif [ -d "$OPENCLAW_HOME/openclaw-docker/workspace" ]; then
    WORKSPACE_DIR="$OPENCLAW_HOME/openclaw-docker/workspace"
else
    echo "Error: No workspace directory found under $OPENCLAW_HOME"
    echo "Has the hardened stack been deployed? Run deploy.sh first."
    exit 1
fi

if [ ! -d "$REPO_DIR" ]; then
    echo "Error: Repository not found at $REPO_DIR"
    echo "Has the hardened stack been deployed? Run deploy.sh first."
    exit 1
fi

echo "Pulling branch '$BRANCH' in $REPO_DIR..."
cd "$REPO_DIR"
git fetch origin
git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" "origin/$BRANCH"
git pull origin "$BRANCH"

echo "Copying skills to $WORKSPACE_DIR/skills/..."
mkdir -p "$WORKSPACE_DIR/skills"
for skill_dir in .claude/skills/*/; do
    skill_name=$(basename "$skill_dir")
    [ "$skill_name" = "_template" ] && continue
    cp -r "$skill_dir" "$WORKSPACE_DIR/skills/$skill_name"
    echo "  -> $skill_name"
done

# Also copy CLAUDE.md and identity files
cp -f CLAUDE.md "$WORKSPACE_DIR/CLAUDE.md" 2>/dev/null || true
cp -f local_resources/openclaw/SOUL.md "$WORKSPACE_DIR/SOUL.md" 2>/dev/null || true
cp -f local_resources/openclaw/AGENTS.md "$WORKSPACE_DIR/AGENTS.md" 2>/dev/null || true

# Detect which agent container to restart
AGENT_CONTAINER=""
for name in hardened-agent openclaw-agent; do
    if docker ps --format '{{.Names}}' | grep -q "^${name}$"; then
        AGENT_CONTAINER="$name"
        break
    fi
done

if [ -n "$AGENT_CONTAINER" ]; then
    echo "Restarting $AGENT_CONTAINER..."
    docker restart "$AGENT_CONTAINER"
    echo "Done. Skills updated and agent restarted."
else
    echo "Warning: No agent container found running. Skills copied but no restart performed."
fi

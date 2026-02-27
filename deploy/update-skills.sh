#!/bin/bash
# update-skills.sh — Pull latest code, resolve all skills, and copy to the workspace
#
# Usage:
#   ./update-skills.sh [BRANCH] [OPENCLAW_HOME]
#
# Defaults:
#   BRANCH:        main
#   OPENCLAW_HOME: /Users/openclaw  (macOS) or /home/openclaw (Linux)
#
# This script mirrors the 'make build-skills' + copy logic from the Ansible playbook.
# It is intended for incremental updates on an already-deployed remote host.

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
if [ -d "$OPENCLAW_HOME/openclaw-hardened/openclaw-data/skills" ]; then
    SKILLS_DEST="$OPENCLAW_HOME/openclaw-hardened/openclaw-data/skills"
elif [ -d "$OPENCLAW_HOME/openclaw-docker/openclaw-data/skills" ]; then
    SKILLS_DEST="$OPENCLAW_HOME/openclaw-docker/openclaw-data/skills"
elif [ -d "$OPENCLAW_HOME/.openclaw/skills" ]; then
    # macOS native (non-containerized)
    SKILLS_DEST="$OPENCLAW_HOME/.openclaw/skills"
else
    echo "Error: No skills directory found under $OPENCLAW_HOME"
    echo "Has the stack been deployed? Run deploy.sh first."
    exit 1
fi

if [ ! -d "$REPO_DIR" ]; then
    echo "Error: Repository not found at $REPO_DIR"
    echo "Has the stack been deployed? Run deploy.sh first."
    exit 1
fi

echo "Pulling branch '$BRANCH' in $REPO_DIR..."
cd "$REPO_DIR"
git fetch origin
git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" "origin/$BRANCH"
git pull origin "$BRANCH"

echo "Resolving skills from skills-registry.yaml..."
python3 - << 'PYEOF'
import subprocess, sys, shutil
from pathlib import Path
try:
    import yaml
except ImportError:
    print("PyYAML not available — skipping skill resolution"); sys.exit(0)
registry = Path('skills-registry.yaml')
if not registry.exists():
    print("No skills-registry.yaml found"); sys.exit(0)
cfg = yaml.safe_load(registry.read_text()) or {}
local_skills = Path('local_skills'); local_skills.mkdir(exist_ok=True)
for skill in cfg.get('skills') or []:
    name = skill['name']
    target = local_skills / name
    if 'path' in skill:
        src = Path(skill['path'])
        if target.is_symlink(): target.unlink()
        elif target.exists(): shutil.rmtree(str(target))
        target.symlink_to(f'../{src}')
        print(f'  Re-linked (core): {name}')
        continue
    git_url = skill['git']
    ref = skill.get('ref', 'main'); subdir = skill.get('subdir', '.')
    print(f'  Updating {name}...')
    if target.is_symlink(): target.unlink()
    elif target.exists(): shutil.rmtree(str(target))
    tmp = local_skills / f'_tmp_{name}'
    try:
        subprocess.run(['git','clone','--depth=1','--branch',ref,git_url,str(tmp)],
                       check=True, capture_output=True)
        src = tmp / subdir if subdir != '.' else tmp
        src.rename(target)
        print(f'  Updated {name}')
    except subprocess.CalledProcessError as e:
        print(f'  Failed {name}: {e}', file=sys.stderr)
    finally:
        if tmp.exists(): shutil.rmtree(str(tmp), ignore_errors=True)
PYEOF

echo "Copying resolved skills to $SKILLS_DEST/..."
mkdir -p "$SKILLS_DEST"
for skill_dir in "$REPO_DIR/local_skills"/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")
    cp -rL "$skill_dir" "$SKILLS_DEST/$skill_name"
    echo "  -> $skill_name"
done

# Also copy CLAUDE.md and identity files
cp -f "$REPO_DIR/CLAUDE.md" "$(dirname "$SKILLS_DEST")/CLAUDE.md" 2>/dev/null || true
cp -f "$REPO_DIR/local_resources/openclaw/SOUL.md"   "$(dirname "$SKILLS_DEST")/SOUL.md"   2>/dev/null || true
cp -f "$REPO_DIR/local_resources/openclaw/AGENTS.md" "$(dirname "$SKILLS_DEST")/AGENTS.md" 2>/dev/null || true

# Detect which agent container to restart
AGENT_CONTAINER=""
for name in hardened-agent openclaw-agent; do
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${name}$"; then
        AGENT_CONTAINER="$name"
        break
    fi
done

if [ -n "$AGENT_CONTAINER" ]; then
    echo "Restarting $AGENT_CONTAINER..."
    docker restart "$AGENT_CONTAINER"
    echo "Done. Skills updated and agent restarted."
else
    echo "Skills copied. No agent container found running — restart manually if needed."
fi

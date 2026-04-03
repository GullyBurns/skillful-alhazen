# Makefile for Skillful Alhazen Repository
# Comprehensive skill portability and project management
SHELL := /bin/bash

# =============================================================================
# Variables
# =============================================================================

PROJECT_ROOT := $(shell pwd)
OPENCLAW_WORKSPACE := $(HOME)/.openclaw/workspace
CLAUDE_SKILLS_DIR := $(PROJECT_ROOT)/.claude/skills
OPENCLAW_SKILLS_DIR := $(OPENCLAW_WORKSPACE)/skills
OPENCLAW_CONFIG := $(HOME)/.openclaw/openclaw.json
TYPEDB_CONTAINER := alhazen-typedb
TYPEDB_DATABASE := alhazen_notebook
TYPEDB_COMPOSE_PROJECT := skillful-alhazen
TYPEDB_SCHEMAS_DIR := $(PROJECT_ROOT)/local_resources/typedb
LOCAL_SKILLS_DIR := $(PROJECT_ROOT)/local_skills
SKILLS_REGISTRY := $(PROJECT_ROOT)/skills-registry.yaml
SKILL_LIBRARY ?=  # override: make build-skills SKILL_LIBRARY=https://github.com/MyOrg/fork

# OS detection
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
    PKG_INSTALL_HINT = brew install
else
    PKG_INSTALL_HINT = apt-get install -y
endif

# Colors for output
RED := \033[31m
GREEN := \033[32m
BLUE := \033[34m
YELLOW := \033[33m
NC := \033[0m

# =============================================================================
# Help
# =============================================================================

.PHONY: help
help: ## Show this help message
	@echo "$(BLUE)Skillful Alhazen Makefile$(NC)"
	@echo "=========================="
	@echo
	@echo "$(GREEN)Setup:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(setup|db-)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo
	@echo "$(GREEN)Skill Deployment:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(deploy|skills|monitoring)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo
	@echo "$(GREEN)Database Management:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E 'db-' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo
	@echo "$(GREEN)Deployment:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E 'deploy-(vps|macmini|status)|openclaw-(stop|start)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo
	@echo "$(GREEN)Remote Access:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E 'tailscale' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo
	@echo "$(GREEN)Documentation:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E 'docs-' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo
	@echo "$(GREEN)Observability:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(skills-token|skills-invocations)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo
	@echo "$(GREEN)Dashboard:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E 'dashboard' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo
	@echo "$(GREEN)Development:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(test|lint|clean)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

# =============================================================================
# Setup
# =============================================================================

# Phase 1: Build — local dev (Claude Code)
.PHONY: build
build: build-env build-skills build-dashboard build-db ## Phase 1: Install deps + resolve skills + start TypeDB
	@echo "$(GREEN)✓ Build complete! Use Claude Code with skills in .claude/skills/$(NC)"

.PHONY: build-env
build-env: ## Install Python dependencies
	@echo "$(BLUE)Installing Python dependencies...$(NC)"
	uv sync --all-extras
	@echo "$(GREEN)✓ Python dependencies installed$(NC)"

.PHONY: build-skills
build-skills: skills-install deploy-claude ## Resolve skills-registry.yaml → local_skills/ + wire .claude/skills/
	@echo "$(GREEN)✓ Skills built$(NC)"

.PHONY: build-db
build-db: db-start db-init ## Start TypeDB and load all schemas (run after build-skills)
	@echo "$(GREEN)✓ TypeDB ready$(NC)"

.PHONY: build-dashboard
build-dashboard: build-skills ## Wire skill dashboard pages/routes/components into Next.js app
	@echo "$(BLUE)Wiring skill dashboards into Next.js app...$(NC)"
	@mkdir -p dashboard/src/components dashboard/src/lib \
	           dashboard/src/app dashboard/src/app/api
	@PUBLIC_SKILLS=$$(uv run python -c "import yaml; cfg=yaml.safe_load(open('skills-registry.yaml')); print(' '.join(s['name'] for s in (cfg.get('skills') or [])))"); \
	while IFS= read -r d; do \
	  skill_name=$$(basename "$$d" | tr -d '()'); \
	  echo " $$PUBLIC_SKILLS " | grep -q " $$skill_name " || { \
	    echo "  Removing stale route group: $$d"; rm -rf "$$d"; }; \
	done < <(find dashboard/src/app -maxdepth 1 -mindepth 1 -name '(*' 2>/dev/null); \
	while IFS= read -r d; do \
	  skill_name=$$(basename "$$d"); \
	  [ "$$skill_name" = "typedb-status" ] && continue; \
	  echo " $$PUBLIC_SKILLS " | grep -q " $$skill_name " || { \
	    echo "  Removing stale API route: $$d"; rm -rf "$$d"; }; \
	done < <(find dashboard/src/app/api -maxdepth 1 -mindepth 1 2>/dev/null); \
	while IFS= read -r d; do \
	  skill_name=$$(basename "$$d"); \
	  [ "$$skill_name" = "ui" ] && continue; \
	  echo " $$PUBLIC_SKILLS " | grep -q " $$skill_name " || { \
	    echo "  Removing stale component dir: $$d"; rm -rf "$$d"; }; \
	done < <(find dashboard/src/components -maxdepth 1 -mindepth 1 2>/dev/null); \
	for f in dashboard/src/lib/*.ts; do \
	  [ -f "$$f" ] || [ -L "$$f" ] || continue; \
	  skill_name=$$(basename "$$f" .ts); \
	  [ "$$skill_name" = "utils" ] && continue; \
	  echo " $$PUBLIC_SKILLS " | grep -q " $$skill_name " || { \
	    echo "  Removing stale lib file: $$f"; rm -f "$$f"; }; \
	done; \
	for skill_dir in local_skills/*/; do \
	  [ -d "$${skill_dir}dashboard" ] || continue; \
	  skill_name=$$(basename $$skill_dir); \
	  echo " $$PUBLIC_SKILLS " | grep -q " $$skill_name " || { echo "  Skipping $${skill_name} (local-registry — not wired into tracked dashboard)"; continue; }; \
	  echo "  Wiring $${skill_name} dashboard..."; \
	  rm -rf "dashboard/src/app/($${skill_name})" 2>/dev/null || true; \
	  rm -rf "dashboard/src/components/$${skill_name}" 2>/dev/null || true; \
	  rm -rf "dashboard/src/app/api/$${skill_name}" 2>/dev/null || true; \
	  rm -f "dashboard/src/lib/$${skill_name}.ts" 2>/dev/null || true; \
	  [ -d "$${skill_dir}dashboard/components" ] && \
	    ln -sfn "$$(pwd)/$${skill_dir}dashboard/components" \
	             "dashboard/src/components/$${skill_name}"; \
	  [ -f "$${skill_dir}dashboard/lib.ts" ] && \
	    ln -sfn "$$(pwd)/$${skill_dir}dashboard/lib.ts" \
	             "dashboard/src/lib/$${skill_name}.ts"; \
	  [ -d "$${skill_dir}dashboard/pages" ] && \
	    ln -sfn "$$(pwd)/$${skill_dir}dashboard/pages" \
	             "dashboard/src/app/($${skill_name})"; \
	  [ -d "$${skill_dir}dashboard/routes" ] && \
	    ln -sfn "$$(pwd)/$${skill_dir}dashboard/routes" \
	             "dashboard/src/app/api/$${skill_name}"; \
	done
	@echo "  Generating dashboard/public/skills-config.json..."
	@uv run python -c "\
import yaml, json, os; \
registry = yaml.safe_load(open('skills-registry.yaml')); \
configs = [{'slug': s['name'], **s['dashboard']} for s in registry.get('skills', []) if s.get('dashboard', {}).get('enabled')]; \
os.makedirs('dashboard/public', exist_ok=True); \
json.dump(configs, open('dashboard/public/skills-config.json', 'w'), indent=2); \
print(f'  {len(configs)} skill dashboards registered') \
"
	@echo "$(GREEN)✓ Skill dashboards wired$(NC)"

# Deprecated aliases (kept for backward compatibility)
.PHONY: setup setup-python setup-typedb
setup: build ## [deprecated] Use 'make build' instead
setup-python: build-env ## [deprecated] Use 'make build-env' instead
setup-typedb: build-db ## [deprecated] Use 'make build-db' instead

# =============================================================================
# Database Management
# =============================================================================

.PHONY: db-start
db-start: ## Start TypeDB container
	@if docker ps --filter "name=$(TYPEDB_CONTAINER)" --filter "status=running" --format '{{.Names}}' | grep -q $(TYPEDB_CONTAINER); then \
		echo "$(GREEN)✓ TypeDB already running$(NC)"; \
	else \
		echo "$(BLUE)Starting TypeDB container...$(NC)"; \
		docker compose -p $(TYPEDB_COMPOSE_PROJECT) up -d; \
		echo "$(BLUE)Waiting for TypeDB to be ready...$(NC)"; \
		uv run python scripts/db_init.py --wait-only --timeout 60; \
		echo "$(GREEN)✓ TypeDB is ready$(NC)"; \
	fi

.PHONY: db-stop
db-stop: ## Stop TypeDB container
	@echo "$(BLUE)Stopping TypeDB container...$(NC)"
	docker compose -p $(TYPEDB_COMPOSE_PROJECT) down
	@echo "$(GREEN)✓ TypeDB stopped$(NC)"

.PHONY: db-init
db-init: ## Create database and load schemas
	@echo "$(BLUE)Initializing TypeDB database '$(TYPEDB_DATABASE)'...$(NC)"
	@SCHEMAS="$(TYPEDB_SCHEMAS_DIR)/alhazen_notebook.tql"; \
	if [ -d "$(LOCAL_SKILLS_DIR)" ]; then \
		for skill_dir in $(LOCAL_SKILLS_DIR)/*/; do \
			schema=$$(readlink -f $$skill_dir)/schema.tql; \
			[ -f "$$schema" ] || continue; \
			SCHEMAS="$$SCHEMAS $$schema"; \
		done; \
	fi; \
	for schema in $(TYPEDB_SCHEMAS_DIR)/namespaces/*.tql; do \
		[ -f "$$schema" ] || continue; \
		SCHEMAS="$$SCHEMAS $$schema"; \
	done; \
	uv run python scripts/db_init.py $$SCHEMAS
	@echo "$(GREEN)✓ Database initialized$(NC)"

.PHONY: qdrant-start
qdrant-start: ## Start Qdrant vector store container
	@echo "$(BLUE)Starting Qdrant container...$(NC)"
	docker compose up -d qdrant
	@echo "$(GREEN)✓ Qdrant running at http://localhost:6333$(NC)"

.PHONY: qdrant-stop
qdrant-stop: ## Stop Qdrant vector store container
	@echo "$(BLUE)Stopping Qdrant container...$(NC)"
	docker compose stop qdrant
	@echo "$(GREEN)✓ Qdrant stopped$(NC)"

.PHONY: db-export
db-export: ## Export database to timestamped zip
	@echo "$(BLUE)Exporting database...$(NC)"
	uv run python $(CLAUDE_SKILLS_DIR)/typedb-notebook/typedb_notebook.py export-db --database $(TYPEDB_DATABASE)
	@echo "$(GREEN)✓ Database exported$(NC)"

.PHONY: package-skill
package-skill: ## Bundle a skill as a distributable zip (requires SKILL=name)
ifndef SKILL
	@echo "$(RED)Error: SKILL variable required. Usage: make package-skill SKILL=jobhunt$(NC)"
	@exit 1
endif
	@echo "$(BLUE)Packaging skill '$(SKILL)'...$(NC)"
	uv run python scripts/package_skill.py $(SKILL)
	@echo "$(GREEN)✓ Skill packaged$(NC)"

.PHONY: install-skill
install-skill: ## Install a skill from a zip bundle (requires ZIP=path)
ifndef ZIP
	@echo "$(RED)Error: ZIP variable required. Usage: make install-skill ZIP=jobhunt-v1.0.zip$(NC)"
	@exit 1
endif
	@echo "$(BLUE)Installing skill from $(ZIP)...$(NC)"
	uv run python scripts/install_skill.py $(ZIP)
	$(MAKE) --no-print-directory deploy-claude
	@echo "$(BLUE)Loading schema into TypeDB...$(NC)"
	@skill_name=$$(uv run python -c "import yaml,zipfile; z=zipfile.ZipFile('$(ZIP)'); print(yaml.safe_load(z.read('skill.yaml'))['name'])" 2>/dev/null); \
	[ -f "local_skills/$$skill_name/schema.tql" ] && \
	  uv run python scripts/db_init.py "local_skills/$$skill_name/schema.tql" || \
	  echo "  No schema.tql found — skipping schema load"
	@echo "$(BLUE)Importing curation-skill-builder knowledge graph...$(NC)"
	@skill_name=$$(uv run python -c "import yaml,zipfile; z=zipfile.ZipFile('$(ZIP)'); print(yaml.safe_load(z.read('skill.yaml'))['name'])" 2>/dev/null); \
	[ -f "local_skills/$$skill_name/data/skill_builder.json" ] && \
	  uv run python $(CLAUDE_SKILLS_DIR)/curation-skill-builder/skill_builder.py import-skill-data \
	    --file "local_skills/$$skill_name/data/skill_builder.json" || true
	@echo "$(BLUE)Wiring dashboard (if present)...$(NC)"
	@skill_name=$$(uv run python -c "import yaml,zipfile; z=zipfile.ZipFile('$(ZIP)'); print(yaml.safe_load(z.read('skill.yaml'))['name'])" 2>/dev/null); \
	[ -d "local_skills/$$skill_name/dashboard" ] && \
	  $(MAKE) --no-print-directory build-dashboard || true
	@echo "$(GREEN)✓ Skill installed. Restart Claude Code to pick up the new skill.$(NC)"

.PHONY: db-migrate
db-migrate: ## Migrate database to new schema (export, transform, reimport)
	@echo "$(BLUE)Running schema migration...$(NC)"
	@echo "$(YELLOW)This will drop and recreate the database. Data is backed up first.$(NC)"
	uv run python $(TYPEDB_SCHEMAS_DIR)/migrate_schema_v2.py migrate --export-path exports/migration_data.json
	@echo "$(GREEN)✓ Migration complete$(NC)"

.PHONY: db-import
db-import: ## Import database from zip (requires ZIP=/path/to/export.zip)
ifndef ZIP
	@echo "$(RED)Error: ZIP variable required. Usage: make db-import ZIP=/path/to/export.zip$(NC)"
	@exit 1
endif
	@echo "$(BLUE)Importing database from $(ZIP)...$(NC)"
	uv run python $(CLAUDE_SKILLS_DIR)/typedb-notebook/typedb_notebook.py import-db --zip $(ZIP) --database $(TYPEDB_DATABASE)
	@echo "$(GREEN)✓ Database imported$(NC)"

# =============================================================================
# Skill Deployment
# =============================================================================

.PHONY: deploy-claude-settings
deploy-claude-settings: ## Write .claude/settings.json with portable PostToolUse hook
	@printf '{\n  "hooks": {\n    "PostToolUse": [\n      {\n        "matcher": "Bash",\n        "hooks": [\n          {\n            "type": "command",\n            "command": "REPO=$$(git rev-parse --show-toplevel) && cd \\"$$REPO\\" && uv run python \\"$$REPO/local_resources/skilllog/skill_logger.py\\""\n          }\n        ]\n      }\n    ]\n  }\n}\n' > $(PROJECT_ROOT)/.claude/settings.json
	@echo "$(GREEN)  ✓ Wrote .claude/settings.json$(NC)"

.PHONY: deploy-claude
deploy-claude: deploy-claude-settings ## Symlink external skills from local_skills/ into .claude/skills/ (for Claude Code)
	@echo "$(BLUE)Deploying external skills to Claude Code...$(NC)"
	@mkdir -p $(CLAUDE_SKILLS_DIR)
	@if [ ! -d "$(LOCAL_SKILLS_DIR)" ]; then \
		echo "$(YELLOW)→ No local_skills/ directory — run 'make skills-install' first$(NC)"; \
	else \
		for skill_dir in $(LOCAL_SKILLS_DIR)/*/; do \
			[ -d "$$skill_dir" ] || continue; \
			skill_name=$$(basename $$skill_dir); \
			target=$(CLAUDE_SKILLS_DIR)/$$skill_name; \
			if [ -L "$$target" ]; then \
				rm "$$target"; \
			elif [ -d "$$target" ]; then \
				echo "$(YELLOW)  → Skipping $$skill_name (real directory exists, not a symlink)$(NC)"; \
				continue; \
			fi; \
			ln -sfn ../../local_skills/$$skill_name "$$target"; \
			echo "$(GREEN)  ✓ Linked: $$skill_name$(NC)"; \
		done; \
		for target in $(CLAUDE_SKILLS_DIR)/*/; do \
			link=$${target%/}; \
			[ -L "$$link" ] || continue; \
			skill_name=$$(basename "$$link"); \
			[ -d "$(LOCAL_SKILLS_DIR)/$$skill_name" ] && continue; \
			echo "$(YELLOW)  → Removing stale symlink: $$skill_name$(NC)"; \
			rm "$$link"; \
		done; \
	fi
	@echo "$(GREEN)✓ External skills deployed to .claude/skills/$(NC)"

.PHONY: deploy-openclaw
deploy-openclaw: deploy-openclaw-skills deploy-openclaw-config deploy-openclaw-docs deploy-openclaw-identity ## Symlink skills + configure OpenClaw + update workspace docs + render identity

.PHONY: deploy-openclaw-skills
deploy-openclaw-skills: ## Symlink core + external skills into OpenClaw workspace/skills/
	@echo "$(BLUE)Deploying skills to OpenClaw workspace...$(NC)"
	@mkdir -p $(OPENCLAW_SKILLS_DIR)
	@# Core skills: real directories in .claude/skills/ (not symlinks, not _template)
	@for skill_dir in $(CLAUDE_SKILLS_DIR)/*/; do \
		link=$${skill_dir%/}; \
		[ -L "$$link" ] && continue; \
		skill_name=$$(basename $$link); \
		[ "$$skill_name" = "_template" ] && continue; \
		target=$(OPENCLAW_SKILLS_DIR)/$$skill_name; \
		[ -L "$$target" ] && rm "$$target"; \
		[ -d "$$target" ] && rm -rf "$$target"; \
		ln -s "$(PROJECT_ROOT)/.claude/skills/$$skill_name" "$$target"; \
		echo "$(GREEN)  ✓ Core: $$skill_name$(NC)"; \
	done
	@# External skills: directories in local_skills/
	@if [ -d "$(LOCAL_SKILLS_DIR)" ]; then \
		for skill_dir in $(LOCAL_SKILLS_DIR)/*/; do \
			[ -d "$$skill_dir" ] || continue; \
			skill_name=$$(basename $$skill_dir); \
			target=$(OPENCLAW_SKILLS_DIR)/$$skill_name; \
			[ -L "$$target" ] && rm "$$target"; \
			[ -d "$$target" ] && rm -rf "$$target"; \
			ln -s "$(PROJECT_ROOT)/local_skills/$$skill_name" "$$target"; \
			echo "$(GREEN)  ✓ External: $$skill_name$(NC)"; \
		done; \
	fi
	@# Remove stale symlinks (point to non-existent targets)
	@for target in $(OPENCLAW_SKILLS_DIR)/*/; do \
		link=$${target%/}; \
		[ -L "$$link" ] || continue; \
		[ -e "$$link" ] || { echo "$(YELLOW)  → Removing stale symlink: $$(basename $$link)$(NC)"; rm "$$link"; }; \
	done
	@echo "$(GREEN)✓ Skills deployed to OpenClaw workspace$(NC)"

.PHONY: deploy-openclaw-config
deploy-openclaw-config: ## Merge skills.entries into openclaw.json (requires jq)
	@echo "$(BLUE)Updating OpenClaw configuration...$(NC)"
	@if ! command -v jq &>/dev/null; then \
		echo "$(RED)✗ jq is required. Install with: $(PKG_INSTALL_HINT) jq$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f "$(OPENCLAW_CONFIG)" ]; then \
		echo "$(RED)✗ OpenClaw config not found: $(OPENCLAW_CONFIG)$(NC)"; \
		exit 1; \
	fi
	@# Build the skills.entries object from all resolved skills in local_skills/
	@patch=$$(echo '{}'); \
	if [ -d "$(LOCAL_SKILLS_DIR)" ]; then \
		for skill_dir in $(LOCAL_SKILLS_DIR)/*/; do \
			[ -d "$$skill_dir" ] || continue; \
			skill_name=$$(basename $$skill_dir); \
			patch=$$(echo "$$patch" | jq --arg name "$$skill_name" --arg root "$(PROJECT_ROOT)" \
				'. + {($$name): {"env": {"ALHAZEN_PROJECT_ROOT": $$root, "TYPEDB_DATABASE": "alhazen_notebook"}}}'); \
		done; \
	fi; \
	jq --argjson entries "$$patch" '.skills.entries = $$entries' "$(OPENCLAW_CONFIG)" > "$(OPENCLAW_CONFIG).tmp" && \
		mv "$(OPENCLAW_CONFIG).tmp" "$(OPENCLAW_CONFIG)"
	@echo "$(GREEN)✓ Updated skills.entries in $(OPENCLAW_CONFIG)$(NC)"
	@# Ensure heartbeat is configured (idempotent — only adds if missing)
	@if jq -e '.agents.defaults.heartbeat' "$(OPENCLAW_CONFIG)" >/dev/null 2>&1; then \
		echo "  $(YELLOW)→ Heartbeat already configured — skipping$(NC)"; \
	else \
		jq '.agents.defaults.heartbeat = {"every": "2h", "target": "last", "activeHours": {"start": "08:00", "end": "22:00", "timezone": "America/Los_Angeles"}}' \
			"$(OPENCLAW_CONFIG)" > "$(OPENCLAW_CONFIG).tmp" && \
			mv "$(OPENCLAW_CONFIG).tmp" "$(OPENCLAW_CONFIG)"; \
		echo "$(GREEN)✓ Added heartbeat config (every 2h, 08:00-22:00 PT)$(NC)"; \
	fi

# Python script: update CLAUDE.md skills table
# Args: sys.argv[1]=skills_dir sys.argv[2]=claude_md_path
define UPDATE_CLAUDE_MD_PY
import os, glob, re, sys
skills_dir = sys.argv[1]
lines = ['| Skill | Description | Script(s) |', '|-------|-------------|-----------|']
for d in sorted(glob.glob(os.path.join(skills_dir, '*'))):
    name = os.path.basename(d)
    if name == '_template' or not os.path.isdir(d):
        continue
    scripts = [f for f in os.listdir(d) if f.endswith('.py')]
    desc = ''
    skill_md = os.path.join(d, 'SKILL.md')
    if os.path.exists(skill_md):
        for line in open(skill_md):
            if line.startswith('description:'):
                desc = line.split(':', 1)[1].strip().strip('"')
                break
    script_str = ', '.join(sorted(scripts)) if scripts else '(no script)'
    lines.append(f'| {name} | {desc} | `{script_str}` |')
table = '\n'.join(lines)
path = sys.argv[2]
content = open(path).read()
pattern = r'(\| Skill \|.*?\n(?:\|.*\n)*)'
if re.search(pattern, content):
    content = re.sub(pattern, table + '\n', content, count=1)
    open(path, 'w').write(content)
    print('  Updated skills table in CLAUDE.md')
else:
    print('  Skills table marker not found in CLAUDE.md -- skipping')
endef
export UPDATE_CLAUDE_MD_PY

.PHONY: deploy-openclaw-docs
deploy-openclaw-docs: ## Update CLAUDE.md skills table in OpenClaw workspace
	@echo "$(BLUE)Updating OpenClaw workspace docs...$(NC)"
	@# --- Update CLAUDE.md skills table ---
	@if [ -f "$(OPENCLAW_WORKSPACE)/CLAUDE.md" ]; then \
		python3 -c "$$UPDATE_CLAUDE_MD_PY" "$(CLAUDE_SKILLS_DIR)" "$(OPENCLAW_WORKSPACE)/CLAUDE.md"; \
	else \
		echo "  $(YELLOW)No CLAUDE.md found in workspace — skipping$(NC)"; \
	fi
	@echo "$(GREEN)✓ OpenClaw workspace docs updated$(NC)"

.PHONY: deploy-openclaw-identity
deploy-openclaw-identity: ## Render identity files (MEMORY, HEARTBEAT, TOOLS, etc.) for OpenClaw workspace
	@echo "$(BLUE)Rendering identity files...$(NC)"
	@# Copy SOUL.md (static, always overwrite from source)
	@if [ -f "$(PROJECT_ROOT)/local_resources/openclaw/SOUL.md" ]; then \
		cp "$(PROJECT_ROOT)/local_resources/openclaw/SOUL.md" "$(OPENCLAW_WORKSPACE)/"; \
		echo "  Copied SOUL.md"; \
	fi
	@uv run python $(PROJECT_ROOT)/src/skillful_alhazen/utils/render_identity.py \
		--workspace $(OPENCLAW_WORKSPACE) render-all
	@echo "$(GREEN)✓ Identity files rendered$(NC)"

.PHONY: render-memory
render-memory: ## Refresh identity files from TypeDB (standalone, any workspace)
	uv run python $(PROJECT_ROOT)/src/skillful_alhazen/utils/render_identity.py \
		--workspace $(OPENCLAW_WORKSPACE) render-all

.PHONY: deploy-goose
deploy-goose: ## Generate MCP config for Goose (future implementation)
	@echo "$(YELLOW)Goose/MCP integration not yet implemented$(NC)"
	@echo "$(BLUE)Future: Will generate ~/.config/goose/profiles.yaml configuration$(NC)"

# =============================================================================
# Skill Management
# =============================================================================

.PHONY: monitoring-on
monitoring-on: ## Enable skill usage logging (sets monitoring.enabled: true in alhazen.yaml)
	@python3 -c "import re; p='alhazen.yaml'; c=open(p).read(); c=re.sub(r'(monitoring:.*?\n\s*enabled:)\s*false',r'\1 true',c,flags=re.DOTALL); open(p,'w').write(c); print('Monitoring enabled in alhazen.yaml')"

.PHONY: monitoring-off
monitoring-off: ## Disable skill usage logging (sets monitoring.enabled: false in alhazen.yaml)
	@python3 -c "import re; p='alhazen.yaml'; c=open(p).read(); c=re.sub(r'(monitoring:.*?\n\s*enabled:)\s*true',r'\1 false',c,flags=re.DOTALL); open(p,'w').write(c); print('Monitoring disabled in alhazen.yaml')"

define SKILLS_LIST_PY
import sys
from pathlib import Path
try:
    import yaml
except ImportError:
    print("PyYAML not available — install with: uv sync"); sys.exit(1)
GREEN = '\033[32m'; YELLOW = '\033[33m'; BLUE = '\033[34m'; MAGENTA = '\033[35m'; NC = '\033[0m'
reg = Path('skills-registry.yaml')
if not reg.exists():
    print("No skills-registry.yaml found"); sys.exit(0)
cfg = yaml.safe_load(reg.read_text()) or {}
skills = list(cfg.get('skills') or [])
local_reg = Path('skills-registry-local.yaml')
if local_reg.exists():
    local_cfg = yaml.safe_load(local_reg.read_text()) or {}
    for s in local_cfg.get('skills') or []:
        s['_local'] = True
        skills.append(s)
print(f"{BLUE}Skills (from skills-registry.yaml + skills-registry-local.yaml):{NC}")
print("=" * 62)
for skill in skills:
    name = skill['name']
    is_local = skill.get('_local', False)
    kind = 'local' if is_local else ('core' if 'path' in skill else 'external')
    color = MAGENTA if is_local else (GREEN if kind == 'core' else YELLOW)
    resolved = Path('local_skills') / name
    desc = ''
    for candidate in [resolved / 'SKILL.md', resolved / 'skill.yaml']:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                if line.startswith('description:'):
                    desc = line.split(':', 1)[1].strip().strip('"')
                    break
            if desc: break
    status = 'ok' if resolved.exists() else 'run make build-skills'
    print(f"  {color}{name:<20}{NC} {desc}  {BLUE}[{kind}]{NC}  {status}")
endef
export SKILLS_LIST_PY

.PHONY: skills-list
skills-list: ## Show all skills from skills-registry.yaml (run 'make build-skills' first to resolve)
	@uv run python -c "$$SKILLS_LIST_PY"

.PHONY: skills-validate
skills-validate: ## Validate all resolved skills have SKILL.md with name: field
	@echo "$(BLUE)Validating skills (run 'make build-skills' first)...$(NC)"
	@valid=true; \
	for skill_dir in $(LOCAL_SKILLS_DIR)/*/; do \
		[ -d "$$skill_dir" ] || continue; \
		skill_name=$$(basename $$skill_dir); \
		skill_md=$$skill_dir/SKILL.md; \
		echo "$(BLUE)→ Validating $$skill_name$(NC)"; \
		if [ ! -f "$$skill_md" ]; then \
			echo "$(RED)  ✗ Missing SKILL.md$(NC)"; valid=false; continue; \
		fi; \
		md_name=$$(grep '^name:' $$skill_md | head -1 | sed 's/name:[[:space:]]*//'); \
		if [ -z "$$md_name" ]; then \
			echo "$(RED)  ✗ Missing name: in SKILL.md$(NC)"; valid=false; \
		elif [ "$$md_name" != "$$skill_name" ]; then \
			echo "$(RED)  ✗ Name mismatch: dir='$$skill_name' SKILL.md='$$md_name'$(NC)"; valid=false; \
		else \
			echo "$(GREEN)  ✓ Valid$(NC)"; \
		fi; \
	done; \
	if [ "$$valid" = "true" ]; then \
		echo "$(GREEN)✓ All skills valid$(NC)"; \
	else \
		echo "$(RED)✗ Validation failed$(NC)"; exit 1; \
	fi

define SKILLS_INSTALL_PY
import os, subprocess, sys, shutil
from pathlib import Path
import yaml
registry = Path('skills-registry.yaml')
if not registry.exists():
    print('No skills-registry.yaml found'); sys.exit(0)
cfg = yaml.safe_load(registry.read_text()) or {}
defaults = cfg.get('defaults') or {}
# Allow env var or make-var override of the skill library URL
skill_library = os.environ.get('ALHAZEN_SKILL_LIBRARY') or defaults.get('git', '')
default_ref = defaults.get('ref', 'main')
skills = list(cfg.get('skills') or [])
# Merge local registry if present (private/client skills not committed to git)
local_reg = Path('skills-registry-local.yaml')
if local_reg.exists():
    local_cfg = yaml.safe_load(local_reg.read_text()) or {}
    skills.extend(local_cfg.get('skills') or [])
if not skills:
    print('No skills registered in skills-registry.yaml'); sys.exit(0)
local_skills = Path('local_skills'); local_skills.mkdir(exist_ok=True)
for skill in skills:
    name = skill['name']
    target = local_skills / name
    if 'path' in skill:
        # Path skill: absolute paths symlink directly; relative paths get ../ prefix
        src = Path(skill['path'])
        if target.is_symlink():
            target.unlink()
        elif target.exists():
            print(f'  Skipping {name} (real directory exists at local_skills/{name})'); continue
        link_target = str(src) if src.is_absolute() else f'../{src}'
        target.symlink_to(link_target)
        kind = 'local' if src.is_absolute() else 'core'
        print(f'  ✓ Linked ({kind}): {name}')
        continue
    # External skill: clone from git
    git_url = skill.get('git') or skill_library
    ref = skill.get('ref') or default_ref
    subdir = skill.get('subdir', '.')
    if not git_url:
        print(f'  ✗ No git URL for {name} and no defaults.git set', file=sys.stderr); continue
    if target.exists() and not target.is_symlink():
        print(f'  Skipping {name} (already installed -- run make skills-update to refresh)'); continue
    if target.is_symlink():
        target.unlink()
    print(f'  Installing {name} from {git_url}@{ref}...')
    tmp = local_skills / f'_tmp_{name}'
    try:
        subprocess.run(['git', 'clone', '--depth=1', '--branch', ref, git_url, str(tmp)], check=True, capture_output=True)
        src = tmp / subdir if subdir != '.' else tmp; src.rename(target)
        print(f'  ✓ Installed {name}')
    except subprocess.CalledProcessError as e:
        print(f'  ✗ Failed to install {name}: {e}', file=sys.stderr)
    finally:
        if tmp.exists(): shutil.rmtree(tmp, ignore_errors=True)
endef
export SKILLS_INSTALL_PY

define SKILLS_UPDATE_PY
import os, subprocess, sys, shutil
from pathlib import Path
import yaml
registry = Path('skills-registry.yaml')
if not registry.exists():
    print('No skills-registry.yaml found'); sys.exit(0)
cfg = yaml.safe_load(registry.read_text()) or {}
defaults = cfg.get('defaults') or {}
skill_library = os.environ.get('ALHAZEN_SKILL_LIBRARY') or defaults.get('git', '')
default_ref = defaults.get('ref', 'main')
skills = list(cfg.get('skills') or [])
# Merge local registry if present (private/client skills not committed to git)
local_reg = Path('skills-registry-local.yaml')
if local_reg.exists():
    local_cfg = yaml.safe_load(local_reg.read_text()) or {}
    skills.extend(local_cfg.get('skills') or [])
if not skills:
    print('No skills registered'); sys.exit(0)
local_skills = Path('local_skills'); local_skills.mkdir(exist_ok=True)
for skill in skills:
    name = skill['name']
    target = local_skills / name
    if 'path' in skill:
        # Path skill: re-link (absolute paths symlink directly; relative get ../ prefix)
        src = Path(skill['path'])
        if target.is_symlink(): target.unlink()
        elif target.exists(): shutil.rmtree(target)
        link_target = str(src) if src.is_absolute() else f'../{src}'
        target.symlink_to(link_target)
        kind = 'local' if src.is_absolute() else 'core'
        print(f'  ✓ Re-linked ({kind}): {name}')
        continue
    # External skill: re-clone from git
    git_url = skill.get('git') or skill_library
    ref = skill.get('ref') or default_ref
    subdir = skill.get('subdir', '.')
    if not git_url:
        print(f'  ✗ No git URL for {name} and no defaults.git set', file=sys.stderr); continue
    print(f'  Updating {name}...')
    if target.is_symlink(): target.unlink()
    elif target.exists(): shutil.rmtree(target)
    tmp = local_skills / f'_tmp_{name}'
    try:
        subprocess.run(['git', 'clone', '--depth=1', '--branch', ref, git_url, str(tmp)], check=True, capture_output=True)
        src = tmp / subdir if subdir != '.' else tmp
        if not src.exists():
            print(f'  ✗ Subdir not found in {name} clone: {subdir}', file=sys.stderr)
        else:
            src.rename(target)
            print(f'  ✓ Updated {name}')
    except subprocess.CalledProcessError as e:
        print(f'  ✗ Failed to clone {name}: {e}', file=sys.stderr)
    except Exception as e:
        print(f'  ✗ Failed to install {name}: {e}', file=sys.stderr)
    finally:
        if tmp.exists(): shutil.rmtree(tmp, ignore_errors=True)
endef
export SKILLS_UPDATE_PY

.PHONY: skills-install
skills-install: ## Resolve skills-registry.yaml into local_skills/ (path: symlinks, git: clones)
	@echo "$(BLUE)Resolving skills from registry...$(NC)"
	@$(if $(SKILL_LIBRARY),ALHAZEN_SKILL_LIBRARY=$(SKILL_LIBRARY)) uv run python -c "$$SKILLS_INSTALL_PY"
	@echo "$(GREEN)✓ Skills resolved to local_skills/$(NC)"

.PHONY: skills-update
skills-update: ## Re-resolve all skills from registry (re-links core, re-clones external) and redeploy
	@echo "$(BLUE)Updating all skills...$(NC)"
	@$(if $(SKILL_LIBRARY),ALHAZEN_SKILL_LIBRARY=$(SKILL_LIBRARY)) uv run python -c "$$SKILLS_UPDATE_PY"
	$(MAKE) --no-print-directory deploy-claude
	@echo "$(GREEN)✓ All skills updated$(NC)"

.PHONY: skills-sync
skills-sync: ## [deprecated] Skills are now self-contained — metadata lives in skill.yaml/SKILL.md
	@echo "$(YELLOW)skills-sync is no longer needed: each skill is its own source of truth.$(NC)"
	@echo "$(YELLOW)Edit skills/*/SKILL.md (core) or local_skills/*/SKILL.md (external) directly.$(NC)"

# =============================================================================
# Skill Observability
# =============================================================================

SKILL_LOGGER := $(PROJECT_ROOT)/local_resources/skilllog/skill_logger.py

.PHONY: skills-token-report
skills-token-report: ## Show token usage summary across all logged skill invocations
	uv run python $(SKILL_LOGGER) token-report

.PHONY: skills-token-report-skill
skills-token-report-skill: ## Show token usage for a specific skill (requires SKILL=name)
ifndef SKILL
	@echo "$(RED)Error: SKILL variable required. Usage: make skills-token-report-skill SKILL=jobhunt$(NC)"
	@exit 1
endif
	uv run python $(SKILL_LOGGER) token-report --skill $(SKILL)

.PHONY: skills-invocations
skills-invocations: ## List recent skill invocations (use SKILL=name to filter)
	@if [ -n "$(SKILL)" ]; then \
		uv run python $(SKILL_LOGGER) list-invocations --skill $(SKILL); \
	else \
		uv run python $(SKILL_LOGGER) list-invocations; \
	fi

# =============================================================================
# Dashboard
# =============================================================================

DASHBOARD_DIR := $(PROJECT_ROOT)/dashboard

.PHONY: dashboard-dev
dashboard-dev: ## Start the Next.js dashboard in development mode (http://localhost:3000)
	@echo "$(BLUE)Starting dashboard in development mode...$(NC)"
	@if [ ! -d "$(DASHBOARD_DIR)/node_modules" ]; then \
		echo "$(YELLOW)Installing dashboard dependencies...$(NC)"; \
		cd $(DASHBOARD_DIR) && npm install; \
	fi
	cd $(DASHBOARD_DIR) && npm run dev

.PHONY: dashboard-build
dashboard-build: ## Build the Next.js dashboard for production
	@echo "$(BLUE)Building dashboard...$(NC)"
	@if [ ! -d "$(DASHBOARD_DIR)/node_modules" ]; then \
		echo "$(YELLOW)Installing dashboard dependencies...$(NC)"; \
		cd $(DASHBOARD_DIR) && npm install; \
	fi
	cd $(DASHBOARD_DIR) && ./node_modules/.bin/next build
	@echo "$(GREEN)✓ Dashboard built$(NC)"

.PHONY: dashboard-skills
dashboard-skills: ## List skills that have dashboards (from YAML manifests)
	@echo "$(BLUE)Skills with dashboards:$(NC)"
	@echo "======================"
	@for skill_yaml in $(SKILLS_MANIFEST_DIR)/*.yaml; do \
		skill_name=$$(basename $$skill_yaml .yaml); \
		if grep -q '^dashboard:' $$skill_yaml 2>/dev/null; then \
			enabled=$$(awk '/^dashboard:/{f=1} f && /enabled:/{print $$2; f=0}' $$skill_yaml); \
			if [ "$$enabled" = "true" ]; then \
				url_path=$$(awk '/^dashboard:/{f=1} f && /url_path:/{gsub(/"/, "", $$2); print $$2; f=0}' $$skill_yaml); \
				printf "$(GREEN)%-20s$(NC) http://localhost:3000%s\n" "$$skill_name" "$$url_path"; \
			fi; \
		fi; \
	done

# =============================================================================
# Development
# =============================================================================

.PHONY: test
test: ## Run tests
	@echo "$(BLUE)Running tests...$(NC)"
	uv run pytest tests/ -v
	@echo "$(GREEN)✓ Tests completed$(NC)"

.PHONY: lint
lint: ## Run ruff linter
	@echo "$(BLUE)Running linter...$(NC)"
	uv run ruff check .
	uv run ruff format --check .
	@echo "$(GREEN)✓ Linting completed$(NC)"

WIKI_DIR ?= $(HOME)/Documents/Coding/skillful-alhazen.wiki

.PHONY: docs-typedb
docs-typedb: ## Regenerate TypeDB 3.x reference docs from typedb-docs repo (needs /tmp/typedb-docs)
	@echo "$(BLUE)Regenerating TypeDB 3.x reference documentation...$(NC)"
	@if [ ! -d /tmp/typedb-docs ]; then \
		echo "$(YELLOW)Cloning typedb-docs repo...$(NC)"; \
		git clone --depth=1 --branch 3.x-development https://github.com/typedb/typedb-docs /tmp/typedb-docs; \
	fi
	uv run python scripts/build_typedb_docs.py
	@echo "$(GREEN)✓ TypeDB 3.x reference docs generated in local_resources/typedb/$(NC)"

.PHONY: docs-schema
docs-schema: ## Generate TypeDB schema documentation (Markdown + Mermaid)
	@echo "$(BLUE)Generating schema documentation...$(NC)"
	uv run python $(TYPEDB_SCHEMAS_DIR)/generate_schema_docs.py
	@echo "$(GREEN)✓ Schema docs generated in local_resources/typedb/docs/$(NC)"

.PHONY: docs-schema-wiki
docs-schema-wiki: ## Generate schema docs + copy to wiki
	@echo "$(BLUE)Generating schema documentation + wiki pages...$(NC)"
	uv run python $(TYPEDB_SCHEMAS_DIR)/generate_schema_docs.py --wiki "$(WIKI_DIR)"
	@echo "$(GREEN)✓ Schema docs generated in local_resources/typedb/docs/ and wiki$(NC)"

.PHONY: clean-dashboard
clean-dashboard: ## Remove all generated skill dashboard wiring from dashboard/src/
	@echo "$(BLUE)Cleaning dashboard skill wiring...$(NC)"
	@while IFS= read -r d; do \
	  echo "  Removing route group: $$d"; rm -rf "$$d"; \
	done < <(find dashboard/src/app -maxdepth 1 -mindepth 1 -name '(*' 2>/dev/null)
	@while IFS= read -r d; do \
	  [ "$$(basename "$$d")" = "typedb-status" ] && continue; \
	  echo "  Removing API route: $$d"; rm -rf "$$d"; \
	done < <(find dashboard/src/app/api -maxdepth 1 -mindepth 1 2>/dev/null)
	@while IFS= read -r d; do \
	  [ "$$(basename "$$d")" = "ui" ] && continue; \
	  echo "  Removing component dir: $$d"; rm -rf "$$d"; \
	done < <(find dashboard/src/components -maxdepth 1 -mindepth 1 2>/dev/null)
	@for f in dashboard/src/lib/*.ts; do \
	  [ -f "$$f" ] || [ -L "$$f" ] || continue; \
	  [ "$$(basename $$f)" = "utils.ts" ] && continue; \
	  echo "  Removing lib file: $$f"; \
	  rm -f "$$f"; \
	done
	@echo "$(GREEN)✓ Dashboard skill wiring cleaned$(NC)"

.PHONY: clean
clean: clean-dashboard ## Clean generated files and skill dashboard wiring
	@echo "$(BLUE)Cleaning generated files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

# =============================================================================
# Tailscale (Remote Access)
# =============================================================================

.PHONY: tailscale-serve
tailscale-serve: ## Expose dashboard over HTTPS on Tailscale network
	@echo "$(BLUE)Starting Tailscale Serve (HTTPS)...$(NC)"
	@if ! command -v tailscale &>/dev/null; then \
		echo "$(RED)✗ Tailscale not installed. Run: $(PKG_INSTALL_HINT) tailscale$(NC)"; \
		exit 1; \
	fi
	@if ! tailscale status &>/dev/null; then \
		echo "$(RED)✗ Tailscale not running. Start it first.$(NC)"; \
		exit 1; \
	fi
	tailscale serve --bg --https 3001 http://127.0.0.1:3001
	@echo
	@TSNAME=$$(tailscale status --json 2>/dev/null | grep -o '"DNSName":"[^"]*"' | head -1 | sed 's/"DNSName":"//;s/\."$$//'); \
	echo "$(GREEN)✓ Tailscale Serve running (HTTPS)$(NC)"; \
	echo "  Dashboard: https://$$TSNAME:3001"

.PHONY: tailscale-stop
tailscale-stop: ## Stop Tailscale Serve proxies
	@echo "$(BLUE)Stopping Tailscale Serve...$(NC)"
	tailscale serve --https 3001 off 2>/dev/null || true
	tailscale serve --http 3001 off 2>/dev/null || true
	@echo "$(GREEN)✓ Tailscale Serve stopped$(NC)"

.PHONY: tailscale-status
tailscale-status: ## Show Tailscale Serve configuration
	@if command -v tailscale &>/dev/null && tailscale status &>/dev/null; then \
		tailscale serve status; \
		echo; \
		TSIP=$$(tailscale ip -4 2>/dev/null); \
		echo "$(GREEN)Tailscale IP:$(NC) $$TSIP"; \
	else \
		echo "$(RED)Tailscale not running$(NC)"; \
	fi

# =============================================================================
# Utility Targets
# =============================================================================

.PHONY: status
status: ## Show project status
	@echo "$(BLUE)Skillful Alhazen Project Status$(NC)"
	@echo "==============================="
	@echo
	@echo "$(GREEN)Project Directory:$(NC) $(PROJECT_ROOT)"
	@echo "$(GREEN)Python Environment:$(NC) $$(uv run python --version)"
	@echo
	@echo "$(GREEN)TypeDB Status:$(NC)"
	@if docker ps --filter "name=$(TYPEDB_CONTAINER)" --filter "status=running" | grep -q $(TYPEDB_CONTAINER); then \
		echo "  $(GREEN)✓ Running$(NC)"; \
		echo "  $(GREEN)Container:$(NC) $(TYPEDB_CONTAINER)"; \
		echo "  $(GREEN)Database:$(NC) $(TYPEDB_DATABASE)"; \
	else \
		echo "  $(RED)✗ Not running$(NC)"; \
	fi
	@echo
	@echo "$(GREEN)Skills Deployment:$(NC)"
	@echo "  $(GREEN)Claude Code:$(NC) $$(ls -1 $(CLAUDE_SKILLS_DIR) 2>/dev/null | grep -v _template | wc -l | tr -d ' ') skills"
	@if [ -d "$(OPENCLAW_SKILLS_DIR)" ]; then \
		echo "  $(GREEN)OpenClaw:$(NC) $$(ls -1 $(OPENCLAW_SKILLS_DIR) 2>/dev/null | wc -l | tr -d ' ') skills (symlinked)"; \
	else \
		echo "  $(GREEN)OpenClaw:$(NC) $(YELLOW)Not deployed$(NC)"; \
	fi

.PHONY: info
info: status ## Alias for status

# =============================================================================
# Deployment
# =============================================================================

DEPLOY_ENV := $(PROJECT_ROOT)/deploy/deploy.env

.PHONY: deploy-vps
deploy-vps: ## Deploy to VPS using deploy/deploy.env (Podman rootless, full hardening)
	@[ -f $(DEPLOY_ENV) ] || { echo "$(RED)✗ Missing deploy/deploy.env — copy deploy/deploy.env.example$(NC)"; exit 1; }
	@echo "$(BLUE)Launching VPS deployment...$(NC)"
	@set -a && . $(DEPLOY_ENV) && set +a && \
	  cd $(PROJECT_ROOT)/deploy && bash deploy.sh \
	    $${DEPLOY_TARGET:+-t "$$DEPLOY_TARGET"} \
	    $${DEPLOY_TARGET_TYPE:+--target-type "$$DEPLOY_TARGET_TYPE"} \
	    $${DEPLOY_PROVIDER:+-p "$$DEPLOY_PROVIDER"} \
	    $${DEPLOY_MODEL:+-m "$$DEPLOY_MODEL"} \
	    $${DEPLOY_API_KEY:+-k "$$DEPLOY_API_KEY"} \
	    $${DEPLOY_BRANCH:+--branch "$$DEPLOY_BRANCH"} \
	    $${DEPLOY_TELEGRAM_TOKEN:+--telegram-token "$$DEPLOY_TELEGRAM_TOKEN"} \
	    $${DEPLOY_TELEGRAM_USER:+--telegram-user "$$DEPLOY_TELEGRAM_USER"} \
	    $${DEPLOY_SSH_USER:+--ssh-user "$$DEPLOY_SSH_USER"} \
	    $${DEPLOY_SSH_KEY:+--ssh-key "$$DEPLOY_SSH_KEY"} \
	    $$([ "$${DEPLOY_ASK_PASS}" = "true" ] && echo --ask-pass || true)

.PHONY: deploy-macmini
deploy-macmini: ## Deploy to Mac Mini using deploy/deploy.env (Docker Desktop, pf firewall)
	@[ -f $(DEPLOY_ENV) ] || { echo "$(RED)✗ Missing deploy/deploy.env — copy deploy/deploy.env.example$(NC)"; exit 1; }
	@echo "$(BLUE)Launching Mac Mini deployment...$(NC)"
	@set -a && . $(DEPLOY_ENV) && set +a && \
	  cd $(PROJECT_ROOT)/deploy && bash deploy.sh \
	    $${DEPLOY_TARGET:+-t "$$DEPLOY_TARGET"} \
	    $${DEPLOY_TARGET_TYPE:+--target-type "$$DEPLOY_TARGET_TYPE"} \
	    $${DEPLOY_PROVIDER:+-p "$$DEPLOY_PROVIDER"} \
	    $${DEPLOY_MODEL:+-m "$$DEPLOY_MODEL"} \
	    $${DEPLOY_API_KEY:+-k "$$DEPLOY_API_KEY"} \
	    $${DEPLOY_BRANCH:+--branch "$$DEPLOY_BRANCH"} \
	    $${DEPLOY_TELEGRAM_TOKEN:+--telegram-token "$$DEPLOY_TELEGRAM_TOKEN"} \
	    $${DEPLOY_TELEGRAM_USER:+--telegram-user "$$DEPLOY_TELEGRAM_USER"} \
	    $${DEPLOY_SSH_USER:+--ssh-user "$$DEPLOY_SSH_USER"} \
	    $${DEPLOY_SSH_KEY:+--ssh-key "$$DEPLOY_SSH_KEY"} \
	    $$([ "$${DEPLOY_ASK_PASS}" = "true" ] && echo --ask-pass || true)

.PHONY: deploy-status
deploy-status: ## Check deployment status on remote
	@echo "$(BLUE)Checking deployment status...$(NC)"
	@if [ -z "$(TARGET)" ]; then \
		echo "$(RED)Error: TARGET variable required. Usage: make deploy-status TARGET=<ip>$(NC)"; \
		exit 1; \
	fi
	@ssh $(TARGET) "docker ps -a 2>/dev/null || podman ps -a 2>/dev/null" || echo "$(RED)Could not connect to $(TARGET)$(NC)"

OPENCLAW_PLISTS := \
	/Library/LaunchDaemons/com.alhazen.openclaw.plist \
	/Library/LaunchDaemons/ai.openclaw.gateway.plist \
	/Library/LaunchDaemons/com.alhazen.litellm.plist \
	/Library/LaunchDaemons/com.alhazen.mcp.plist \
	/Library/LaunchDaemons/com.openclaw.monitor.plist \
	/Library/LaunchDaemons/com.openclaw.pf.plist

.PHONY: openclaw-stop
openclaw-stop: ## Stop all OpenClaw launchd services (requires sudo)
	@echo "$(BLUE)Stopping OpenClaw services...$(NC)"
	@for plist in $(OPENCLAW_PLISTS); do \
		if [ -f "$$plist" ]; then \
			echo "  Unloading $$plist"; \
			sudo launchctl unload "$$plist" 2>/dev/null || true; \
		fi; \
	done
	@echo "$(GREEN)✓ OpenClaw services stopped$(NC)"

.PHONY: openclaw-start
openclaw-start: ## Start all OpenClaw launchd services (requires sudo)
	@echo "$(BLUE)Starting OpenClaw services...$(NC)"
	@for plist in $(OPENCLAW_PLISTS); do \
		if [ -f "$$plist" ]; then \
			echo "  Loading $$plist"; \
			sudo launchctl load "$$plist"; \
		fi; \
	done
	@echo "$(GREEN)✓ OpenClaw services started$(NC)"

# Default target
.DEFAULT_GOAL := help
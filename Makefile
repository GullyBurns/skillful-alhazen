# Makefile for Skillful Alhazen Repository
# Comprehensive skill portability and project management

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
SKILLS_MANIFEST_DIR := $(PROJECT_ROOT)/local_resources/skills
TYPEDB_SCHEMAS_DIR := $(PROJECT_ROOT)/local_resources/typedb

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
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(deploy|skills)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo
	@echo "$(GREEN)Database Management:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E 'db-' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo
	@echo "$(GREEN)Remote Access:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E 'tailscale' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo
	@echo "$(GREEN)Development:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(test|lint|clean)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

# =============================================================================
# Setup
# =============================================================================

.PHONY: setup
setup: setup-python setup-typedb ## Install Python deps, start TypeDB, init database
	@echo "$(GREEN)✓ Setup complete!$(NC)"

.PHONY: setup-python
setup-python: ## Install Python dependencies
	@echo "$(BLUE)Installing Python dependencies...$(NC)"
	uv sync --all-extras
	@echo "$(GREEN)✓ Python dependencies installed$(NC)"

.PHONY: setup-typedb
setup-typedb: db-start db-init ## Start TypeDB and initialize database
	@echo "$(GREEN)✓ TypeDB setup complete$(NC)"

# =============================================================================
# Database Management
# =============================================================================

.PHONY: db-start
db-start: ## Start TypeDB container
	@echo "$(BLUE)Starting TypeDB container...$(NC)"
	docker compose -f docker-compose-typedb.yml up -d
	@echo "$(BLUE)Waiting for TypeDB to be ready...$(NC)"
	@for i in {1..30}; do \
		if docker exec $(TYPEDB_CONTAINER) /opt/typedb-all-linux-x86_64/typedb console --server=localhost:1729 <<< 'exit' 2>/dev/null; then \
			echo "$(GREEN)✓ TypeDB is ready$(NC)"; \
			break; \
		fi; \
		sleep 2; \
		if [ $$i -eq 30 ]; then \
			echo "$(RED)✗ TypeDB failed to start within 60 seconds$(NC)"; \
			exit 1; \
		fi; \
	done

.PHONY: db-stop
db-stop: ## Stop TypeDB container
	@echo "$(BLUE)Stopping TypeDB container...$(NC)"
	docker compose -f docker-compose-typedb.yml down
	@echo "$(GREEN)✓ TypeDB stopped$(NC)"

.PHONY: db-init
db-init: ## Create database and load schemas
	@echo "$(BLUE)Initializing TypeDB database...$(NC)"
	@echo "$(BLUE)Creating database: $(TYPEDB_DATABASE)$(NC)"
	docker exec -i $(TYPEDB_CONTAINER) /opt/typedb-all-linux-x86_64/typedb console --server=localhost:1729 << 'EOF' || true
	database create $(TYPEDB_DATABASE)
	exit
	EOF
	@echo "$(BLUE)Loading core schema...$(NC)"
	docker exec -i $(TYPEDB_CONTAINER) /opt/typedb-all-linux-x86_64/typedb console --server=localhost:1729 << 'EOF'
	transaction $(TYPEDB_DATABASE) schema write
	source /schema/alhazen_notebook.tql
	commit
	exit
	EOF
	@echo "$(BLUE)Loading namespace schemas...$(NC)"
	@for schema in $(TYPEDB_SCHEMAS_DIR)/namespaces/*.tql; do \
		schema_name=$$(basename $$schema); \
		echo "$(BLUE)Loading $$schema_name...$(NC)"; \
		docker exec -i $(TYPEDB_CONTAINER) /opt/typedb-all-linux-x86_64/typedb console --server=localhost:1729 << EOF || true; \
		transaction $(TYPEDB_DATABASE) schema write; \
		source /schema/namespaces/$$schema_name; \
		commit; \
		exit; \
		EOF \
	done
	@echo "$(GREEN)✓ Database initialized$(NC)"

.PHONY: db-export
db-export: ## Export database to timestamped zip
	@echo "$(BLUE)Exporting database...$(NC)"
	uv run python $(CLAUDE_SKILLS_DIR)/typedb-notebook/typedb_notebook.py export-db --database $(TYPEDB_DATABASE)
	@echo "$(GREEN)✓ Database exported$(NC)"

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

.PHONY: deploy-claude
deploy-claude: ## Copy/update skills to .claude/skills/ (for Claude Code)
	@echo "$(BLUE)Deploying skills to Claude Code...$(NC)"
	@if [ -d "$(CLAUDE_SKILLS_DIR)" ]; then \
		echo "$(GREEN)✓ Skills already exist in .claude/skills/$(NC)"; \
		echo "$(YELLOW)→ Run 'make skills-sync' to update metadata$(NC)"; \
	else \
		echo "$(RED)✗ No skills found in .claude/skills/$(NC)"; \
		echo "$(YELLOW)→ Skills should be committed in the repository$(NC)"; \
		exit 1; \
	fi

.PHONY: deploy-openclaw
deploy-openclaw: ## Symlink skills to OpenClaw + configure
	@echo "$(BLUE)Deploying skills to OpenClaw...$(NC)"
	
	# Create OpenClaw skills directory if it doesn't exist
	@mkdir -p $(OPENCLAW_SKILLS_DIR)
	
	# Create symlinks for each skill
	@for skill_dir in $(CLAUDE_SKILLS_DIR)/*/; do \
		if [ -d "$$skill_dir" ] && [ "$$(basename $$skill_dir)" != "_template" ]; then \
			skill_name=$$(basename $$skill_dir); \
			target_dir=$(OPENCLAW_SKILLS_DIR)/$$skill_name; \
			if [ -L "$$target_dir" ]; then \
				echo "$(YELLOW)→ Updating symlink: $$skill_name$(NC)"; \
				rm "$$target_dir"; \
			elif [ -d "$$target_dir" ]; then \
				echo "$(YELLOW)→ Replacing directory with symlink: $$skill_name$(NC)"; \
				rm -rf "$$target_dir"; \
			else \
				echo "$(BLUE)→ Creating symlink: $$skill_name$(NC)"; \
			fi; \
			ln -s "$$skill_dir" "$$target_dir"; \
		fi; \
	done
	
	# Generate OpenClaw configuration patch
	@echo "$(BLUE)Generating OpenClaw configuration...$(NC)"
	@echo "$(YELLOW)Add the following to your $(OPENCLAW_CONFIG):$(NC)"
	@echo
	@echo "{"
	@echo "  \"skills\": {"
	@echo "    \"entries\": {"
	@for skill_yaml in $(SKILLS_MANIFEST_DIR)/*.yaml; do \
		skill_name=$$(basename $$skill_yaml .yaml); \
		echo "      \"$$skill_name\": {"; \
		echo "        \"env\": {"; \
		echo "          \"ALHAZEN_PROJECT_ROOT\": \"$(PROJECT_ROOT)\""; \
		echo "        }"; \
		echo "      },"; \
	done
	@echo "    }"
	@echo "  }"
	@echo "}"
	@echo
	@echo "$(GREEN)✓ Skills symlinked to OpenClaw$(NC)"
	@echo "$(YELLOW)→ Manually apply the JSON configuration above$(NC)"

.PHONY: deploy-goose
deploy-goose: ## Generate MCP config for Goose (future implementation)
	@echo "$(YELLOW)Goose/MCP integration not yet implemented$(NC)"
	@echo "$(BLUE)Future: Will generate ~/.config/goose/profiles.yaml configuration$(NC)"

# =============================================================================
# Skill Management
# =============================================================================

.PHONY: skills-list
skills-list: ## Show all available skills
	@echo "$(BLUE)Available Skills:$(NC)"
	@echo "================"
	@for skill_yaml in $(SKILLS_MANIFEST_DIR)/*.yaml; do \
		skill_name=$$(basename $$skill_yaml .yaml); \
		description=$$(grep '^description:' $$skill_yaml | sed 's/description: *"//;s/"$$//'); \
		printf "$(GREEN)%-20s$(NC) %s\n" "$$skill_name" "$$description"; \
	done

.PHONY: skills-validate
skills-validate: ## Validate SKILL.md frontmatter
	@echo "$(BLUE)Validating skills...$(NC)"
	@valid=true; \
	for skill_yaml in $(SKILLS_MANIFEST_DIR)/*.yaml; do \
		skill_name=$$(basename $$skill_yaml .yaml); \
		skill_md=$(CLAUDE_SKILLS_DIR)/$$skill_name/SKILL.md; \
		echo "$(BLUE)→ Validating $$skill_name$(NC)"; \
		if [ ! -f "$$skill_md" ]; then \
			echo "$(RED)  ✗ Missing SKILL.md file$(NC)"; \
			valid=false; \
			continue; \
		fi; \
		yaml_name=$$(grep '^name:' $$skill_yaml | sed 's/name: *//'); \
		md_name=$$(grep '^name:' $$skill_md | sed 's/name: *//'); \
		if [ "$$yaml_name" != "$$md_name" ]; then \
			echo "$(RED)  ✗ Name mismatch: YAML='$$yaml_name' MD='$$md_name'$(NC)"; \
			valid=false; \
		else \
			echo "$(GREEN)  ✓ Valid$(NC)"; \
		fi; \
	done; \
	if [ "$$valid" = "true" ]; then \
		echo "$(GREEN)✓ All skills valid$(NC)"; \
	else \
		echo "$(RED)✗ Validation failed$(NC)"; \
		exit 1; \
	fi

.PHONY: skills-sync
skills-sync: ## Sync gold-standard metadata to deployed copies
	@echo "$(BLUE)Syncing skill metadata...$(NC)"
	@for skill_yaml in $(SKILLS_MANIFEST_DIR)/*.yaml; do \
		skill_name=$$(basename $$skill_yaml .yaml); \
		skill_md=$(CLAUDE_SKILLS_DIR)/$$skill_name/SKILL.md; \
		echo "$(BLUE)→ Syncing $$skill_name$(NC)"; \
		if [ ! -f "$$skill_md" ]; then \
			echo "$(RED)  ✗ SKILL.md not found$(NC)"; \
			continue; \
		fi; \
		name=$$(grep '^name:' $$skill_yaml | sed 's/name: *//'); \
		description=$$(grep '^description:' $$skill_yaml | sed 's/description: *"//;s/"$$//'); \
		license=$$(grep '^license:' $$skill_yaml | sed 's/license: *//'); \
		compatibility=$$(grep '^compatibility:' $$skill_yaml | sed 's/compatibility: *"//;s/"$$//'); \
		temp_file=$$(mktemp); \
		echo "---" > $$temp_file; \
		echo "name: $$name" >> $$temp_file; \
		echo "description: \"$$description\"" >> $$temp_file; \
		if [ -n "$$license" ]; then \
			echo "license: $$license" >> $$temp_file; \
		fi; \
		if [ -n "$$compatibility" ]; then \
			echo "compatibility: \"$$compatibility\"" >> $$temp_file; \
		fi; \
		echo "---" >> $$temp_file; \
		echo >> $$temp_file; \
		sed -n '/^---$$/,/^---$$/d; /^---$$/,$${/^---$$/d; p;}' $$skill_md >> $$temp_file; \
		mv $$temp_file $$skill_md; \
		echo "$(GREEN)  ✓ Updated$(NC)"; \
	done
	@echo "$(GREEN)✓ All skills synchronized$(NC)"

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

.PHONY: clean
clean: ## Clean generated files
	@echo "$(BLUE)Cleaning generated files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

# =============================================================================
# Tailscale (Remote Access)
# =============================================================================

.PHONY: tailscale-serve
tailscale-serve: ## Expose hub and dashboard over HTTPS on Tailscale network
	@echo "$(BLUE)Starting Tailscale Serve (HTTPS)...$(NC)"
	@if ! command -v tailscale &>/dev/null; then \
		echo "$(RED)✗ Tailscale not installed. Run: brew install tailscale$(NC)"; \
		exit 1; \
	fi
	@if ! tailscale status &>/dev/null; then \
		echo "$(RED)✗ Tailscale not running. Start it first.$(NC)"; \
		exit 1; \
	fi
	tailscale serve --bg --https 8080 http://127.0.0.1:8080
	tailscale serve --bg --https 3001 http://127.0.0.1:3001
	@echo
	@TSNAME=$$(tailscale status --json 2>/dev/null | grep -o '"DNSName":"[^"]*"' | head -1 | sed 's/"DNSName":"//;s/\."$$//'); \
	echo "$(GREEN)✓ Tailscale Serve running (HTTPS)$(NC)"; \
	echo "  Hub:       https://$$TSNAME:8080"; \
	echo "  Dashboard: https://$$TSNAME:3001"

.PHONY: tailscale-stop
tailscale-stop: ## Stop Tailscale Serve proxies
	@echo "$(BLUE)Stopping Tailscale Serve...$(NC)"
	tailscale serve --https 8080 off 2>/dev/null || true
	tailscale serve --https 3001 off 2>/dev/null || true
	tailscale serve --http 8080 off 2>/dev/null || true
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

# Default target
.DEFAULT_GOAL := help
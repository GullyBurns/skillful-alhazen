# Dashboard Dockerfile for Skillful-Alhazen
# Multi-stage build with Node.js + Python + uv for running skill scripts

# ==============================================================================
# Stage 1: Python base with uv
# ==============================================================================
FROM python:3.11-slim AS python-base
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# ==============================================================================
# Stage 2: Install Python dependencies
# ==============================================================================
FROM python-base AS python-deps
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
# Copy source for version detection (pyproject.toml uses dynamic version from __init__.py)
COPY src/skillful_alhazen/__init__.py ./src/skillful_alhazen/
RUN uv sync --extra typedb --extra skills --extra skilllog --no-dev

# ==============================================================================
# Stage 3: Node.js build
# ==============================================================================
FROM node:20-slim AS node-builder

# Work at project-root level so local_skills/ sits adjacent to dashboard/
WORKDIR /app

# Install dashboard dependencies first (better layer caching)
COPY dashboard/package*.json ./dashboard/
RUN cd dashboard && npm ci

# Copy dashboard source (host symlinks for skill dashboards are dangling in Docker;
# they'll be overwritten by ln -sfn below)
COPY dashboard/ ./dashboard/

# Copy skill dashboard code (only the small dashboard/ subdirs, not full repos)
COPY local_skills/jobhunt/dashboard/ ./local_skills/jobhunt/dashboard/
COPY local_skills/techrecon/dashboard/ ./local_skills/techrecon/dashboard/

# Wire skill dashboards using real file copies (symlinks crossing the project boundary
# cause ENOENT during Next.js build; cp avoids that entirely)
RUN mkdir -p dashboard/src/components dashboard/src/lib \
             dashboard/src/app dashboard/src/app/api && \
    for skill_dir in local_skills/*/; do \
      [ -d "${skill_dir}dashboard" ] || continue; \
      skill_name=$(basename $skill_dir); \
      if [ -d "${skill_dir}dashboard/components" ]; then \
        rm -rf "dashboard/src/components/${skill_name}"; \
        cp -r "${skill_dir}dashboard/components" "dashboard/src/components/${skill_name}"; \
      fi; \
      if [ -f "${skill_dir}dashboard/lib.ts" ]; then \
        rm -f "dashboard/src/lib/${skill_name}.ts"; \
        cp "${skill_dir}dashboard/lib.ts" "dashboard/src/lib/${skill_name}.ts"; \
      fi; \
      if [ -d "${skill_dir}dashboard/pages" ]; then \
        rm -rf "dashboard/src/app/(${skill_name})"; \
        cp -r "${skill_dir}dashboard/pages" "dashboard/src/app/(${skill_name})"; \
      fi; \
      if [ -d "${skill_dir}dashboard/routes" ]; then \
        rm -rf "dashboard/src/app/api/${skill_name}"; \
        cp -r "${skill_dir}dashboard/routes" "dashboard/src/app/api/${skill_name}"; \
      fi; \
    done

WORKDIR /app/dashboard
RUN npm run build

# ==============================================================================
# Stage 4: Final runtime
# ==============================================================================
FROM python:3.11-slim AS runner

# Install Node.js and curl (for uv)
RUN apt-get update && \
    apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy Python environment and project files
COPY --from=python-deps /app/.venv /app/.venv
COPY pyproject.toml uv.lock README.md ./
COPY src/skillful_alhazen/__init__.py ./src/skillful_alhazen/
# Copy skill scripts directly from real source paths (avoids .claude/skills/* symlinks)
COPY local_skills/jobhunt/jobhunt.py ./.claude/skills/jobhunt/
COPY local_skills/jobhunt/job_forager.py ./.claude/skills/jobhunt/
COPY skills/typedb-notebook/typedb_notebook.py ./.claude/skills/typedb-notebook/
COPY local_skills/techrecon/techrecon.py ./.claude/skills/techrecon/

# Copy Node.js build and dependencies
COPY --from=node-builder /app/dashboard/.next ./.next
COPY --from=node-builder /app/dashboard/public ./public
COPY --from=node-builder /app/dashboard/package*.json ./
COPY --from=node-builder /app/dashboard/node_modules ./node_modules

# Environment configuration
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PROJECT_ROOT=/app
ENV TYPEDB_HOST=typedb
ENV TYPEDB_PORT=1729
ENV TYPEDB_DATABASE=alhazen_notebook

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["npm", "start"]

# Dashboard Dockerfile for Skillful-Alhazen
# Multi-stage build with Node.js + Python + uv for running jobhunt.py

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
RUN uv sync --all-extras --no-dev

# ==============================================================================
# Stage 3: Node.js build
# ==============================================================================
FROM node:20-slim AS node-builder
WORKDIR /app/dashboard
COPY dashboard/package*.json ./
RUN npm ci
COPY dashboard/ ./
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
COPY pyproject.toml uv.lock ./
COPY .claude/skills/jobhunt/jobhunt.py ./.claude/skills/jobhunt/

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

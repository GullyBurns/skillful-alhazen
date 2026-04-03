# Claude Code Native Capabilities Reference

> Reference for skill authors: complete catalogue of Claude Code's built-in tools and slash
> commands, grouped by function. Use this to write skills that leverage native capabilities
> optimally rather than reimplementing what the harness already provides.

---

## TOOLS

Tools are callable actions Claude invokes during a turn. They appear in the tool list and
are called programmatically. Each tool has a dedicated implementation with permission checks,
UI rendering, and security validation built in.

---

### File System

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **Read** (FileReadTool) | Read file contents | Supports images (multimodal), PDFs (page ranges), Jupyter notebooks; `offset`/`limit` params for large files; returns line-numbered output |
| **Write** (FileWriteTool) | Write or overwrite a file | Requires prior Read if file exists; prefer Edit for partial changes |
| **Edit** (FileEditTool) | Exact string replacement in a file | Requires prior Read; `old_string` must be unique in file or use `replace_all`; preserves indentation |
| **Glob** (GlobTool) | File pattern matching across codebase | Supports `**/*.ext` globs; returns paths sorted by modification time; faster than Bash find |
| **Grep** (GrepTool) | Ripgrep-based content search | Full regex; `output_mode`: content/files_with_matches/count; `type` param for language filtering; `-A/-B/-C` context lines; `multiline` mode |

**When to prefer native file tools over Bash:**
- Reading: always use Read, not `cat`/`head`/`tail`
- Searching: always use Grep, not `grep`/`rg`; Glob not `find`/`ls`
- Editing: always use Edit, not `sed`/`awk`
- Creating: always use Write, not `echo >` or heredocs

---

### Code Execution

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **Bash** (BashTool) | Execute shell commands | Permission-gated for destructive operations; sandbox support on macOS; validates `sed` usage; command semantics analysis; read-only/path validation; working directory persists between calls but shell state does not |
| **PowerShell** (PowerShellTool) | Windows PowerShell execution | Parallel security layers to Bash; CLM type constraints; git safety checks; destructive command warnings |
| **REPL** (REPLTool) | Interactive language REPL | Primitive tools for stateful REPL sessions; for scripting languages needing persistent state |

**Bash security layers:** bashSecurity → destructiveCommandWarning → pathValidation →
modeValidation → readOnlyValidation → sedValidation → shouldUseSandbox

---

### Code Intelligence

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **LSP** (LSPTool) | Language Server Protocol queries | Symbol lookup, type info, go-to-definition, diagnostics formatting; `symbolContext` for enriched output; requires IDE integration active |

---

### Agent Orchestration

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **Agent** (AgentTool) | Launch specialized subagents | Built-in agent types below; supports `isolation: "worktree"` for isolated git branches; `run_in_background` for async; agents have full tool access unless restricted |
| **SendMessage** (SendMessageTool) | Send message to a running agent | Resumes agent by ID with full context preserved; use to continue previously spawned agents |
| **ToolSearch** (ToolSearchTool) | Fetch deferred tool schemas | Loads full parameter schemas for tools deferred at startup; required before calling deferred tools; use `select:ToolName` or keyword query |

**Built-in Agent types:**
- `general-purpose` — Research, multi-step tasks, broad codebase search; has access to all tools
- `Explore` — Fast codebase exploration; file patterns, keyword search, code structure questions; thoroughness levels: quick/medium/very thorough; read-only tools only
- `Plan` — Architecture and implementation planning; returns step-by-step plans; read-only tools only
- `claude-code-guide` — Claude Code feature questions, API/SDK usage, hooks, MCP, settings; use for "how do I" questions about the harness
- `superpowers:code-reviewer` — Post-implementation review against plan and coding standards
- `statusline-setup` — Configure Claude Code status line in settings.json

**Agent tool strategy:**
- Use multiple agents concurrently for independent tasks (single message, multiple Agent calls)
- Background agents: use `run_in_background: true` when you don't need results immediately
- Foreground agents: default; use when results are needed before proceeding
- Don't duplicate work subagents are already doing

---

### Task Management

Tasks are long-running background shell processes managed by the harness.

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **TaskCreate** | Create a background task | Returns task ID; task runs shell command asynchronously |
| **TaskGet** | Get task status and details | Check if completed/running/failed |
| **TaskList** | List all current tasks | Shows all tasks with status |
| **TaskUpdate** | Update task status | Set to in_progress, completed, blocked, etc. |
| **TaskStop** | Stop a running task | Sends termination signal |
| **TaskOutput** | Read task stdout/stderr | Retrieve output from background tasks |
| **TodoWrite** (TodoWriteTool) | Write/update todo list | Tracks work items in current session; visible in UI; use for multi-step task tracking |

---

### Planning & Mode Control

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **EnterPlanMode** (EnterPlanModeTool) | Enter plan/review mode | Disables code-executing tools; safe for planning discussions; user sees plan before any execution |
| **ExitPlanMode** (ExitPlanModeV2Tool) | Exit plan mode, approve execution | Re-enables execution tools; V2 variant is current |
| **EnterWorktree** (EnterWorktreeTool) | Create/enter isolated git worktree | Isolates changes from working directory; auto-cleaned if no changes made; useful for feature branches |
| **ExitWorktree** (ExitWorktreeTool) | Exit git worktree | Returns to main working directory |

---

### Web & External Data

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **WebFetch** (WebFetchTool) | Fetch URL content | Preapproved domain list; content conversion for HTML; use for docs, APIs, pages |
| **WebSearch** (WebSearchTool) | Search the web | Returns ranked results with snippets; good for current events, library docs |
| **Brief** (BriefTool) | Upload context/attachments | Uploads files to conversation context; multimodal attachments |

---

### MCP Integration

MCP (Model Context Protocol) extends Claude with external tool servers.

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **MCPTool** | Execute tools from MCP servers | Dynamic tool proxy; `classifyForCollapse` for UI grouping; tools appear prefixed with `mcp__<server>__` |
| **ListMcpResources** (ListMcpResourcesTool) | List resources from MCP servers | Resources are data endpoints (not tools) on MCP servers |
| **ReadMcpResource** (ReadMcpResourceTool) | Read a specific MCP resource | Fetch resource content by URI |
| **McpAuth** (McpAuthTool) | Authenticate with MCP servers | OAuth/token flow for protected MCP servers |

---

### Notebook

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **NotebookEdit** (NotebookEditTool) | Edit Jupyter notebook cells | Targeted cell editing; preserves notebook structure; use for `.ipynb` files |

---

### Scheduling

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **CronCreate** (CronCreateTool) | Create a scheduled cron job | Schedule recurring Claude tasks; cron expression syntax |
| **CronDelete** (CronDeleteTool) | Delete a cron job | By job ID |
| **CronList** (CronListTool) | List all scheduled jobs | Shows schedule, status, last run |

---

### Configuration

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **Config** (ConfigTool) | Read/write Claude Code settings | Reads and writes `settings.json`/`settings.local.json`; `supportedSettings` defines valid keys; use for model, theme, permissions, hooks, env vars |

---

### Skills

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **Skill** (SkillTool) | Invoke a named skill | Loads skill content and presents it; never use Read tool on skill files; use `skill: "name", args: "..."` |

---

### Interaction

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **AskUserQuestion** (AskUserQuestionTool) | Ask the user a clarifying question | Use when genuinely blocked by ambiguity; prefer this over making assumptions on irreversible actions |

---

### Utility

| Tool | Purpose | Key notes |
|------|---------|-----------|
| **Sleep** (SleepTool) | Wait for a duration | Use sparingly; avoid polling loops; prefer background tasks + notifications |
| **SyntheticOutput** (SyntheticOutputTool) | Emit structured/formatted output | Synthetic message injection for testing and formatting |
| **RemoteTrigger** (RemoteTriggerTool) | Trigger remote operations | Cross-machine action dispatch |
| **TeamCreate** (TeamCreateTool) | Create an agent team | Multi-agent team management |
| **TeamDelete** (TeamDeleteTool) | Delete an agent team | |

---

---

## COMMANDS

Commands are slash-invokable interactions (`/command`). They surface in the REPL UI and are
invoked by the user (not by Claude directly). Some have sub-commands. Skills can reference
these as things users can run, or can instruct Claude to suggest them.

---

### Session Management

| Command | Purpose | Notes |
|---------|---------|-------|
| `/clear` | Clear conversation history | Sub: `caches` (clear caches), `conversation` (clear history only) |
| `/compact` | Compact transcript | Summarizes history to reduce context window usage; use when context is getting large |
| `/resume` | Resume a previous session | List and select from saved sessions |
| `/exit` | Exit Claude Code | |
| `/rename` | Rename current session | Auto-generates descriptive name if no argument given |
| `/session` | Session info and management | View session metadata |
| `/rewind` | Rewind to earlier checkpoint | Undoes turns back to a selected point |
| `/tag` | Tag session | Bookmark for retrieval |
| `/summary` | Generate conversation summary | Produces a summary of what's been done |

---

### Git & Version Control

| Command | Purpose | Notes |
|---------|---------|-------|
| `/commit` | Create git commit | Staged changes; follows commit message conventions |
| `/commit-push-pr` | Commit + push + open PR | All-in-one git workflow; uses `gh` |
| `/branch` | Git branch operations | Create, switch, list branches |
| `/diff` | Show current git diff | Staged and unstaged changes |
| `/review` | Code review | Standard review; ultrareview variant for deep review (gated) |
| `/pr_comments` | Show PR review comments | Fetches comments from current PR |
| `/autofix-pr` | Auto-fix issues in a PR | Automated remediation of PR feedback |

---

### Model & Output Configuration

| Command | Purpose | Notes |
|---------|---------|-------|
| `/config` | Read/write settings | Direct settings.json access |
| `/model` | Switch AI model | Lists available models; switches active model |
| `/theme` | Change color theme | Light/dark/system + custom themes |
| `/color` | Color output settings | Fine-grained color controls |
| `/output-style` | Output formatting | markdown, plain, structured modes |
| `/effort` | Adjust thinking effort | Controls extended thinking budget |
| `/fast` | Toggle fast mode | Same model (Opus 4.6), faster output via streaming optimization |
| `/vim` | Toggle vim keybindings | Modal editing in REPL input |
| `/keybindings` | Configure keyboard shortcuts | Edit `~/.claude/keybindings.json`; chord bindings supported |

---

### Authentication & Permissions

| Command | Purpose | Notes |
|---------|---------|-------|
| `/login` | Authenticate | Anthropic OAuth or API key |
| `/logout` | Sign out | |
| `/permissions` | Manage tool permission rules | Allow/deny specific tools or prefixes; view current rules |
| `/privacy-settings` | Privacy configuration | Control telemetry, data sharing |
| `/rate-limit-options` | Configure rate limiting | Handle rate limit behavior |
| `/oauth-refresh` | Refresh OAuth tokens | Manual token refresh |

---

### Context & Files

| Command | Purpose | Notes |
|---------|---------|-------|
| `/add-dir` | Add directory to context | Includes additional dirs beyond CWD |
| `/files` | List/manage context files | View what's in active context |
| `/context` | Context window management | Usage info; sub: `context-noninteractive` for scripted use |
| `/copy` | Copy last output to clipboard | |
| `/export` | Export conversation | Save to file |
| `/brief` | Send context/attachments | Upload files to conversation |
| `/btw` | Add context note inline | "By the way" — inject context without breaking flow |

---

### Cost & Usage

| Command | Purpose | Notes |
|---------|---------|-------|
| `/cost` | Show session token cost | Current session spend |
| `/usage` | Show token usage | Input/output/cache token breakdown |
| `/extra-usage` | Detailed usage breakdown | Sub: `core`, `noninteractive`; per-tool breakdowns |
| `/stats` | Usage statistics | Historical usage patterns |
| `/insights` | Usage insights | Patterns and recommendations |

---

### Extensions & Plugins

| Command | Purpose | Notes |
|---------|---------|-------|
| `/mcp` | MCP server management | Add, list, connect, configure MCP servers; `xaaIdpCommand` for enterprise IdP |
| `/plugin` | Plugin management | Browse marketplace, install, configure, validate plugins; trust flow |
| `/hooks` | Manage automation hooks | Configure shell commands that fire on events (PreToolUse, PostToolUse, Stop, etc.) |
| `/reload-plugins` | Hot-reload plugins | Without restarting Claude Code |
| `/skills` | Skills management | List, view, manage installed skills |

---

### IDE & Integrations

| Command | Purpose | Notes |
|---------|---------|-------|
| `/ide` | IDE integration settings | Configure VS Code / Cursor / JetBrains extensions |
| `/desktop` | Desktop/GUI integration | Native app integration |
| `/mobile` | Mobile integration | Claude mobile app pairing |
| `/chrome` | Chrome DevTools integration | Browser debugging; network inspection |
| `/voice` | Voice input | Configure speech-to-text |
| `/terminalSetup` | Terminal configuration | Shell integration, completions, prompt |
| `/statusline` | Status line configuration | Customize the REPL status line display |

---

### Remote & Infrastructure

| Command | Purpose | Notes |
|---------|---------|-------|
| `/remote-setup` | Remote Claude Code wizard | Multi-step setup for remote/cloud execution |
| `/remote-env` | Configure remote environment | Environment variables for remote sessions |
| `/teleport` | Teleport-based remote connection | SSH via Teleport proxy |
| `/bridge` | Bridge to external models/services | Route to other AI services |
| `/bridge-kick` | Kick/reset bridge connection | |

---

### Agents & Planning

| Command | Purpose | Notes |
|---------|---------|-------|
| `/agents` | Manage agent instances | View running agents, their state |
| `/plan` | Enter plan mode | Structured planning before execution |
| `/ultraplan` | Extended deep planning | Enhanced planning with more analysis passes |
| `/advisor` | AI advisor mode | Meta-level recommendations about approach |
| `/tasks` | Task management UI | View/manage TaskCreate tasks |
| `/passes` | Review passes management | Configure multi-pass review workflows |

---

### Diagnostics & Debug

| Command | Purpose | Notes |
|---------|---------|-------|
| `/doctor` | Health check | Diagnoses auth, config, connectivity issues |
| `/heapdump` | Node.js memory heap dump | Debug memory leaks in the harness |
| `/debug-tool-call` | Debug a tool call | Inspect tool call input/output |
| `/status` | Connection and system status | API connectivity, active session info |
| `/ant-trace` | Anthropic internal tracing | Internal observability (Anthropic use) |
| `/ctx_viz` | Context visualization | Visual breakdown of context window |
| `/env` | Show environment variables | What's visible to the harness |
| `/thinkback` | Inspect prior thinking | View extended thinking from previous turns |
| `/thinkback-play` | Replay thinking | Replay thinking trace interactively |

---

### Setup & Onboarding

| Command | Purpose | Notes |
|---------|---------|-------|
| `/init` | Initialize project | Creates `CLAUDE.md`; project-specific instructions |
| `/init-verifiers` | Set up test verifiers | Configure automated verification hooks |
| `/install` | Install/reinstall Claude Code | |
| `/install-github-app` | GitHub Actions integration | Multi-step wizard: OAuth → repo select → secrets → workflow |
| `/install-slack-app` | Slack integration | Bot setup |
| `/onboarding` | Run onboarding flow | First-time user setup |
| `/upgrade` | Upgrade Claude Code | |
| `/version` | Show version | |
| `/release-notes` | Show release notes | Changelog for current version |

---

### Memory

| Command | Purpose | Notes |
|---------|---------|-------|
| `/memory` | Memory management | View, edit, clear memory files in `~/.claude/projects/*/memory/`; manages persistent memory across sessions |

---

### Security & Safety

| Command | Purpose | Notes |
|---------|---------|-------|
| `/security-review` | Security-focused code review | Targeted security analysis |
| `/sandbox-toggle` | Toggle sandbox execution | Enable/disable macOS sandbox for Bash |
| `/permissions` | Permission rules | (see Auth section above) |

---

### Miscellaneous & Internal

| Command | Purpose | Notes |
|---------|---------|-------|
| `/share` | Share conversation | Generates shareable link |
| `/feedback` | Send feedback to Anthropic | Bug reports, feature requests |
| `/issue` | File GitHub issue | Opens issue in Claude Code repo |
| `/perf-issue` | Report performance issue | Performance-specific reporting |
| `/bughunter` | Systematic bug hunting | Focused bug-finding session mode |
| `/good-claude` | Positive reinforcement | Easter egg; affects nothing |
| `/stickers` | Stickers | Visual Easter egg |
| `/break-cache` | Break prompt cache | Force cache invalidation (dev/testing) |
| `/mock-limits` | Mock rate limits | Simulate rate limit conditions (dev) |
| `/reset-limits` | Reset rate limit counters | Clear rate limit state (dev) |
| `/backfill-sessions` | Backfill session history | Migrate/import session data |

---

## Skill Writing Guidelines

### Tools to always prefer over Bash equivalents

```
Read          > cat, head, tail, sed (for reading)
Edit          > sed, awk (for replacing)
Write         > echo >, heredoc (for creating)
Glob          > find, ls (for file search)
Grep          > grep, rg (for content search)
AskUserQuestion > assuming and proceeding
```

### When to spawn agents vs. use tools directly

- **Agent** when: task is independent, multi-step, can run in isolation, benefits from
  specialization, or would pollute main context window with noise
- **Direct tools** when: simple targeted lookup, 1-3 file reads, specific search
- **Parallel agents** when: 2+ fully independent tasks with no shared state

### Tool permission architecture

- Destructive Bash operations require explicit permission (bashPermissions)
- Tools can be blocked by name or prefix (ToolPermissionContext)
- Simple mode: only BashTool + FileReadTool + FileEditTool
- MCP tools toggleable independently

### Mode gates

- **Plan mode**: EnterPlanMode disables execution tools; safe to present plans
- **Worktree**: EnterWorktree provides isolated branch; ExitWorktree returns home
- **Trust gate**: deferred init (plugins, skills, MCP, hooks) only loads when trusted=True

### Context window management

- `/compact` to summarize history when context is large
- TaskOutput to avoid streaming large outputs into context
- Agent with `run_in_background` to keep noise out of main context
- ToolSearch to defer loading tool schemas until needed

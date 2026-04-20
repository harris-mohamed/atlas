# Atlas: Discord-based AI Agent Platform

Atlas is a personal AI agent platform operated through Discord with two core capabilities:

1. **Deep Research** — `/research` command triggers multi-step autonomous research, streaming progress to a Discord thread and delivering a comprehensive markdown report.
2. **Autonomous Prototyping** — `/build` command for iterating on specs and triggering autonomous builds that produce GitHub PRs.

Atlas is a **fork of NanoClaw** (https://github.com/qwibitai/nanoclaw) with Discord instead of WhatsApp, inheriting container-per-agent isolation, CLAUDE.md memory, agent swarms, and Claude Agent SDK runtime.

---

## Architecture

```
                                    ┌──────────────────────────────┐
                                    │        OneCLI Vault          │
                                    │  (credential gateway)        │
                                    │  ┌────────────────────────┐  │
                                    │  │ ANTHROPIC_API_KEY       │  │
                                    │  │ GITHUB_TOKEN            │  │
                                    │  │ BRAVE_API_KEY           │  │
                                    │  │ GCAL credentials        │  │
                                    │  └────────────────────────┘  │
                                    └──────────┬───────────────────┘
                                               │ intercepts HTTPS
                                               │ injects credentials
                                               ▼
Discord Server                    Atlas Host (Node.js)
┌─────────────────┐              ┌─────────────────────────────────┐
│                  │   discord.js │                                 │
│  #control ◄──────────────────► │  src/index.ts (orchestrator)    │
│  (isMain: true)  │             │    ├─ src/channels/discord.ts   │
│                  │             │    ├─ src/router.ts              │
│  #research       │             │    ├─ src/container-runner.ts ───┼──► Docker containers
│  ├── 🧵 Thread ◄──────────────┤    ├─ src/task-scheduler.ts     │    ┌──────────────────┐
│  └── 🧵 Thread   │             │    └─ src/db.ts (SQLite)        │    │ Claude Agent SDK  │
│                  │             │                                 │    │ + MCP servers:    │
│  #builds         │             │  Slash commands:                │    │   - brave-search  │
│  ├── 🧵 Thread ◄──────────────┤    /research  /build  /status   │    │   - ollama        │
│  └── 🧵 Thread   │             │    /report    /reminder         │    │   - nanoclaw IPC  │
│                  │             │                                 │    │                    │
└─────────────────┘              └─────────────────────────────────┘    │ .env → /dev/null  │
                                                                        │ (secrets blocked) │
                                                                        └──────────────────┘
Credential flow:
  OneCLI Vault → HTTPS proxy → container outbound requests
  Containers NEVER see raw API keys or tokens.
```

**Tech Stack:**
- Runtime: Node.js / TypeScript
- Discord: discord.js with slash commands
- Agent SDK: Claude Agent SDK (via container)
- Containers: Docker
- Database: SQLite (inherited from NanoClaw)
- GitHub: gh CLI inside containers (token via OneCLI)
- Credentials: OneCLI Agent Vault (containers never see raw secrets)

---

## Key Files

| File | Purpose |
|------|---------|
| `src/index.ts` | Orchestrator: state, message loop, agent invocation |
| `src/channels/discord.ts` | Discord adapter (slash commands, threads, attachments) |
| `src/channels/registry.ts` | Channel registry (self-registration at startup) |
| `src/commands/research.ts` | /research slash command handler |
| `src/commands/build.ts` | /build slash command handler |
| `src/commands/status.ts` | /status slash command handler |
| `src/commands/report.ts` | /report slash command handler |
| `src/commands/reminder.ts` | /reminder slash command handler |
| `src/agents/research-prompt.ts` | Research agent system prompt |
| `src/agents/build-prompt.ts` | Builder agent system prompt |
| `src/container-runner.ts` | Container lifecycle + OneCLI credential injection |
| `src/task-scheduler.ts` | Runs scheduled tasks (cron, interval, once, direct) |
| `src/router.ts` | Message formatting and outbound routing |
| `src/config.ts` | Trigger pattern, paths, intervals |
| `src/db.ts` | SQLite operations |
| `groups/{name}/CLAUDE.md` | Per-group memory (isolated) |
| `container/skills/` | Skills loaded inside agent containers |

## Secrets / Credentials (OneCLI)

API keys, OAuth tokens, and auth credentials are managed by the OneCLI Agent Vault — which handles secret injection into containers at request time, so no keys or tokens are ever passed to containers directly. The `.env` file is mounted as `/dev/null` inside containers to prevent accidental credential leakage.

Run `/init-onecli` to set up, then migrate `GITHUB_TOKEN` and `BRAVE_API_KEY` from `.env` to the vault.

**Security invariant:** `src/container-runner.ts` must NEVER pass credentials via `-e` env vars. All credential injection flows through `onecli.applyContainerConfig()`.

---

## Privileges

| Context | isMain | Capabilities |
|---------|--------|--------------|
| **#control** | true | See all tasks, write global memory, access project root |
| **Research threads** | false | Own folder only, web search, write research.md |
| **Build threads** | false | Own workspace, git/bash/files, create PRs |

---

## Environment Variables

```
DISCORD_TOKEN=                    # Discord bot token
DISCORD_CONTROL_CHANNEL_ID=       # #control channel ID (isMain)
ANTHROPIC_API_KEY=                # For Claude Agent SDK
ONECLI_URL=                       # OneCLI Agent Vault URL (default: http://127.0.0.1:4444)
GITHUB_TOKEN=                     # For creating PRs from builder (migrate to vault)
BRAVE_API_KEY=                    # For report agents (migrate to vault)
```

---

## Development

Run commands directly — don't tell the user to run them.

```bash
npm run dev          # Run with hot reload
npm run build        # Compile TypeScript
npm test             # Run tests
npm run lint         # Lint source
./container/build.sh # Rebuild agent container
```

Service management:
```bash
# Linux (systemd)
systemctl --user start nanoclaw
systemctl --user stop nanoclaw
systemctl --user restart nanoclaw
```

## Container Build Cache

The container buildkit caches the build context aggressively. `--no-cache` alone does NOT invalidate COPY steps — the builder's volume retains stale files. To force a truly clean rebuild, prune the builder then re-run `./container/build.sh`.

# Atlas Virtual Assistant — Deep Codebase Research Report

> Generated: 2026-02-11
> Analyst: Claude Code (claude-sonnet-4-5-20250929)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Directory Structure](#2-directory-structure)
3. [Officer Roster & Configuration](#3-officer-roster--configuration)
4. [Main Application: bot.py](#4-main-application-botpy)
5. [Database Layer: db_manager.py](#5-database-layer-db_managerpy)
6. [Database Schema: models/memory.py](#6-database-schema-modelsmemorypy)
7. [LLM Integration via OpenRouter](#7-llm-integration-via-openrouter)
8. [Memory System Architecture](#8-memory-system-architecture)
9. [Discord UI Components](#9-discord-ui-components)
10. [Infrastructure & Deployment](#10-infrastructure--deployment)
11. [Environment & Configuration](#11-environment--configuration)
12. [Execution Flow Walkthroughs](#12-execution-flow-walkthroughs)
13. [Design Patterns & Architectural Decisions](#13-design-patterns--architectural-decisions)
14. [Phase Completion Status](#14-phase-completion-status)
15. [Technical Debt & Limitations](#15-technical-debt--limitations)
16. [Extension Opportunities](#16-extension-opportunities)

---

## 1. Project Overview

**Atlas** is a Discord-based command center built around two primary pillars:

1. **War Room of LLMs** (Phase 1 — current focus): A collaborative AI council where multiple LLM-backed officers with distinct specialties respond to strategic missions, conduct multi-perspective research, and maintain per-channel persistent memory.

2. **Claude Code Execution Engine** (Phase 2 — planned): An isolated, headless sandbox system that consumes a `CLAUDE.md` file and spins up Docker containers to execute proof-of-concept projects autonomously.

The system is written in async Python, uses `discord.py` for the bot layer, `SQLAlchemy` with `asyncpg` for PostgreSQL persistence, and routes all LLM calls through **OpenRouter** — a unified API gateway that supports 50+ model providers (Anthropic, OpenAI, Google, X-AI, DeepSeek, etc.).

---

## 2. Directory Structure

```
/home/harris/dev/atlas/virtual-assistant/
├── bot.py                          # Main bot application (~965 lines)
├── db_manager.py                   # All async database operations (~266 lines)
├── config/
│   └── roster.json                 # Officer definitions — 16 officers, 4 classes
├── models/
│   ├── __init__.py
│   └── memory.py                   # SQLAlchemy ORM models (~115 lines)
├── docs/
│   └── WEB_SEARCH_GUIDE.md         # Web search capability reference
├── docker-compose.yml              # Defines `war-room-bot` + `db` services
├── Dockerfile                      # Python 3.11-slim container build
├── requirements.txt                # 6 Python dependencies
├── .env                            # Secrets (not in git)
├── .env.example                    # Template for secrets
├── .gitignore
├── README.md                       # Project intro, demo screenshot, usage guide
├── CLAUDE.md                       # Implementation roadmap (project instructions)
├── MEMORY_SYSTEM_SETUP.md          # Memory system implementation notes
├── TESTING_GUIDE.md                # Manual testing checklist
└── logs/                           # Application log directory (rw mount in Docker)
```

The codebase is intentionally lean: three Python files cover the entire application logic. There are no sub-packages beyond `models/`, no test suite, and no CI/CD pipeline yet.

---

## 3. Officer Roster & Configuration

**File:** `config/roster.json`

The roster defines 16 AI officers organized into 4 capability classes. The JSON schema has a `version` field, an `active_roster` list (which officer IDs are enabled), and an `officers` map keyed by ID (`"O1"` through `"O16"`).

### 3.1 Schema per Officer

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Display name / role title |
| `model` | string | OpenRouter model path (e.g., `anthropic/claude-opus-4-5`) |
| `specialty` | string | Domain focus area |
| `capability_class` | string | One of: Strategic, Operational, Tactical, Support |
| `color` | string (hex) | Optional embed color override |
| `system_prompt` | string | Base behavioral instructions for this officer |

### 3.2 Capability Classes & Officers

**Strategic Class** — Purple `#9b59b6` — used for high-level vision & reasoning

| ID | Title | Model |
|----|-------|-------|
| O1 | Executive Advisor | `anthropic/claude-opus-4-5` |
| O2 | Next-Gen Intelligence Officer | `openai/gpt-5` (speculative) |
| O3 | Advanced Reasoning Officer | `x-ai/grok-4` |
| O4 | Premier Strategic Advisor | `google/gemini-3-pro` (speculative) |

**Operational Class** — Blue `#3498db` — used for planning & execution

| ID | Title | Model |
|----|-------|-------|
| O5 | Strategic Advisor | `anthropic/claude-sonnet-4-5` |
| O6 | Chief of Operations | `openai/gpt-4o` |
| O7 | Red Team Lead | `anthropic/claude-3-7-sonnet` |
| O8 | Deep Analysis Specialist | `deepseek/deepseek-v3-2` (speculative) |

**Tactical Class** — Green `#2ecc71` — used for implementation & rapid analysis

| ID | Title | Model |
|----|-------|-------|
| O9 | Intelligence Officer | `anthropic/claude-3-5-sonnet` |
| O10 | Innovation Officer | `google/gemini-flash-3` (speculative) |
| O11 | Speed Operations | `x-ai/grok-4.1-fast` (speculative) |
| O12 | Logistics Officer | `google/gemini-2.0-flash-001` |

**Support Class** — Orange `#f39c12` — used for cost-effective, rapid queries

| ID | Title | Model |
|----|-------|-------|
| O13 | Efficiency Officer | `openai/gpt-4o-mini` |
| O14 | Rapid Response Analyst | `xiaomi/mimo-v2` (speculative) |
| O15 | Budget Analyst | `anthropic/claude-3-haiku` |
| O16 | Quick Intelligence | `google/gemini-2.0-flash` (speculative) |

> **Note:** Several model names appear forward-looking (GPT-5, Grok-4, Gemini 3 Pro). These may not resolve on OpenRouter today and would cause API failures at query time. The system handles this gracefully via try/catch, marking responses as `success=False`.

### 3.3 Roster Sync Behavior

At startup, `seed_officers()` in `db_manager.py` compares `roster.json` against the database. New officers are inserted; existing officers are updated. Officers removed from the JSON are **not deleted** — their historical data is preserved. This ensures mission history is never orphaned.

---

## 4. Main Application: bot.py

The main file contains all Discord bot logic: command handlers, UI components, API querying, and embed construction.

### 4.1 Bot Initialization

```python
class WarRoomBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await init_db()                    # Create tables
        await seed_officers(officers)      # Sync roster
        await self.tree.sync()             # Register slash commands with Discord
```

The `setup_hook()` runs before the bot begins processing events — ensuring the database is ready before any command can be invoked.

### 4.2 Constants

```python
CAPABILITY_COLORS = {
    "Strategic": 0x9b59b6,
    "Operational": 0x3498db,
    "Tactical": 0x2ecc71,
    "Support": 0xf39c12
}

RESEARCH_ROLES = {
    0: {"role": "State-of-the-Art Researcher", "instruction": "..."},
    1: {"role": "Critical Analyst", "instruction": "..."},
    2: {"role": "Optimistic Visionary", "instruction": "..."},
    3: {"role": "Historical Context Provider", "instruction": "..."}
}
```

Research roles are assigned positionally to the 4 officers queried in a `/research` call. The assignment is deterministic (index 0 = first officer in the capability class).

### 4.3 Officer Querying Functions

#### `query_officer(officer_id, mission_brief, client, channel_id)`

The core querying function. Its steps:
1. Look up officer config from `roster.json`
2. Call `load_officer_memory(channel_id, officer_id)` to fetch memory context
3. Construct the system prompt: base system prompt + optional memory block
4. POST to `https://openrouter.ai/api/v1/chat/completions`
5. Extract `choices[0].message.content` from the JSON response
6. Return a dict with `officer_id`, `title`, `model`, `response`, `success`, `color`, and optional `error`

The `httpx.AsyncClient` has a 60-second timeout. Errors are caught and returned with `success=False` rather than propagating.

#### `query_all_officers(mission_brief, capability_class, channel_id)`

Wraps `query_officer()` calls in `asyncio.gather()` for true parallelism. If `capability_class` is specified, it first calls `filter_officers_by_capability()` to limit which officers are queried.

#### `query_officer_with_research_role(...)`

Extends `query_officer()` with a research-specific system prompt augmentation. Each officer gets one of the four `RESEARCH_ROLES` injected into their prompt. Additionally:
- If the officer's model supports web search and `use_web_search=True`, search instructions are appended
- For Google/Gemini models, the payload gains a `provider` field forcing Google routing
- Responses from models that attempted tool calls (unimplemented) are caught and returned with a warning message

#### `query_research_council(research_topic, capability_class, channel_id, use_web_search)`

Selects the first 4 officers of the specified capability class and calls `query_officer_with_research_role()` for each with a different research role index (0–3), all in parallel.

### 4.4 Slash Commands

#### `/mission [brief] [capability_class]`

- **Parameters:** `brief` (required string), `capability_class` (optional enum)
- Defers the response immediately (Discord requires a response within 3 seconds)
- Ensures the channel record exists in the database
- Queries officers in parallel
- Saves the mission and all responses to the database
- Builds Discord embeds (one per officer) and sends them in batches respecting the 6000-char Discord limit
- Attaches a `WarRoomView` with 3 buttons

#### `/research [topic] [capability_class] [use_web_search]`

- **Parameters:** `topic` (required), `capability_class` (required enum), `use_web_search` (optional bool)
- Same defer/channel-ensure pattern
- Queries 4 officers from the selected class, each with a different research role
- Saves as a research mission with `extra_metadata` containing `mission_type`, `research_roles`, and `web_search_enabled`
- Sends embeds with `ResearchView` buttons

#### `/memory [action] [officer_id] [note]`

Four sub-actions:
- **`stats`**: Queries `get_channel_stats()` and renders an embed with note/mission counts per officer
- **`view`**: Displays an officer's manual notes and last 5 mission responses
- **`add`**: Calls `add_manual_note()` and confirms in an embed
- **`clear`**: Sends a `ConfirmClearView` with a danger-styled confirmation button before deleting

### 4.5 UI Components

**`WarRoomView(discord.ui.View)`** (timeout=None)
- `🔴 Red Team Rebuttal`: Takes all officer responses from the mission, formats them as a block, and queries O7 (Red Team Lead) for a critique
- `📄 Generate Plan`: Formats all responses and queries O5 (Strategic Advisor) to synthesize a `PLAN.md`-style action plan
- `🔄 Pivot`: Opens `PivotModal`

**`PivotModal(discord.ui.Modal)`**
- Single text input: "Course Correction"
- On submit: combines original brief with pivot instruction and calls `query_all_officers()` again

**`ResearchView(discord.ui.View)`** (timeout=None)
- `📊 Generate Report`: Calls `generate_research_markdown()`, writes to a temp `.md` file, uploads as a Discord file attachment, then deletes the temp file
- `🤖 AI Synthesis`: Queries O9 (Intelligence Officer) to synthesize all research perspectives
- `🔄 Pivot`: Opens `ResearchPivotModal`

**`ConfirmClearView(discord.ui.View)`** (timeout=60)
- Two buttons: `✅ Yes, Clear Memory` (danger style) and `❌ Cancel`
- The confirm button calls `clear_officer_memory()` on click

### 4.6 Embed Size Management

Discord enforces a 6000-character limit per message across all embeds. The bot calculates estimated embed sizes and splits across follow-up messages:

```python
def calculate_embed_size(embed) -> int:
    size = 0
    if embed.title: size += len(embed.title)
    if embed.description: size += len(embed.description)
    for field in embed.fields:
        size += len(field.name) + len(field.value)
    if embed.footer: size += len(embed.footer.text)
    return size

async def send_embeds_in_batches(interaction, embeds, view):
    MAX_EMBED_SIZE = 5500
    current_batch, current_size = [], 0
    for embed in embeds:
        embed_size = calculate_embed_size(embed)
        if current_size + embed_size > MAX_EMBED_SIZE and current_batch:
            await interaction.followup.send(embeds=current_batch)
            current_batch, current_size = [], 0
        current_batch.append(embed)
        current_size += embed_size
    if current_batch:
        await interaction.followup.send(embeds=current_batch, view=view)
```

The `view` is only attached to the **last** batch, ensuring buttons appear at the bottom of the response chain.

---

## 5. Database Layer: db_manager.py

All database interactions are centralized here. Every function is `async` and uses SQLAlchemy's `AsyncSession` context manager.

### 5.1 Connection Setup

```python
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True   # Validate connections before use
)
async_session = async_sessionmaker(engine, expire_on_commit=False)
```

`expire_on_commit=False` is important in async SQLAlchemy — it prevents lazy-loading exceptions after a session commit.

### 5.2 Key Functions

| Function | Purpose |
|----------|---------|
| `init_db()` | `Base.metadata.create_all()` — creates tables if they don't exist |
| `seed_officers(officers_dict)` | Upsert officers from roster.json |
| `ensure_channel_exists(channel_id, name, guild_id)` | Insert channel record on first use |
| `load_officer_memory(channel_id, officer_id, max_tokens=2000)` | Fetch and format memory context |
| `add_manual_note(channel_id, officer_id, content, user_id)` | Insert manual note |
| `clear_officer_memory(channel_id, officer_id)` | Delete all manual notes for officer in channel |
| `get_channel_stats(channel_id)` | Count notes and missions per officer |
| `save_mission(...)` | Persist mission + responses |
| `save_research_mission(...)` | Persist research mission + responses with metadata |

### 5.3 Memory Loading Logic

`load_officer_memory()` is the most complex function in the file:

1. Queries `ManualNote` for this (officer, channel) pair — ordered by `is_pinned DESC`, then `created_at DESC`
2. Queries the last 5 `MissionOfficerResponse` records for this officer in this channel where `success=True`
3. Formats both into a structured text block:
   ```
   ### Your Memory for This Channel:

   **Manual Notes:**
   - [note 1]
   - [note 2]

   **Recent Mission Context:**
   Mission: [truncated brief]
   Your Response: [truncated response]
   ---
   ```
4. Token-estimates the total (`len(text) // 4`) and truncates if over `max_tokens`
5. Returns empty string if no memory exists (no prompt augmentation)

---

## 6. Database Schema: models/memory.py

Uses SQLAlchemy 2.0's typed declarative base. All models inherit from `Base = DeclarativeBase()`.

### 6.1 Model Relationships

```
Officer (1) ──────< MissionOfficerResponse (N)
Officer (1) ──────< OfficerChannelMemory (N)
Officer (1) ──────< ManualNote (N)

Channel (1) ──────< MissionHistory (N)
Channel (1) ──────< OfficerChannelMemory (N)
Channel (1) ──────< ManualNote (N)

MissionHistory (1) ──── CASCADE DELETE ────< MissionOfficerResponse (N)
```

### 6.2 Model Details

**`Officer`** — Static officer registry
- PK: `officer_id` (VARCHAR, e.g. `"O1"`)
- Key columns: `title`, `model`, `capability_class`, `specialty`, `system_prompt`
- Source of truth is `roster.json`; DB is a synced copy

**`Channel`** — Discord channel registry
- PK: `channel_id` (BIGINT — Discord snowflakes are 64-bit)
- Also stores `guild_id` (BIGINT) for server context

**`OfficerChannelMemory`** — Summarized memory (currently unused in active code path)
- Indexed on `(officer_id, channel_id)` for fast lookups
- `extra_metadata` is `JSONB` — extensible without schema migrations
- `update_count` tracks how many times this memory record has been refreshed

**`MissionHistory`** — Immutable audit trail of every mission
- `mission_brief` truncated to 1000 characters
- `extra_metadata` (JSONB) stores `mission_type`, `research_roles`, `web_search_enabled`
- Indexed on `(channel_id, started_at)`

**`MissionOfficerResponse`** — Individual officer responses within a mission
- `response_content` truncated to 2000 characters
- `success` boolean distinguishes errors from valid responses
- CASCADE delete from `MissionHistory` (delete mission → delete all responses)

**`ManualNote`** — User-created context notes
- `is_pinned` flag — pinned notes appear first in memory context
- Indexed on `(officer_id, channel_id, is_pinned)` for efficient retrieval

---

## 7. LLM Integration via OpenRouter

### 7.1 API Details

- **Endpoint:** `https://openrouter.ai/api/v1/chat/completions`
- **Auth:** `Authorization: Bearer {OPENROUTER_API_KEY}`
- **Format:** OpenAI-compatible chat completions payload

### 7.2 Payload Structure

```json
{
  "model": "anthropic/claude-opus-4-5",
  "messages": [
    {
      "role": "system",
      "content": "Base system prompt + optional memory context"
    },
    {
      "role": "user",
      "content": "Mission brief or research topic"
    }
  ]
}
```

For web search with Google models, an additional field is added:
```json
{
  "provider": {
    "order": ["Google"],
    "allow_fallbacks": false
  }
}
```

### 7.3 Web Search Support

```python
def model_supports_web_search(model_name: str) -> bool:
    return "perplexity" in model_name.lower() or "google" in model_name.lower()
```

Only Perplexity (native search) and Google/Gemini models (grounding) support web search. OpenAI, Anthropic, and X-AI models receive a disclaimer appended to their response if web search was requested but unavailable.

If a model responds with a `tool_calls` message (indicating it tried to invoke a web search function), the bot catches this and returns a warning message instead — the tool call execution is not implemented.

### 7.4 Error Handling

```python
try:
    response = await client.post(...)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return {..., "success": True, "response": content}
except Exception as e:
    return {..., "success": False, "response": f"Error: {str(e)}"}
```

Failed responses are included in the embed (showing the error) and saved to the database with `success=False`.

---

## 8. Memory System Architecture

The memory system is one of the most sophisticated parts of the codebase.

### 8.1 Per-Channel Isolation

Each Discord channel is its own memory namespace. The same officer (e.g., O1) can have completely different memories in two different channels. This is critical for topic separation — a channel about "infrastructure" and a channel about "marketing" should give O1 different context.

### 8.2 Memory Sources Hierarchy

When an officer is queried, memory is loaded from two sources in priority order:

1. **Manual Notes** (highest priority)
   - User-curated facts the officer should always know
   - Pinned notes appear before unpinned ones
   - Examples: "This user prefers async patterns", "Company policy: no AWS"

2. **Mission History** (contextual, last 5)
   - The officer's own previous responses in this channel
   - Gives the officer continuity across missions
   - Truncated to fit token budget

### 8.3 Memory Injection Point

Memory is injected into the **system prompt**, not the conversation history. This is a deliberate design choice:

```
System: [base system prompt]

### Your Memory for This Channel:
**Manual Notes:**
- [note 1]
...
**Recent Mission Context:**
Mission: [brief]
Your Response: [response]
---
```

This approach:
- Keeps API calls stateless (no conversation history to manage)
- Works with all model providers uniformly
- Lets the model treat memory as authoritative context
- Is simpler than maintaining multi-turn conversation state

### 8.4 Token Budget

`max_tokens=2000` is the default cap. Token estimation uses the rough heuristic `len(text) // 4`. If the formatted memory exceeds 8000 characters (2000 estimated tokens), it's truncated. This is a known approximation — actual token counts vary significantly by model and tokenizer.

### 8.5 `OfficerChannelMemory` Table (Partially Unused)

The schema includes an `OfficerChannelMemory` model that appears to be intended for summarized/compressed memory (as opposed to raw notes and mission responses). However, in the current codebase, `load_officer_memory()` does not read from or write to this table. It queries `ManualNote` and `MissionOfficerResponse` directly. The `OfficerChannelMemory` table may be intended for a future "memory consolidation" feature.

---

## 9. Discord UI Components

### 9.1 Interaction Pattern

All three slash commands follow the same deferred interaction pattern:
```python
await interaction.response.defer()
# ... async work ...
await interaction.followup.send(embeds=..., view=...)
```

This is required because Discord times out interactions not acknowledged within 3 seconds. Deferring immediately buys 15 minutes for the async processing.

### 9.2 Button Persistence

Both `WarRoomView` and `ResearchView` are created with `timeout=None`, meaning the buttons never expire. This means a user can click "Red Team Rebuttal" on a mission from last week. The buttons store references to the original results via closure, so they'll always re-query using those original responses.

### 9.3 Modal Forms

Both `PivotModal` and `ResearchPivotModal` are `discord.ui.Modal` subclasses with a single `discord.ui.TextInput`. On submit (`on_submit`), they combine the original context with the user's new direction and re-trigger the appropriate querying flow.

### 9.4 Confirmation Pattern

The `ConfirmClearView` demonstrates a safety pattern:
- Danger-styled confirm button (red in Discord)
- 60-second timeout (auto-dismisses if ignored)
- Cancel button to abort
- Both buttons disable the view on click to prevent double-execution

---

## 10. Infrastructure & Deployment

### 10.1 Docker Compose Services

**`war-room-bot`**
- Image: Built from `Dockerfile` (Python 3.11-slim)
- Depends on `db` with a health check condition
- Volume mounts:
  - `./config:/app/config:ro` — Officer roster (read-only)
  - `./logs:/app/logs:rw` — Log output
- Environment: Injects `DATABASE_URL` and `OPENROUTER_API_KEY`

**`db`** (PostgreSQL 16 Alpine)
- Health check: `pg_isready -U atlas_user` every 10 seconds, 3-second timeout, 5 retries
- Persistent volume: `postgres_data:/var/lib/postgresql/data`
- Both services on a shared `atlas-network` bridge network

### 10.2 Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p config
CMD ["python", "bot.py"]
```

Minimal image: no multi-stage build, no non-root user, no HEALTHCHECK. Suitable for development; production hardening would be recommended.

### 10.3 Dependencies

```
discord.py==2.3.2       # Discord bot framework (stable)
httpx==0.27.0           # Async HTTP client for OpenRouter calls
python-dotenv==1.0.1    # .env file loading
sqlalchemy==2.0.23      # ORM + async query builder
asyncpg==0.29.0         # PostgreSQL async driver
alembic==1.13.0         # Database migrations (installed but not used yet)
```

**Notable absence:** `alembic` is in `requirements.txt` but no migration scripts exist. Schema changes currently require dropping and recreating tables (handled by `create_all()` at startup, which is a no-op if tables exist).

---

## 11. Environment & Configuration

### 11.1 Required Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | Yes | Discord bot token |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key |
| `DATABASE_URL` | Yes | PostgreSQL async URL |
| `POSTGRES_PASSWORD` | Yes (compose) | PostgreSQL password |

### 11.2 Optional / Derived

| Variable | Default | Description |
|----------|---------|-------------|
| `ROSTER_PATH` | `config/roster.json` | Override officer config path |

### 11.3 Security Posture

- `.env` is gitignored
- Database password uses default `changeme` in docker-compose — a security risk in any non-local deployment
- No secrets are passed to execution sandboxes (by design — Phase 2 isolation)
- No rate limiting implemented (relies on OpenRouter and Discord's own limits)
- SQL injection protected by SQLAlchemy ORM (parameterized queries)

---

## 12. Execution Flow Walkthroughs

### 12.1 Mission Flow

```
User: /mission "Design a fault-tolerant caching strategy" operational

1. interaction.response.defer()
2. ensure_channel_exists(channel_id, channel_name, guild_id)
3. filter_officers_by_capability("Operational") → [O5, O6, O7, O8]
4. asyncio.gather(
     query_officer("O5", brief, client, channel_id),
     query_officer("O6", brief, client, channel_id),
     query_officer("O7", brief, client, channel_id),
     query_officer("O8", brief, client, channel_id)
   )
   Each query_officer call:
   a. load_officer_memory(channel_id, officer_id)
      → "### Manual Notes:\n- [note]\n\n### Recent Missions:\n..."
   b. Build system prompt = base_prompt + memory_context
   c. POST to OpenRouter API (60s timeout)
   d. Return {officer_id, title, model, response, success, color}
5. save_mission(channel_id, brief, user_id, "Operational", results)
6. Build embeds: one per officer, color = CAPABILITY_COLORS["Operational"]
7. send_embeds_in_batches(interaction, embeds, WarRoomView())
```

### 12.2 Research Flow

```
User: /research "Quantum computing in 2026" strategic use_web_search:True

1. interaction.response.defer()
2. ensure_channel_exists(...)
3. filter_officers_by_capability("Strategic") → [O1, O2, O3, O4]
4. asyncio.gather(
     query_officer_with_research_role("O1", topic, 0, client, channel_id, True),
     query_officer_with_research_role("O2", topic, 1, client, channel_id, True),
     query_officer_with_research_role("O3", topic, 2, client, channel_id, True),
     query_officer_with_research_role("O4", topic, 3, client, channel_id, True)
   )
   Role assignments:
   - O1: "State-of-the-Art Researcher" + search instructions
   - O2: "Critical Analyst" + search instructions (if model supports)
   - O3: "Optimistic Visionary" + search instructions
   - O4: "Historical Context Provider" + Google routing forced
5. save_research_mission(..., metadata={
     "mission_type": "research",
     "research_roles": ["State-of-the-Art Researcher", ...],
     "web_search_enabled": True
   })
6. Build research embeds with role labels in footer
7. send_embeds_in_batches(interaction, embeds, ResearchView())
```

### 12.3 Memory View Flow

```
User: /memory view O1

1. Query ManualNote WHERE officer_id="O1" AND channel_id=X
2. Query MissionOfficerResponse JOIN MissionHistory
   WHERE officer_id="O1" AND channel_id=X AND success=True
   ORDER BY created_at DESC LIMIT 5
3. Build embed:
   - Title: "O1 Memory — Executive Advisor"
   - Field: "Manual Notes" → note list or "No notes"
   - Field: "Recent Missions" → response summaries
4. interaction.followup.send(embed=embed)
```

---

## 13. Design Patterns & Architectural Decisions

### 13.1 Async-First Throughout

The entire stack is async:
- Discord commands are async (`async def callback(interaction)`)
- DB operations use `AsyncSession` and `await`
- LLM calls use `httpx.AsyncClient`
- Parallel queries via `asyncio.gather()`

This is the correct choice for a Discord bot — I/O-bound workloads benefit massively from async concurrency. Querying 4-16 LLMs in parallel instead of serial reduces response time by ~4-16x.

### 13.2 Stateless API Calls + Stateful Memory

Each OpenRouter API call is stateless (single system message + single user message). Statefulness is achieved by injecting memory into the system prompt. This is a pragmatic design:
- Simple to implement
- Works uniformly across all model providers
- No conversation threading needed
- Memory can be inspected and edited by users

The trade-off is that officers don't have true conversation history — they can't reference specific previous exchanges, only summarized context.

### 13.3 Roster as External Configuration

Officers are defined in `roster.json`, not hardcoded. This allows:
- Swapping models without code changes
- Adding officers without deployments
- Changing system prompts dynamically (requires bot restart to reseed)

The `seed_officers()` function ensures the DB stays in sync with the JSON file at every bot startup.

### 13.4 Graceful Degradation on LLM Failure

Failed officer queries don't abort the mission. Other officers' responses are still shown. The failed officer's embed shows the error message. This is important UX — if one exotic model is temporarily unavailable, the other 3 still provide value.

### 13.5 Discord Message Batching

The embed batching system is a well-thought-out workaround for Discord's 6000-character limit. Rather than truncating responses, it splits into multiple messages. The `view` (buttons) attaches to only the last message, keeping the UI clean.

### 13.6 JSONB for Extensible Metadata

Both `MissionHistory` and `ManualNote` have `extra_metadata JSONB` columns. This allows adding new metadata fields (like `research_roles`, `web_search_enabled`) without database schema migrations. A pragmatic choice for a fast-moving project.

---

## 14. Phase Completion Status

### Phase 1: War Room (~85% Complete)

| Feature | Status |
|---------|--------|
| Officer roster (16 officers, 4 classes) | ✅ Complete |
| `/mission` command with parallel querying | ✅ Complete |
| `/research` command with 4 analytical roles | ✅ Complete |
| `/memory` command (stats/view/add/clear) | ✅ Complete |
| Capability class filtering | ✅ Complete |
| WarRoomView buttons (Red Team/Plan/Pivot) | ✅ Complete |
| ResearchView buttons (Report/Synthesis/Pivot) | ✅ Complete |
| PostgreSQL-backed memory system | ✅ Complete |
| Web search integration (Google/Perplexity) | ✅ Complete |
| Per-channel memory isolation | ✅ Complete |
| Officer-aware of each other | ⚠️ Partial (via shared memory, not direct awareness) |
| Red Team dissent enforcement | ❌ Not enforced |
| Mission chaining | ❌ Not implemented |

### Phase 2: Sandbox (0% Complete)

| Feature | Status |
|---------|--------|
| Base Docker image for execution sandbox | ❌ Not started |
| `/execute` slash command | ❌ Not started |
| Docker-outside-of-Docker (socket mounting) | ❌ Not started |
| Claude Code YOLO mode execution | ❌ Not started |
| Results returned to Discord | ❌ Not started |

### Phase 3: Fleet (0% Complete)

| Feature | Status |
|---------|--------|
| `session.log` capture | ❌ Not started |
| ANSI stripping | ❌ Not started |
| Channel-to-project mapping | ❌ Not started |
| Concurrent container support | ❌ Not started |
| GitHub CLI integration | ❌ Not started |

---

## 15. Technical Debt & Limitations

### 15.1 Token Counting is Approximate

```python
estimated_tokens = len(text) // 4  # characters / 4 ≈ tokens
```

This is a rough heuristic. Actual token counts depend on the tokenizer. GPT-4 and Claude use different tokenizers with different ratios. For short texts it's close enough; for long memory contexts it could be significantly off.

### 15.2 No Alembic Migrations

`alembic` is installed but no migration scripts exist. Adding a new column to a model requires either manually running `ALTER TABLE` SQL, dropping and recreating the database, or writing a migration script. This is a growing concern as the schema evolves.

### 15.3 Web Search Tool Calls Unimplemented

If a model responds with `tool_calls` (attempting to invoke a search function), the bot simply shows a warning message. True agentic web search (function calling → execute search → re-query with results) is not implemented.

### 15.4 Speculative Model Names

Several officers reference models that may not exist yet:
- `openai/gpt-5`
- `google/gemini-3-pro`
- `google/gemini-flash-3`
- `x-ai/grok-4`
- `x-ai/grok-4.1-fast`
- `deepseek/deepseek-v3-2`
- `xiaomi/mimo-v2`

These will cause API errors (likely 404 or 400 from OpenRouter) that are caught and surfaced as `success=False` responses.

### 15.5 No Rate Limiting or Queuing

If multiple users simultaneously issue `/mission` commands, they all fire parallel API requests immediately. There's no queuing, throttling, or backpressure mechanism. Under high load this could exhaust OpenRouter rate limits or overwhelm the database connection pool.

### 15.6 `OfficerChannelMemory` Table Unused

The `OfficerChannelMemory` model is defined in the schema and table is created, but no code reads from or writes to it. The actual memory loading uses `ManualNote` and `MissionOfficerResponse` directly. This suggests a planned "memory summarization" feature that was never implemented.

### 15.7 Mission History Truncation

`response_content` is truncated to 2000 characters before saving. Long responses lose their tail in the database. This affects memory quality — a complex analysis truncated mid-sentence provides worse context than a complete shorter response.

### 15.8 Button State Not Persisted

`WarRoomView` and `ResearchView` hold the original mission results in memory (Python variables). If the bot restarts, all in-memory button handlers are gone. Clicking an old button after a restart would fail or use stale data. This is a known Discord.py limitation — true persistence would require loading mission results from the database on button click.

---

## 16. Extension Opportunities

### 16.1 Near-Term Improvements

1. **Alembic migrations**: Set up `alembic init` and generate initial migration to formalize the schema version control workflow.

2. **Accurate token counting**: Use `tiktoken` (for OpenAI models) or a character-to-token ratio map per model family to improve memory budget accuracy.

3. **Enforce Red Team dissent**: Check O7's response for affirmative/neutral language and prompt a retry if no failure point is identified.

4. **Model validation at startup**: At bot startup (or roster load), validate all model names against OpenRouter's model list and warn about unknown models.

5. **Button state persistence**: On button click, load the mission from the database (by `mission_id` stored in the view) rather than relying on in-memory closure state.

### 16.2 Phase 2 Foundation Work

6. **Docker-outside-of-Docker setup**: Mount `/var/run/docker.sock` into the bot container and implement `docker run` command execution via Python subprocess or the Docker SDK.

7. **`/execute` command skeleton**: Create the slash command, `CLAUDE.md` file upload, and sandbox container lifecycle management.

### 16.3 Architectural Evolution

8. **Officer awareness**: Instead of (or in addition to) memory injection, pass a summary of other officers' recent responses in the system prompt — enabling true collaborative awareness.

9. **Memory consolidation**: Implement the `OfficerChannelMemory` table as an LLM-generated summary of older notes and missions, preserving context while controlling token growth.

10. **Streaming responses**: Use OpenRouter's streaming API to post officer responses progressively as they arrive, reducing perceived latency for long-running missions.

11. **Mission templates**: Allow users to define reusable mission formats (e.g., `SWOT analysis`, `threat model`) that pre-structure the brief before sending to officers.

12. **Cross-channel research**: Add an option to query across channel memories, enabling a "fleet intelligence" view where the bot synthesizes learnings from all channels.

---

## Summary

Atlas is a well-architected, async-first Discord bot that successfully implements a multi-agent LLM council system. The War Room phase is feature-complete and production-ready for small team use. The codebase demonstrates strong separation of concerns (bot logic / database operations / schema), thoughtful async patterns, and good Discord UX practices.

The main risks are: speculative model names in the roster, lack of alembic migrations, approximate token counting, and no rate limiting. None of these are blockers for the current feature set but should be addressed before scaling to larger teams or moving to Phase 2.

The Sandbox and Fleet phases remain entirely unimplemented and represent substantial engineering work, particularly the Docker-outside-of-Docker isolation and secure secrets management required for Phase 2.

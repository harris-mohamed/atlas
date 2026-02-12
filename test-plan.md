# Atlas Virtual Assistant — Test Plan

> Status: Proposed
> Author: Claude Code
> Last Updated: 2026-02-11

---

## Table of Contents

1. [Goals & Philosophy](#1-goals--philosophy)
2. [Testing Stack](#2-testing-stack)
3. [Test Pyramid](#3-test-pyramid)
4. [Unit Tests](#4-unit-tests)
5. [Integration Tests](#5-integration-tests)
6. [End-to-End Tests](#6-end-to-end-tests)
7. [Contract Tests](#7-contract-tests)
8. [GitHub Actions CI/CD Pipeline](#8-github-actions-cicd-pipeline)
9. [Directory Structure](#9-directory-structure)
10. [Test Data & Fixtures](#10-test-data--fixtures)
11. [Coverage Requirements](#11-coverage-requirements)
12. [Implementation Roadmap](#12-implementation-roadmap)

---

## 1. Goals & Philosophy

### What We're Protecting

The Atlas codebase has three layers of logic that are independently testable:

1. **Database operations** (`db_manager.py`) — memory loading, mission persistence, officer seeding
2. **LLM querying logic** (`bot.py` functions) — prompt construction, response parsing, web search routing
3. **Discord interaction handlers** (`bot.py` commands) — command parsing, embed construction, button behavior

### Principles

- **Test behavior, not implementation.** Assert what functions return and what state they create — not how they do it internally.
- **Mock at the boundary.** External services (Discord API, OpenRouter, PostgreSQL) are always mocked in unit tests. Only integration tests touch real infrastructure.
- **Fast feedback loop.** Unit tests must run in under 5 seconds. The full CI suite should complete in under 3 minutes.
- **Deterministic.** Tests never depend on network calls, random values, or wall-clock time. All external dependencies are mocked or frozen.
- **One assertion per test (where practical).** Makes failures self-documenting.

---

## 2. Testing Stack

| Tool | Purpose | Why |
|------|---------|-----|
| `pytest` | Test runner | Industry standard for Python |
| `pytest-asyncio` | Async test support | Required for async bot/db functions |
| `pytest-cov` | Coverage measurement | HTML + XML reports for CI |
| `pytest-mock` | `mocker` fixture for mocks/patches | Cleaner than `unittest.mock` directly |
| `respx` | Mock `httpx` requests | Intercepts OpenRouter API calls at the transport layer |
| `freezegun` | Freeze `datetime.now()` | Deterministic timestamp assertions |
| `factory_boy` | Test data factories | Consistent, reusable model instances |
| `asyncpg` + `sqlalchemy` | Real async DB driver | Used in integration tests only |
| `pytest-docker` or `testcontainers-python` | Spin up PostgreSQL for integration tests | Isolated, disposable database |

### Install

```toml
# pyproject.toml (recommended) or requirements-dev.txt
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=. --cov-report=term-missing --cov-report=xml"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "pytest-mock>=3.12",
    "respx>=0.21",
    "freezegun>=1.4",
    "factory-boy>=3.3",
    "testcontainers[postgres]>=4.0",
]
```

---

## 3. Test Pyramid

```
            ┌─────────────────┐
            │   E2E Tests      │  ← Few, slow, catch integration smoke
            │  (2-3 scenarios) │
           ─┼─────────────────┼─
          ┌─┤ Integration Tests├─┐  ← DB + real queries
          │ │  (20-30 tests)   │ │
         ─┼─┼─────────────────┼─┼─
        ┌─┤ │   Unit Tests     │ ├─┐  ← Fast, isolated, majority
        │ │ │  (80-100 tests)  │ │ │
        └─┴─┴─────────────────┴─┴─┘
```

| Layer | Count (target) | Speed | Runs on |
|-------|---------------|-------|---------|
| Unit | ~90 tests | < 5s total | Every push |
| Integration | ~25 tests | ~30s | Every push (via Docker) |
| E2E | ~3 scenarios | ~2min | `main` branch only |
| Contract | ~10 tests | ~5s | Every push |

---

## 4. Unit Tests

All unit tests live in `tests/unit/`. No network calls, no database. All external dependencies are mocked.

---

### 4.1 `tests/unit/test_db_manager.py`

These tests mock the SQLAlchemy `AsyncSession` to verify that `db_manager.py` functions build correct queries and handle data correctly.

#### `test_init_db_creates_tables`
- Mock `Base.metadata.create_all`
- Assert it is called once with the engine

#### `test_seed_officers_inserts_new_officers`
- Provide a roster dict with 2 officers
- Mock the session to return no existing officers
- Assert `session.add()` is called twice with the correct `Officer` objects

#### `test_seed_officers_updates_existing_officers`
- Provide a roster dict
- Mock the session to return one existing officer
- Assert the existing officer's fields are updated (not a new insert)

#### `test_seed_officers_preserves_removed_officers`
- Roster has O1 only; DB has O1 + O2
- Assert O2 is NOT deleted (preserved for history)

#### `test_ensure_channel_exists_inserts_new_channel`
- Mock `session.get()` returning `None`
- Assert `session.add()` called with correct `Channel` object

#### `test_ensure_channel_exists_skips_existing_channel`
- Mock `session.get()` returning an existing `Channel`
- Assert `session.add()` is NOT called

#### `test_load_officer_memory_returns_empty_string_when_no_data`
- Mock queries returning empty lists
- Assert return value is `""`

#### `test_load_officer_memory_formats_manual_notes`
- Mock notes query returning 2 notes (one pinned, one not)
- Assert output contains `**Manual Notes:**`
- Assert pinned note appears before unpinned note

#### `test_load_officer_memory_formats_mission_context`
- Mock notes returning empty, mission responses returning 3 items
- Assert output contains `**Recent Mission Context:**`
- Assert each mission brief and response is included

#### `test_load_officer_memory_respects_token_limit`
- Mock enough content to exceed `max_tokens=2000` limit
- Assert the returned string's estimated token count ≤ 2000

#### `test_load_officer_memory_combines_notes_and_missions`
- Mock both sources returning data
- Assert output contains both `**Manual Notes:**` and `**Recent Mission Context:**`

#### `test_add_manual_note_inserts_correctly`
- Assert `session.add()` called with a `ManualNote` with correct fields:
  - `officer_id`, `channel_id`, `note_content`, `created_by_user_id`

#### `test_clear_officer_memory_deletes_only_manual_notes`
- Mock a `DELETE` query
- Assert the WHERE clause targets `ManualNote` for the correct `(officer_id, channel_id)` pair
- Assert `MissionOfficerResponse` is NOT deleted

#### `test_get_channel_stats_returns_correct_counts`
- Mock count queries for each officer
- Assert returned dict has expected `{officer_id: {notes: N, missions: M}}` shape

#### `test_save_mission_creates_history_and_responses`
- Provide 2 officer results (1 success, 1 failure)
- Assert one `MissionHistory` and two `MissionOfficerResponse` records added
- Assert failed response has `success=False` and `error_message` set

#### `test_save_research_mission_stores_metadata`
- Assert `MissionHistory.extra_metadata` contains `mission_type`, `research_roles`, `web_search_enabled`

#### `test_save_mission_truncates_long_brief`
- Provide a brief longer than 1000 characters
- Assert saved `mission_brief` is ≤ 1000 characters

#### `test_save_mission_truncates_long_response`
- Provide a response longer than 2000 characters
- Assert saved `response_content` is ≤ 2000 characters

---

### 4.2 `tests/unit/test_officer_querying.py`

Tests for `query_officer`, `query_all_officers`, and `query_officer_with_research_role` using `respx` to intercept `httpx` calls.

#### `test_query_officer_returns_success_on_200`
- Mock OpenRouter returning `{"choices": [{"message": {"content": "Test response"}}]}`
- Assert result has `success=True` and `response="Test response"`

#### `test_query_officer_includes_officer_metadata`
- Assert result includes `officer_id`, `title`, `model`, `color`

#### `test_query_officer_injects_memory_into_system_prompt`
- Mock `load_officer_memory` returning `"### Your Memory..."` string
- Capture the HTTP request body
- Assert the system message content contains the memory string

#### `test_query_officer_returns_failure_on_api_error`
- Mock OpenRouter returning HTTP 500
- Assert result has `success=False` and `response` contains `"Error"`

#### `test_query_officer_returns_failure_on_timeout`
- Mock `httpx` raising `httpx.TimeoutException`
- Assert result has `success=False`

#### `test_query_officer_handles_tool_call_response`
- Mock OpenRouter returning a `tool_calls` message instead of text content
- Assert result contains warning about unimplemented search

#### `test_query_all_officers_runs_in_parallel`
- Mock all OpenRouter calls to succeed
- Assert all 4 officers in a class are queried (check call count)
- Use `asyncio` timing to confirm they ran concurrently (optional)

#### `test_query_all_officers_filters_by_capability_class`
- Call with `capability_class="Operational"`
- Assert only O5, O6, O7, O8 were queried (not all 16)

#### `test_query_all_officers_with_no_filter_queries_all`
- Call with `capability_class=None`
- Assert all active officers were queried

#### `test_query_all_officers_partial_failure_still_returns_all`
- Mock 1 officer failing, 3 succeeding
- Assert all 4 results are returned
- Assert failed one has `success=False`, others have `success=True`

#### `test_query_officer_with_research_role_injects_role_prompt`
- Use role_index=0 ("State-of-the-Art Researcher")
- Capture request body
- Assert system prompt contains the role's instruction string

#### `test_query_officer_with_research_role_adds_web_search_for_google`
- Officer model = `"google/gemini-2.0-flash-001"`
- `use_web_search=True`
- Assert payload includes `provider: {order: ["Google"]}`

#### `test_query_officer_with_research_role_skips_web_search_for_anthropic`
- Officer model = `"anthropic/claude-sonnet-4-5"`
- `use_web_search=True`
- Assert payload does NOT include `provider` field
- Assert response includes the "web search not available" disclaimer

#### `test_model_supports_web_search_perplexity`
- Assert `model_supports_web_search("perplexity/sonar")` returns `True`

#### `test_model_supports_web_search_google`
- Assert `model_supports_web_search("google/gemini-2.0-flash")` returns `True`

#### `test_model_supports_web_search_anthropic`
- Assert `model_supports_web_search("anthropic/claude-sonnet-4-5")` returns `False`

#### `test_model_supports_web_search_openai`
- Assert `model_supports_web_search("openai/gpt-4o")` returns `False`

---

### 4.3 `tests/unit/test_embed_building.py`

Tests for embed construction, sizing, and batching logic.

#### `test_calculate_embed_size_empty_embed`
- Create embed with no content
- Assert size is 0 (or minimal)

#### `test_calculate_embed_size_counts_all_fields`
- Create embed with title, description, 2 fields, footer
- Assert size equals sum of all string lengths

#### `test_send_embeds_in_batches_single_batch`
- Provide 3 small embeds (total < 5500 chars)
- Assert only one `followup.send` call is made

#### `test_send_embeds_in_batches_splits_large_set`
- Provide 3 embeds where each is ~2500 chars
- Assert two `followup.send` calls are made

#### `test_send_embeds_in_batches_view_on_last_only`
- Provide embeds requiring 2 batches
- Assert the `view` is only passed to the second (last) `followup.send`

#### `test_get_officer_color_uses_explicit_color`
- Officer dict has `"color": "0xff0000"`
- Assert returned color is `0xff0000`

#### `test_get_officer_color_falls_back_to_capability_class`
- Officer dict has no `color` field, `capability_class="Strategic"`
- Assert returned color is `0x9b59b6` (purple)

#### `test_filter_officers_by_capability_returns_correct_ids`
- Assert `filter_officers_by_capability("Tactical")` returns `["O9", "O10", "O11", "O12"]`

#### `test_filter_officers_by_capability_only_returns_active`
- Remove O10 from `active_roster`
- Assert O10 is not in the result

---

### 4.4 `tests/unit/test_research_markdown.py`

Tests for the markdown report generation function.

#### `test_generate_research_markdown_includes_topic`
- Assert output contains the research topic

#### `test_generate_research_markdown_includes_all_officer_responses`
- Provide 4 officer results
- Assert each officer's name and response appears in the output

#### `test_generate_research_markdown_includes_web_search_note`
- Pass `use_web_search=True`
- Assert output contains a note about web search being enabled

#### `test_generate_research_markdown_valid_markdown_structure`
- Assert output starts with `# ` (H1 heading)
- Assert output contains at least 4 `## ` (H2) sections

#### `test_generate_research_markdown_handles_failed_officers`
- Provide one officer result with `success=False`
- Assert the failed officer section shows error state rather than blank

---

### 4.5 `tests/unit/test_models.py`

Tests for SQLAlchemy model correctness (field types, relationships, defaults).

#### `test_officer_model_pk_is_string`
- Instantiate `Officer(officer_id="O1", ...)`
- Assert `officer_id` is stored as a string

#### `test_mission_history_truncates_brief_on_assignment`
- Test that the application-level truncation (in `db_manager.py`) produces ≤ 1000 chars

#### `test_channel_model_requires_bigint_id`
- Verify `channel_id` column is BigInteger (important for Discord snowflakes)

#### `test_manual_note_default_is_pinned_false`
- Create a `ManualNote` without specifying `is_pinned`
- Assert `is_pinned` defaults to `False`

---

## 5. Integration Tests

Integration tests run against a **real PostgreSQL instance** (via `testcontainers`). They test that the ORM, the database driver, and the schema work correctly together.

All integration tests live in `tests/integration/`.

### Fixtures

```python
# tests/integration/conftest.py

@pytest.fixture(scope="session")
async def postgres_container():
    """Spin up a PostgreSQL container for the entire test session."""
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest.fixture(scope="function")
async def db_session(postgres_container):
    """Create a fresh schema for each test, rolled back after."""
    engine = create_async_engine(postgres_container.get_connection_url())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

### Test Cases

#### `test_seed_officers_round_trip`
- Seed officers from a test roster dict
- Query the `officer` table
- Assert all officers are present with correct fields

#### `test_seed_officers_idempotent`
- Seed the same roster twice
- Assert officer count does not double

#### `test_ensure_channel_creates_and_retrieves`
- Call `ensure_channel_exists(123, "general", 456)`
- Query the `channel` table
- Assert the record exists with the correct values

#### `test_add_and_load_manual_note`
- Add a manual note for O1 in channel 100
- Call `load_officer_memory(100, "O1")`
- Assert the note content appears in the output

#### `test_pinned_note_appears_before_unpinned`
- Add one unpinned note, then one pinned note
- Call `load_officer_memory(...)`
- Assert pinned note appears first in output

#### `test_memory_is_channel_isolated`
- Add a note for O1 in channel 100
- Call `load_officer_memory(200, "O1")`  ← different channel
- Assert output is empty (no cross-channel bleed)

#### `test_clear_memory_removes_notes_but_not_missions`
- Add a manual note and a mission response for O1 in channel 100
- Call `clear_officer_memory(100, "O1")`
- Call `load_officer_memory(100, "O1")`
- Assert manual note is gone
- Assert mission context still appears

#### `test_save_mission_and_retrieve_in_memory`
- Save a mission with 2 officer responses
- Call `load_officer_memory(channel_id, officer_id)` for one of the officers
- Assert the mission brief and response appear in the memory context

#### `test_save_mission_cascade_delete`
- Save a mission
- Delete the `MissionHistory` record
- Assert associated `MissionOfficerResponse` records are also deleted

#### `test_get_channel_stats_accuracy`
- Add 2 notes for O1, 1 note for O2; save 3 missions with O1 responses
- Call `get_channel_stats(channel_id)`
- Assert `{O1: {notes: 2, missions: 3}, O2: {notes: 1, missions: 0}}`

#### `test_save_research_mission_metadata_stored`
- Save a research mission with `web_search_enabled=True` and role metadata
- Query `MissionHistory` directly
- Assert `extra_metadata` JSONB contains expected keys

#### `test_mission_brief_truncated_at_1000_chars`
- Save a mission with a 2000-character brief
- Query the saved record
- Assert `mission_brief` is exactly 1000 characters

#### `test_concurrent_missions_do_not_interfere`
- Concurrently save 5 missions with `asyncio.gather()`
- Assert all 5 are present in the database with distinct IDs

---

## 6. End-to-End Tests

E2E tests simulate real Discord interactions using a test bot token pointing at a **private Discord test server**. These are slow and require real credentials — they run only on the `main` branch.

> **Prerequisite:** A dedicated Discord test guild and bot with permissions. Store `DISCORD_TEST_TOKEN` and `DISCORD_TEST_GUILD_ID` as GitHub Secrets.

### Setup

```python
# tests/e2e/conftest.py
@pytest.fixture(scope="session")
async def test_bot():
    """Start the bot connected to the test guild."""
    bot = WarRoomBot()
    asyncio.create_task(bot.start(DISCORD_TEST_TOKEN))
    await asyncio.sleep(5)  # Wait for bot to connect
    yield bot
    await bot.close()
```

### Test Scenarios

#### `test_e2e_mission_command_responds`
1. Send `/mission brief:"Test mission for CI" capability_class:Support` to test channel
2. Wait up to 30 seconds for a response
3. Assert at least one embed appears in the channel
4. Assert embed has a non-empty description (officer responded)

#### `test_e2e_memory_add_persists_across_missions`
1. Send `/memory add O13 note:"Always use bullet points"`
2. Send `/mission brief:"Give me a summary" capability_class:Support`
3. Assert O13's response contains bullet points (manual inspection or heuristic)

#### `test_e2e_research_command_generates_report`
1. Send `/research topic:"Python async patterns" capability_class:Support use_web_search:False`
2. Assert 4 embeds appear with different role labels in footers
3. Click "Generate Report" button
4. Assert a `.md` file attachment appears in the next message

> **Note:** E2E tests validate the happy path only. They are not substitutes for unit tests — they exist to catch deployment-level breakage.

---

## 7. Contract Tests

Contract tests verify that our assumptions about external APIs (OpenRouter, Discord) remain valid, without making real network calls.

### 7.1 OpenRouter Response Contract

#### `test_openrouter_response_schema`
- Given a real-looking OpenRouter response fixture
- Assert `choices[0].message.content` is accessible and a string

#### `test_openrouter_tool_call_schema`
- Given a tool_calls response fixture
- Assert our parsing handles it without raising `KeyError`

#### `test_openrouter_error_response_schema`
- Given a 400/500 response fixture
- Assert our error handler extracts a readable message

### 7.2 Roster Config Contract

#### `test_roster_json_all_required_fields_present`
- Load `config/roster.json`
- For every officer in `active_roster`, assert:
  - `title`, `model`, `specialty`, `capability_class`, `system_prompt` all exist
  - `capability_class` is one of `["Strategic", "Operational", "Tactical", "Support"]`

#### `test_roster_json_no_duplicate_officer_ids`
- Assert no officer ID appears more than once

#### `test_roster_json_active_roster_ids_exist`
- Assert every ID in `active_roster` has a corresponding entry in `officers`

#### `test_roster_json_capability_class_has_exactly_4_officers_when_filtered`
- For each capability class, assert exactly 4 officers belong to it

#### `test_roster_json_is_valid_json`
- Attempt to parse `config/roster.json`
- Assert no `json.JSONDecodeError` is raised

---

## 8. GitHub Actions CI/CD Pipeline

### 8.1 Pipeline Overview

```
On: push to any branch, pull_request to main
  ├── Job: lint          (ruff, black --check)
  ├── Job: unit-tests    (pytest tests/unit/, no Docker)
  ├── Job: contract-tests (pytest tests/contract/)
  └── Job: integration-tests (pytest tests/integration/, Docker required)

On: push to main only
  └── Job: e2e-tests     (pytest tests/e2e/, requires Discord test guild)
```

### 8.2 Workflow File: `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: ["**"]
  pull_request:
    branches: [main]

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install linting tools
        run: pip install ruff black
      - name: Run ruff
        run: ruff check .
      - name: Run black (check mode)
        run: black --check .

  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Run unit tests
        run: pytest tests/unit/ tests/contract/ -v --cov=. --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
          flags: unit

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: atlas_user
          POSTGRES_PASSWORD: testpassword
          POSTGRES_DB: atlas_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      DATABASE_URL: postgresql+asyncpg://atlas_user:testpassword@localhost:5432/atlas_test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Run integration tests
        run: pytest tests/integration/ -v --cov=. --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
          flags: integration
```

### 8.3 E2E Workflow: `.github/workflows/e2e.yml`

```yaml
name: E2E Tests

on:
  push:
    branches: [main]

jobs:
  e2e:
    name: End-to-End Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: atlas_user
          POSTGRES_PASSWORD: testpassword
          POSTGRES_DB: atlas_e2e
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      DATABASE_URL: postgresql+asyncpg://atlas_user:testpassword@localhost:5432/atlas_e2e
      DISCORD_TOKEN: ${{ secrets.DISCORD_E2E_TOKEN }}
      OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
      DISCORD_TEST_GUILD_ID: ${{ secrets.DISCORD_TEST_GUILD_ID }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Run E2E tests
        run: pytest tests/e2e/ -v --timeout=60
```

### 8.4 Required GitHub Secrets

| Secret | Used By | Description |
|--------|---------|-------------|
| `DISCORD_E2E_TOKEN` | E2E workflow | Bot token for the test Discord server |
| `OPENROUTER_API_KEY` | E2E workflow | Real OpenRouter key (incurs cost) |
| `DISCORD_TEST_GUILD_ID` | E2E workflow | ID of the private test Discord server |
| `CODECOV_TOKEN` | Both workflows | For coverage reporting (optional) |

### 8.5 Branch Protection Rules (Recommended)

In GitHub → Settings → Branches → Add rule for `main`:
- [x] Require status checks to pass before merging
  - Required checks: `Lint`, `Unit Tests`, `Integration Tests`
- [x] Require branches to be up to date before merging
- [x] Require pull request reviews (1 approval)
- [x] Do not allow bypassing the above settings

---

## 9. Directory Structure

```
tests/
├── conftest.py                     # Shared fixtures (e.g., roster data, mock officer)
├── fixtures/
│   ├── roster_test.json            # Minimal 4-officer roster for testing
│   ├── openrouter_success.json     # Sample OpenRouter success response
│   ├── openrouter_tool_call.json   # Sample tool_calls response
│   └── openrouter_error.json       # Sample 500 error response
├── unit/
│   ├── conftest.py
│   ├── test_db_manager.py
│   ├── test_officer_querying.py
│   ├── test_embed_building.py
│   ├── test_research_markdown.py
│   └── test_models.py
├── integration/
│   ├── conftest.py                 # testcontainers PostgreSQL fixture
│   └── test_db_integration.py
├── contract/
│   ├── test_openrouter_contract.py
│   └── test_roster_contract.py
└── e2e/
    ├── conftest.py                 # Live bot fixture
    └── test_discord_e2e.py
```

---

## 10. Test Data & Fixtures

### Shared `conftest.py` (top-level)

```python
import pytest
import json

TEST_ROSTER = {
    "version": "1.0.0",
    "active_roster": ["T1", "T2", "T3", "T4"],
    "officers": {
        "T1": {
            "title": "Test Officer Alpha",
            "model": "anthropic/claude-3-haiku",
            "specialty": "Testing",
            "capability_class": "Support",
            "system_prompt": "You are a test officer.",
        },
        # ... T2, T3, T4
    }
}

@pytest.fixture
def test_roster():
    return TEST_ROSTER

@pytest.fixture
def mock_officer():
    return TEST_ROSTER["officers"]["T1"] | {"officer_id": "T1"}

@pytest.fixture
def openrouter_success_response():
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "This is a test response from the officer."
            }
        }]
    }

@pytest.fixture
def openrouter_tool_call_response():
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"function": {"name": "web_search"}}]
            }
        }]
    }
```

### `fixtures/roster_test.json`

A minimal valid roster used in contract tests to validate the schema without needing the real production roster.

---

## 11. Coverage Requirements

| Module | Minimum Coverage |
|--------|-----------------|
| `db_manager.py` | 90% |
| `bot.py` (pure functions) | 85% |
| `models/memory.py` | 80% |
| **Overall** | **80%** |

These thresholds are enforced in CI via:

```toml
# pyproject.toml
[tool.coverage.report]
fail_under = 80
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
]
```

Discord command handlers (`@tree.command`) are excluded from coverage requirements because they require a live Discord connection. The business logic they call (querying, saving, embed-building) is covered by unit tests.

---

## 12. Implementation Roadmap

### Sprint 1 — Foundation (Day 1–2)

- [ ] Add `pyproject.toml` with `[tool.pytest.ini_options]` and dev dependencies
- [ ] Create `requirements-dev.txt`
- [ ] Create `tests/` directory structure with placeholder `conftest.py` files
- [ ] Write shared fixtures in `tests/conftest.py`
- [ ] Add `.github/workflows/ci.yml` (lint + unit test jobs, no tests yet)
- [ ] Verify the empty test suite passes in CI

### Sprint 2 — Unit Tests: Database (Day 3–5)

- [ ] Write all `tests/unit/test_db_manager.py` tests (mock-only)
- [ ] Refactor `db_manager.py` if needed to make functions testable (dependency injection for session)
- [ ] Reach ≥ 90% coverage on `db_manager.py`

### Sprint 3 — Unit Tests: Bot Logic (Day 6–8)

- [ ] Write all `tests/unit/test_officer_querying.py` tests using `respx`
- [ ] Write `tests/unit/test_embed_building.py`
- [ ] Write `tests/unit/test_research_markdown.py`
- [ ] Write `tests/unit/test_models.py`

### Sprint 4 — Contract & Integration Tests (Day 9–11)

- [ ] Write `tests/contract/test_roster_contract.py`
- [ ] Write `tests/contract/test_openrouter_contract.py`
- [ ] Add `integration-tests` job to CI with PostgreSQL service
- [ ] Write all `tests/integration/test_db_integration.py` tests

### Sprint 5 — E2E & Branch Protection (Day 12–14)

- [ ] Set up private Discord test server
- [ ] Add GitHub Secrets for E2E credentials
- [ ] Write `tests/e2e/test_discord_e2e.py` (3 scenarios)
- [ ] Add `.github/workflows/e2e.yml`
- [ ] Configure branch protection on `main`
- [ ] Add Codecov badge to README

### Ongoing

- [ ] Add a test for every new feature before merging
- [ ] Update coverage thresholds as the codebase matures
- [ ] Add `pytest-xdist` for parallel test execution when the suite grows
- [ ] Consider snapshot testing for embed output (assert embed structure hasn't changed)

---

## Appendix: Refactoring Notes for Testability

Some current patterns in `bot.py` will need minor adjustments to be cleanly testable:

1. **Extract pure functions** — Functions like `generate_research_markdown()` and `calculate_embed_size()` are already pure (no side effects). Keep them that way.

2. **Dependency-inject the HTTP client** — `query_officer()` currently creates its own `httpx.AsyncClient`. Accept it as a parameter (or use a module-level client) so tests can inject a `respx`-mocked client.

3. **Dependency-inject roster config** — Several functions read from the module-level `officers` dict loaded at import time. Accept this as a parameter to allow tests to pass `TEST_ROSTER` instead.

4. **Separate command handlers from logic** — The slash command callbacks do everything: DB operations, API calls, embed construction, and send. Consider extracting the core logic into standalone async functions that the command callbacks call. This lets you test the logic without a live Discord connection.

   Example refactor:
   ```python
   # Testable logic function
   async def execute_mission(brief, capability_class, channel_id, user_id) -> list[dict]:
       results = await query_all_officers(brief, capability_class, channel_id)
       await save_mission(channel_id, brief, user_id, capability_class, results)
       return results

   # Thin command handler
   @tree.command()
   async def mission(interaction, brief, capability_class=None):
       await interaction.response.defer()
       results = await execute_mission(brief, capability_class, interaction.channel_id, interaction.user.id)
       embeds = [build_officer_embed(r) for r in results]
       await send_embeds_in_batches(interaction, embeds, WarRoomView(results))
   ```

5. **Centralize config loading** — Move roster loading into a `load_roster(path)` function so tests can point it at `fixtures/roster_test.json`.

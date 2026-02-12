"""
E2E test fixtures — requires a live Discord connection and real credentials.
Only runs on the main branch via the e2e GitHub Actions workflow.

Prerequisites:
  - DISCORD_E2E_TOKEN: Bot token for the test Discord server
  - DISCORD_TEST_GUILD_ID: ID of the private test server
  - OPENROUTER_API_KEY: Real OpenRouter key
  - DATABASE_URL: PostgreSQL connection string
"""
import os

import pytest
import pytest_asyncio

# E2E tests are skipped entirely if credentials are not present.
# This prevents accidental runs in local/unit test environments.
DISCORD_E2E_TOKEN = os.getenv("DISCORD_E2E_TOKEN")
DISCORD_TEST_GUILD_ID = os.getenv("DISCORD_TEST_GUILD_ID")

if not DISCORD_E2E_TOKEN or not DISCORD_TEST_GUILD_ID:
    pytest.skip(
        "E2E credentials not set (DISCORD_E2E_TOKEN, DISCORD_TEST_GUILD_ID). "
        "Skipping all E2E tests.",
        allow_module_level=True,
    )


@pytest_asyncio.fixture(scope="session")
async def test_guild_id():
    return int(DISCORD_TEST_GUILD_ID)

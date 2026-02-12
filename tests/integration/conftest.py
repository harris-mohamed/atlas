"""
Integration test fixtures.

Uses a real PostgreSQL instance pointed to by DATABASE_URL.

In CI:   automatically provided by the GitHub Actions `services:` postgres sidecar.
Locally: run `docker compose up db -d` first, then run tests.

Tests are skipped automatically if DATABASE_URL is not set.
Each test function gets a completely fresh schema (drop_all → create_all).
"""
import os
import pytest
import pytest_asyncio

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    pytest.skip(
        "DATABASE_URL not set — skipping integration tests. "
        "Run `docker compose up db -d` and set DATABASE_URL to run locally.",
        allow_module_level=True,
    )


@pytest_asyncio.fixture(autouse=True)
async def clean_schema():
    """
    Drop and recreate all tables before every integration test.
    This gives each test a guaranteed empty database.

    engine.dispose() is called before connecting to clear any stale pool
    connections from the previous test's event loop (pytest-asyncio creates
    a new loop per test function by default).
    """
    from db_manager import engine
    from models.memory import Base

    await engine.dispose()  # clear stale pool connections from previous loop

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

"""
Unit test fixtures — all external dependencies are mocked.
No database, no network calls.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_db_session(mocker):
    """A mock SQLAlchemy AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock(return_value=None)
    return session


@pytest.fixture
def mock_async_session_maker(mock_db_session):
    """A mock async_sessionmaker that yields the mock session via context manager."""
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    maker = MagicMock()
    maker.return_value = ctx
    return maker


@pytest.fixture
def mock_httpx_client():
    """A mock httpx.AsyncClient."""
    client = AsyncMock()
    return client

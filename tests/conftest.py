"""
Shared fixtures available to all test layers.
"""
import json
import pathlib
import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Roster fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_roster():
    """A minimal 4-officer roster used in place of the real config/roster.json."""
    with open(FIXTURES_DIR / "roster_test.json") as f:
        return json.load(f)


@pytest.fixture
def test_officers(test_roster):
    """The officers dict from the test roster."""
    return test_roster["officers"]


@pytest.fixture
def test_active_roster(test_roster):
    """The active_roster list from the test roster."""
    return test_roster["active_roster"]


@pytest.fixture
def mock_officer():
    """A single officer dict (T1) with officer_id included, for use in unit tests."""
    return {
        "officer_id": "T1",
        "title": "Test Officer Alpha",
        "model": "anthropic/claude-3-haiku",
        "specialty": "Unit Testing",
        "capability_class": "Support",
        "color": "0xaabbcc",
        "system_prompt": "You are Test Officer Alpha. Respond concisely for testing purposes.",
    }


@pytest.fixture
def mock_officer_no_color():
    """An officer dict without an explicit color — falls back to capability_class color."""
    return {
        "officer_id": "T2",
        "title": "Test Officer Beta",
        "model": "openai/gpt-4o-mini",
        "specialty": "Integration Testing",
        "capability_class": "Support",
        "system_prompt": "You are Test Officer Beta.",
    }


# ---------------------------------------------------------------------------
# OpenRouter API response fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def openrouter_success_response():
    """A valid OpenRouter chat completion response."""
    with open(FIXTURES_DIR / "openrouter_success.json") as f:
        return json.load(f)


@pytest.fixture
def openrouter_tool_call_response():
    """An OpenRouter response where the model attempted a tool call."""
    with open(FIXTURES_DIR / "openrouter_tool_call.json") as f:
        return json.load(f)


@pytest.fixture
def openrouter_error_response():
    """An OpenRouter 500 error response body."""
    with open(FIXTURES_DIR / "openrouter_error.json") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Shared channel / user constants
# ---------------------------------------------------------------------------

TEST_CHANNEL_ID = 111222333444555666
TEST_GUILD_ID = 999888777666555444
TEST_USER_ID = 123456789012345678
TEST_CHANNEL_NAME = "test-channel"


# ---------------------------------------------------------------------------
# Mock officer query result helpers
# ---------------------------------------------------------------------------

def make_officer_result(
    officer_id: str = "T1",
    title: str = "Test Officer Alpha",
    model: str = "anthropic/claude-3-haiku",
    response: str = "This is a test response.",
    success: bool = True,
    color: int = 0xaabbcc,
    research_role: str = None,
    error: str = None,
) -> dict:
    """Build a mock officer query result dict matching the shape returned by query_officer()."""
    result = {
        "officer_id": officer_id,
        "title": title,
        "model": model,
        "response": response if success else f"Error: {error or 'Unknown error'}",
        "success": success,
        "color": color,
    }
    if research_role:
        result["research_role"] = research_role
    return result


@pytest.fixture
def mock_officer_results():
    """Four successful officer results for a Support-class mission."""
    return [
        make_officer_result("T1", response="Alpha's analysis here."),
        make_officer_result("T2", title="Test Officer Beta", response="Beta's analysis here."),
        make_officer_result("T3", title="Test Officer Gamma", response="Gamma's analysis here."),
        make_officer_result("T4", title="Test Officer Delta", response="Delta's analysis here."),
    ]


@pytest.fixture
def mock_officer_results_with_failure(mock_officer_results):
    """Officer results where T3 has failed."""
    results = list(mock_officer_results)
    results[2] = make_officer_result(
        "T3", title="Test Officer Gamma", success=False, error="Model unavailable"
    )
    return results

"""
Contract test fixtures — validates our assumptions about external schemas
(roster.json, OpenRouter API shapes) without making real network calls.
"""
import json
import pathlib
import pytest

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def production_roster():
    """The real config/roster.json from the project."""
    with open(PROJECT_ROOT / "config" / "roster.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def production_officers(production_roster):
    return production_roster["officers"]


@pytest.fixture(scope="session")
def production_active_roster(production_roster):
    return production_roster["active_roster"]

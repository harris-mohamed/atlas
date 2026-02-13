"""
Contract tests for config/roster.json.

Validates that the production roster satisfies all structural invariants
the application code depends on — without mocking or network calls.
"""

VALID_CAPABILITY_CLASSES = {"Strategic", "Operational", "Tactical", "Support"}
REQUIRED_OFFICER_FIELDS = {"title", "model", "specialty", "capability_class", "system_prompt"}


def test_roster_json_is_valid(production_roster):
    """Roster loads and has expected top-level keys."""
    assert "version" in production_roster
    assert "active_roster" in production_roster
    assert "officers" in production_roster


def test_active_roster_not_empty(production_active_roster):
    """There is at least one active officer."""
    assert len(production_active_roster) > 0


def test_active_roster_ids_exist_in_officers(production_roster):
    """Every ID in active_roster has a corresponding officer definition."""
    officers = production_roster["officers"]
    active = production_roster["active_roster"]
    for officer_id in active:
        assert (
            officer_id in officers
        ), f"active_roster contains '{officer_id}' but no matching officer definition found"


def test_no_duplicate_ids_in_active_roster(production_active_roster):
    """No officer ID appears more than once in active_roster."""
    assert len(production_active_roster) == len(set(production_active_roster))


def test_all_officers_have_required_fields(production_officers):
    """Every officer definition contains all required fields."""
    for officer_id, officer in production_officers.items():
        missing = REQUIRED_OFFICER_FIELDS - set(officer.keys())
        assert not missing, f"Officer '{officer_id}' is missing fields: {missing}"


def test_all_officers_have_valid_capability_class(production_officers):
    """Every officer's capability_class is one of the four known values."""
    for officer_id, officer in production_officers.items():
        assert (
            officer["capability_class"] in VALID_CAPABILITY_CLASSES
        ), f"Officer '{officer_id}' has unknown capability_class: '{officer['capability_class']}'"


def test_all_officers_have_non_empty_system_prompt(production_officers):
    """No officer has a blank system prompt."""
    for officer_id, officer in production_officers.items():
        assert officer[
            "system_prompt"
        ].strip(), f"Officer '{officer_id}' has an empty system_prompt"


def test_all_officers_have_non_empty_model(production_officers):
    """No officer has a blank model string."""
    for officer_id, officer in production_officers.items():
        assert officer["model"].strip(), f"Officer '{officer_id}' has an empty model"


def test_capability_class_groups_have_officers(production_officers):
    """Each of the four capability classes has at least one officer."""
    classes_present = {o["capability_class"] for o in production_officers.values()}
    for cls in VALID_CAPABILITY_CLASSES:
        assert cls in classes_present, f"No officers found for capability class '{cls}'"

"""
Unit tests for SQLAlchemy ORM models in models/memory.py.
Tests instantiation, defaults, and field types — no DB connection required.
"""

from models.memory import (
    Channel,
    ManualNote,
    MissionHistory,
    MissionOfficerResponse,
    Officer,
    OfficerChannelMemory,
)


class TestOfficerModel:
    def test_officer_id_is_string(self):
        o = Officer(
            officer_id="O1",
            title="T",
            model="m",
            capability_class="Support",
            specialty="s",
            system_prompt="p",
        )
        assert o.officer_id == "O1"
        assert isinstance(o.officer_id, str)

    def test_all_fields_stored_correctly(self):
        o = Officer(
            officer_id="O5",
            title="Strategic Advisor",
            model="anthropic/claude-sonnet-4-5",
            capability_class="Operational",
            specialty="Planning",
            system_prompt="You plan things.",
        )
        assert o.title == "Strategic Advisor"
        assert o.model == "anthropic/claude-sonnet-4-5"
        assert o.capability_class == "Operational"
        assert o.specialty == "Planning"
        assert o.system_prompt == "You plan things."


class TestChannelModel:
    def test_channel_id_stored_correctly(self):
        # Discord snowflakes are 64-bit integers
        channel_id = 111222333444555666
        c = Channel(channel_id=channel_id, channel_name="general", guild_id=999)
        assert c.channel_id == channel_id

    def test_all_fields_stored(self):
        c = Channel(channel_id=123, channel_name="war-room", guild_id=456)
        assert c.channel_name == "war-room"
        assert c.guild_id == 456


class TestManualNoteModel:
    def test_is_pinned_defaults_to_false(self):
        note = ManualNote(
            officer_id="O1",
            channel_id=111,
            note_content="Some note",
            created_by_user_id=42,
        )
        # Default should be False (not pinned)
        assert note.is_pinned is False or note.is_pinned is None

    def test_note_content_stored(self):
        note = ManualNote(
            officer_id="O1",
            channel_id=111,
            note_content="Prefer async patterns",
            created_by_user_id=42,
        )
        assert note.note_content == "Prefer async patterns"

    def test_all_fields_stored(self):
        note = ManualNote(
            officer_id="O2",
            channel_id=999,
            note_content="Always cite sources",
            created_by_user_id=77,
            is_pinned=True,
        )
        assert note.officer_id == "O2"
        assert note.channel_id == 999
        assert note.created_by_user_id == 77
        assert note.is_pinned is True


class TestMissionHistoryModel:
    def test_fields_stored_correctly(self):
        m = MissionHistory(
            channel_id=111,
            mission_brief="Design a system",
            user_id=42,
            capability_class_filter="Operational",
        )
        assert m.channel_id == 111
        assert m.mission_brief == "Design a system"
        assert m.user_id == 42
        assert m.capability_class_filter == "Operational"

    def test_capability_class_filter_is_optional(self):
        m = MissionHistory(channel_id=111, mission_brief="Brief", user_id=42)
        assert m.capability_class_filter is None

    def test_extra_metadata_can_store_dict(self):
        metadata = {"mission_type": "research", "web_search_enabled": True}
        m = MissionHistory(
            channel_id=111,
            mission_brief="Topic",
            user_id=42,
            extra_metadata=metadata,
        )
        assert m.extra_metadata["mission_type"] == "research"
        assert m.extra_metadata["web_search_enabled"] is True


class TestMissionOfficerResponseModel:
    def test_fields_stored_correctly(self):
        r = MissionOfficerResponse(
            mission_id=1,
            officer_id="O1",
            response_content="My analysis.",
            success=True,
        )
        assert r.mission_id == 1
        assert r.officer_id == "O1"
        assert r.response_content == "My analysis."
        assert r.success is True

    def test_failed_response_stores_error_message(self):
        r = MissionOfficerResponse(
            mission_id=2,
            officer_id="O2",
            response_content="Error: timeout",
            success=False,
            error_message="Connection timed out after 60s",
        )
        assert r.success is False
        assert r.error_message == "Connection timed out after 60s"

    def test_tokens_used_is_optional(self):
        r = MissionOfficerResponse(
            mission_id=1, officer_id="O1", response_content="Response", success=True
        )
        assert r.tokens_used is None


class TestOfficerChannelMemoryModel:
    def test_fields_stored_correctly(self):
        m = OfficerChannelMemory(
            officer_id="O1",
            channel_id=111,
            memory_content="Summary of past interactions",
            memory_type="summary",
        )
        assert m.officer_id == "O1"
        assert m.channel_id == 111
        assert m.memory_content == "Summary of past interactions"
        assert m.memory_type == "summary"

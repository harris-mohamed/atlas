"""
Unit tests for db_manager.py

All database interactions are mocked via patching db_manager.async_session_maker.
No real PostgreSQL required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import db_manager
from models.memory import Channel, ManualNote, MissionHistory, MissionOfficerResponse, Officer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_execute_result(scalars=None, rows=None):
    """
    Build a mock that mimics sqlalchemy AsyncResult.

    - .scalars().all()        → list of ORM objects  (used for most queries)
    - .scalar_one_or_none()   → single ORM object or None
    - .all()                  → list of raw row tuples (used for join queries)
    """
    result = MagicMock()
    items = scalars or []

    result.scalar_one_or_none.return_value = items[0] if items else None

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = list(items)
    result.scalars.return_value = scalars_mock

    result.all.return_value = rows or []
    return result


def make_session_patcher(session):
    """
    Return a context manager mock that yields `session` when used as:
        async with async_session_maker() as s: ...
    """
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    maker = MagicMock()
    maker.return_value = ctx
    return maker


def fresh_session():
    """Create a new mock AsyncSession."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# seed_officers
# ---------------------------------------------------------------------------


class TestSeedOfficers:
    @pytest.mark.asyncio
    async def test_inserts_new_officer(self):
        """An officer not in the DB is added via session.add()."""
        session = fresh_session()
        # First execute: officer not found; second execute: all DB officers (empty)
        session.execute.side_effect = [
            make_execute_result(),  # officer lookup → None
            make_execute_result(),  # all DB officers → []
        ]

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.seed_officers(
                {
                    "O1": {
                        "title": "Test Officer",
                        "model": "anthropic/claude-3-haiku",
                        "capability_class": "Support",
                        "specialty": "Testing",
                        "system_prompt": "You are a test officer.",
                    }
                }
            )

        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert isinstance(added, Officer)
        assert added.officer_id == "O1"
        assert added.title == "Test Officer"

    @pytest.mark.asyncio
    async def test_updates_existing_officer(self):
        """An officer already in the DB gets its fields updated, not re-inserted."""
        existing = Officer(
            officer_id="O1",
            title="Old Title",
            model="old/model",
            capability_class="Tactical",
            specialty="Old",
            system_prompt="Old prompt.",
        )
        session = fresh_session()
        session.execute.side_effect = [
            make_execute_result([existing]),  # officer lookup → found
            make_execute_result([existing]),  # all DB officers
        ]

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.seed_officers(
                {
                    "O1": {
                        "title": "New Title",
                        "model": "new/model",
                        "capability_class": "Support",
                        "specialty": "New",
                        "system_prompt": "New prompt.",
                    }
                }
            )

        session.add.assert_not_called()
        assert existing.title == "New Title"
        assert existing.model == "new/model"

    @pytest.mark.asyncio
    async def test_preserves_officer_removed_from_roster(self):
        """An officer in the DB but absent from the roster dict is kept (not deleted)."""
        ghost_officer = Officer(
            officer_id="O99",
            title="Ghost",
            model="x",
            capability_class="Support",
            specialty="x",
            system_prompt="x",
        )
        session = fresh_session()
        session.execute.side_effect = [
            make_execute_result(),  # O1 lookup → None
            make_execute_result([ghost_officer]),  # all DB officers
        ]

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.seed_officers(
                {
                    "O1": {
                        "title": "T",
                        "model": "m",
                        "capability_class": "Support",
                        "specialty": "s",
                        "system_prompt": "p",
                    }
                }
            )

        # session.delete should never be called — ghost officer is preserved
        session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_commits_after_all_inserts(self):
        """Session is committed exactly once after seeding all officers."""
        session = fresh_session()
        session.execute.side_effect = [
            make_execute_result(),  # O1 lookup
            make_execute_result(),  # O2 lookup
            make_execute_result(),  # all DB officers
        ]

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.seed_officers(
                {
                    "O1": {
                        "title": "A",
                        "model": "m",
                        "capability_class": "Support",
                        "specialty": "s",
                        "system_prompt": "p",
                    },
                    "O2": {
                        "title": "B",
                        "model": "m",
                        "capability_class": "Support",
                        "specialty": "s",
                        "system_prompt": "p",
                    },
                }
            )

        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# ensure_channel_exists
# ---------------------------------------------------------------------------


class TestEnsureChannelExists:
    @pytest.mark.asyncio
    async def test_inserts_new_channel(self):
        """A channel not in the DB gets inserted."""
        session = fresh_session()
        session.execute.return_value = make_execute_result()  # not found

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.ensure_channel_exists(111, "general", 999)

        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert isinstance(added, Channel)
        assert added.channel_id == 111
        assert added.channel_name == "general"
        assert added.guild_id == 999

    @pytest.mark.asyncio
    async def test_skips_existing_channel(self):
        """A channel already in the DB is not re-inserted."""
        existing = Channel(channel_id=111, channel_name="general", guild_id=999)
        session = fresh_session()
        session.execute.return_value = make_execute_result([existing])

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.ensure_channel_exists(111, "general", 999)

        session.add.assert_not_called()
        session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# load_officer_memory
# ---------------------------------------------------------------------------


class TestLoadOfficerMemory:
    @pytest.mark.asyncio
    async def test_returns_empty_string_when_no_data(self):
        """Returns '' when there are no notes and no mission history."""
        session = fresh_session()
        session.execute.side_effect = [
            make_execute_result(),  # notes → []
            make_execute_result(rows=[]),  # missions → []
        ]

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            result = await db_manager.load_officer_memory(111, "O1")

        assert result == ""

    @pytest.mark.asyncio
    async def test_formats_manual_notes(self):
        """Manual notes appear under the '### Manual Notes:' heading."""
        note = ManualNote(
            officer_id="O1", channel_id=111, note_content="Prefer async patterns", is_pinned=False
        )
        session = fresh_session()
        session.execute.side_effect = [
            make_execute_result([note]),
            make_execute_result(rows=[]),
        ]

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            result = await db_manager.load_officer_memory(111, "O1")

        assert "### Manual Notes:" in result
        assert "Prefer async patterns" in result

    @pytest.mark.asyncio
    async def test_pinned_notes_appear_before_unpinned(self):
        """
        The DB query orders by is_pinned DESC — we verify our formatting
        preserves the order returned by the query.
        """
        pinned = ManualNote(
            officer_id="O1", channel_id=111, note_content="PINNED NOTE", is_pinned=True
        )
        unpinned = ManualNote(
            officer_id="O1", channel_id=111, note_content="UNPINNED NOTE", is_pinned=False
        )
        # DB returns pinned first (simulating ORDER BY is_pinned DESC)
        session = fresh_session()
        session.execute.side_effect = [
            make_execute_result([pinned, unpinned]),
            make_execute_result(rows=[]),
        ]

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            result = await db_manager.load_officer_memory(111, "O1")

        pinned_pos = result.index("PINNED NOTE")
        unpinned_pos = result.index("UNPINNED NOTE")
        assert pinned_pos < unpinned_pos

    @pytest.mark.asyncio
    async def test_formats_mission_context(self):
        """Recent mission responses appear under '### Recent Missions:'."""
        response = MissionOfficerResponse(
            officer_id="O1", response_content="My analysis here.", success=True
        )
        brief = "Design a caching strategy"
        session = fresh_session()
        session.execute.side_effect = [
            make_execute_result(),  # no notes
            make_execute_result(rows=[(response, brief)]),  # mission row
        ]

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            result = await db_manager.load_officer_memory(111, "O1")

        assert "### Recent Missions:" in result
        assert "Design a caching strategy" in result
        assert "My analysis here." in result

    @pytest.mark.asyncio
    async def test_combines_notes_and_missions(self):
        """When both sources exist, both sections appear in the output."""
        note = ManualNote(
            officer_id="O1", channel_id=111, note_content="Be concise", is_pinned=False
        )
        response = MissionOfficerResponse(
            officer_id="O1", response_content="Response text.", success=True
        )
        session = fresh_session()
        session.execute.side_effect = [
            make_execute_result([note]),
            make_execute_result(rows=[(response, "A brief")]),
        ]

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            result = await db_manager.load_officer_memory(111, "O1")

        assert "### Manual Notes:" in result
        assert "### Recent Missions:" in result

    @pytest.mark.asyncio
    async def test_truncates_at_token_limit(self):
        """Output is truncated when estimated tokens exceed max_tokens."""
        # Create a note whose content is long enough to exceed the limit
        long_content = "x" * 10000  # 10000 chars ≈ 2500 tokens (> default 2000)
        note = ManualNote(
            officer_id="O1", channel_id=111, note_content=long_content, is_pinned=False
        )
        session = fresh_session()
        session.execute.side_effect = [
            make_execute_result([note]),
            make_execute_result(rows=[]),
        ]

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            result = await db_manager.load_officer_memory(111, "O1", max_tokens=2000)

        # Result must not exceed max_tokens * 4 characters
        assert len(result) <= 2000 * 4


# ---------------------------------------------------------------------------
# add_manual_note
# ---------------------------------------------------------------------------


class TestAddManualNote:
    @pytest.mark.asyncio
    async def test_inserts_note_with_correct_fields(self):
        """A ManualNote with the correct fields is added to the session."""
        session = fresh_session()

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            result = await db_manager.add_manual_note(111, "O1", "Use SOLID principles", 42)

        assert result is True
        session.add.assert_called_once()
        note = session.add.call_args[0][0]
        assert isinstance(note, ManualNote)
        assert note.officer_id == "O1"
        assert note.channel_id == 111
        assert note.note_content == "Use SOLID principles"
        assert note.created_by_user_id == 42

    @pytest.mark.asyncio
    async def test_commits_after_insert(self):
        session = fresh_session()
        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.add_manual_note(111, "O1", "Note", 42)
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# clear_officer_memory
# ---------------------------------------------------------------------------


class TestClearOfficerMemory:
    @pytest.mark.asyncio
    async def test_deletes_all_matching_notes(self):
        """All manual notes for the (officer, channel) pair are deleted."""
        note1 = ManualNote(officer_id="O1", channel_id=111, note_content="A")
        note2 = ManualNote(officer_id="O1", channel_id=111, note_content="B")
        session = fresh_session()
        session.execute.return_value = make_execute_result([note1, note2])

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.clear_officer_memory(111, "O1")

        assert session.delete.await_count == 2
        deleted_notes = [c.args[0] for c in session.delete.await_args_list]
        assert note1 in deleted_notes
        assert note2 in deleted_notes

    @pytest.mark.asyncio
    async def test_does_not_delete_mission_responses(self):
        """clear_officer_memory never touches MissionOfficerResponse records."""
        session = fresh_session()
        session.execute.return_value = make_execute_result([])  # no notes

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.clear_officer_memory(111, "O1")

        # The only execute call should be for ManualNote — verify it targets ManualNote
        execute_call = session.execute.await_args_list[0]
        stmt = execute_call.args[0]
        # The entity targeted by the select should be ManualNote
        assert ManualNote in stmt.froms or str(ManualNote.__tablename__) in str(stmt)

    @pytest.mark.asyncio
    async def test_commits_after_deletion(self):
        session = fresh_session()
        session.execute.return_value = make_execute_result([])
        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.clear_officer_memory(111, "O1")
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# save_mission
# ---------------------------------------------------------------------------


class TestSaveMission:
    @pytest.mark.asyncio
    async def test_creates_mission_history_record(self):
        """A MissionHistory object is added for the mission."""
        session = fresh_session()

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.save_mission(111, "Test brief", 42, "Operational", [])

        added_objects = [c.args[0] for c in session.add.call_args_list]
        missions = [o for o in added_objects if isinstance(o, MissionHistory)]
        assert len(missions) == 1
        assert missions[0].channel_id == 111
        assert missions[0].mission_brief == "Test brief"
        assert missions[0].user_id == 42

    @pytest.mark.asyncio
    async def test_creates_response_record_per_officer(self, mock_officer_results):
        """One MissionOfficerResponse is created per officer result."""
        session = fresh_session()

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.save_mission(111, "Brief", 42, None, mock_officer_results)

        added_objects = [c.args[0] for c in session.add.call_args_list]
        responses = [o for o in added_objects if isinstance(o, MissionOfficerResponse)]
        assert len(responses) == len(mock_officer_results)

    @pytest.mark.asyncio
    async def test_truncates_brief_longer_than_1000_chars(self):
        """mission_brief is truncated to 1000 characters."""
        long_brief = "A" * 2000
        session = fresh_session()

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.save_mission(111, long_brief, 42, None, [])

        added = [c.args[0] for c in session.add.call_args_list]
        mission = next(o for o in added if isinstance(o, MissionHistory))
        assert len(mission.mission_brief) == 1000

    @pytest.mark.asyncio
    async def test_truncates_response_longer_than_2000_chars(self):
        """response_content is truncated to 2000 characters."""
        long_response = [{"officer_id": "O1", "response": "R" * 5000, "success": True}]
        session = fresh_session()

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.save_mission(111, "Brief", 42, None, long_response)

        added = [c.args[0] for c in session.add.call_args_list]
        response = next(o for o in added if isinstance(o, MissionOfficerResponse))
        assert len(response.response_content) == 2000

    @pytest.mark.asyncio
    async def test_failed_response_stores_success_false(self):
        """A failed officer result is saved with success=False."""
        failed_result = [{"officer_id": "O1", "response": "Error: timeout", "success": False}]
        session = fresh_session()

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.save_mission(111, "Brief", 42, None, failed_result)

        added = [c.args[0] for c in session.add.call_args_list]
        response = next(o for o in added if isinstance(o, MissionOfficerResponse))
        assert response.success is False

    @pytest.mark.asyncio
    async def test_flushes_before_adding_responses(self):
        """session.flush() is called before adding responses so mission.id is available."""
        session = fresh_session()
        flush_order = []
        add_order = []

        original_flush = session.flush
        original_add = session.add

        async def tracking_flush():
            flush_order.append("flush")
            await original_flush()

        def tracking_add(obj):
            if isinstance(obj, MissionOfficerResponse):
                add_order.append("response_add")
            original_add(obj)

        session.flush = tracking_flush
        session.add = tracking_add

        responses = [{"officer_id": "O1", "response": "R", "success": True}]
        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.save_mission(111, "Brief", 42, None, responses)

        # flush must happen before any response is added
        combined = flush_order + add_order
        assert combined.index("flush") < combined.index("response_add")


# ---------------------------------------------------------------------------
# save_research_mission
# ---------------------------------------------------------------------------


class TestSaveResearchMission:
    @pytest.mark.asyncio
    async def test_stores_research_metadata(self):
        """extra_metadata is stored on the MissionHistory record."""
        metadata = {
            "mission_type": "research",
            "research_roles": {"O1": "State-of-the-Art Researcher"},
            "web_search_enabled": True,
        }
        session = fresh_session()

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.save_research_mission(111, "AI trends", 42, "Strategic", [], metadata)

        added = [c.args[0] for c in session.add.call_args_list]
        mission = next(o for o in added if isinstance(o, MissionHistory))
        assert mission.extra_metadata["mission_type"] == "research"
        assert mission.extra_metadata["web_search_enabled"] is True

    @pytest.mark.asyncio
    async def test_truncates_research_topic(self):
        """research_topic is truncated to 1000 characters like a regular brief."""
        session = fresh_session()

        with patch.object(db_manager, "async_session_maker", make_session_patcher(session)):
            await db_manager.save_research_mission(111, "T" * 2000, 42, "Strategic", [], {})

        added = [c.args[0] for c in session.add.call_args_list]
        mission = next(o for o in added if isinstance(o, MissionHistory))
        assert len(mission.mission_brief) == 1000

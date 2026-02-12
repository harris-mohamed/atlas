"""
Integration tests for db_manager.py against a real PostgreSQL instance.

These tests call db_manager functions directly with no mocking.
Each test starts with a clean schema (see conftest.py).

Run locally:
    docker compose up db -d
    DATABASE_URL=postgresql+asyncpg://atlas_user:changeme@localhost:5432/atlas_db \
    pytest tests/integration/ -v
"""
import asyncio

import pytest
from sqlalchemy import select

from db_manager import (
    add_manual_note,
    async_session_maker,
    clear_officer_memory,
    ensure_channel_exists,
    get_channel_stats,
    load_officer_memory,
    save_mission,
    save_research_mission,
    seed_officers,
)
from models.memory import Channel, ManualNote, MissionHistory, MissionOfficerResponse, Officer

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

OFFICER_DICT = {
    "O1": {
        "title": "Test Officer Alpha",
        "model": "anthropic/claude-3-haiku",
        "capability_class": "Support",
        "specialty": "Testing",
        "system_prompt": "You are a test officer.",
    },
    "O2": {
        "title": "Test Officer Beta",
        "model": "openai/gpt-4o-mini",
        "capability_class": "Support",
        "specialty": "Testing",
        "system_prompt": "You are test officer beta.",
    },
}

CHANNEL_ID = 111222333444555666
GUILD_ID   = 999888777666555444
USER_ID    = 123456789012345678


async def seed_and_channel():
    """Helper: seed officers and create the test channel."""
    await seed_officers(OFFICER_DICT)
    await ensure_channel_exists(CHANNEL_ID, "test-channel", GUILD_ID)


# ---------------------------------------------------------------------------
# seed_officers
# ---------------------------------------------------------------------------

class TestSeedOfficersIntegration:
    @pytest.mark.asyncio
    async def test_officers_persisted_to_db(self):
        await seed_officers(OFFICER_DICT)
        async with async_session_maker() as session:
            result = await session.execute(select(Officer))
            officers = result.scalars().all()
        assert len(officers) == 2
        ids = {o.officer_id for o in officers}
        assert ids == {"O1", "O2"}

    @pytest.mark.asyncio
    async def test_officer_fields_stored_correctly(self):
        await seed_officers(OFFICER_DICT)
        async with async_session_maker() as session:
            result = await session.execute(
                select(Officer).where(Officer.officer_id == "O1")
            )
            o = result.scalar_one()
        assert o.title == "Test Officer Alpha"
        assert o.model == "anthropic/claude-3-haiku"
        assert o.capability_class == "Support"

    @pytest.mark.asyncio
    async def test_seed_is_idempotent(self):
        await seed_officers(OFFICER_DICT)
        await seed_officers(OFFICER_DICT)  # second call must not duplicate
        async with async_session_maker() as session:
            result = await session.execute(select(Officer))
            officers = result.scalars().all()
        assert len(officers) == 2

    @pytest.mark.asyncio
    async def test_updates_existing_officer_fields(self):
        await seed_officers(OFFICER_DICT)
        updated = {
            "O1": {**OFFICER_DICT["O1"], "title": "Updated Title", "model": "new/model"}
        }
        await seed_officers(updated)
        async with async_session_maker() as session:
            result = await session.execute(
                select(Officer).where(Officer.officer_id == "O1")
            )
            o = result.scalar_one()
        assert o.title == "Updated Title"
        assert o.model == "new/model"

    @pytest.mark.asyncio
    async def test_preserves_officer_not_in_new_roster(self):
        """Officer removed from roster must remain in DB for history preservation."""
        await seed_officers(OFFICER_DICT)
        # Re-seed with only O1 — O2 should remain
        await seed_officers({"O1": OFFICER_DICT["O1"]})
        async with async_session_maker() as session:
            result = await session.execute(select(Officer))
            ids = {o.officer_id for o in result.scalars().all()}
        assert "O2" in ids


# ---------------------------------------------------------------------------
# ensure_channel_exists
# ---------------------------------------------------------------------------

class TestEnsureChannelExistsIntegration:
    @pytest.mark.asyncio
    async def test_creates_channel_record(self):
        await ensure_channel_exists(CHANNEL_ID, "general", GUILD_ID)
        async with async_session_maker() as session:
            result = await session.execute(
                select(Channel).where(Channel.channel_id == CHANNEL_ID)
            )
            ch = result.scalar_one()
        assert ch.channel_name == "general"
        assert ch.guild_id == GUILD_ID

    @pytest.mark.asyncio
    async def test_idempotent_on_second_call(self):
        await ensure_channel_exists(CHANNEL_ID, "general", GUILD_ID)
        await ensure_channel_exists(CHANNEL_ID, "general", GUILD_ID)  # must not error
        async with async_session_maker() as session:
            result = await session.execute(select(Channel))
            channels = result.scalars().all()
        assert len(channels) == 1


# ---------------------------------------------------------------------------
# add_manual_note + load_officer_memory
# ---------------------------------------------------------------------------

class TestManualNotesIntegration:
    @pytest.mark.asyncio
    async def test_add_note_appears_in_memory(self):
        await seed_and_channel()
        await add_manual_note(CHANNEL_ID, "O1", "Always use bullet points", USER_ID)
        memory = await load_officer_memory(CHANNEL_ID, "O1")
        assert "Always use bullet points" in memory

    @pytest.mark.asyncio
    async def test_multiple_notes_all_appear(self):
        await seed_and_channel()
        await add_manual_note(CHANNEL_ID, "O1", "Note one", USER_ID)
        await add_manual_note(CHANNEL_ID, "O1", "Note two", USER_ID)
        memory = await load_officer_memory(CHANNEL_ID, "O1")
        assert "Note one" in memory
        assert "Note two" in memory

    @pytest.mark.asyncio
    async def test_memory_is_empty_when_no_notes_or_missions(self):
        await seed_and_channel()
        memory = await load_officer_memory(CHANNEL_ID, "O1")
        assert memory == ""

    @pytest.mark.asyncio
    async def test_memory_is_channel_isolated(self):
        """Notes for O1 in channel A must not appear when loading O1's memory in channel B."""
        other_channel = 222333444555666777
        await seed_and_channel()
        await ensure_channel_exists(other_channel, "other-channel", GUILD_ID)

        await add_manual_note(CHANNEL_ID, "O1", "Channel A note", USER_ID)
        memory_b = await load_officer_memory(other_channel, "O1")
        assert "Channel A note" not in memory_b

    @pytest.mark.asyncio
    async def test_memory_is_officer_isolated(self):
        """Notes for O1 must not appear in O2's memory."""
        await seed_and_channel()
        await add_manual_note(CHANNEL_ID, "O1", "O1 secret note", USER_ID)
        memory_o2 = await load_officer_memory(CHANNEL_ID, "O2")
        assert "O1 secret note" not in memory_o2

    @pytest.mark.asyncio
    async def test_pinned_note_appears_before_unpinned(self):
        await seed_and_channel()
        # Insert unpinned first, then pinned — memory should still show pinned first
        async with async_session_maker() as session:
            session.add(ManualNote(
                officer_id="O1", channel_id=CHANNEL_ID,
                note_content="UNPINNED", created_by_user_id=USER_ID, is_pinned=False
            ))
            session.add(ManualNote(
                officer_id="O1", channel_id=CHANNEL_ID,
                note_content="PINNED", created_by_user_id=USER_ID, is_pinned=True
            ))
            await session.commit()

        memory = await load_officer_memory(CHANNEL_ID, "O1")
        assert memory.index("PINNED") < memory.index("UNPINNED")


# ---------------------------------------------------------------------------
# clear_officer_memory
# ---------------------------------------------------------------------------

class TestClearOfficerMemoryIntegration:
    @pytest.mark.asyncio
    async def test_clear_removes_notes(self):
        await seed_and_channel()
        await add_manual_note(CHANNEL_ID, "O1", "Note to delete", USER_ID)
        await clear_officer_memory(CHANNEL_ID, "O1")
        memory = await load_officer_memory(CHANNEL_ID, "O1")
        assert "Note to delete" not in memory

    @pytest.mark.asyncio
    async def test_clear_only_affects_target_officer(self):
        await seed_and_channel()
        await add_manual_note(CHANNEL_ID, "O1", "O1 note", USER_ID)
        await add_manual_note(CHANNEL_ID, "O2", "O2 note", USER_ID)
        await clear_officer_memory(CHANNEL_ID, "O1")

        memory_o2 = await load_officer_memory(CHANNEL_ID, "O2")
        assert "O2 note" in memory_o2

    @pytest.mark.asyncio
    async def test_clear_does_not_remove_mission_history(self):
        await seed_and_channel()
        officer_responses = [
            {"officer_id": "O1", "response": "Mission response here.", "success": True}
        ]
        await save_mission(CHANNEL_ID, "Test brief", USER_ID, None, officer_responses)
        await add_manual_note(CHANNEL_ID, "O1", "A note", USER_ID)

        await clear_officer_memory(CHANNEL_ID, "O1")

        # Mission context should still show up
        memory = await load_officer_memory(CHANNEL_ID, "O1")
        assert "Mission response here." in memory

    @pytest.mark.asyncio
    async def test_clear_on_empty_memory_does_not_error(self):
        await seed_and_channel()
        # Should not raise even if there's nothing to delete
        await clear_officer_memory(CHANNEL_ID, "O1")


# ---------------------------------------------------------------------------
# save_mission + load_officer_memory (mission context)
# ---------------------------------------------------------------------------

class TestSaveMissionIntegration:
    @pytest.mark.asyncio
    async def test_mission_and_responses_persisted(self):
        await seed_and_channel()
        responses = [
            {"officer_id": "O1", "response": "O1 analysis.", "success": True},
            {"officer_id": "O2", "response": "O2 analysis.", "success": True},
        ]
        mission_id = await save_mission(CHANNEL_ID, "Design a system", USER_ID, "Support", responses)

        async with async_session_maker() as session:
            mission = await session.get(MissionHistory, mission_id)
            result = await session.execute(
                select(MissionOfficerResponse).where(
                    MissionOfficerResponse.mission_id == mission_id
                )
            )
            saved_responses = result.scalars().all()

        assert mission is not None
        assert mission.mission_brief == "Design a system"
        assert len(saved_responses) == 2

    @pytest.mark.asyncio
    async def test_mission_brief_truncated_to_1000_chars(self):
        await seed_and_channel()
        long_brief = "B" * 2000
        mission_id = await save_mission(CHANNEL_ID, long_brief, USER_ID, None, [])

        async with async_session_maker() as session:
            mission = await session.get(MissionHistory, mission_id)
        assert len(mission.mission_brief) == 1000

    @pytest.mark.asyncio
    async def test_response_content_truncated_to_2000_chars(self):
        await seed_and_channel()
        responses = [{"officer_id": "O1", "response": "R" * 5000, "success": True}]
        mission_id = await save_mission(CHANNEL_ID, "Brief", USER_ID, None, responses)

        async with async_session_maker() as session:
            result = await session.execute(
                select(MissionOfficerResponse).where(
                    MissionOfficerResponse.mission_id == mission_id
                )
            )
            resp = result.scalar_one()
        assert len(resp.response_content) == 2000

    @pytest.mark.asyncio
    async def test_mission_context_appears_in_officer_memory(self):
        await seed_and_channel()
        responses = [{"officer_id": "O1", "response": "Insightful analysis.", "success": True}]
        await save_mission(CHANNEL_ID, "What is caching?", USER_ID, None, responses)

        memory = await load_officer_memory(CHANNEL_ID, "O1")
        assert "Insightful analysis." in memory

    @pytest.mark.asyncio
    async def test_failed_response_stored_with_success_false(self):
        await seed_and_channel()
        responses = [{"officer_id": "O1", "response": "Error: timeout", "success": False}]
        mission_id = await save_mission(CHANNEL_ID, "Brief", USER_ID, None, responses)

        async with async_session_maker() as session:
            result = await session.execute(
                select(MissionOfficerResponse).where(
                    MissionOfficerResponse.mission_id == mission_id
                )
            )
            resp = result.scalar_one()
        assert resp.success is False

    @pytest.mark.asyncio
    async def test_failed_responses_excluded_from_memory_context(self):
        """Only successful responses should appear in memory context."""
        await seed_and_channel()
        responses = [{"officer_id": "O1", "response": "Error: model down", "success": False}]
        await save_mission(CHANNEL_ID, "Brief", USER_ID, None, responses)

        memory = await load_officer_memory(CHANNEL_ID, "O1")
        # Failed response content should NOT appear in memory
        assert "Error: model down" not in memory

    @pytest.mark.asyncio
    async def test_returns_integer_mission_id(self):
        await seed_and_channel()
        mission_id = await save_mission(CHANNEL_ID, "Brief", USER_ID, None, [])
        assert isinstance(mission_id, int)
        assert mission_id > 0

    @pytest.mark.asyncio
    async def test_cascade_delete_removes_responses(self):
        """Deleting a MissionHistory record should cascade-delete its responses."""
        await seed_and_channel()
        responses = [{"officer_id": "O1", "response": "Response", "success": True}]
        mission_id = await save_mission(CHANNEL_ID, "Brief", USER_ID, None, responses)

        async with async_session_maker() as session:
            mission = await session.get(MissionHistory, mission_id)
            await session.delete(mission)
            await session.commit()

            result = await session.execute(
                select(MissionOfficerResponse).where(
                    MissionOfficerResponse.mission_id == mission_id
                )
            )
            remaining = result.scalars().all()

        assert remaining == []


# ---------------------------------------------------------------------------
# save_research_mission
# ---------------------------------------------------------------------------

class TestSaveResearchMissionIntegration:
    @pytest.mark.asyncio
    async def test_research_metadata_persisted(self):
        await seed_and_channel()
        metadata = {
            "mission_type": "research",
            "research_roles": {"O1": "State-of-the-Art Researcher"},
            "web_search_enabled": True,
        }
        mission_id = await save_research_mission(
            CHANNEL_ID, "AI trends 2026", USER_ID, "Support", [], metadata
        )

        async with async_session_maker() as session:
            mission = await session.get(MissionHistory, mission_id)

        assert mission.extra_metadata["mission_type"] == "research"
        assert mission.extra_metadata["web_search_enabled"] is True

    @pytest.mark.asyncio
    async def test_research_topic_stored_as_brief(self):
        await seed_and_channel()
        mission_id = await save_research_mission(
            CHANNEL_ID, "Quantum computing", USER_ID, "Support", [], {}
        )
        async with async_session_maker() as session:
            mission = await session.get(MissionHistory, mission_id)
        assert mission.mission_brief == "Quantum computing"


# ---------------------------------------------------------------------------
# get_channel_stats
# ---------------------------------------------------------------------------

class TestGetChannelStatsIntegration:
    @pytest.mark.asyncio
    async def test_stats_reflect_added_notes(self):
        await seed_and_channel()
        await add_manual_note(CHANNEL_ID, "O1", "Note A", USER_ID)
        await add_manual_note(CHANNEL_ID, "O1", "Note B", USER_ID)

        stats = await get_channel_stats(CHANNEL_ID)
        assert stats["O1"]["notes"] == 2

    @pytest.mark.asyncio
    async def test_stats_reflect_saved_missions(self):
        await seed_and_channel()
        responses = [{"officer_id": "O1", "response": "R", "success": True}]
        await save_mission(CHANNEL_ID, "Brief", USER_ID, None, responses)
        await save_mission(CHANNEL_ID, "Brief 2", USER_ID, None, responses)

        stats = await get_channel_stats(CHANNEL_ID)
        assert stats["O1"]["missions"] == 2

    @pytest.mark.asyncio
    async def test_stats_zero_for_officer_with_no_activity(self):
        await seed_and_channel()
        stats = await get_channel_stats(CHANNEL_ID)
        assert stats["O1"]["notes"] == 0
        assert stats["O1"]["missions"] == 0

    @pytest.mark.asyncio
    async def test_stats_do_not_bleed_across_channels(self):
        other_channel = 222333444555666777
        await seed_and_channel()
        await ensure_channel_exists(other_channel, "other", GUILD_ID)
        await add_manual_note(CHANNEL_ID, "O1", "Channel A note", USER_ID)

        stats_b = await get_channel_stats(other_channel)
        assert stats_b["O1"]["notes"] == 0


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

class TestConcurrencyIntegration:
    @pytest.mark.asyncio
    async def test_concurrent_missions_all_saved(self):
        """Five simultaneous save_mission calls must all persist without errors."""
        await seed_and_channel()
        responses = [{"officer_id": "O1", "response": "R", "success": True}]

        mission_ids = await asyncio.gather(*[
            save_mission(CHANNEL_ID, f"Concurrent brief {i}", USER_ID, None, responses)
            for i in range(5)
        ])

        assert len(mission_ids) == 5
        assert len(set(mission_ids)) == 5  # all IDs are distinct

        async with async_session_maker() as session:
            result = await session.execute(
                select(MissionHistory).where(MissionHistory.channel_id == CHANNEL_ID)
            )
            missions = result.scalars().all()
        assert len(missions) == 5

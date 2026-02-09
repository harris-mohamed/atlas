from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from models.memory import Base, Officer, Channel, OfficerChannelMemory, MissionHistory, MissionOfficerResponse, ManualNote
import os
from typing import Optional, List, Dict
from datetime import datetime

# Initialize async engine
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://atlas_user:changeme@localhost:5432/atlas_db")
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    """Initialize database schema and seed officers from roster.json"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database schema created")

async def seed_officers(officers_dict: dict):
    """Seed/update officers table from roster.json (handles roster changes)"""
    async with async_session_maker() as session:
        for officer_id, officer_data in officers_dict.items():
            # Check if officer exists using ORM query
            result = await session.execute(
                select(Officer).where(Officer.officer_id == officer_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # UPDATE existing officer if roster changed
                existing.title = officer_data["title"]
                existing.model = officer_data["model"]
                existing.capability_class = officer_data["capability_class"]
                existing.specialty = officer_data["specialty"]
                existing.system_prompt = officer_data["system_prompt"]
                print(f"♻️ Updated officer {officer_id}")
            else:
                # INSERT new officer
                officer = Officer(
                    officer_id=officer_id,
                    title=officer_data["title"],
                    model=officer_data["model"],
                    capability_class=officer_data["capability_class"],
                    specialty=officer_data["specialty"],
                    system_prompt=officer_data["system_prompt"]
                )
                session.add(officer)
                print(f"✅ Created officer {officer_id}")

        # HANDLE REMOVED OFFICERS: Check if any officers in DB are not in roster
        all_db_officers = await session.execute(select(Officer))
        for db_officer in all_db_officers.scalars().all():
            if db_officer.officer_id not in officers_dict:
                # Keep but mark as inactive (safer, preserves history)
                print(f"⚠️ Officer {db_officer.officer_id} in DB but not in roster (keeping for history)")

        await session.commit()
    print(f"✅ Roster sync complete: {len(officers_dict)} officers")

async def ensure_channel_exists(channel_id: int, channel_name: str, guild_id: int):
    """Create channel record if it doesn't exist"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Channel).where(Channel.channel_id == channel_id)
        )
        existing = result.scalar_one_or_none()

        if not existing:
            channel = Channel(
                channel_id=channel_id,
                channel_name=channel_name,
                guild_id=guild_id
            )
            session.add(channel)
            await session.commit()

async def load_officer_memory(channel_id: int, officer_id: str, max_tokens: int = 2000) -> str:
    """Load officer's memory for a channel and format as prompt-ready context"""
    async with async_session_maker() as session:
        # Load manual notes
        notes_result = await session.execute(
            select(ManualNote)
            .where(ManualNote.officer_id == officer_id)
            .where(ManualNote.channel_id == channel_id)
            .order_by(ManualNote.is_pinned.desc(), ManualNote.created_at.desc())
            .limit(10)
        )
        notes = notes_result.scalars().all()

        # Load recent mission responses (last 5)
        missions_result = await session.execute(
            select(MissionOfficerResponse, MissionHistory.mission_brief)
            .join(MissionHistory)
            .where(MissionOfficerResponse.officer_id == officer_id)
            .where(MissionHistory.channel_id == channel_id)
            .where(MissionOfficerResponse.success == True)
            .order_by(MissionHistory.started_at.desc())
            .limit(5)
        )
        mission_data = missions_result.all()

        # Format memory context
        context_parts = []

        if notes:
            notes_text = "\n".join([f"- {note.note_content}" for note in notes])
            context_parts.append(f"### Manual Notes:\n{notes_text}")

        if mission_data:
            missions_text = "\n".join([
                f"- Brief: {brief[:100]}... | Response: {response.response_content[:200]}..."
                for response, brief in mission_data
            ])
            context_parts.append(f"### Recent Missions:\n{missions_text}")

        full_context = "\n\n".join(context_parts)

        # Token estimation and truncation
        estimated_tokens = len(full_context) // 4
        if estimated_tokens > max_tokens:
            return full_context[:max_tokens * 4]

        return full_context

async def save_mission(
    channel_id: int,
    mission_brief: str,
    user_id: int,
    capability_class_filter: Optional[str],
    officer_responses: List[Dict]
) -> int:
    """Save mission and all officer responses to database"""
    async with async_session_maker() as session:
        # Create mission record
        mission = MissionHistory(
            channel_id=channel_id,
            mission_brief=mission_brief[:1000],  # Truncate long briefs
            user_id=user_id,
            capability_class_filter=capability_class_filter,
            completed_at=datetime.utcnow()
        )
        session.add(mission)
        await session.flush()  # Get mission.id

        # Save each officer response
        for response_data in officer_responses:
            response = MissionOfficerResponse(
                mission_id=mission.id,
                officer_id=response_data["officer_id"],
                response_content=response_data["response"][:2000],  # Truncate
                tokens_used=len(response_data["response"]) // 4,  # Estimate
                success=response_data["success"],
                error_message=response_data.get("error")
            )
            session.add(response)

        await session.commit()
        return mission.id

async def save_research_mission(
    channel_id: int,
    research_topic: str,
    user_id: int,
    capability_class: str,
    officer_responses: List[Dict],
    research_metadata: Dict
) -> int:
    """Save research mission with research-specific metadata."""
    async with async_session_maker() as session:
        mission = MissionHistory(
            channel_id=channel_id,
            mission_brief=research_topic[:1000],
            user_id=user_id,
            capability_class_filter=capability_class,
            completed_at=datetime.utcnow(),
            extra_metadata=research_metadata  # Contains mission_type: "research"
        )
        session.add(mission)
        await session.flush()

        # Save officer responses
        for response_data in officer_responses:
            response = MissionOfficerResponse(
                mission_id=mission.id,
                officer_id=response_data["officer_id"],
                response_content=response_data["response"][:2000],
                tokens_used=len(response_data["response"]) // 4,
                success=response_data["success"],
                error_message=response_data.get("error")
            )
            session.add(response)

        await session.commit()
        return mission.id

async def add_manual_note(
    channel_id: int,
    officer_id: str,
    note_content: str,
    created_by_user_id: int
) -> bool:
    """Add a manual note to officer's memory"""
    async with async_session_maker() as session:
        note = ManualNote(
            officer_id=officer_id,
            channel_id=channel_id,
            note_content=note_content,
            created_by_user_id=created_by_user_id
        )
        session.add(note)
        await session.commit()
    return True

async def clear_officer_memory(channel_id: int, officer_id: str):
    """Clear all manual notes for an officer in a channel (ORM-based)"""
    async with async_session_maker() as session:
        # Delete manual notes using ORM (cleaner than raw SQL)
        result = await session.execute(
            select(ManualNote).where(
                ManualNote.officer_id == officer_id,
                ManualNote.channel_id == channel_id
            )
        )
        notes_to_delete = result.scalars().all()

        for note in notes_to_delete:
            await session.delete(note)

        # Note: Mission history is preserved for audit trail
        # This is safer than CASCADE DELETE

        await session.commit()
        print(f"🗑️ Cleared {len(notes_to_delete)} notes for {officer_id} in channel {channel_id}")

async def get_channel_stats(channel_id: int) -> Dict:
    """Get memory statistics for all officers in a channel"""
    async with async_session_maker() as session:
        stats = {}

        for officer_id in [f"O{i}" for i in range(1, 17)]:
            # Count notes
            notes_result = await session.execute(
                select(ManualNote).where(
                    ManualNote.officer_id == officer_id,
                    ManualNote.channel_id == channel_id
                )
            )
            notes_count = len(notes_result.scalars().all())

            # Count mission responses
            missions_result = await session.execute(
                select(MissionOfficerResponse)
                .join(MissionHistory)
                .where(
                    MissionOfficerResponse.officer_id == officer_id,
                    MissionHistory.channel_id == channel_id
                )
            )
            missions_count = len(missions_result.scalars().all())

            stats[officer_id] = {
                "notes": notes_count,
                "missions": missions_count
            }

        return stats

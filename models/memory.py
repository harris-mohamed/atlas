from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Officer(Base):
    __tablename__ = "officers"

    officer_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    capability_class: Mapped[str] = mapped_column(String(50))
    specialty: Mapped[str] = mapped_column(String(100))
    system_prompt: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    memories: Mapped[list["OfficerChannelMemory"]] = relationship(
        back_populates="officer", cascade="all, delete-orphan"
    )
    responses: Mapped[list["MissionOfficerResponse"]] = relationship(back_populates="officer")
    notes: Mapped[list["ManualNote"]] = relationship(
        back_populates="officer", cascade="all, delete-orphan"
    )


class Channel(Base):
    __tablename__ = "channels"

    channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_name: Mapped[str] = mapped_column(String(255))
    guild_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    memories: Mapped[list["OfficerChannelMemory"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )
    missions: Mapped[list["MissionHistory"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )
    notes: Mapped[list["ManualNote"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )


class OfficerChannelMemory(Base):
    __tablename__ = "officer_channel_memory"
    __table_args__ = (Index("idx_officer_channel_mem", "officer_id", "channel_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    officer_id: Mapped[str] = mapped_column(ForeignKey("officers.officer_id"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.channel_id"))
    memory_content: Mapped[str] = mapped_column(Text)
    memory_type: Mapped[str] = mapped_column(String(50))
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    update_count: Mapped[int] = mapped_column(Integer, default=1)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    officer: Mapped["Officer"] = relationship(back_populates="memories")
    channel: Mapped["Channel"] = relationship(back_populates="memories")


class MissionHistory(Base):
    __tablename__ = "mission_history"
    __table_args__ = (Index("idx_mission_channel", "channel_id", "started_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.channel_id"))
    mission_brief: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]]
    capability_class_filter: Mapped[Optional[str]] = mapped_column(String(50))
    user_id: Mapped[int] = mapped_column(BigInteger)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    channel: Mapped["Channel"] = relationship(back_populates="missions")
    officer_responses: Mapped[list["MissionOfficerResponse"]] = relationship(
        back_populates="mission", cascade="all, delete-orphan"
    )


class MissionOfficerResponse(Base):
    __tablename__ = "mission_officer_response"
    __table_args__ = (Index("idx_mission_responses", "mission_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("mission_history.id", ondelete="CASCADE"))
    officer_id: Mapped[str] = mapped_column(ForeignKey("officers.officer_id"))
    response_content: Mapped[str] = mapped_column(Text)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    mission: Mapped["MissionHistory"] = relationship(back_populates="officer_responses")
    officer: Mapped["Officer"] = relationship(back_populates="responses")


class ManualNote(Base):
    __tablename__ = "manual_notes"
    __table_args__ = (Index("idx_manual_notes", "officer_id", "channel_id", "is_pinned"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    officer_id: Mapped[str] = mapped_column(ForeignKey("officers.officer_id"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.channel_id"))
    note_content: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Relationships
    officer: Mapped["Officer"] = relationship(back_populates="notes")
    channel: Mapped["Channel"] = relationship(back_populates="notes")

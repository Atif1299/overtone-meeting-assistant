"""Tests for persistent database storage and BotSession model."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session, sessionmaker

# Add backend to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import Base, create_tables, SessionLocal, get_db
from models.bot_session import BotSession, BotSessionState, AgentMode


@pytest.fixture
def test_db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db_session(test_db_engine):
    """Create a fresh database session for each test."""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    db = TestSessionLocal()
    yield db
    db.close()


class TestDatabaseConnection:
    """Test database initialization and connection."""

    def test_create_tables(self, test_db_engine):
        """Test that all tables are created successfully."""
        # Verify bot_sessions table exists
        inspector_obj = inspect(test_db_engine)
        tables = inspector_obj.get_table_names()
        assert "bot_sessions" in tables

    def test_get_db_dependency(self):
        """Test the get_db dependency injection function."""
        db_gen = get_db()
        db = next(db_gen)
        assert isinstance(db, Session)
        try:
            db_gen.send(None)
        except StopIteration:
            pass


class TestBotSessionModel:
    """Test BotSession model."""

    def test_create_bot_session_minimal(self, test_db_session):
        """Test creating a BotSession with minimal required fields."""
        session = BotSession(
            session_id="test-session-001",
            bot_id="bot-001",
            bot_name="TestBot",
            meeting_url="https://zoom.us/j/123456",
        )
        test_db_session.add(session)
        test_db_session.commit()
        test_db_session.refresh(session)

        assert session.session_id == "test-session-001"
        assert session.bot_id == "bot-001"
        assert session.bot_name == "TestBot"
        assert session.created_at is not None
        assert session.state == BotSessionState.CREATED.value

    def test_create_bot_session_with_urls(self, test_db_session):
        """Test creating a BotSession with PDF and metadata URLs."""
        session = BotSession(
            session_id="test-session-002",
            bot_id="bot-002",
            bot_name="TestBot",
            meeting_url="https://zoom.us/j/123456",
            pdf_url="https://example.com/document.pdf",
            metadata_url="https://example.com/metadata.json",
        )
        test_db_session.add(session)
        test_db_session.commit()
        test_db_session.refresh(session)

        assert session.pdf_url == "https://example.com/document.pdf"
        assert session.metadata_url == "https://example.com/metadata.json"

    def test_bot_session_default_values(self, test_db_session):
        """Test that default values are set correctly."""
        session = BotSession(
            session_id="test-session-003",
            bot_id="bot-003",
            bot_name="TestBot",
            meeting_url="https://zoom.us/j/123456",
        )
        test_db_session.add(session)
        test_db_session.commit()
        test_db_session.refresh(session)

        assert session.state == BotSessionState.CREATED.value
        assert session.agent_mode == AgentMode.REALTIME.value
        assert session.agent_name == "default"
        assert session.extra == {}

    def test_bot_session_timestamps(self, test_db_session):
        """Test that timestamps are set and updated correctly."""
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        session = BotSession(
            session_id="test-session-004",
            bot_id="bot-004",
            bot_name="TestBot",
            meeting_url="https://zoom.us/j/123456",
        )
        test_db_session.add(session)
        test_db_session.commit()
        test_db_session.refresh(session)
        after = datetime.now(timezone.utc).replace(tzinfo=None)

        # SQLite may strip timezone info, so compare naive datetimes
        created_at_naive = session.created_at.replace(tzinfo=None) if session.created_at.tzinfo else session.created_at
        updated_at_naive = session.updated_at.replace(tzinfo=None) if session.updated_at.tzinfo else session.updated_at
        assert before <= created_at_naive <= after
        assert before <= updated_at_naive <= after
        # Check that timestamps are very close (within 1 second)
        time_diff = abs((updated_at_naive - created_at_naive).total_seconds())
        assert time_diff < 1.0, f"Timestamps differ by {time_diff} seconds"


class TestBotSessionCRUD:
    """Test CRUD operations on BotSession."""

    def test_create_session(self, test_db_session):
        """Test creating a BotSession."""
        session = BotSession(
            session_id="test-crud-001",
            bot_id="bot-crud-001",
            bot_name="CRUDBot",
            meeting_url="https://zoom.us/j/789012",
        )
        test_db_session.add(session)
        test_db_session.commit()
        assert session.session_id == "test-crud-001"

    def test_read_session_by_id(self, test_db_session):
        """Test retrieving a BotSession by ID."""
        session = BotSession(
            session_id="test-crud-002",
            bot_id="bot-crud-002",
            bot_name="CRUDBot",
            meeting_url="https://zoom.us/j/789012",
        )
        test_db_session.add(session)
        test_db_session.commit()

        retrieved = test_db_session.query(BotSession).filter(
            BotSession.session_id == "test-crud-002"
        ).first()
        assert retrieved is not None
        assert retrieved.bot_name == "CRUDBot"

    def test_update_session(self, test_db_session):
        """Test updating a BotSession."""
        session = BotSession(
            session_id="test-crud-003",
            bot_id="bot-crud-003",
            bot_name="CRUDBot",
            meeting_url="https://zoom.us/j/789012",
            state=BotSessionState.CREATED.value,
        )
        test_db_session.add(session)
        test_db_session.commit()

        # Update the session
        session.state = BotSessionState.IN_CALL.value
        session.last_status_message = "Bot joined the call"
        test_db_session.commit()
        test_db_session.refresh(session)

        assert session.state == BotSessionState.IN_CALL.value
        assert session.last_status_message == "Bot joined the call"

    def test_delete_session(self, test_db_session):
        """Test deleting a BotSession."""
        session = BotSession(
            session_id="test-crud-004",
            bot_id="bot-crud-004",
            bot_name="CRUDBot",
            meeting_url="https://zoom.us/j/789012",
        )
        test_db_session.add(session)
        test_db_session.commit()

        test_db_session.delete(session)
        test_db_session.commit()

        retrieved = test_db_session.query(BotSession).filter(
            BotSession.session_id == "test-crud-004"
        ).first()
        assert retrieved is None

    def test_query_multiple_sessions(self, test_db_session):
        """Test querying multiple BotSessions."""
        for i in range(5):
            session = BotSession(
                session_id=f"test-crud-multi-{i}",
                bot_id=f"bot-crud-multi-{i}",
                bot_name="CRUDBot",
                meeting_url="https://zoom.us/j/789012",
            )
            test_db_session.add(session)
        test_db_session.commit()

        sessions = test_db_session.query(BotSession).filter(
            BotSession.session_id.ilike("test-crud-multi%")
        ).all()
        assert len(sessions) == 5


class TestBotSessionStateTransitions:
    """Test state transitions in BotSession."""

    def test_state_transitions(self, test_db_session):
        """Test transitioning through session states."""
        session = BotSession(
            session_id="test-state-001",
            bot_id="bot-state-001",
            bot_name="StateBot",
            meeting_url="https://zoom.us/j/123456",
        )
        test_db_session.add(session)
        test_db_session.commit()

        # Transition through states
        states = [
            BotSessionState.JOINING,
            BotSessionState.IN_WAITING_ROOM,
            BotSessionState.IN_CALL,
            BotSessionState.RECORDING,
            BotSessionState.CALL_ENDED,
            BotSessionState.DONE,
        ]

        for state in states:
            session.state = state.value
            test_db_session.commit()
            test_db_session.refresh(session)
            assert session.state == state.value

    def test_session_expiration(self, test_db_session):
        """Test setting session expiration time."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        session = BotSession(
            session_id="test-expiry-001",
            bot_id="bot-expiry-001",
            bot_name="ExpiryBot",
            meeting_url="https://zoom.us/j/123456",
            expires_at=future_time,
        )
        test_db_session.add(session)
        test_db_session.commit()
        test_db_session.refresh(session)

        assert session.expires_at is not None
        # SQLite strips timezone info, so compare naive datetimes
        expires_at_naive = session.expires_at.replace(tzinfo=None) if session.expires_at.tzinfo else session.expires_at
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        assert expires_at_naive > now_naive

    def test_session_status_tracking(self, test_db_session):
        """Test tracking status codes and messages."""
        session = BotSession(
            session_id="test-status-001",
            bot_id="bot-status-001",
            bot_name="StatusBot",
            meeting_url="https://zoom.us/j/123456",
        )
        test_db_session.add(session)
        test_db_session.commit()

        session.last_status_code = "200"
        session.last_status_message = "Successfully joined meeting"
        session.last_transcript_snippet = "Thanks for having me"
        test_db_session.commit()
        test_db_session.refresh(session)

        assert session.last_status_code == "200"
        assert session.last_status_message == "Successfully joined meeting"
        assert session.last_transcript_snippet == "Thanks for having me"


class TestBotSessionAgentMode:
    """Test agent mode configurations."""

    def test_realtime_mode(self, test_db_session):
        """Test creating a session in realtime mode."""
        session = BotSession(
            session_id="test-realtime-001",
            bot_id="bot-realtime-001",
            bot_name="RealtimeBot",
            meeting_url="https://zoom.us/j/123456",
            agent_mode=AgentMode.REALTIME.value,
        )
        test_db_session.add(session)
        test_db_session.commit()
        test_db_session.refresh(session)

        assert session.agent_mode == AgentMode.REALTIME.value

    def test_webhook_mode(self, test_db_session):
        """Test creating a session in webhook mode."""
        session = BotSession(
            session_id="test-webhook-001",
            bot_id="bot-webhook-001",
            bot_name="WebhookBot",
            meeting_url="https://zoom.us/j/123456",
            agent_mode=AgentMode.WEBHOOK.value,
        )
        test_db_session.add(session)
        test_db_session.commit()
        test_db_session.refresh(session)

        assert session.agent_mode == AgentMode.WEBHOOK.value

    def test_agent_version_tracking(self, test_db_session):
        """Test tracking agent versions."""
        session = BotSession(
            session_id="test-version-001",
            bot_id="bot-version-001",
            bot_name="VersionBot",
            meeting_url="https://zoom.us/j/123456",
            agent_version=3,
        )
        test_db_session.add(session)
        test_db_session.commit()
        test_db_session.refresh(session)

        assert session.agent_version == 3


class TestBotSessionExtras:
    """Test flexible JSON storage for extra data."""

    def test_store_extra_data(self, test_db_session):
        """Test storing flexible JSON data in extras."""
        extra_data = {
            "customer_id": "cust-123",
            "presentation_name": "Q1 Earnings",
            "tags": ["important", "featured"],
        }
        session = BotSession(
            session_id="test-extra-001",
            bot_id="bot-extra-001",
            bot_name="ExtraBot",
            meeting_url="https://zoom.us/j/123456",
            extra=extra_data,
        )
        test_db_session.add(session)
        test_db_session.commit()
        test_db_session.refresh(session)

        assert session.extra["customer_id"] == "cust-123"
        assert "important" in session.extra["tags"]

    def test_modify_extra_data(self, test_db_session):
        """Test modifying extra data."""
        session = BotSession(
            session_id="test-extra-002",
            bot_id="bot-extra-002",
            bot_name="ExtraBot",
            meeting_url="https://zoom.us/j/123456",
            extra={"count": 0},
        )
        test_db_session.add(session)
        test_db_session.commit()

        # Create a new dict for JSON column modification (SQLAlchemy tracking)
        session.extra = {"count": 5, "new_field": "new_value"}
        test_db_session.commit()
        test_db_session.refresh(session)

        assert session.extra["count"] == 5
        assert session.extra["new_field"] == "new_value"

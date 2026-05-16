"""
Shared pytest fixtures for ScheduleHelper test suite.

Sets up an in-memory SQLite database, fakeredis, and mocks the Telegram bot
so that the FastAPI application can be tested without real external services.
"""
import os
from cryptography.fernet import Fernet
from unittest.mock import AsyncMock, patch

# ── Env vars must be set BEFORE main is imported ───────────────────────────
os.environ["MASTER_KEY"] = Fernet.generate_key().decode()
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-purposes-only!!!"
os.environ["DATABASE_URL"] = "sqlite://"          # placeholder; overridden below
os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:AABBCCDDEEFFaabbccddeeff1234567890Ab"
os.environ["ADMIN_TELEGRAM_ID"] = "123456789"

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from main import app, Base, get_password_hash, UserDB, Schedule, Event, Message, RoomKey

# ── Test engine (in-memory SQLite, single shared connection) ───────────────
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

# Redirect main's globals so get_db() and lifespan use the test engine
main.engine = _test_engine
main.SessionLocal = _TestSessionLocal

Base.metadata.create_all(bind=_test_engine)


# ── Cleanup between tests ──────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def clean_tables():
    yield
    session = _TestSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    finally:
        session.close()


# ── Basic fixtures ─────────────────────────────────────────────────────────
@pytest.fixture
def db():
    """Raw DB session for creating seed data in tests."""
    session = _TestSessionLocal()
    yield session
    session.close()


@pytest.fixture
def fake_redis():
    """Fresh in-memory Redis for each test."""
    return fakeredis.FakeAsyncRedis(decode_responses=True)


@pytest.fixture
def client(fake_redis):
    """
    TestClient with:
    - fakeredis replacing the real Redis client
    - Telegram notification functions mocked
    """
    main.redis_client = fake_redis
    with patch("main.send_telegram_notification", new=AsyncMock(return_value=None)):
        with patch("main.send_admin_alert", new=AsyncMock(return_value=None)):
            with TestClient(app, raise_server_exceptions=True) as c:
                yield c


# ── User fixtures ──────────────────────────────────────────────────────────
@pytest.fixture
def admin_user(db):
    user = UserDB(
        username="test_admin",
        password_hash=get_password_hash("adminpass123"),
        telegram_id=900001,
        role="admin",
        full_name="Admin User",
        last_notified_event_ids=[],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_token(client, admin_user):
    resp = client.post("/token", data={"username": "test_admin", "password": "adminpass123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def student_user(db):
    user = UserDB(
        username="test_student",
        password_hash=get_password_hash("studentpass123"),
        telegram_id=900002,
        role="student",
        full_name="Student User",
        group_number="ИБ-11БО",
        subgroup=1,
        last_notified_event_ids=[],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def student_token(client, student_user):
    resp = client.post("/token", data={"username": "test_student", "password": "studentpass123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def teacher_user(db):
    user = UserDB(
        username="test_teacher",
        password_hash=get_password_hash("teacherpass123"),
        telegram_id=900003,
        role="teacher",
        full_name="Test Teacher",
        department="Кафедра ИБ",
        last_notified_event_ids=[],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def teacher_token(client, teacher_user):
    resp = client.post("/token", data={"username": "test_teacher", "password": "teacherpass123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def leader_user(db):
    user = UserDB(
        username="test_leader",
        password_hash=get_password_hash("leaderpass123"),
        telegram_id=900004,
        role="group_leader",
        full_name="Group Leader",
        group_number="ИБ-11БО",
        subgroup=1,
        last_notified_event_ids=[],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def leader_token(client, leader_user):
    resp = client.post("/token", data={"username": "test_leader", "password": "leaderpass123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ── Schedule / Event helpers ───────────────────────────────────────────────
@pytest.fixture
def sample_schedule(db):
    from datetime import time, date
    s = Schedule(
        group_number="ИБ-11БО",
        day_of_week=1,
        start_time=time(9, 0),
        end_time=time(10, 30),
        lesson_type="lecture",
        subject="Математика",
        classroom="А-101",
        teacher_name="Иванов И.И.",
        subgroup=None,
        week_type="both",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
        is_active=True,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@pytest.fixture
def sample_event(db):
    from datetime import datetime
    import pytz
    from main import to_utc, MOSCOW_TZ
    start = to_utc(datetime(2030, 6, 1, 10, 0))
    e = Event(
        title="Контрольная по математике",
        event_type="Контрольная",
        start_datetime=start,
        group_number="ИБ-11БО",
        description="Темы 1-5",
        is_active=True,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e

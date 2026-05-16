"""Tests for utility functions in main.py."""
import pytest
from datetime import datetime
from cryptography.fernet import Fernet

import pytz

import main
from main import (
    sanitize_message,
    to_utc,
    to_moscow,
    create_access_token,
    create_refresh_token,
    verify_password,
    get_password_hash,
    encrypt_content,
    decrypt_content,
    check_room_access,
    MOSCOW_TZ,
)


# ── sanitize_message ───────────────────────────────────────────────────────
class TestSanitizeMessage:
    def test_empty_string_returns_empty(self):
        assert sanitize_message("") == ""

    def test_none_returns_empty(self):
        assert sanitize_message(None) == ""

    def test_normal_text_unchanged(self):
        result = sanitize_message("Hello, world!")
        assert result == "Hello, world!"

    def test_html_is_escaped(self):
        result = sanitize_message("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_message_truncated_at_2000_chars(self):
        long_msg = "a" * 2500
        result = sanitize_message(long_msg)
        assert len(result) <= 2010  # 2000 + "..."
        assert result.endswith("...")

    def test_message_exactly_2000_chars_not_truncated(self):
        msg = "b" * 2000
        result = sanitize_message(msg)
        assert not result.endswith("...")

    def test_on_event_attribute_removed(self):
        result = sanitize_message('<img onerror="alert(1)">')
        assert "onerror=" not in result

    def test_ampersand_escaped(self):
        result = sanitize_message("a & b")
        assert "&amp;" in result


# ── Timezone helpers ───────────────────────────────────────────────────────
class TestTimezoneHelpers:
    def test_to_utc_naive_datetime(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        result = to_utc(naive)
        assert result.tzinfo is not None
        assert result.tzinfo == pytz.UTC

    def test_to_utc_aware_moscow_datetime(self):
        aware = MOSCOW_TZ.localize(datetime(2026, 1, 1, 12, 0, 0))
        result = to_utc(aware)
        assert result.tzinfo == pytz.UTC
        # Moscow is UTC+3
        assert result.hour == 9

    def test_to_moscow_naive_datetime(self):
        naive_utc = datetime(2026, 1, 1, 9, 0, 0)
        result = to_moscow(naive_utc)
        assert result.tzinfo is not None
        assert result.hour == 12  # UTC+3

    def test_to_moscow_aware_utc_datetime(self):
        aware_utc = pytz.UTC.localize(datetime(2026, 1, 1, 9, 0, 0))
        result = to_moscow(aware_utc)
        assert result.hour == 12


# ── Password utilities ─────────────────────────────────────────────────────
class TestPasswordUtils:
    def test_hash_and_verify_correct_password(self):
        password = "mysecurepassword"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed)

    def test_verify_wrong_password_returns_false(self):
        hashed = get_password_hash("correct")
        assert not verify_password("wrong", hashed)

    def test_same_password_produces_different_hashes(self):
        h1 = get_password_hash("password")
        h2 = get_password_hash("password")
        assert h1 != h2  # argon2 uses random salt


# ── JWT token creation ─────────────────────────────────────────────────────
class TestTokenCreation:
    def test_create_access_token_returns_string(self):
        token = create_access_token({"sub": "user1"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_access_token_contains_correct_subject(self):
        from jose import jwt
        token = create_access_token({"sub": "testuser"})
        payload = jwt.decode(token, main.SECRET_KEY, algorithms=[main.ALGORITHM])
        assert payload["sub"] == "testuser"

    def test_access_token_has_expiry(self):
        from jose import jwt
        token = create_access_token({"sub": "testuser"})
        payload = jwt.decode(token, main.SECRET_KEY, algorithms=[main.ALGORITHM])
        assert "exp" in payload

    def test_create_refresh_token_has_type_refresh(self):
        from jose import jwt
        token = create_refresh_token({"sub": "testuser"})
        payload = jwt.decode(token, main.SECRET_KEY, algorithms=[main.ALGORITHM])
        assert payload.get("type") == "refresh"

    def test_refresh_token_is_different_from_access_token(self):
        access = create_access_token({"sub": "user"})
        refresh = create_refresh_token({"sub": "user"})
        assert access != refresh


# ── Message encryption ─────────────────────────────────────────────────────
class TestMessageEncryption:
    @pytest.fixture
    def room_key(self):
        return Fernet(Fernet.generate_key())

    def test_encrypt_and_decrypt_round_trip(self, room_key):
        original = "Привет, мир!"
        encrypted = encrypt_content(original, room_key)
        decrypted = decrypt_content(encrypted, room_key)
        assert decrypted == original

    def test_encrypted_content_differs_from_original(self, room_key):
        content = "Hello"
        encrypted = encrypt_content(content, room_key)
        assert encrypted != content

    def test_decrypt_empty_string_returns_empty(self, room_key):
        result = decrypt_content("", room_key)
        assert result == ""

    def test_decrypt_invalid_data_returns_error_string(self, room_key):
        result = decrypt_content("not-valid-base64-fernet-data", room_key)
        assert "не удалось расшифровать" in result

    def test_encrypt_with_different_keys_produces_different_output(self):
        key1 = Fernet(Fernet.generate_key())
        key2 = Fernet(Fernet.generate_key())
        e1 = encrypt_content("test", key1)
        e2 = encrypt_content("test", key2)
        assert e1 != e2


# ── check_room_access ──────────────────────────────────────────────────────
class TestCheckRoomAccess:
    def _make_user(self, role, group_number=None, user_id=1):
        """Helper to create a simple user-like object (no SQLAlchemy machinery needed)."""
        from types import SimpleNamespace
        return SimpleNamespace(id=user_id, role=role, group_number=group_number)

    def test_student_can_access_own_group(self, db):
        user = self._make_user("student", "ИБ-11БО", user_id=1)
        assert check_room_access("group:ИБ-11БО", user, db) is True

    def test_student_cannot_access_other_group(self, db):
        user = self._make_user("student", "ИБ-11БО", user_id=1)
        assert check_room_access("group:ИБ-21БО", user, db) is False

    def test_teacher_can_access_teachers_room(self, db):
        user = self._make_user("teacher")
        assert check_room_access("teachers", user, db) is True

    def test_student_cannot_access_teachers_room(self, db):
        user = self._make_user("student", "ИБ-11БО")
        assert check_room_access("teachers", user, db) is False

    def test_admin_can_access_teachers_room(self, db):
        user = self._make_user("admin")
        assert check_room_access("teachers", user, db) is True

    def test_invalid_room_id_returns_false(self, db):
        user = self._make_user("admin")
        assert check_room_access("", user, db) is False
        assert check_room_access("unknown:room", user, db) is False

    def test_too_long_room_id_returns_false(self, db):
        user = self._make_user("student", "ИБ-11БО")
        assert check_room_access("group:" + "x" * 200, user, db) is False

    def test_private_room_requires_teacher_participant(self, db):
        from main import UserDB
        # Create student and teacher in DB
        student = UserDB(
            username="s1", password_hash="x", telegram_id=1, role="student",
            group_number="ИБ-11БО", last_notified_event_ids=[]
        )
        teacher = UserDB(
            username="t1", password_hash="x", telegram_id=2, role="teacher",
            last_notified_event_ids=[]
        )
        db.add_all([student, teacher])
        db.commit()
        db.refresh(student)
        db.refresh(teacher)

        uid1 = min(student.id, teacher.id)
        uid2 = max(student.id, teacher.id)
        room_id = f"private:{uid1}_{uid2}"

        student.id = student.id  # ensure id is set
        assert check_room_access(room_id, student, db) is True

    def test_private_room_student_not_participant_returns_false(self, db):
        user = self._make_user("student", "ИБ-11БО", user_id=999)
        assert check_room_access("private:1_2", user, db) is False

    def test_private_room_invalid_format_returns_false(self, db):
        user = self._make_user("student", "ИБ-11БО", user_id=1)
        assert check_room_access("private:abc_def", user, db) is False

    def test_group_room_invalid_chars_returns_false(self, db):
        user = self._make_user("student", "ИБ-11БО")
        assert check_room_access("group:<script>", user, db) is False

"""Tests for chat-related endpoints."""
import pytest

from main import Message, RoomKey, UserDB


class TestChatHistory:
    def test_student_can_read_own_group_chat(self, client, student_token, student_user, db):
        resp = client.get(
            f"/chat/history/group:ИБ-11БО",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "messages" in body
        assert "has_more" in body

    def test_student_cannot_read_other_group_chat(self, client, student_token):
        resp = client.get(
            "/chat/history/group:ИБ-21БО",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 403

    def test_teacher_can_read_teachers_room(self, client, teacher_token):
        resp = client.get(
            "/chat/history/teachers",
            headers={"Authorization": f"Bearer {teacher_token}"},
        )
        assert resp.status_code == 200

    def test_student_cannot_read_teachers_room(self, client, student_token):
        resp = client.get(
            "/chat/history/teachers",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 403

    def test_chat_history_returns_decrypted_messages(self, client, student_token, student_user, db):
        from main import get_or_create_room_key, encrypt_content
        room_id = "group:ИБ-11БО"
        room_key = get_or_create_room_key(room_id, db)
        encrypted = encrypt_content("Привет всем!", room_key)

        msg = Message(
            room_id=room_id,
            sender_id=student_user.id,
            sender_username=student_user.username,
            sender_full_name=student_user.full_name,
            content=encrypted,
            is_encrypted=True,
        )
        db.add(msg)
        db.commit()

        resp = client.get(
            f"/chat/history/{room_id}",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert any(m["content"] == "Привет всем!" for m in messages)

    def test_chat_history_unencrypted_message(self, client, student_token, student_user, db):
        msg = Message(
            room_id="group:ИБ-11БО",
            sender_id=student_user.id,
            sender_username=student_user.username,
            sender_full_name=student_user.full_name,
            content="Открытое сообщение",
            is_encrypted=False,
        )
        db.add(msg)
        db.commit()

        resp = client.get(
            "/chat/history/group:ИБ-11БО",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        messages = resp.json()["messages"]
        assert any(m["content"] == "Открытое сообщение" for m in messages)

    def test_chat_history_pagination(self, client, student_token, student_user, db):
        for i in range(5):
            db.add(Message(
                room_id="group:ИБ-11БО",
                sender_id=student_user.id,
                sender_username=student_user.username,
                sender_full_name=student_user.full_name,
                content=f"Message {i}",
                is_encrypted=False,
            ))
        db.commit()

        resp = client.get(
            "/chat/history/group:ИБ-11БО",
            params={"limit": 2, "offset": 0},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()["messages"]) == 2
        assert resp.json()["has_more"] is True

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/chat/history/group:ИБ-11БО")
        assert resp.status_code == 401

    def test_private_chat_between_student_and_teacher(self, client, student_user, teacher_user, db):
        from main import get_password_hash
        # Login as student
        login = client.post("/token", data={"username": "test_student", "password": "studentpass123"})
        student_token = login.json()["access_token"]

        uid1 = min(student_user.id, teacher_user.id)
        uid2 = max(student_user.id, teacher_user.id)
        room_id = f"private:{uid1}_{uid2}"

        resp = client.get(
            f"/chat/history/{room_id}",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 200


class TestMyChats:
    def test_student_gets_group_and_private_chats(self, client, student_token, student_user, teacher_user):
        resp = client.get("/my-chats", headers={"Authorization": f"Bearer {student_token}"})
        assert resp.status_code == 200
        chats = resp.json()
        types = [c["type"] for c in chats]
        assert "group" in types
        assert "private" in types

    def test_teacher_gets_teachers_chat(self, client, teacher_token):
        resp = client.get("/my-chats", headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        chats = resp.json()
        types = [c["type"] for c in chats]
        assert "teachers" in types

    def test_admin_gets_teachers_chat(self, client, admin_token):
        resp = client.get("/my-chats", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        chats = resp.json()
        types = [c["type"] for c in chats]
        assert "teachers" in types

    def test_student_without_group_gets_only_private_chats(self, client, db):
        user = UserDB(
            username="nogroup2",
            password_hash=__import__("main").get_password_hash("pass123"),
            telegram_id=555555,
            role="student",
            last_notified_event_ids=[],
        )
        db.add(user)
        db.commit()

        login = client.post("/token", data={"username": "nogroup2", "password": "pass123"})
        token = login.json()["access_token"]

        resp = client.get("/my-chats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        chats = resp.json()
        for chat in chats:
            assert chat["type"] != "group"

    def test_group_chat_sorted_first(self, client, student_token, student_user, teacher_user):
        resp = client.get("/my-chats", headers={"Authorization": f"Bearer {student_token}"})
        chats = resp.json()
        if len(chats) > 1:
            assert chats[0]["type"] == "group"

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/my-chats")
        assert resp.status_code == 401


class TestGetTeachers:
    def test_returns_list_of_teachers(self, client, student_token, teacher_user):
        resp = client.get("/teachers", headers={"Authorization": f"Bearer {student_token}"})
        assert resp.status_code == 200
        teachers = resp.json()
        assert isinstance(teachers, list)
        usernames = [t["username"] for t in teachers]
        assert "test_teacher" in usernames

    def test_response_contains_expected_fields(self, client, student_token, teacher_user):
        resp = client.get("/teachers", headers={"Authorization": f"Bearer {student_token}"})
        for teacher in resp.json():
            for field in ["id", "username", "full_name", "department"]:
                assert field in teacher

    def test_non_teachers_not_in_list(self, client, admin_token, admin_user, student_user):
        resp = client.get("/teachers", headers={"Authorization": f"Bearer {admin_token}"})
        usernames = [t["username"] for t in resp.json()]
        assert "test_admin" not in usernames
        assert "test_student" not in usernames

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/teachers")
        assert resp.status_code == 401

    def test_teacher_with_no_full_name_uses_username(self, client, admin_token, db):
        from main import get_password_hash
        user = UserDB(
            username="nameless_teacher",
            password_hash=get_password_hash("pass123"),
            telegram_id=666666,
            role="teacher",
            full_name=None,
            last_notified_event_ids=[],
        )
        db.add(user)
        db.commit()

        resp = client.get("/teachers", headers={"Authorization": f"Bearer {admin_token}"})
        for t in resp.json():
            if t["username"] == "nameless_teacher":
                assert t["full_name"] == "nameless_teacher"


class TestOnlineUsers:
    def test_student_can_get_online_users_in_own_group(self, client, student_token, student_user):
        resp = client.get(
            "/chat/online/group:ИБ-11БО",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 200
        assert "users" in resp.json()

    def test_student_cannot_get_online_in_other_group(self, client, student_token):
        resp = client.get(
            "/chat/online/group:ИБ-21БО",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 403

    def test_online_users_response_structure(self, client, student_token, student_user):
        resp = client.get(
            "/chat/online/group:ИБ-11БО",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        body = resp.json()
        assert isinstance(body["users"], list)
        # No WebSocket connections in tests, so list is empty
        assert len(body["users"]) == 0


class TestRoomKeyManagement:
    def test_get_or_create_room_key_creates_key(self, db):
        from main import get_or_create_room_key
        key = get_or_create_room_key("group:TestGroup", db)
        assert key is not None
        # Check it was persisted
        record = db.query(RoomKey).filter(RoomKey.room_id == "group:TestGroup").first()
        assert record is not None

    def test_get_or_create_room_key_returns_same_key(self, db):
        from main import get_or_create_room_key
        key1 = get_or_create_room_key("group:SameGroup", db)
        key2 = get_or_create_room_key("group:SameGroup", db)
        # Encrypt the same text with both keys and check they produce same result when decrypted
        from main import encrypt_content, decrypt_content
        encrypted = encrypt_content("test", key1)
        decrypted = decrypt_content(encrypted, key2)
        assert decrypted == "test"

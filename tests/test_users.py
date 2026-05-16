"""Tests for user management endpoints."""
import pytest

from main import UserDB, get_password_hash


class TestCreateUser:
    def test_admin_can_create_user(self, client, admin_token):
        resp = client.post(
            "/users/",
            json={
                "username": "new_student",
                "password": "pass1234",
                "telegram_id": 111001,
                "role": "student",
                "full_name": "Новый Студент",
                "group_number": "ИБ-21БО",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "new_student"
        assert body["role"] == "student"

    def test_non_admin_cannot_create_user(self, client, student_token):
        resp = client.post(
            "/users/",
            json={
                "username": "other_user",
                "password": "pass1234",
                "telegram_id": 222001,
                "role": "student",
            },
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 403

    def test_duplicate_username_returns_400(self, client, admin_token, admin_user):
        resp = client.post(
            "/users/",
            json={
                "username": "test_admin",
                "password": "pass1234",
                "telegram_id": 333001,
                "role": "student",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    def test_duplicate_telegram_id_returns_400(self, client, admin_token, admin_user):
        resp = client.post(
            "/users/",
            json={
                "username": "another_user",
                "password": "pass1234",
                "telegram_id": 900001,  # same as admin_user
                "role": "student",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_create_first_student_creates_group_chat(self, client, admin_token, db):
        resp = client.post(
            "/users/",
            json={
                "username": "first_student",
                "password": "pass1234",
                "telegram_id": 444001,
                "role": "student",
                "group_number": "Новая-группа",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        from main import Message
        msg = db.query(Message).filter(Message.room_id == "group:Новая-группа").first()
        assert msg is not None

    def test_create_user_without_token_returns_401(self, client):
        resp = client.post(
            "/users/",
            json={"username": "x", "password": "x", "telegram_id": 1, "role": "student"},
        )
        assert resp.status_code == 401


class TestGetUsers:
    def test_admin_can_list_users(self, client, admin_token, student_user):
        resp = client.get("/users/", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 2  # admin + student

    def test_non_admin_cannot_list_users(self, client, student_token):
        resp = client.get("/users/", headers={"Authorization": f"Bearer {student_token}"})
        assert resp.status_code == 403

    def test_filter_users_by_role(self, client, admin_token, student_user, teacher_user):
        resp = client.get(
            "/users/",
            params={"role": "student"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        for user in resp.json():
            assert user["role"] == "student"

    def test_filter_users_by_group(self, client, admin_token, student_user):
        resp = client.get(
            "/users/",
            params={"group_number": "ИБ-11БО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        for user in resp.json():
            assert user["group_number"] == "ИБ-11БО"


class TestGetCurrentUser:
    def test_returns_own_profile(self, client, student_token, student_user):
        resp = client.get("/users/me", headers={"Authorization": f"Bearer {student_token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "test_student"
        assert body["role"] == "student"

    def test_response_contains_expected_fields(self, client, admin_token, admin_user):
        resp = client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"})
        body = resp.json()
        for field in ["id", "username", "role", "telegram_id", "created_at"]:
            assert field in body


class TestUpdateUser:
    def test_admin_can_update_user(self, client, admin_token, student_user):
        resp = client.put(
            f"/users/{student_user.id}",
            json={"full_name": "Обновлённое Имя"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Обновлённое Имя"

    def test_update_nonexistent_user_returns_404(self, client, admin_token):
        resp = client.put(
            "/users/99999",
            json={"full_name": "X"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    def test_update_to_duplicate_username_returns_400(self, client, admin_token, admin_user, student_user):
        resp = client.put(
            f"/users/{student_user.id}",
            json={"username": "test_admin"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_update_to_duplicate_telegram_id_returns_400(self, client, admin_token, admin_user, student_user):
        resp = client.put(
            f"/users/{student_user.id}",
            json={"telegram_id": 900001},  # admin's tg id
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_update_with_invalid_notification_json_returns_400(self, client, admin_token, student_user):
        resp = client.put(
            f"/users/{student_user.id}",
            json={"notification_settings": "not-valid-json"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400


class TestDeleteUser:
    def test_admin_can_delete_user(self, client, admin_token, student_user, db):
        resp = client.delete(
            f"/users/{student_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert db.query(UserDB).filter(UserDB.id == student_user.id).first() is None

    def test_delete_nonexistent_user_returns_404(self, client, admin_token):
        resp = client.delete(
            "/users/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    def test_non_admin_cannot_delete_user(self, client, student_token, teacher_user):
        resp = client.delete(
            f"/users/{teacher_user.id}",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 403


class TestChangePassword:
    def test_change_password_successfully(self, client, student_token):
        resp = client.put(
            "/users/me/password",
            json={"current_password": "studentpass123", "new_password": "newpassword456"},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Password changed successfully"

    def test_wrong_current_password_returns_401(self, client, student_token):
        resp = client.put(
            "/users/me/password",
            json={"current_password": "wrongpassword", "new_password": "newpassword456"},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 401

    def test_same_password_returns_400(self, client, student_token):
        resp = client.put(
            "/users/me/password",
            json={"current_password": "studentpass123", "new_password": "studentpass123"},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 400


class TestNotificationSettings:
    def test_update_notification_settings(self, client, student_token, student_user):
        resp = client.put(
            "/users/me/notification-settings",
            json={"notification_settings": '{"event_reminder": 60}'},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 200

    def test_invalid_json_notification_settings_returns_400(self, client, student_token):
        resp = client.put(
            "/users/me/notification-settings",
            json={"notification_settings": "not-json"},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 400

    def test_negative_event_reminder_returns_400(self, client, student_token):
        resp = client.put(
            "/users/me/notification-settings",
            json={"notification_settings": '{"event_reminder": -5}'},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 400

    def test_disable_notifications_with_minus_one(self, client, student_token):
        resp = client.put(
            "/users/me/notification-settings",
            json={"notification_settings": '{"event_reminder": -1}'},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 200

    def test_changing_event_reminder_resets_notified_ids(self, client, student_token, student_user, db):
        # First set some notification IDs
        student_user.last_notified_event_ids = [1, 2, 3]
        db.commit()

        client.put(
            "/users/me/notification-settings",
            json={"notification_settings": '{"event_reminder": 120}'},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        db.refresh(student_user)
        assert student_user.last_notified_event_ids == []

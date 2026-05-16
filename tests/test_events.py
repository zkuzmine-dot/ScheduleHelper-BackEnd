"""Tests for event management endpoints."""
import pytest

from main import Event, UserDB


FUTURE_DATETIME = "2030-06-15 14:00"

VALID_EVENT = {
    "title": "Экзамен по математике",
    "event_type": "Экзамен",
    "start_datetime": FUTURE_DATETIME,
    "group_number": "ИБ-11БО",
    "description": "Билеты 1-30",
}


class TestCreateEvent:
    def test_admin_can_create_event(self, client, admin_token):
        resp = client.post(
            "/events/",
            json=VALID_EVENT,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Экзамен по математике"
        assert body["event_type"] == "Экзамен"
        assert body["group_number"] == "ИБ-11БО"

    def test_teacher_can_create_event(self, client, teacher_token):
        resp = client.post(
            "/events/",
            json=VALID_EVENT,
            headers={"Authorization": f"Bearer {teacher_token}"},
        )
        assert resp.status_code == 200

    def test_group_leader_can_create_event(self, client, leader_token):
        resp = client.post(
            "/events/",
            json=VALID_EVENT,
            headers={"Authorization": f"Bearer {leader_token}"},
        )
        assert resp.status_code == 200

    def test_student_cannot_create_event(self, client, student_token):
        resp = client.post(
            "/events/",
            json=VALID_EVENT,
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 403

    def test_invalid_datetime_format_returns_400(self, client, admin_token):
        bad = {**VALID_EVENT, "start_datetime": "15/06/2030 14:00"}
        resp = client.post(
            "/events/",
            json=bad,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_create_event_without_description(self, client, admin_token):
        no_desc = {k: v for k, v in VALID_EVENT.items() if k != "description"}
        resp = client.post(
            "/events/",
            json=no_desc,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] is None

    def test_create_event_unauthenticated_returns_401(self, client):
        resp = client.post("/events/", json=VALID_EVENT)
        assert resp.status_code == 401

    def test_all_event_types_are_accepted(self, client, admin_token):
        for event_type in ["Тест", "Контрольная", "Экзамен", "Другое"]:
            data = {**VALID_EVENT, "event_type": event_type, "title": f"Событие {event_type}"}
            resp = client.post(
                "/events/",
                json=data,
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert resp.status_code == 200, f"Failed for event_type={event_type}"


class TestGetEvents:
    def test_admin_can_get_events(self, client, admin_token, sample_event):
        resp = client.get("/events/", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_student_gets_own_group_events(self, client, student_token, sample_event):
        resp = client.get("/events/", headers={"Authorization": f"Bearer {student_token}"})
        assert resp.status_code == 200
        for e in resp.json():
            assert e["group_number"] == "ИБ-11БО"

    def test_filter_events_by_group(self, client, admin_token, sample_event):
        resp = client.get(
            "/events/",
            params={"group_number": "ИБ-11БО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        for e in resp.json():
            assert e["group_number"] == "ИБ-11БО"

    def test_past_events_not_returned(self, client, admin_token, db):
        from datetime import datetime
        import pytz
        from main import to_utc, MOSCOW_TZ

        past_event = Event(
            title="Прошедшее событие",
            event_type="Тест",
            start_datetime=to_utc(datetime(2020, 1, 1, 10, 0)),
            group_number="ИБ-11БО",
            is_active=True,
        )
        db.add(past_event)
        db.commit()

        resp = client.get(
            "/events/",
            params={"group_number": "ИБ-11БО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        titles = [e["title"] for e in resp.json()]
        assert "Прошедшее событие" not in titles

    def test_student_without_group_returns_400(self, client, db):
        from main import get_password_hash
        user = UserDB(
            username="nogroup_s",
            password_hash=get_password_hash("pass123"),
            telegram_id=888888,
            role="student",
            last_notified_event_ids=[],
        )
        db.add(user)
        db.commit()

        login = client.post("/token", data={"username": "nogroup_s", "password": "pass123"})
        token = login.json()["access_token"]
        resp = client.get("/events/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400


class TestUpdateEvent:
    def test_admin_can_update_event(self, client, admin_token, sample_event):
        resp = client.put(
            f"/events/{sample_event.id}",
            json={"title": "Обновлённое событие"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Обновлённое событие"

    def test_update_start_datetime(self, client, admin_token, sample_event):
        resp = client.put(
            f"/events/{sample_event.id}",
            json={"start_datetime": "2031-01-01 09:00"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    def test_update_invalid_datetime_returns_400(self, client, admin_token, sample_event):
        resp = client.put(
            f"/events/{sample_event.id}",
            json={"start_datetime": "invalid-date"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_update_nonexistent_event_returns_404(self, client, admin_token):
        resp = client.put(
            "/events/99999",
            json={"title": "X"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    def test_student_cannot_update_event(self, client, student_token, sample_event):
        resp = client.put(
            f"/events/{sample_event.id}",
            json={"title": "X"},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 403

    def test_update_group_clears_notified_ids(self, client, admin_token, sample_event, student_user, db):
        student_user.last_notified_event_ids = [sample_event.id]
        db.commit()

        client.put(
            f"/events/{sample_event.id}",
            json={"group_number": "ИБ-21БО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        db.refresh(student_user)
        assert sample_event.id not in (student_user.last_notified_event_ids or [])


class TestDeleteEvent:
    def test_admin_can_soft_delete_event(self, client, admin_token, sample_event, db):
        resp = client.delete(
            f"/events/{sample_event.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        db.refresh(sample_event)
        assert sample_event.is_active is False

    def test_delete_nonexistent_event_returns_404(self, client, admin_token):
        resp = client.delete(
            "/events/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    def test_student_cannot_delete_event(self, client, student_token, sample_event):
        resp = client.delete(
            f"/events/{sample_event.id}",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 403

    def test_deleted_event_not_in_list(self, client, admin_token, sample_event):
        client.delete(
            f"/events/{sample_event.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = client.get(
            "/events/",
            params={"group_number": "ИБ-11БО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        ids = [e["id"] for e in resp.json()]
        assert sample_event.id not in ids

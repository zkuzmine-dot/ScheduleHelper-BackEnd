"""Tests for schedule management endpoints."""
import pytest

from main import Schedule, UserDB


VALID_SCHEDULE = {
    "group_number": "ИБ-11БО",
    "day_of_week": 2,
    "start_time": "09:00",
    "end_time": "10:30",
    "lesson_type": "lecture",
    "subject": "Информатика",
    "classroom": "А-202",
    "teacher_name": "Иванов И.И.",
    "week_type": "both",
    "valid_from": "2026-01-01",
    "valid_to": "2026-12-31",
}


class TestCreateSchedule:
    def test_admin_can_create_schedule(self, client, admin_token):
        resp = client.post(
            "/schedules/",
            json=VALID_SCHEDULE,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["subject"] == "Информатика"
        assert body["group_number"] == "ИБ-11БО"
        assert body["lesson_type"] == "lecture"

    def test_teacher_can_create_schedule(self, client, teacher_token):
        resp = client.post(
            "/schedules/",
            json=VALID_SCHEDULE,
            headers={"Authorization": f"Bearer {teacher_token}"},
        )
        assert resp.status_code == 200

    def test_group_leader_can_create_schedule(self, client, leader_token):
        resp = client.post(
            "/schedules/",
            json=VALID_SCHEDULE,
            headers={"Authorization": f"Bearer {leader_token}"},
        )
        assert resp.status_code == 200

    def test_student_cannot_create_schedule(self, client, student_token):
        resp = client.post(
            "/schedules/",
            json=VALID_SCHEDULE,
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 403

    def test_invalid_time_format_returns_400(self, client, admin_token):
        bad = {**VALID_SCHEDULE, "start_time": "9:00am"}
        resp = client.post(
            "/schedules/",
            json=bad,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_invalid_end_time_format_returns_400(self, client, admin_token):
        bad = {**VALID_SCHEDULE, "end_time": "not-a-time"}
        resp = client.post(
            "/schedules/",
            json=bad,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_invalid_day_of_week_returns_400(self, client, admin_token):
        bad = {**VALID_SCHEDULE, "day_of_week": 8}
        resp = client.post(
            "/schedules/",
            json=bad,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_day_of_week_zero_returns_400(self, client, admin_token):
        bad = {**VALID_SCHEDULE, "day_of_week": 0}
        resp = client.post(
            "/schedules/",
            json=bad,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_invalid_valid_from_format_returns_400(self, client, admin_token):
        bad = {**VALID_SCHEDULE, "valid_from": "01-01-2026"}
        resp = client.post(
            "/schedules/",
            json=bad,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_invalid_valid_to_format_returns_400(self, client, admin_token):
        bad = {**VALID_SCHEDULE, "valid_to": "01-01-2026"}
        resp = client.post(
            "/schedules/",
            json=bad,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_create_schedule_without_optional_fields(self, client, admin_token):
        minimal = {
            "group_number": "ИБ-31БО",
            "day_of_week": 3,
            "start_time": "11:00",
            "end_time": "12:30",
            "lesson_type": "lab",
            "subject": "Физика",
            "week_type": "numerator",
        }
        resp = client.post(
            "/schedules/",
            json=minimal,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200


class TestGetSchedules:
    def test_admin_can_get_all_schedules(self, client, admin_token, sample_schedule):
        resp = client.get(
            "/schedules/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_student_gets_own_group_schedules(self, client, student_token, sample_schedule):
        resp = client.get(
            "/schedules/",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 200
        for s in resp.json():
            assert s["group_number"] == "ИБ-11БО"

    def test_filter_by_group_number(self, client, admin_token, sample_schedule):
        resp = client.get(
            "/schedules/",
            params={"group_number": "ИБ-11БО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        for s in resp.json():
            assert s["group_number"] == "ИБ-11БО"

    def test_student_without_group_returns_400(self, client, db):
        from main import get_password_hash
        user = UserDB(
            username="nogroup_student",
            password_hash=get_password_hash("pass123"),
            telegram_id=777777,
            role="student",
            last_notified_event_ids=[],
        )
        db.add(user)
        db.commit()

        login = client.post("/token", data={"username": "nogroup_student", "password": "pass123"})
        token = login.json()["access_token"]

        resp = client.get("/schedules/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400

    def test_filter_by_week_current(self, client, admin_token, sample_schedule):
        resp = client.get(
            "/schedules/",
            params={"week": "current"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    def test_filter_by_week_next(self, client, admin_token, sample_schedule):
        resp = client.get(
            "/schedules/",
            params={"week": "next"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200


class TestUpdateSchedule:
    def test_admin_can_update_schedule(self, client, admin_token, sample_schedule):
        resp = client.put(
            f"/schedules/{sample_schedule.id}",
            json={"subject": "Обновлённый предмет"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["subject"] == "Обновлённый предмет"

    def test_update_time_fields(self, client, admin_token, sample_schedule):
        resp = client.put(
            f"/schedules/{sample_schedule.id}",
            json={"start_time": "10:00", "end_time": "11:30"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["start_time"] == "10:00"

    def test_update_nonexistent_schedule_returns_404(self, client, admin_token):
        resp = client.put(
            "/schedules/99999",
            json={"subject": "X"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    def test_update_invalid_start_time_returns_400(self, client, admin_token, sample_schedule):
        resp = client.put(
            f"/schedules/{sample_schedule.id}",
            json={"start_time": "bad-time"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_update_invalid_end_time_returns_400(self, client, admin_token, sample_schedule):
        resp = client.put(
            f"/schedules/{sample_schedule.id}",
            json={"end_time": "bad-time"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_update_invalid_day_of_week_returns_400(self, client, admin_token, sample_schedule):
        resp = client.put(
            f"/schedules/{sample_schedule.id}",
            json={"day_of_week": 0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_update_invalid_valid_from_returns_400(self, client, admin_token, sample_schedule):
        resp = client.put(
            f"/schedules/{sample_schedule.id}",
            json={"valid_from": "not-a-date"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_update_invalid_valid_to_returns_400(self, client, admin_token, sample_schedule):
        resp = client.put(
            f"/schedules/{sample_schedule.id}",
            json={"valid_to": "not-a-date"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_student_cannot_update_schedule(self, client, student_token, sample_schedule):
        resp = client.put(
            f"/schedules/{sample_schedule.id}",
            json={"subject": "X"},
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 403


class TestDeleteSchedule:
    def test_admin_can_soft_delete_schedule(self, client, admin_token, sample_schedule, db):
        resp = client.delete(
            f"/schedules/{sample_schedule.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        db.refresh(sample_schedule)
        assert sample_schedule.is_active is False

    def test_delete_nonexistent_schedule_returns_404(self, client, admin_token):
        resp = client.delete(
            "/schedules/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    def test_student_cannot_delete_schedule(self, client, student_token, sample_schedule):
        resp = client.delete(
            f"/schedules/{sample_schedule.id}",
            headers={"Authorization": f"Bearer {student_token}"},
        )
        assert resp.status_code == 403

    def test_deleted_schedule_not_in_list(self, client, admin_token, sample_schedule):
        client.delete(
            f"/schedules/{sample_schedule.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = client.get(
            "/schedules/",
            params={"group_number": "ИБ-11БО"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        ids = [s["id"] for s in resp.json()]
        assert sample_schedule.id not in ids

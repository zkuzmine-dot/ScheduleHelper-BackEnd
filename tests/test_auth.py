"""Tests for authentication endpoints: /token, /refresh, /logout."""
import pytest
from jose import jwt

import main


class TestLogin:
    def test_successful_login_returns_tokens(self, client, admin_user):
        resp = client.post("/token", data={"username": "test_admin", "password": "adminpass123"})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    def test_wrong_password_returns_401(self, client, admin_user):
        resp = client.post("/token", data={"username": "test_admin", "password": "wrongpassword"})
        assert resp.status_code == 401

    def test_unknown_user_returns_401(self, client):
        resp = client.post("/token", data={"username": "nobody", "password": "pass"})
        assert resp.status_code == 401

    def test_access_token_contains_username(self, client, admin_user):
        resp = client.post("/token", data={"username": "test_admin", "password": "adminpass123"})
        token = resp.json()["access_token"]
        payload = jwt.decode(token, main.SECRET_KEY, algorithms=[main.ALGORITHM])
        assert payload["sub"] == "test_admin"

    def test_login_updates_last_login(self, client, admin_user, db):
        assert admin_user.last_login is None
        client.post("/token", data={"username": "test_admin", "password": "adminpass123"})
        db.refresh(admin_user)
        assert admin_user.last_login is not None

    def test_rate_limit_blocks_after_max_attempts(self, client, fake_redis):
        # Exceed 5 attempts from same IP
        for _ in range(5):
            client.post("/token", data={"username": "nobody", "password": "bad"})
        resp = client.post("/token", data={"username": "nobody", "password": "bad"})
        assert resp.status_code == 429

    def test_tgid_param_updates_telegram_id(self, client, admin_user, db):
        resp = client.post(
            "/token",
            data={"username": "test_admin", "password": "adminpass123"},
            params={"tgid": 999999},
        )
        assert resp.status_code == 200
        db.refresh(admin_user)
        assert admin_user.telegram_id == 999999

    def test_tgid_param_not_updated_if_taken_by_another_user(self, client, admin_user, student_user):
        # student_user has telegram_id=900002
        resp = client.post(
            "/token",
            data={"username": "test_admin", "password": "adminpass123"},
            params={"tgid": 900002},
        )
        assert resp.status_code == 200
        # admin's telegram_id should NOT change to 900002 (already taken)


class TestRefreshToken:
    def test_refresh_returns_new_tokens(self, client, admin_user):
        login_resp = client.post("/token", data={"username": "test_admin", "password": "adminpass123"})
        refresh_token = login_resp.json()["refresh_token"]

        resp = client.post("/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body

    def test_invalid_refresh_token_returns_401(self, client):
        resp = client.post("/refresh", json={"refresh_token": "invalid.token.here"})
        assert resp.status_code == 401

    def test_access_token_used_as_refresh_returns_401(self, client, admin_user):
        login_resp = client.post("/token", data={"username": "test_admin", "password": "adminpass123"})
        access_token = login_resp.json()["access_token"]

        resp = client.post("/refresh", json={"refresh_token": access_token})
        assert resp.status_code == 401

    def test_refresh_for_deleted_user_returns_401(self, client, admin_user, db):
        login_resp = client.post("/token", data={"username": "test_admin", "password": "adminpass123"})
        refresh_token = login_resp.json()["refresh_token"]

        db.delete(admin_user)
        db.commit()

        resp = client.post("/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 401


class TestLogout:
    def test_logout_returns_success_message(self, client, admin_token):
        resp = client.post(
            "/logout",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert "logged out" in resp.json()["message"].lower()

    def test_access_token_blacklisted_after_logout(self, client, admin_token):
        client.post("/logout", headers={"Authorization": f"Bearer {admin_token}"})
        resp = client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 401

    def test_logout_with_refresh_token(self, client, admin_user):
        login_resp = client.post("/token", data={"username": "test_admin", "password": "adminpass123"})
        access_token = login_resp.json()["access_token"]
        refresh_token = login_resp.json()["refresh_token"]

        resp = client.post(
            "/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200

    def test_logout_without_token_returns_401(self, client):
        resp = client.post("/logout")
        assert resp.status_code == 401

    def test_get_current_user_with_valid_token(self, client, admin_token):
        resp = client.get("/users/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "test_admin"

    def test_get_current_user_without_token_returns_401(self, client):
        resp = client.get("/users/me")
        assert resp.status_code == 401

    def test_get_current_user_with_invalid_token_returns_401(self, client):
        resp = client.get("/users/me", headers={"Authorization": "Bearer invalid.jwt.token"})
        assert resp.status_code == 401

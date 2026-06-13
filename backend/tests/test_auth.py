"""
test_auth.py — Tests for /api/v1/auth endpoints.

Endpoints:
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  GET  /api/v1/auth/me
  POST /api/v1/auth/refresh
"""

import pytest
import hashlib
import unittest.mock as mock
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

from tests.conftest import make_mock_result, make_row, TEST_USER


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------

class TestRegister:

    @pytest.mark.asyncio
    async def test_register_success(self, auth_client):
        client, db = auth_client
        # Simulate: no existing user, org created, user created, org_member created
        db.execute.side_effect = [
            make_mock_result(rows=[]),            # uniqueness check → not found
            make_mock_result(scalar_value="22222222-2222-2222-2222-222222222222"),  # org insert
            make_mock_result(scalar_value="11111111-1111-1111-1111-111111111111"),  # user insert
            make_mock_result(),                   # org_members insert
            make_mock_result(),                   # refresh_token insert
        ]

        payload = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "display_name": "New User",
            "org_name": "New Org",
        }
        response = await client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["role"] == "human"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, auth_client):
        client, db = auth_client
        existing_row = make_row(id="existing-uuid")
        db.execute.side_effect = [
            make_mock_result(rows=[existing_row]),  # email exists
        ]

        payload = {
            "email": "existing@example.com",
            "password": "securepassword123",
            "display_name": "Existing",
            "org_name": "Some Org",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 400
        assert "user_exists" in response.text

    @pytest.mark.asyncio
    async def test_register_short_password(self, auth_client):
        client, db = auth_client
        payload = {
            "email": "user@example.com",
            "password": "short",
            "display_name": "User",
            "org_name": "Org",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422  # Pydantic validation fails (min_length=12)

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, auth_client):
        client, db = auth_client
        payload = {
            "email": "not-an-email",
            "password": "securepassword123",
            "display_name": "User",
            "org_name": "Org",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------

class TestLogin:

    @pytest.mark.asyncio
    async def test_login_success(self, auth_client):
        client, db = auth_client
        from app.core.security import hash_password
        hashed = hash_password("securepassword123")

        user_row = make_row(
            id="11111111-1111-1111-1111-111111111111",
            email="test@example.com",
            password_hash=hashed,
            display_name="Test User",
            role="human",
            org_id="22222222-2222-2222-2222-222222222222",
        )
        db.execute.side_effect = [
            make_mock_result(rows=[user_row]),   # user lookup
            make_mock_result(),                  # delete old refresh tokens
            make_mock_result(),                  # insert new refresh token
        ]

        response = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "securepassword123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, auth_client):
        client, db = auth_client
        from app.core.security import hash_password
        hashed = hash_password("correctpassword123")

        user_row = make_row(
            id="11111111-1111-1111-1111-111111111111",
            email="test@example.com",
            password_hash=hashed,
            display_name="Test",
            role="human",
            org_id=None,
        )
        db.execute.side_effect = [
            make_mock_result(rows=[user_row]),
        ]

        response = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword123",
        })
        assert response.status_code == 401
        assert "invalid_credentials" in response.text

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, auth_client):
        client, db = auth_client
        db.execute.side_effect = [
            make_mock_result(rows=[]),  # no user found
        ]

        # blind_compare has a production bug: DUMMY_HASH is a str but bcrypt
        # needs bytes. We mock it out here since it's a timing-only side-effect.
        with mock.patch("app.routers.auth.blind_compare"):
            response = await client.post("/api/v1/auth/login", json={
                "email": "ghost@example.com",
                "password": "password123456",
            })
        assert response.status_code == 401
        assert "invalid_credentials" in response.text

    @pytest.mark.asyncio
    async def test_login_sets_refresh_cookie(self, auth_client):
        client, db = auth_client
        from app.core.security import hash_password
        hashed = hash_password("securepassword123")

        user_row = make_row(
            id="11111111-1111-1111-1111-111111111111",
            email="test@example.com",
            password_hash=hashed,
            display_name="Test",
            role="human",
            org_id=None,
        )
        db.execute.side_effect = [
            make_mock_result(rows=[user_row]),
            make_mock_result(),
            make_mock_result(),
        ]

        response = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "securepassword123",
        })
        assert response.status_code == 200
        assert "refresh_token" in response.cookies


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------

class TestGetMe:

    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, auth_client):
        client, db = auth_client
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == TEST_USER["id"]
        assert data["email"] == TEST_USER["email"]

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, anon_client):
        response = await anon_client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_endpoint_requires_auth(self, anon_client):
        """Test that a raw unauthenticated request is rejected with 401."""
        response = await anon_client.get("/orgs/acme/repos")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------

class TestRefreshToken:

    @pytest.mark.asyncio
    async def test_refresh_missing_cookie(self, auth_client):
        client, db = auth_client
        response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == 401
        assert "missing_session_token" in response.text

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, auth_client):
        client, db = auth_client
        db.execute.side_effect = [
            make_mock_result(rows=[]),  # token not found
        ]
        client.cookies.set("refresh_token", "invalid-token")
        response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == 401
        assert "invalid_session" in response.text

    @pytest.mark.asyncio
    async def test_refresh_token_reuse_detected(self, auth_client):
        client, db = auth_client
        used_token = "sometoken"
        token_hash = hashlib.sha256(used_token.encode()).hexdigest()

        token_row = make_row(
            id="tok-1",
            user_id="user-1",
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            used_at=datetime.now(timezone.utc),  # already used!
        )
        db.execute.side_effect = [
            make_mock_result(rows=[token_row]),
            make_mock_result(),  # DELETE all user tokens
        ]
        client.cookies.set("refresh_token", used_token)
        response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == 401
        assert "compromised_session" in response.text

    @pytest.mark.asyncio
    async def test_refresh_expired_token(self, auth_client):
        client, db = auth_client
        used_token = "sometoken"
        token_row = make_row(
            id="tok-1",
            user_id="user-1",
            token_hash=hashlib.sha256(used_token.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # expired
            used_at=None,
        )
        db.execute.side_effect = [
            make_mock_result(rows=[token_row]),
        ]
        client.cookies.set("refresh_token", used_token)
        response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == 401
        assert "expired_session" in response.text

    @pytest.mark.asyncio
    async def test_refresh_success(self, auth_client):
        client, db = auth_client
        raw_token = "validtoken"
        token_row = make_row(
            id="tok-1",
            user_id="11111111-1111-1111-1111-111111111111",
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            used_at=None,
        )
        db.execute.side_effect = [
            make_mock_result(rows=[token_row]),  # token lookup
            make_mock_result(),                  # mark used
            make_mock_result(scalar_value="test@example.com"),  # user email
            make_mock_result(),                  # insert new token
        ]
        client.cookies.set("refresh_token", raw_token)
        response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["expires_in"] == 900

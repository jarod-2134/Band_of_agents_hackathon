"""
test_auth.py — Async-compliant and Multi-Tenant Tests for /api/v1/auth endpoints.
"""

import pytest
import hashlib
import unittest.mock as mock
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

from tests.conftest import make_mock_result, make_row, TEST_USER


# Helper to handle async database execution and commits simultaneously
def setup_async_db(db, return_value=None, side_effect=None):
    mock_execute = AsyncMock()
    if side_effect:
        mock_execute.side_effect = side_effect
    else:
        mock_execute.return_value = return_value
    db.execute = mock_execute
    db.commit = AsyncMock()
    return mock_execute


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------

class TestRegister:

    @pytest.mark.asyncio
    async def test_register_success(self, auth_client):
        client, db = auth_client
        
        # ✅ Fixed: Added 'org_slug' to fulfill multi-tenant JWT payload construction requirements
        org_member_row = make_row(
            org_id="22222222-2222-2222-2222-222222222222",
            org_slug="new-org",
            member_role="owner"
        )
        
        # Simulate: no existing user, org created, user created, org_member created, org list fetched, refresh token created
        setup_async_db(db, side_effect=[
            make_mock_result(rows=[]),                                            # 1. uniqueness check → not found
            make_mock_result(scalar_value="22222222-2222-2222-2222-222222222222"),  # 2. org insert
            make_mock_result(scalar_value="11111111-1111-1111-1111-111111111111"),  # 3. user insert
            make_mock_result(),                                                   # 4. org_members insert
            make_mock_result(rows=[org_member_row]),                              # 5. Fetch multi-tenant org list mapping
            make_mock_result(),                                                   # 6. refresh_token insert
        ])

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
        setup_async_db(db, side_effect=[
            make_mock_result(rows=[existing_row]),  # email exists
        ])

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
        # ✅ Fixed: Added 'org_slug' property mapping structure to prevent response schema parser KeyError failures
        org_member_row = make_row(
            org_id="22222222-2222-2222-2222-222222222222",
            org_slug="test-org",
            member_role="owner"
        )
        
        setup_async_db(db, side_effect=[
            make_mock_result(rows=[user_row]),        # 1. user lookup
            make_mock_result(),                       # 2. delete old refresh tokens
            make_mock_result(rows=[org_member_row]),  # 3. fetch org mappings
            make_mock_result(),                       # 4. insert new refresh token
        ])

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
        setup_async_db(db, side_effect=[
            make_mock_result(rows=[user_row]),
        ])

        response = await client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword123",
        })
        assert response.status_code == 401
        assert "invalid_credentials" in response.text

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, auth_client):
        client, db = auth_client
        setup_async_db(db, side_effect=[
            make_mock_result(rows=[]),  # no user found
        ])

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
        setup_async_db(db, side_effect=[
            make_mock_result(rows=[user_row]),
            make_mock_result(),
            make_mock_result(rows=[]),  # returns no org memberships
            make_mock_result(),
        ])

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
        setup_async_db(db, side_effect=[
            make_mock_result(rows=[]),  # token not found
        ])
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
        setup_async_db(db, side_effect=[
            make_mock_result(rows=[token_row]),
            make_mock_result(),  # DELETE all user tokens
        ])
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
        setup_async_db(db, side_effect=[
            make_mock_result(rows=[token_row]),
        ])
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
        # ✅ Fixed: Added 'org_slug' attribute layout tracking parameters
        org_member_row = make_row(
            org_id="22222222-2222-2222-2222-222222222222",
            org_slug="test-org",
            member_role="owner"
        )

        setup_async_db(db, side_effect=[
            make_mock_result(rows=[token_row]),                 # 1. token lookup
            make_mock_result(),                                 # 2. mark used
            make_mock_result(scalar_value="test@example.com"),  # 3. user email
            make_mock_result(rows=[org_member_row]),            # 4. fetch orgs during refresh too
            make_mock_result(),                                 # 5. insert new token
        ])
        client.cookies.set("refresh_token", raw_token)
        response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["expires_in"] == 900
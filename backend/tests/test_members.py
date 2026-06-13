"""
test_members.py — Tests for /api/v1/orgs/{slug}/users endpoints.

Endpoints:
  GET    /api/v1/orgs/{slug}/users
  POST   /api/v1/orgs/{slug}/users/invite
  PATCH  /api/v1/orgs/{slug}/users/{id}
  DELETE /api/v1/orgs/{slug}/users/{id}
"""

import pytest
from tests.conftest import make_mock_result, make_row, TEST_USER, TEST_ORG


ORG_SLUG = TEST_ORG["slug"]
BASE = f"/api/v1/orgs/{ORG_SLUG}/users"


class TestListMembers:

    @pytest.mark.asyncio
    async def test_list_members_returns_users(self, auth_client):
        client, db = auth_client
        member_row = make_row(
            id="11111111-1111-1111-1111-111111111111",
            email="test@example.com",
            display_name="Test User",
            role="owner",
            status="active",
            last_active="2026-01-01T00:00:00",
        )
        db.execute.return_value = make_mock_result(rows=[member_row])

        response = await client.get(BASE)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_list_members_unauthenticated(self, anon_client):
        response = await anon_client.get(BASE)
        assert response.status_code in (401, 403)


class TestInviteUser:

    @pytest.mark.asyncio
    async def test_invite_new_user(self, auth_client):
        client, db = auth_client
        db.execute.side_effect = [
            make_mock_result(rows=[]),  # no existing membership
            make_mock_result(),         # insert invite
        ]

        response = await client.post(f"{BASE}/invite", json={
            "email": "newmember@example.com",
            "role": "member",
        })
        assert response.status_code == 201
        data = response.json()
        assert "Invitation dispatched" in data["message"]
        assert "expires_at" in data

    @pytest.mark.asyncio
    async def test_invite_existing_member_returns_400(self, auth_client):
        client, db = auth_client
        db.execute.side_effect = [
            make_mock_result(rows=[make_row(id=1)]),  # already a member
        ]

        response = await client.post(f"{BASE}/invite", json={
            "email": "existing@example.com",
            "role": "member",
        })
        assert response.status_code == 400
        assert "already an active member" in response.text

    @pytest.mark.asyncio
    async def test_invite_invalid_email(self, auth_client):
        client, db = auth_client
        response = await client.post(f"{BASE}/invite", json={
            "email": "not-valid",
            "role": "member",
        })
        assert response.status_code == 422


class TestChangeMemberRole:

    @pytest.mark.asyncio
    async def test_change_role_success(self, auth_client):
        client, db = auth_client
        member_row = make_row(member_role="member")
        db.execute.side_effect = [
            make_mock_result(rows=[member_row]),  # target lookup
            make_mock_result(),                   # update role
        ]

        target_id = "99999999-9999-9999-9999-999999999999"
        response = await client.patch(f"{BASE}/{target_id}", json={"role": "admin"})
        assert response.status_code == 200
        data = response.json()
        assert data["new_role"] == "admin"

    @pytest.mark.asyncio
    async def test_change_role_member_not_found(self, auth_client):
        client, db = auth_client
        db.execute.side_effect = [
            make_mock_result(rows=[]),  # not found
        ]

        response = await client.patch(f"{BASE}/nonexistent-id", json={"role": "admin"})
        assert response.status_code == 404


class TestRemoveMember:

    @pytest.mark.asyncio
    async def test_remove_other_member_success(self, auth_client):
        client, db = auth_client
        member_row = make_row(member_role="member")
        db.execute.side_effect = [
            make_mock_result(rows=[member_row]),  # target lookup
            make_mock_result(),                   # delete
        ]

        other_id = "99999999-9999-9999-9999-999999999999"
        response = await client.delete(f"{BASE}/{other_id}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_cannot_remove_self(self, auth_client):
        client, db = auth_client
        # Trying to remove yourself (same id as TEST_USER)
        response = await client.delete(f"{BASE}/{TEST_USER['id']}")
        assert response.status_code == 400
        assert "Cannot remove yourself" in response.text

    @pytest.mark.asyncio
    async def test_remove_nonexistent_member(self, auth_client):
        client, db = auth_client
        db.execute.side_effect = [
            make_mock_result(rows=[]),  # target not found
        ]

        response = await client.delete(f"{BASE}/nonexistent-id")
        assert response.status_code == 404

"""
test_org.py — Tests for /api/v1/orgs endpoints.

Endpoints:
  GET    /api/v1/orgs
  POST   /api/v1/orgs
  GET    /api/v1/orgs/{slug}
  PATCH  /api/v1/orgs/{slug}
  DELETE /api/v1/orgs/{slug}
"""

import pytest
from tests.conftest import make_mock_result, make_row, TEST_USER, TEST_ORG


class TestListOrgs:

    @pytest.mark.asyncio
    async def test_list_orgs_returns_user_orgs(self, auth_client):
        client, db = auth_client
        org_row = make_row(
            id="22222222-2222-2222-2222-222222222222",
            slug="test-org",
            name="Test Org",
            member_role="owner",
        )
        db.execute.return_value = make_mock_result(rows=[org_row])

        response = await client.get("/api/v1/orgs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["slug"] == "test-org"
        assert data[0]["member_role"] == "owner"

    @pytest.mark.asyncio
    async def test_list_orgs_empty(self, auth_client):
        client, db = auth_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get("/api/v1/orgs")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_orgs_unauthenticated(self, anon_client):
        response = await anon_client.get("/api/v1/orgs")
        assert response.status_code == 401


class TestCreateOrg:

    @pytest.mark.asyncio
    async def test_create_org_success(self, auth_client):
        client, db = auth_client
        new_org_row = make_row(
            id="33333333-3333-3333-3333-333333333333",
            name="New Org",
            slug="new-org",
        )
        db.execute.side_effect = [
            make_mock_result(rows=[new_org_row]),  # org insert with RETURNING
            make_mock_result(),                    # org_members insert
        ]

        response = await client.post("/api/v1/orgs", json={"name": "New Org", "slug": "new-org"})
        assert response.status_code == 201
        data = response.json()
        assert data["slug"] == "new-org"
        assert data["name"] == "New Org"
        assert data["member_role"] == "owner"

    @pytest.mark.asyncio
    async def test_create_org_auto_generates_slug(self, auth_client):
        client, db = auth_client
        new_org_row = make_row(
            id="33333333-3333-3333-3333-333333333333",
            name="My Org Name",
            slug="my-org-name",
        )
        db.execute.side_effect = [
            make_mock_result(rows=[new_org_row]),
            make_mock_result(),
        ]
        # Sending no slug — server should generate one
        response = await client.post("/api/v1/orgs", json={"name": "My Org Name"})
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_org_unauthenticated(self, anon_client):
        response = await anon_client.post("/api/v1/orgs", json={"name": "Org"})
        assert response.status_code == 401


class TestGetOrg:

    @pytest.mark.asyncio
    async def test_get_org_success(self, auth_client):
        client, db = auth_client
        counts_row = make_row(member_count=3, repo_count=5)
        db.execute.return_value = make_mock_result(rows=[counts_row])

        response = await client.get("/api/v1/orgs/test-org")
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == "test-org"
        assert "member_count" in data
        assert "repo_count" in data

    @pytest.mark.asyncio
    async def test_get_org_not_member(self, anon_client):
        # anon_client has no org context → middleware returns 401 or 403
        response = await anon_client.get("/api/v1/orgs/some-org")
        assert response.status_code in (401, 403)


class TestUpdateOrg:

    @pytest.mark.asyncio
    async def test_update_org_success(self, auth_client):
        client, db = auth_client
        db.execute.return_value = make_mock_result()

        response = await client.patch("/api/v1/orgs/test-org", json={"name": "Updated Org"})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Org"

    @pytest.mark.asyncio
    async def test_update_org_no_name_returns_400(self, auth_client):
        client, db = auth_client
        response = await client.patch("/api/v1/orgs/test-org", json={})
        assert response.status_code == 400


class TestDeleteOrg:

    @pytest.mark.asyncio
    async def test_delete_org_queues_background_job(self, auth_client):
        client, db = auth_client
        response = await client.delete("/api/v1/orgs/test-org")
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "queued"
        assert "job_id" in data

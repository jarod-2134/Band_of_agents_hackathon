"""
test_issues.py — Tests for /api/v1/orgs/{org_id}/issues endpoints.

Endpoints:
  POST /api/v1/orgs/{org_id}/issues/index
  POST /api/v1/orgs/{org_id}/issues/search-similar
"""

import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import make_mock_result, make_row, TEST_ORG

ORG_ID = TEST_ORG["org_id"]
BASE = f"/api/v1/orgs/{ORG_ID}/issues"


class TestCreateAndIndexIssue:

    @pytest.mark.asyncio
    async def test_create_issue_success(self, auth_client):
        client, db = auth_client
        # Issue insert returns id; embedding insert returns nothing
        db.execute.side_effect = [
            make_mock_result(scalar_value="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),  # issue insert
            make_mock_result(),                                                       # embedding insert
        ]

        response = await client.post(f"{BASE}/index", json={
            "title": "Login button is broken",
            "description": "Clicking login does nothing",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "indexed"
        assert "issue_id" in data

    @pytest.mark.asyncio
    async def test_create_issue_unauthenticated(self, anon_client):
        response = await anon_client.post(f"{BASE}/index", json={
            "title": "Bug",
            "description": "Something broke",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_issue_missing_fields(self, auth_client):
        client, db = auth_client
        response = await client.post(f"{BASE}/index", json={"title": "Only title"})
        assert response.status_code == 422


class TestSearchSimilarIssues:

    @pytest.mark.asyncio
    async def test_search_returns_results(self, auth_client):
        client, db = auth_client
        result_row = make_row(
            issue_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            chunk_text="Login bug text",
            cosine_distance=0.1,
        )
        db.execute.return_value = make_mock_result(rows=[result_row])

        response = await client.post(f"{BASE}/search-similar", json={
            "title": "Login bug",
            "description": "broken login",
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["score"] == pytest.approx(0.9, abs=0.01)

    @pytest.mark.asyncio
    async def test_search_empty_results(self, auth_client):
        client, db = auth_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.post(f"{BASE}/search-similar", json={
            "title": "Nonexistent",
            "description": "No match",
        })
        assert response.status_code == 200
        assert response.json() == []

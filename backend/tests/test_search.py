"""
test_search.py — Tests for /orgs/{org_slug}/search endpoints.

Endpoints:
  POST /orgs/{org_slug}/search/code
  POST /orgs/{org_slug}/search/issues
  POST /orgs/{org_slug}/search/memory
  POST /orgs/{org_slug}/search/repos/{repo_id}/search/code
"""

import pytest
from tests.conftest import make_mock_result, make_row

ORG = "test-org"
BASE = f"/orgs/{ORG}/search"


class TestSearchCode:

    @pytest.mark.asyncio
    async def test_search_code_success(self, sync_client):
        client, db = sync_client
        result_row = make_row(content="def login():", filepath="auth.py", repo_id="repo-1")
        db.execute.return_value = make_mock_result(rows=[result_row])

        response = await client.post(f"{BASE}/code", json={"query": "login function", "limit": 5})
        assert response.status_code == 200
        assert "results" in response.json()

    @pytest.mark.asyncio
    async def test_search_code_empty_results(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.post(f"{BASE}/code", json={"query": "no match"})
        assert response.status_code == 200
        assert response.json()["results"] == []

    @pytest.mark.asyncio
    async def test_search_code_missing_query(self, sync_client):
        client, db = sync_client
        response = await client.post(f"{BASE}/code", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_search_code_with_filters(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.post(f"{BASE}/code", json={
            "query": "auth",
            "filters": {"author": "alice", "branch": "main"},
        })
        assert response.status_code == 200


class TestSearchIssues:

    @pytest.mark.asyncio
    async def test_search_issues_success(self, sync_client):
        client, db = sync_client
        result_row = make_row(issue_id=1, title="Login bug", status="open")
        db.execute.return_value = make_mock_result(rows=[result_row])

        response = await client.post(f"{BASE}/issues", json={"query": "login"})
        assert response.status_code == 200
        assert "results" in response.json()

    @pytest.mark.asyncio
    async def test_search_issues_missing_query(self, sync_client):
        client, db = sync_client
        response = await client.post(f"{BASE}/issues", json={})
        assert response.status_code == 422


class TestSearchMemory:

    @pytest.mark.asyncio
    async def test_search_memory_success(self, sync_client):
        client, db = sync_client
        result_row = make_row(summary="Deployed feature X", importance_weight=0.9, agent_id=1)
        db.execute.return_value = make_mock_result(rows=[result_row])

        response = await client.post(f"{BASE}/memory", json={"query": "deploy feature"})
        assert response.status_code == 200
        assert "results" in response.json()

    @pytest.mark.asyncio
    async def test_search_memory_empty(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.post(f"{BASE}/memory", json={"query": "nothing"})
        assert response.status_code == 200
        assert response.json()["results"] == []


class TestRepoScopedSearch:

    @pytest.mark.asyncio
    async def test_search_repo_code_success(self, sync_client):
        client, db = sync_client
        result_row = make_row(content="class Auth:", filepath="auth.py")
        db.execute.return_value = make_mock_result(rows=[result_row])

        response = await client.post(f"{BASE}/repos/42/search/code", json={"query": "auth class"})
        assert response.status_code == 200
        assert "results" in response.json()

    @pytest.mark.asyncio
    async def test_search_repo_code_empty(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.post(f"{BASE}/repos/42/search/code", json={"query": "nothing"})
        assert response.status_code == 200
        assert response.json()["results"] == []

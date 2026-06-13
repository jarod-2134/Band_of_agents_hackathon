"""
test_repos.py — Tests for /orgs/{org_slug}/repos endpoints.

Endpoints:
  GET    /orgs/{org_slug}/repos
  POST   /orgs/{org_slug}/repos
  GET    /orgs/{org_slug}/repos/{repo_id}
  PATCH  /orgs/{org_slug}/repos/{repo_id}
  DELETE /orgs/{org_slug}/repos/{repo_id}
  GET    /orgs/{org_slug}/repos/{repo_id}/branches
  POST   /orgs/{org_slug}/repos/{repo_id}/branches
  GET    /orgs/{org_slug}/repos/{repo_id}/branches/{branch_name}
  DELETE /orgs/{org_slug}/repos/{repo_id}/branches/{branch_name}
  PATCH  /orgs/{org_slug}/repos/{repo_id}/branches/{branch_name}/protect
  GET    /orgs/{org_slug}/repos/{repo_id}/commits
  POST   /orgs/{org_slug}/repos/{repo_id}/commit
"""

import pytest
from unittest.mock import MagicMock, patch
from tests.conftest import make_mock_result, make_row, TEST_ORG

ORG = "test-org"
BASE = f"/orgs/{ORG}/repos"
REPO_ID = "repo-123"


class TestListRepos:

    @pytest.mark.asyncio
    async def test_list_repos_success(self, sync_client):
        client, db = sync_client
        repo_row = make_row(id=REPO_ID, name="my-repo", org_slug=ORG, fs_path="test-org-my-repo")
        db.execute.return_value = make_mock_result(rows=[repo_row])

        response = await client.get(BASE)
        assert response.status_code == 200
        data = response.json()
        assert "repositories" in data
        assert len(data["repositories"]) == 1

    @pytest.mark.asyncio
    async def test_list_repos_empty(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(BASE)
        assert response.status_code == 200
        assert response.json()["repositories"] == []


class TestCreateRepo:

    @pytest.mark.asyncio
    async def test_create_repo_success(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(scalar_value="new-repo-id")

        with patch("app.routers.repos.os.path.exists", return_value=False), \
             patch("app.routers.repos.os.makedirs"), \
             patch("app.routers.repos.pygit2.init_repository"):
            response = await client.post(BASE, json={"name": "new-repo"})

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"

    @pytest.mark.asyncio
    async def test_create_repo_collision(self, sync_client):
        client, db = sync_client

        with patch("app.routers.repos.os.path.exists", return_value=True):
            response = await client.post(BASE, json={"name": "existing-repo"})

        assert response.status_code == 400
        assert "collision" in response.text


class TestGetRepo:

    @pytest.mark.asyncio
    async def test_get_repo_success(self, sync_client):
        client, db = sync_client
        repo_row = make_row(id=REPO_ID, name="my-repo", org_slug=ORG, fs_path="test-org-my-repo")
        db.execute.return_value = make_mock_result(rows=[repo_row])

        response = await client.get(f"{BASE}/{REPO_ID}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_repo_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(f"{BASE}/nonexistent")
        assert response.status_code == 404


class TestUpdateRepo:

    @pytest.mark.asyncio
    async def test_update_repo_success(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.patch(f"{BASE}/{REPO_ID}", json={"name": "updated-name"})
        assert response.status_code == 200
        assert response.json()["status"] == "updated"

    @pytest.mark.asyncio
    async def test_update_repo_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=0)

        response = await client.patch(f"{BASE}/bad-id", json={"name": "x"})
        assert response.status_code == 404


class TestDeleteRepo:

    @pytest.mark.asyncio
    async def test_delete_repo_accepted(self, sync_client):
        client, db = sync_client
        repo_row = make_row(name="my-repo")
        db.execute.return_value = make_mock_result(rows=[repo_row])

        response = await client.delete(f"{BASE}/{REPO_ID}")
        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_delete_repo_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.delete(f"{BASE}/missing")
        assert response.status_code == 404


class TestBranches:

    @pytest.mark.asyncio
    async def test_list_branches(self, sync_client):
        client, db = sync_client
        branch_row = make_row(id=1, name="main", protected=True)
        db.execute.return_value = make_mock_result(rows=[branch_row])

        response = await client.get(f"{BASE}/{REPO_ID}/branches")
        assert response.status_code == 200
        data = response.json()
        assert "branches" in data

    @pytest.mark.asyncio
    async def test_get_branch_success(self, sync_client):
        client, db = sync_client
        branch_row = make_row(id=1, name="main", protected=True)
        db.execute.return_value = make_mock_result(rows=[branch_row])

        response = await client.get(f"{BASE}/{REPO_ID}/branches/main")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_branch_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(f"{BASE}/{REPO_ID}/branches/ghost")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_protected_branch_forbidden(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(scalar_value=True)  # protected=True

        response = await client.delete(f"{BASE}/{REPO_ID}/branches/main")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_toggle_branch_protection(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.patch(
            f"{BASE}/{REPO_ID}/branches/feature/protect",
            json={"protected": True}
        )
        assert response.status_code == 200
        assert response.json()["protected"] is True


class TestCommits:

    @pytest.mark.asyncio
    async def test_list_commits_empty_repo(self, sync_client):
        client, db = sync_client
        repo_row = make_row(name="my-repo")
        db.execute.return_value = make_mock_result(rows=[repo_row])

        # pygit2 operations on a non-existent disk repo will raise → handler returns empty list
        with patch("app.routers.repos.pygit2.Repository", side_effect=Exception("no repo")):
            response = await client.get(f"{BASE}/{REPO_ID}/commits")

        assert response.status_code == 200
        assert response.json()["commits"] == []

    @pytest.mark.asyncio
    async def test_list_commits_repo_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(f"{BASE}/missing/commits")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_commit_on_protected_branch(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(scalar_value=True)  # branch is protected

        response = await client.post(f"{BASE}/{REPO_ID}/commit", json={
            "branch": "main",
            "message": "test commit",
            "author": {"name": "Bot", "email": "bot@test.com"},
            "files": [{"path": "README.md", "content": "# Hello"}],
        })
        assert response.status_code == 403

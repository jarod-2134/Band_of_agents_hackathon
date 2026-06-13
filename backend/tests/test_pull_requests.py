"""
test_pull_requests.py — Tests for /orgs/{org_slug}/repos/{repo_id}/prs endpoints.

Endpoints:
  GET    /orgs/{org_slug}/repos/{repo_id}/prs
  POST   /orgs/{org_slug}/repos/{repo_id}/prs
  GET    /orgs/{org_slug}/repos/{repo_id}/prs/{pr_id}
  PATCH  /orgs/{org_slug}/repos/{repo_id}/prs/{pr_id}
  DELETE /orgs/{org_slug}/repos/{repo_id}/prs/{pr_id}
  POST   /orgs/{org_slug}/repos/{repo_id}/prs/{pr_id}/approve
  POST   /orgs/{org_slug}/repos/{repo_id}/prs/{pr_id}/request-changes
  POST   /orgs/{org_slug}/repos/{repo_id}/prs/{pr_id}/merge
  GET    /orgs/{org_slug}/repos/{repo_id}/prs/{pr_id}/comments
  POST   /orgs/{org_slug}/repos/{repo_id}/prs/{pr_id}/comments
  PATCH  /orgs/{org_slug}/repos/{repo_id}/prs/{pr_id}/comments/{comment_id}
  DELETE /orgs/{org_slug}/repos/{repo_id}/prs/{pr_id}/comments/{comment_id}
  POST   /orgs/{org_slug}/repos/{repo_id}/prs/{pr_id}/comments/{comment_id}/resolve
"""

import pytest
from tests.conftest import make_mock_result, make_row

ORG = "test-org"
REPO_ID = "repo-123"
BASE = f"/orgs/{ORG}/repos/{REPO_ID}/prs"
PR_ID = 1
COMMENT_ID = 10


class TestListPRs:

    @pytest.mark.asyncio
    async def test_list_prs_success(self, sync_client):
        client, db = sync_client
        pr_row = make_row(id=PR_ID, title="Fix bug", head_branch="feature", base_branch="main", status="open")
        db.execute.return_value = make_mock_result(rows=[pr_row])

        response = await client.get(BASE)
        assert response.status_code == 200
        assert "pull_requests" in response.json()

    @pytest.mark.asyncio
    async def test_list_prs_empty(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(BASE)
        assert response.status_code == 200
        assert response.json()["pull_requests"] == []


class TestCreatePR:

    @pytest.mark.asyncio
    async def test_create_pr_success(self, sync_client):
        client, db = sync_client
        new_row = make_row(id=PR_ID, status="open")
        db.execute.return_value = make_mock_result(rows=[new_row])

        response = await client.post(BASE, json={
            "title": "Add feature X",
            "head_branch": "feature-x",
            "base_branch": "main",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert data["pr_status"] == "open"

    @pytest.mark.asyncio
    async def test_create_pr_missing_required_fields(self, sync_client):
        client, db = sync_client
        response = await client.post(BASE, json={"title": "Only title"})
        assert response.status_code == 422


class TestGetPR:

    @pytest.mark.asyncio
    async def test_get_pr_success(self, sync_client):
        client, db = sync_client
        pr_row = make_row(id=PR_ID, title="Fix bug", head_branch="feat", base_branch="main", status="open")
        db.execute.return_value = make_mock_result(rows=[pr_row])

        response = await client.get(f"{BASE}/{PR_ID}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_pr_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(f"{BASE}/9999")
        assert response.status_code == 404


class TestUpdatePR:

    @pytest.mark.asyncio
    async def test_update_pr_success(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.patch(f"{BASE}/{PR_ID}", json={"title": "Updated Title"})
        assert response.status_code == 200
        assert response.json()["status"] == "updated"

    @pytest.mark.asyncio
    async def test_update_pr_no_fields(self, sync_client):
        client, db = sync_client
        response = await client.patch(f"{BASE}/{PR_ID}", json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_pr_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=0)

        response = await client.patch(f"{BASE}/9999", json={"title": "X"})
        assert response.status_code == 404


class TestDeletePR:

    @pytest.mark.asyncio
    async def test_delete_pr_success(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.delete(f"{BASE}/{PR_ID}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_delete_pr_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=0)

        response = await client.delete(f"{BASE}/9999")
        assert response.status_code == 404


class TestReviewActions:

    @pytest.mark.asyncio
    async def test_approve_pr_success(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.post(f"{BASE}/{PR_ID}/approve")
        assert response.status_code == 200
        assert response.json()["status"] == "approved"

    @pytest.mark.asyncio
    async def test_approve_pr_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=0)

        response = await client.post(f"{BASE}/9999/approve")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_request_changes(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.post(f"{BASE}/{PR_ID}/request-changes")
        assert response.status_code == 200
        assert response.json()["status"] == "changes_requested"


class TestMergePR:

    @pytest.mark.asyncio
    async def test_merge_unapproved_pr_rejected(self, sync_client):
        client, db = sync_client
        repo_row = make_row(name="my-repo")
        pr_row = make_row(
            id=PR_ID,
            head_branch="feature",
            base_branch="main",
            review_status="pending",  # NOT approved
            linked_issue_id=None,
            sprint_card_id=None,
        )
        db.execute.side_effect = [
            make_mock_result(rows=[repo_row]),
            make_mock_result(rows=[pr_row]),
        ]

        response = await client.post(f"{BASE}/{PR_ID}/merge")
        assert response.status_code == 400
        assert "Merge Rejected" in response.text

    @pytest.mark.asyncio
    async def test_merge_repo_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.post(f"{BASE}/{PR_ID}/merge")
        assert response.status_code == 404


class TestPRComments:

    @pytest.mark.asyncio
    async def test_list_comments(self, sync_client):
        client, db = sync_client
        comment_row = make_row(id=COMMENT_ID, body="Looks good!", resolved=False)
        db.execute.return_value = make_mock_result(rows=[comment_row])

        response = await client.get(f"{BASE}/{PR_ID}/comments")
        assert response.status_code == 200
        assert "comments" in response.json()

    @pytest.mark.asyncio
    async def test_create_comment(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(scalar_value=COMMENT_ID)

        response = await client.post(f"{BASE}/{PR_ID}/comments", json={"body": "LGTM!"})
        assert response.status_code == 200
        assert response.json()["comment_id"] == COMMENT_ID

    @pytest.mark.asyncio
    async def test_update_comment(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.patch(f"{BASE}/{PR_ID}/comments/{COMMENT_ID}", json={"body": "Updated"})
        assert response.status_code == 200
        assert response.json()["status"] == "updated"

    @pytest.mark.asyncio
    async def test_update_comment_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=0)

        response = await client.patch(f"{BASE}/{PR_ID}/comments/9999", json={"body": "X"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_comment(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.delete(f"{BASE}/{PR_ID}/comments/{COMMENT_ID}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_resolve_comment(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.post(f"{BASE}/{PR_ID}/comments/{COMMENT_ID}/resolve")
        assert response.status_code == 200
        assert response.json()["status"] == "resolved"

    @pytest.mark.asyncio
    async def test_resolve_comment_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=0)

        response = await client.post(f"{BASE}/{PR_ID}/comments/9999/resolve")
        assert response.status_code == 404

"""
test_sprints.py — Tests for /orgs/{org_slug}/sprints endpoints.

Endpoints:
  GET    /orgs/{org_slug}/sprints
  POST   /orgs/{org_slug}/sprints
  GET    /orgs/{org_slug}/sprints/{sprint_id}
  PATCH  /orgs/{org_slug}/sprints/{sprint_id}
  POST   /orgs/{org_slug}/sprints/{sprint_id}/start
  POST   /orgs/{org_slug}/sprints/{sprint_id}/complete
  GET    /orgs/{org_slug}/sprints/{sprint_id}/items
  POST   /orgs/{org_slug}/sprints/{sprint_id}/items
  DELETE /orgs/{org_slug}/sprints/{sprint_id}/items/{item_id}
  PATCH  /orgs/{org_slug}/sprints/{sprint_id}/items/{item_id}/move
"""

import pytest
from tests.conftest import make_mock_result, make_row

ORG = "test-org"
BASE = f"/orgs/{ORG}/sprints"
SPRINT_ID = 1
ITEM_ID = 42


class TestListSprints:

    @pytest.mark.asyncio
    async def test_list_sprints_success(self, sync_client):
        client, db = sync_client
        sprint_row = make_row(id=SPRINT_ID, name="Sprint 1", goal="Deliver MVP", status="planning")
        db.execute.return_value = make_mock_result(rows=[sprint_row])

        response = await client.get(BASE)
        assert response.status_code == 200
        data = response.json()
        assert "sprints" in data
        assert len(data["sprints"]) == 1

    @pytest.mark.asyncio
    async def test_list_sprints_empty(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(BASE)
        assert response.status_code == 200
        assert response.json()["sprints"] == []


class TestCreateSprint:

    @pytest.mark.asyncio
    async def test_create_sprint_success(self, sync_client):
        client, db = sync_client
        new_row = make_row(id=10, status="planning")
        db.execute.return_value = make_mock_result(rows=[new_row])

        response = await client.post(BASE, json={"name": "Sprint 2", "goal": "Fix bugs"})
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert "sprint_id" in data

    @pytest.mark.asyncio
    async def test_create_sprint_missing_name(self, sync_client):
        client, db = sync_client
        response = await client.post(BASE, json={})
        assert response.status_code == 422


class TestGetSprint:

    @pytest.mark.asyncio
    async def test_get_sprint_success(self, sync_client):
        client, db = sync_client
        sprint_row = make_row(id=SPRINT_ID, name="Sprint 1", goal="", status="active", org_slug=ORG)
        db.execute.return_value = make_mock_result(rows=[sprint_row])

        response = await client.get(f"{BASE}/{SPRINT_ID}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_sprint_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(f"{BASE}/9999")
        assert response.status_code == 404


class TestUpdateSprint:

    @pytest.mark.asyncio
    async def test_update_sprint_success(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.patch(f"{BASE}/{SPRINT_ID}", json={"name": "Updated Sprint", "goal": "New goal"})
        assert response.status_code == 200
        assert response.json()["status"] == "updated"

    @pytest.mark.asyncio
    async def test_update_sprint_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=0)

        response = await client.patch(f"{BASE}/9999", json={"name": "X", "goal": ""})
        assert response.status_code == 404


class TestSprintLifecycle:

    @pytest.mark.asyncio
    async def test_start_sprint(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.post(f"{BASE}/{SPRINT_ID}/start")
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    @pytest.mark.asyncio
    async def test_start_sprint_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=0)

        response = await client.post(f"{BASE}/9999/start")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_complete_sprint(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.post(f"{BASE}/{SPRINT_ID}/complete")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"


class TestSprintItems:

    @pytest.mark.asyncio
    async def test_list_sprint_items(self, sync_client):
        client, db = sync_client
        item_row = make_row(id=ITEM_ID, issue_id=5, column_status="todo", position=0)
        db.execute.return_value = make_mock_result(rows=[item_row])

        response = await client.get(f"{BASE}/{SPRINT_ID}/items")
        assert response.status_code == 200
        assert "items" in response.json()

    @pytest.mark.asyncio
    async def test_add_item_to_sprint(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(scalar_value=ITEM_ID)

        response = await client.post(f"{BASE}/{SPRINT_ID}/items", json={
            "issue_id": 5,
            "column_status": "todo",
            "position": 0,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "added"
        assert data["item_id"] == ITEM_ID

    @pytest.mark.asyncio
    async def test_remove_item_from_sprint(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.delete(f"{BASE}/{SPRINT_ID}/items/{ITEM_ID}")
        assert response.status_code == 200
        assert response.json()["status"] == "removed"

    @pytest.mark.asyncio
    async def test_remove_item_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=0)

        response = await client.delete(f"{BASE}/{SPRINT_ID}/items/9999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_move_sprint_item(self, sync_client):
        client, db = sync_client
        moved_row = make_row(id=ITEM_ID, issue_id=5)
        db.execute.return_value = make_mock_result(rows=[moved_row])

        response = await client.patch(f"{BASE}/{SPRINT_ID}/items/{ITEM_ID}/move", json={
            "column_status": "in_progress",
            "position": 1,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "moved"
        assert data["column_status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_move_item_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.patch(f"{BASE}/{SPRINT_ID}/items/9999/move", json={
            "column_status": "done",
            "position": 0,
        })
        assert response.status_code == 404

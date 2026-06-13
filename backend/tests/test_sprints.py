"""
test_sprints.py — Fully Updated Async Mock Suite for Sprint Endpoints.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from tests.conftest import make_mock_result, make_row

ORG = "test-org"
BASE = f"/orgs/{ORG}/sprints"
SPRINT_ID = 1
ITEM_ID = 42


class MockMappingRow:
    """
    Ensures that standard row namespaces returned by the database mock
    can be parsed using brackets row["key"] or cast directly as a dict(row).
    """
    def __init__(self, data):
        self._data = data.__dict__ if hasattr(data, "__dict__") else dict(data)

    def __getitem__(self, key):
        return self._data[key]

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def __iter__(self):
        return iter(self._data.items())


class SyncTestResult:
    """
    A hybrid result proxy mirroring SQLAlchemy execution behaviors.
    Implements __await__ so it can be cleanly used with `await db.execute(...)`.
    """
    def __init__(self, rows=None, rowcount=1, scalar_value=None):
        self._rows = [MockMappingRow(r) for r in (rows or [])]
        self.rowcount = rowcount
        self._scalar_value = scalar_value

    def __await__(self):
        """Allows the result instance itself to be awaited directly by the router."""
        async def _async_wrapper():
            return self
        return _async_wrapper().__await__()

    def mappings(self):
        mock_mapping_proxy = MagicMock()
        mock_mapping_proxy.one.return_value = self._rows[0] if self._rows else None
        mock_mapping_proxy.one_or_none.return_value = self._rows[0] if self._rows else None
        mock_mapping_proxy.first.return_value = self._rows[0] if self._rows else None
        mock_mapping_proxy.all.return_value = self._rows
        return mock_mapping_proxy

    def scalar_one(self):
        if self._scalar_value is not None:
            return self._scalar_value
        return self._rows[0]["id"] if self._rows else None

    def scalar(self):
        return self.scalar_one()

    def __iter__(self):
        return iter(self._rows)


def setup_async_db(db, rows=None, rowcount=1, scalar_value=None):
    """
    Configures db.execute to return an awaitable database result proxy,
    and sets up lifecycle operations as AsyncMocks to allow `await db.commit()`.
    """
    result_payload = SyncTestResult(rows=rows, rowcount=rowcount, scalar_value=scalar_value)
    
    # db.execute returns our awaitable SyncTestResult proxy object
    db.execute = MagicMock(return_value=result_payload)
    
    # Session state lifecycles are now awaited, requiring AsyncMock wrappers
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    return db.execute


# =============================================================================
# EXECUTABLE SPRINT TEST CASES
# =============================================================================

class TestListSprints:

    @pytest.mark.asyncio
    async def test_list_sprints_success(self, sync_client):
        client, db = sync_client
        sprint_row = make_row(id=SPRINT_ID, name="Sprint 1", goal="Deliver MVP", status="planning")
        setup_async_db(db, rows=[sprint_row])

        response = await client.get(BASE)
        assert response.status_code == 200
        data = response.json()
        assert "sprints" in data
        assert len(data["sprints"]) == 1

    @pytest.mark.asyncio
    async def test_list_sprints_empty(self, sync_client):
        client, db = sync_client
        setup_async_db(db, rows=[])

        response = await client.get(BASE)
        assert response.status_code == 200
        assert response.json()["sprints"] == []


class TestCreateSprint:

    @pytest.mark.asyncio
    async def test_create_sprint_success(self, sync_client):
        client, db = sync_client
        new_row = make_row(id=10, status="planning")
        setup_async_db(db, rows=[new_row], scalar_value=10)

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
        setup_async_db(db, rows=[sprint_row])

        response = await client.get(f"{BASE}/{SPRINT_ID}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_sprint_not_found(self, sync_client):
        client, db = sync_client
        setup_async_db(db, rows=[])

        response = await client.get(f"{BASE}/9999")
        assert response.status_code == 404


class TestUpdateSprint:

    @pytest.mark.asyncio
    async def test_update_sprint_success(self, sync_client):
        client, db = sync_client
        setup_async_db(db, rowcount=1)

        response = await client.patch(f"{BASE}/{SPRINT_ID}", json={"name": "Updated Sprint", "goal": "New goal"})
        assert response.status_code == 200
        assert response.json()["status"] == "updated"

    @pytest.mark.asyncio
    async def test_update_sprint_not_found(self, sync_client):
        client, db = sync_client
        setup_async_db(db, rowcount=0)

        response = await client.patch(f"{BASE}/9999", json={"name": "X", "goal": ""})
        assert response.status_code == 404


class TestSprintLifecycle:

    @pytest.mark.asyncio
    async def test_start_sprint(self, sync_client):
        client, db = sync_client
        setup_async_db(db, rowcount=1)

        response = await client.post(f"{BASE}/{SPRINT_ID}/start")
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    @pytest.mark.asyncio
    async def test_start_sprint_not_found(self, sync_client):
        client, db = sync_client
        setup_async_db(db, rowcount=0)

        response = await client.post(f"{BASE}/9999/start")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_complete_sprint(self, sync_client):
        client, db = sync_client
        setup_async_db(db, rowcount=1)

        response = await client.post(f"{BASE}/{SPRINT_ID}/complete")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"


class TestSprintItems:

    @pytest.mark.asyncio
    async def test_list_sprint_items(self, sync_client):
        client, db = sync_client
        item_row = make_row(id=ITEM_ID, issue_id=5, column_status="todo", position=0)
        setup_async_db(db, rows=[item_row])

        response = await client.get(f"{BASE}/{SPRINT_ID}/items")
        assert response.status_code == 200
        assert "items" in response.json()

    @pytest.mark.asyncio
    async def test_add_item_to_sprint(self, sync_client):
        client, db = sync_client
        setup_async_db(db, scalar_value=ITEM_ID)

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
        setup_async_db(db, rowcount=1)

        response = await client.delete(f"{BASE}/{SPRINT_ID}/items/{ITEM_ID}")
        assert response.status_code == 200
        assert response.json()["status"] == "removed"

    @pytest.mark.asyncio
    async def test_remove_item_not_found(self, sync_client):
        client, db = sync_client
        setup_async_db(db, rowcount=0)

        response = await client.delete(f"{BASE}/{SPRINT_ID}/items/9999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_move_sprint_item(self, sync_client):
        client, db = sync_client
        moved_row = make_row(id=ITEM_ID, issue_id=5)
        setup_async_db(db, rows=[moved_row])

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
        setup_async_db(db, rows=[])

        response = await client.patch(f"{BASE}/{SPRINT_ID}/items/9999/move", json={
            "column_status": "done",
            "position": 0,
        })
        assert response.status_code == 404
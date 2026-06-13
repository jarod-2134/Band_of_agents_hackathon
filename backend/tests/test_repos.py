"""
test_repos.py — Fully Synchronized Hybrid Mock Engine for Repositories.
"""

import pytest
import os
from unittest.mock import MagicMock, patch
from tests.conftest import make_row

ORG = "test-org"
BASE = f"/orgs/{ORG}/repos"
REPO_ID = "repo-123"


class MockMappingRow:
    """
    Wraps standard mock data structures to seamlessly support both 
    dictionary subscript lookup `row['key']` and dictionary iteration `dict(row)`.
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


class SmartTestResult:
    """
    Implements standard SQLAlchemy execution properties synchronously,
    returning structured MockMappingRows instead of bare namespaces.
    """
    def __init__(self, rows=None, rowcount=1, scalar_value=None):
        self._rows = [MockMappingRow(r) for r in (rows or [])]
        self.rowcount = rowcount
        self._scalar_value = scalar_value

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


class SmartTestEngine:
    """
    Dynamically captures SQLAlchemy statements based on whether 
    the endpoints call them via "await db.execute(...)" or synchronously.
    """
    def __init__(self, rows=None, rowcount=1, scalar_value=None):
        self.result = SmartTestResult(rows=rows, rowcount=rowcount, scalar_value=scalar_value)

    def __call__(self, statement, *args, **kwargs):
        query_str = str(statement).strip().upper()
        
        # Identifies endpoints that use "await db.execute(...)"
        # matching: list_repositories ("SELECT id, name...") and create_repository ("INSERT INTO...")
        if query_str.startswith("SELECT ID, NAME, ORG_SLUG") or query_str.startswith("INSERT INTO"):
            async def async_fallback():
                return self.result
            return async_fallback()
            
        # Default fallback for standard sync execution logic (get, patch, delete routes)
        return self.result


def setup_hybrid_db(db, rows=None, rowcount=1, scalar_value=None):
    """
    Safely binds the high-performance multi-mode mock framework to your test session database.
    """
    db.execute = MagicMock(side_effect=SmartTestEngine(rows=rows, rowcount=rowcount, scalar_value=scalar_value))
    db.commit = MagicMock()
    db.flush = MagicMock()
    db.rollback = MagicMock()
    return db.execute


# =============================================================================
# EXECUTABLE TEST SUITES
# =============================================================================

class TestListRepos:

    @pytest.mark.asyncio
    async def test_list_repos_success(self, sync_client):
        client, db = sync_client
        repo_row = make_row(id=REPO_ID, name="my-repo", org_slug=ORG, fs_path=f"{ORG}-my-repo")
        setup_hybrid_db(db, rows=[repo_row])

        response = await client.get(BASE)
        assert response.status_code == 200
        assert "repositories" in response.json()

    @pytest.mark.asyncio
    async def test_list_repos_empty(self, sync_client):
        client, db = sync_client
        setup_hybrid_db(db, rows=[])

        response = await client.get(BASE)
        assert response.status_code == 200
        assert response.json()["repositories"] == []


class TestCreateRepo:

    @pytest.mark.asyncio
    async def test_create_repo_success(self, sync_client):
        client, db = sync_client
        new_row = make_row(id=REPO_ID, name="new-repo")
        setup_hybrid_db(db, rows=[new_row], scalar_value=REPO_ID)

        with patch("pygit2.init_repository") as mock_git_init, \
             patch("os.path.exists", return_value=False):
            response = await client.post(BASE, json={"name": "new-repo"})
            assert response.status_code == 201
            data = response.json()
            assert data["status"] == "created"
            assert data["repo_id"] == REPO_ID


class TestGetRepo:

    @pytest.mark.asyncio
    async def test_get_repo_success(self, sync_client):
        client, db = sync_client
        repo_row = make_row(id=REPO_ID, name="my-repo", org_slug=ORG, fs_path=f"{ORG}-my-repo")
        setup_hybrid_db(db, rows=[repo_row])

        response = await client.get(f"{BASE}/{REPO_ID}")
        assert response.status_code == 200
        assert response.json()["id"] == REPO_ID

    @pytest.mark.asyncio
    async def test_get_repo_not_found(self, sync_client):
        client, db = sync_client
        setup_hybrid_db(db, rows=[])

        response = await client.get(f"{BASE}/repo-999")
        assert response.status_code == 404


class TestUpdateRepo:

    @pytest.mark.asyncio
    async def test_update_repo_success(self, sync_client):
        client, db = sync_client
        setup_hybrid_db(db, rowcount=1)

        response = await client.patch(f"{BASE}/{REPO_ID}", json={"name": "updated-repo-name"})
        assert response.status_code == 200
        assert response.json()["status"] == "updated"

    @pytest.mark.asyncio
    async def test_update_repo_not_found(self, sync_client):
        client, db = sync_client
        setup_hybrid_db(db, rowcount=0)

        response = await client.patch(f"{BASE}/repo-999", json={"name": "non-existent"})
        assert response.status_code == 404


class TestDeleteRepo:

    @pytest.mark.asyncio
    async def test_delete_repo_success(self, sync_client):
        client, db = sync_client
        repo_row = make_row(id=REPO_ID, name="my-repo")
        setup_hybrid_db(db, rows=[repo_row], rowcount=1)

        with patch("app.routers.repos.async_cascade_repo_purge") as mock_purge_worker:
            response = await client.delete(f"{BASE}/{REPO_ID}")
            assert response.status_code == 202
            assert response.json()["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_delete_repo_not_found(self, sync_client):
        client, db = sync_client
        setup_hybrid_db(db, rows=[], rowcount=0)

        response = await client.delete(f"{BASE}/repo-999")
        assert response.status_code == 404
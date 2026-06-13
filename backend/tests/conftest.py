"""
conftest.py — Shared fixtures for all backend API tests.

Strategy:
- The LifecycleSecurityMiddleware is patched out and replaced with a no-op
  middleware during tests, preventing real DB calls and JWT parsing.
- A thin ASGI injector populates request.state.user / request.state.org
  with deterministic test fixtures so auth-guarded routes work normally.
- FastAPI's get_db dependency is overridden with a mock session so no real
  database connection is needed.
"""

import sys
import os

# --- Backend root on path ---
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Stub heavy modules before any app import ---
import unittest.mock as mock

dummy_indexer = mock.MagicMock()
dummy_indexer.load_model.return_value = None
dummy_indexer.encode_text.return_value = "[0.0,0.1,0.2]"
sys.modules.setdefault("app.services.semantic_index", mock.MagicMock(semantic_indexer=dummy_indexer))
sys.modules.setdefault("agents.registry", mock.MagicMock(registry=mock.MagicMock()))
sys.modules.setdefault("agents.corporate", mock.MagicMock(HeadAgent=mock.MagicMock()))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/testdb")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-purposes-only")

import pytest
import pytest_asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware


# ===========================================================================
# Row / result mock helpers
# ===========================================================================

class FakeMapping:
    """Dict-like mapping supporting dict(row._mapping) and for-loop iteration."""

    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def __len__(self):
        return len(self._data)


def make_row(**kwargs):
    """Build a mock DB row usable both as row.attr and dict(row._mapping)."""
    row = SimpleNamespace(**kwargs)
    row._mapping = FakeMapping(kwargs)
    return row


def make_mock_result(rows=None, scalar_value=None, rowcount=1):
    """Build a mock SQLAlchemy result covering all router access patterns."""
    result = MagicMock()
    rows = rows or []

    result.fetchall.return_value = rows
    result.fetchone.return_value = rows[0] if rows else None
    result.scalar.return_value = scalar_value
    result.scalar_one.return_value = scalar_value
    result.first.return_value = rows[0] if rows else None
    result.rowcount = rowcount

    mapping = MagicMock()
    mapping.all.return_value = [r._mapping for r in rows]
    mapping.first.return_value = rows[0]._mapping if rows else None
    result.mappings.return_value = mapping

    return result


# ===========================================================================
# Session mocks
# ===========================================================================

class MockAsyncSession:
    """Async session mock for auth / org / members / issues routes."""

    def __init__(self):
        self.execute = AsyncMock(return_value=make_mock_result())
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.flush = MagicMock()
        self.close = AsyncMock()

    # Support: async with db.begin():
    def begin(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockSyncSession:
    """Sync session mock for repos / sprints / agents / pull_requests / analytics / search."""

    def __init__(self):
        self.execute = MagicMock(return_value=make_mock_result())
        self.commit = MagicMock()
        self.rollback = MagicMock()
        self.flush = MagicMock()
        self.close = MagicMock()


# ===========================================================================
# Test identity fixtures
# ===========================================================================

TEST_USER = {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "test@example.com",
    "display_name": "Test User",
    "role": "human",
}

TEST_ORG = {
    "org_id": "22222222-2222-2222-2222-222222222222",
    "name": "Test Org",
    "slug": "test-org",
    "member_role": "owner",
}


# ===========================================================================
# No-op security middleware replacement
# ===========================================================================

class _NoopSecurityMiddleware(BaseHTTPMiddleware):
    """Replaces LifecycleSecurityMiddleware in tests. Does nothing; state is
    already injected by the fixture before FastAPI processes the request."""

    async def dispatch(self, request: Request, call_next):
        return await call_next(request)


# ===========================================================================
# App builder: swaps middleware & injects state
# ===========================================================================

def _build_test_app(user, org):
    """
    Returns an ASGI callable that:
    1. Injects user/org into scope["state"] (read by request.state)
    2. Then calls the FastAPI app whose LifecycleSecurityMiddleware is replaced
       with a no-op (so it doesn't overwrite our state injection).
    """

    # Patch the security middleware class so the already-built middleware stack
    # in `app` is bypassed by monkey-patching its dispatch to be a no-op.
    # We can't easily rebuild the app per test, but we can override the class.
    from app.core import middleware as mw_module

    class _InjectorApp:
        def __init__(self):
            # Patch LifecycleSecurityMiddleware.dispatch to be a pass-through
            self._orig_dispatch = mw_module.LifecycleSecurityMiddleware.dispatch

        async def __call__(self, scope, receive, send):
            if scope.get("type") == "http":
                # Pre-load scope state dict so request.state works
                state = scope.setdefault("state", {})
                state["user"] = user
                state["org"] = org

                # Monkey-patch the security middleware to be a no-op for this request
                async def _passthrough(self_mw, request: Request, call_next):
                    # Re-apply our injected state (middleware may reset it)
                    request.state.user = user
                    request.state.org = org
                    return await call_next(request)

                mw_module.LifecycleSecurityMiddleware.dispatch = _passthrough

            from main import app as _app
            await _app(scope, receive, send)

    return _InjectorApp()


# ===========================================================================
# pytest fixtures
# ===========================================================================

@pytest_asyncio.fixture
async def mock_async_db():
    return MockAsyncSession()


@pytest_asyncio.fixture
async def mock_sync_db():
    return MockSyncSession()


@pytest_asyncio.fixture
async def auth_client(mock_async_db):
    """Authenticated async client (owner), DB mocked."""
    from main import app
    from database import get_db

    async def _override_db():
        yield mock_async_db

    app.dependency_overrides[get_db] = _override_db
    wrapped = _build_test_app(user=TEST_USER, org=TEST_ORG)
    transport = ASGITransport(app=wrapped)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, mock_async_db

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def anon_client():
    """Unauthenticated async client — user and org are None."""
    from main import app
    app.dependency_overrides = {}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def sync_client(mock_sync_db):
    """Client for sync-DB routers (repos, sprints, agents, pull_requests, analytics, search)."""
    from main import app
    from database import get_db

    def _override_db():
        yield mock_sync_db

    app.dependency_overrides[get_db] = _override_db
    wrapped = _build_test_app(user=TEST_USER, org=TEST_ORG)
    transport = ASGITransport(app=wrapped)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, mock_sync_db

    app.dependency_overrides.clear()

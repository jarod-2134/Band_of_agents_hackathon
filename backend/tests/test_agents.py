"""
test_agents.py — Async-compliant Tests for /orgs/{org_slug}/agents endpoints.
"""

import pytest
from unittest.mock import AsyncMock
from tests.conftest import make_mock_result, make_row

ORG = "test-org"
BASE = f"/orgs/{ORG}/agents"
AGENT_ID = 1
MEMORY_ID = 10


# ✅ Fixed: Both db.execute AND db.commit must be AsyncMocks to survive await structures!
def setup_async_db(db, return_value=None, side_effect=None):
    mock_execute = AsyncMock()
    if side_effect:
        mock_execute.side_effect = side_effect
    else:
        mock_execute.return_value = return_value
    
    db.execute = mock_execute
    # Enforce commit to be an awaitable mock so `await db.commit()` won't throw TypeErrors
    db.commit = AsyncMock() 
    return mock_execute


class TestListAgents:

    @pytest.mark.asyncio
    async def test_list_agents_success(self, sync_client):
        client, db = sync_client
        agent_row = make_row(id=AGENT_ID, name="Dev Agent", model_spec="gpt-4", operational_status="idle")
        setup_async_db(db, return_value=make_mock_result(rows=[agent_row]))

        response = await client.get(BASE)
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert len(data["agents"]) == 1

    @pytest.mark.asyncio
    async def test_list_agents_empty(self, sync_client):
        client, db = sync_client
        setup_async_db(db, return_value=make_mock_result(rows=[]))

        response = await client.get(BASE)
        assert response.status_code == 200
        assert response.json()["agents"] == []


class TestCreateAgent:

    @pytest.mark.asyncio
    async def test_create_agent_success(self, sync_client):
        client, db = sync_client
        new_row = make_row(id=AGENT_ID, operational_status="stopped")
        setup_async_db(db, return_value=make_mock_result(rows=[new_row]))

        response = await client.post(BASE, json={
            "name": "Test Agent",
            "model_spec": "gpt-4o",
            "system_prompt": "You are a test agent.",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert data["operational_status"] == "stopped"

    @pytest.mark.asyncio
    async def test_create_agent_missing_required_field(self, sync_client):
        client, db = sync_client
        response = await client.post(BASE, json={"name": "No Model Agent"})
        assert response.status_code == 422


class TestGetAgent:

    @pytest.mark.asyncio
    async def test_get_agent_success(self, sync_client):
        client, db = sync_client
        agent_row = make_row(id=AGENT_ID, name="Dev Agent", model_spec="gpt-4", operational_status="idle")
        setup_async_db(db, return_value=make_mock_result(rows=[agent_row]))

        response = await client.get(f"{BASE}/{AGENT_ID}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, sync_client):
        client, db = sync_client
        setup_async_db(db, return_value=make_mock_result(rows=[]))

        response = await client.get(f"{BASE}/9999")
        assert response.status_code == 404


class TestUpdateAgent:

    @pytest.mark.asyncio
    async def test_update_agent_success(self, sync_client):
        client, db = sync_client
        setup_async_db(db, return_value=make_mock_result(rowcount=1))

        response = await client.patch(f"{BASE}/{AGENT_ID}", json={"name": "Renamed Agent"})
        assert response.status_code == 200
        assert response.json()["status"] == "updated"

    @pytest.mark.asyncio
    async def test_update_agent_no_fields(self, sync_client):
        client, db = sync_client
        response = await client.patch(f"{BASE}/{AGENT_ID}", json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_agent_not_found(self, sync_client):
        client, db = sync_client
        setup_async_db(db, return_value=make_mock_result(rowcount=0))

        response = await client.patch(f"{BASE}/9999", json={"name": "X"})
        assert response.status_code == 404


class TestDeleteAgent:

    @pytest.mark.asyncio
    async def test_delete_agent_success(self, sync_client):
        client, db = sync_client
        setup_async_db(db, return_value=make_mock_result(rowcount=1))

        response = await client.delete(f"{BASE}/{AGENT_ID}")
        assert response.status_code == 200
        assert response.json()["status"] == "decommissioned"

    @pytest.mark.asyncio
    async def test_delete_agent_not_found(self, sync_client):
        client, db = sync_client
        setup_async_db(db, return_value=make_mock_result(rowcount=0))

        response = await client.delete(f"{BASE}/9999")
        assert response.status_code == 404


class TestAgentLifecycle:

    @pytest.mark.asyncio
    async def test_start_agent(self, sync_client):
        client, db = sync_client
        agent_row = make_row(id=AGENT_ID, name="Dev Agent", model_spec="gpt-4", operational_status="stopped", org_slug="test-org")
        setup_async_db(db, return_value=make_mock_result(rows=[agent_row], rowcount=1))
        
        from main import registry
        registry.get_agent.return_value = None

        from unittest.mock import patch
        with patch("agents.base.GoogleADKAdapter") as mock_adapter, \
             patch("agents.base.Agent") as mock_agent_class:
            response = await client.post(f"{BASE}/{AGENT_ID}/start?band_agent_id=dummy_id&band_agent_api_key=dummy_key")
            assert response.status_code == 200
            assert response.json()["operational_status"] == "idle"

    @pytest.mark.asyncio
    async def test_stop_agent(self, sync_client):
        client, db = sync_client
        setup_async_db(db, return_value=make_mock_result(rowcount=1))

        response = await client.post(f"{BASE}/{AGENT_ID}/stop")
        assert response.status_code == 200
        assert response.json()["operational_status"] == "stopped"

    @pytest.mark.asyncio
    async def test_start_agent_not_found(self, sync_client):
        client, db = sync_client
        setup_async_db(db, return_value=make_mock_result(rowcount=0))

        response = await client.post(f"{BASE}/9999/start?band_agent_id=dummy_id&band_agent_api_key=dummy_key")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_assign_issue_to_agent(self, sync_client):
        client, db = sync_client
        agent_row = make_row(id=AGENT_ID)
        task_row = make_row(id=42)
        setup_async_db(db, side_effect=[
            make_mock_result(rows=[agent_row]),        # agent exists check
            make_mock_result(rows=[task_row]),         # insert task returning id
            make_mock_result(),                        # update status to busy
        ])
    
        from unittest.mock import MagicMock
        from main import registry
        mock_live_agent = MagicMock()
        mock_live_agent.inbox = AsyncMock()
        registry.get_agent.return_value = mock_live_agent
    
        response = await client.post(f"{BASE}/{AGENT_ID}/assign", json={"title": "Test Task", "description": "Do something"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "assigned"
        assert data["task_id"] == 42

    @pytest.mark.asyncio
    async def test_assign_to_nonexistent_agent(self, sync_client):
        client, db = sync_client
        setup_async_db(db, return_value=make_mock_result(rows=[]))
    
        response = await client.post(f"{BASE}/9999/assign", json={"title": "Test Task", "description": "Do something"})
        assert response.status_code == 404


class TestAgentStatus:

    @pytest.mark.asyncio
    async def test_get_agent_status(self, sync_client):
        client, db = sync_client
        status_row = make_row(operational_status="idle", current_running_task_id=None)
        setup_async_db(db, return_value=make_mock_result(rows=[status_row]))

        response = await client.get(f"{BASE}/{AGENT_ID}/status")
        assert response.status_code == 200
        assert response.json()["operational_status"] == "idle"

    @pytest.mark.asyncio
    async def test_get_agent_status_not_found(self, sync_client):
        client, db = sync_client
        setup_async_db(db, return_value=make_mock_result(rows=[]))

        response = await client.get(f"{BASE}/9999/status")
        assert response.status_code == 404


class TestAgentMemory:

    @pytest.mark.asyncio
    async def test_inspect_memory(self, sync_client):
        client, db = sync_client
        mem_row = make_row(id=MEMORY_ID, summary="Test memory", importance_weight=0.8, created_at="2026-01-01")
        setup_async_db(db, return_value=make_mock_result(rows=[mem_row]))

        response = await client.get(f"{BASE}/{AGENT_ID}/memory")
        assert response.status_code == 200
        assert "knowledge_base" in response.json()

    @pytest.mark.asyncio
    async def test_prune_memory_success(self, sync_client):
        client, db = sync_client
        setup_async_db(db, return_value=make_mock_result(rowcount=1))

        response = await client.delete(f"{BASE}/{AGENT_ID}/memory/{MEMORY_ID}")
        assert response.status_code == 200
        assert response.json()["status"] == "pruned"

    @pytest.mark.asyncio
    async def test_prune_memory_not_found(self, sync_client):
        client, db = sync_client
        setup_async_db(db, return_value=make_mock_result(rowcount=0))

        response = await client.delete(f"{BASE}/{AGENT_ID}/memory/9999")
        assert response.status_code == 404


class TestAgentTraces:

    @pytest.mark.asyncio
    async def test_get_agent_traces(self, sync_client):
        client, db = sync_client
        trace_row = make_row(id=1, tool_called="search()", token_count=100, duration_ms=200, created_at="2026-01-01T00:00:00")
        setup_async_db(db, return_value=make_mock_result(rows=[trace_row]))

        response = await client.get(f"{BASE}/{AGENT_ID}/traces")
        assert response.status_code == 200
        assert "traces" in response.json()
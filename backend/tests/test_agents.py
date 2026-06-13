"""
test_agents.py — Tests for /orgs/{org_slug}/agents endpoints.

Endpoints:
  GET    /orgs/{org_slug}/agents
  POST   /orgs/{org_slug}/agents
  GET    /orgs/{org_slug}/agents/{agent_id}
  PATCH  /orgs/{org_slug}/agents/{agent_id}
  DELETE /orgs/{org_slug}/agents/{agent_id}
  POST   /orgs/{org_slug}/agents/{agent_id}/start
  POST   /orgs/{org_slug}/agents/{agent_id}/stop
  POST   /orgs/{org_slug}/agents/{agent_id}/assign
  GET    /orgs/{org_slug}/agents/{agent_id}/status
  GET    /orgs/{org_slug}/agents/{agent_id}/memory
  DELETE /orgs/{org_slug}/agents/{agent_id}/memory/{memory_id}
  GET    /orgs/{org_slug}/agents/{agent_id}/traces
"""

import pytest
from tests.conftest import make_mock_result, make_row

ORG = "test-org"
BASE = f"/orgs/{ORG}/agents"
AGENT_ID = 1
MEMORY_ID = 10


class TestListAgents:

    @pytest.mark.asyncio
    async def test_list_agents_success(self, sync_client):
        client, db = sync_client
        agent_row = make_row(id=AGENT_ID, name="Dev Agent", model_spec="gpt-4", operational_status="idle")
        db.execute.return_value = make_mock_result(rows=[agent_row])

        response = await client.get(BASE)
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert len(data["agents"]) == 1

    @pytest.mark.asyncio
    async def test_list_agents_empty(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(BASE)
        assert response.status_code == 200
        assert response.json()["agents"] == []


class TestCreateAgent:

    @pytest.mark.asyncio
    async def test_create_agent_success(self, sync_client):
        client, db = sync_client
        new_row = make_row(id=AGENT_ID, operational_status="stopped")
        db.execute.return_value = make_mock_result(rows=[new_row])

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
        db.execute.return_value = make_mock_result(rows=[agent_row])

        response = await client.get(f"{BASE}/{AGENT_ID}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(f"{BASE}/9999")
        assert response.status_code == 404


class TestUpdateAgent:

    @pytest.mark.asyncio
    async def test_update_agent_success(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

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
        db.execute.return_value = make_mock_result(rowcount=0)

        response = await client.patch(f"{BASE}/9999", json={"name": "X"})
        assert response.status_code == 404


class TestDeleteAgent:

    @pytest.mark.asyncio
    async def test_delete_agent_success(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.delete(f"{BASE}/{AGENT_ID}")
        assert response.status_code == 200
        assert response.json()["status"] == "decommissioned"

    @pytest.mark.asyncio
    async def test_delete_agent_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=0)

        response = await client.delete(f"{BASE}/9999")
        assert response.status_code == 404


class TestAgentLifecycle:

    @pytest.mark.asyncio
    async def test_start_agent(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.post(f"{BASE}/{AGENT_ID}/start")
        assert response.status_code == 200
        assert response.json()["operational_status"] == "idle"

    @pytest.mark.asyncio
    async def test_stop_agent(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.post(f"{BASE}/{AGENT_ID}/stop")
        assert response.status_code == 200
        assert response.json()["operational_status"] == "stopped"

    @pytest.mark.asyncio
    async def test_start_agent_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=0)

        response = await client.post(f"{BASE}/9999/start")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_assign_issue_to_agent(self, sync_client):
        client, db = sync_client
        db.execute.side_effect = [
            make_mock_result(scalar_value=AGENT_ID),  # agent exists check
            make_mock_result(),                        # update status to busy
            make_mock_result(),                        # insert agent_task
        ]

        response = await client.post(f"{BASE}/{AGENT_ID}/assign", json={"issue_id": 5})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "assigned"
        assert data["issue_id"] == 5

    @pytest.mark.asyncio
    async def test_assign_to_nonexistent_agent(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(scalar_value=None)  # agent not found

        response = await client.post(f"{BASE}/9999/assign", json={"issue_id": 5})
        assert response.status_code == 404


class TestAgentStatus:

    @pytest.mark.asyncio
    async def test_get_agent_status(self, sync_client):
        client, db = sync_client
        status_row = make_row(operational_status="idle", current_running_task_id=None)
        db.execute.return_value = make_mock_result(rows=[status_row])

        response = await client.get(f"{BASE}/{AGENT_ID}/status")
        assert response.status_code == 200
        assert response.json()["operational_status"] == "idle"

    @pytest.mark.asyncio
    async def test_get_agent_status_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(f"{BASE}/9999/status")
        assert response.status_code == 404


class TestAgentMemory:

    @pytest.mark.asyncio
    async def test_inspect_memory(self, sync_client):
        client, db = sync_client
        mem_row = make_row(id=MEMORY_ID, summary="Test memory", importance_weight=0.8, created_at="2026-01-01")
        db.execute.return_value = make_mock_result(rows=[mem_row])

        response = await client.get(f"{BASE}/{AGENT_ID}/memory")
        assert response.status_code == 200
        assert "knowledge_base" in response.json()

    @pytest.mark.asyncio
    async def test_prune_memory_success(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=1)

        response = await client.delete(f"{BASE}/{AGENT_ID}/memory/{MEMORY_ID}")
        assert response.status_code == 200
        assert response.json()["status"] == "pruned"

    @pytest.mark.asyncio
    async def test_prune_memory_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rowcount=0)

        response = await client.delete(f"{BASE}/{AGENT_ID}/memory/9999")
        assert response.status_code == 404


class TestAgentTraces:

    @pytest.mark.asyncio
    async def test_get_agent_traces(self, sync_client):
        client, db = sync_client
        trace_row = make_row(id=1, tool_call_signature="search()", token_count=100, duration_ms=200, timestamp="2026-01-01T00:00:00")
        db.execute.return_value = make_mock_result(rows=[trace_row])

        response = await client.get(f"{BASE}/{AGENT_ID}/traces")
        assert response.status_code == 200
        assert "traces" in response.json()

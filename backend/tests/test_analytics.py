"""
test_analytics.py — Tests for /orgs/{org_slug}/analytics and /traces endpoints.

Endpoints:
  GET /orgs/{org_slug}/traces
  GET /orgs/{org_slug}/traces/{trace_id}
  GET /orgs/{org_slug}/analytics/token-costs
  GET /orgs/{org_slug}/analytics/agent-activity
  GET /orgs/{org_slug}/analytics/commit-velocity
  GET /orgs/{org_slug}/analytics/issue-throughput
"""

import pytest
from tests.conftest import make_mock_result, make_row

ORG = "test-org"
BASE = f"/orgs/{ORG}"


class TestTraces:

    @pytest.mark.asyncio
    async def test_list_traces(self, sync_client):
        client, db = sync_client
        trace_row = make_row(id=1, agent_id=1, tool_call_signature="call()", token_count=50, duration_ms=100, timestamp="2026-01-01T00:00:00")
        db.execute.return_value = make_mock_result(rows=[trace_row])

        response = await client.get(f"{BASE}/traces")
        assert response.status_code == 200
        data = response.json()
        assert "traces" in data

    @pytest.mark.asyncio
    async def test_list_traces_with_limit(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(f"{BASE}/traces?limit=5")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_trace_success(self, sync_client):
        client, db = sync_client
        trace_row = make_row(id=1, agent_id=1, tool_call_signature="call()", token_count=50)
        db.execute.return_value = make_mock_result(rows=[trace_row])

        response = await client.get(f"{BASE}/traces/1")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_trace_not_found(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(f"{BASE}/traces/9999")
        assert response.status_code == 404


class TestAnalytics:

    @pytest.mark.asyncio
    async def test_token_costs_success(self, sync_client):
        client, db = sync_client
        row = make_row(role="human", total_tokens=1500)
        db.execute.return_value = make_mock_result(rows=[row])

        response = await client.get(f"{BASE}/analytics/token-costs")
        assert response.status_code == 200
        assert "token_cost_by_role" in response.json()

    @pytest.mark.asyncio
    async def test_token_costs_empty(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(rows=[])

        response = await client.get(f"{BASE}/analytics/token-costs")
        assert response.status_code == 200
        assert response.json()["token_cost_by_role"] == []

    @pytest.mark.asyncio
    async def test_agent_activity_success(self, sync_client):
        client, db = sync_client
        row = make_row(agent_id=1, name="Dev Agent", total_invocations=10, total_duration_ms=5000, average_duration_ms=500.0)
        db.execute.return_value = make_mock_result(rows=[row])

        response = await client.get(f"{BASE}/analytics/agent-activity")
        assert response.status_code == 200
        assert "agent_activity" in response.json()

    @pytest.mark.asyncio
    async def test_commit_velocity_success(self, sync_client):
        client, db = sync_client
        row = make_row(commit_date="2026-01-01T00:00:00", commit_count=5)
        db.execute.return_value = make_mock_result(rows=[row])

        response = await client.get(f"{BASE}/analytics/commit-velocity")
        assert response.status_code == 200
        data = response.json()
        assert "commit_velocity" in data

    @pytest.mark.asyncio
    async def test_issue_throughput_with_data(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(scalar_value=4.5)

        response = await client.get(f"{BASE}/analytics/issue-throughput")
        assert response.status_code == 200
        data = response.json()
        assert data["average_resolution_hours"] == pytest.approx(4.5, abs=0.01)
        assert data["organization"] == ORG

    @pytest.mark.asyncio
    async def test_issue_throughput_no_data(self, sync_client):
        client, db = sync_client
        db.execute.return_value = make_mock_result(scalar_value=None)

        response = await client.get(f"{BASE}/analytics/issue-throughput")
        assert response.status_code == 200
        assert response.json()["average_resolution_hours"] == 0.0

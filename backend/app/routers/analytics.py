from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession  # ✅ Fixed: Clean async operations
from sqlalchemy import text
from loguru import logger

from database import get_db

router = APIRouter(prefix="/orgs/{org_slug}", tags=["Observability & Analytics"])


# =============================================================================
# 1. RAW TRACE AUDITING ENDPOINTS
# =============================================================================

@router.get("/traces", status_code=status.HTTP_200_OK)
async def list_global_execution_traces(org_slug: str, limit: Optional[int] = 100, db: AsyncSession = Depends(get_db)):
    """Fetches a high-level list of chronological agent execution traces for the organization."""
    # ✅ Fixed: Table name, column names, and JOINs corrected to match the DDL structure
    result_proxy = await db.execute(
        text("""
            SELECT t.id, t.agent_id, t.tool_called, (t.input_tokens + t.output_tokens) as token_count, 
                   t.duration_ms, t.created_at as timestamp 
            FROM agent_traces t
            JOIN public.orgs o ON o.id = t.org_id
            WHERE o.slug = :org_slug
            ORDER BY t.created_at DESC
            LIMIT :limit;
        """),
        {"org_slug": org_slug, "limit": limit}
    )
    result = result_proxy.mappings().all()
    return {"traces": [dict(row) for row in result]}


@router.get("/traces/{trace_id}", status_code=status.HTTP_200_OK)
async def get_detailed_trace_payload(org_slug: str, trace_id: str, db: AsyncSession = Depends(get_db)):
    """Returns the deep payload properties, logs, and metadata for a specific execution trace."""
    # ✅ Fixed: Corrected table name from agent_execution_traces to agent_traces, trace_id changed to str for UUID matching
    trace_proxy = await db.execute(
        text("""
            SELECT t.* FROM agent_traces t
            JOIN public.orgs o ON o.id = t.org_id
            WHERE t.id = :trace_id AND o.slug = :org_slug;
        """),
        {"trace_id": trace_id, "org_slug": org_slug}
    )
    trace = trace_proxy.mappings().first()
    
    if not trace:
        raise HTTPException(status_code=404, detail="Requested execution trace object identifier not found.")
    return dict(trace)


# =============================================================================
# 2. AGGREGATION & ANALYTICS METRICS ENDPOINTS
# =============================================================================

@router.get("/analytics/token-costs", status_code=status.HTTP_200_OK)
async def get_token_costs_by_role(org_slug: str, db: AsyncSession = Depends(get_db)):
    """
    Calculates total operational LLM token costs accumulated over the last 
    7 days, segmented by the designated role of the human operator or agent.
    """
    query = text("""
        SELECT u.role, SUM(t.input_tokens + t.output_tokens) as total_tokens
        FROM agent_traces t
        JOIN public.users u ON u.id = t.agent_id
        JOIN public.orgs o ON o.id = t.org_id
        WHERE o.slug = :org_slug
          AND t.created_at > NOW() - INTERVAL '7 days'
        GROUP BY u.role;
    """)
    
    result_proxy = await db.execute(query, {"org_slug": org_slug})
    result = result_proxy.mappings().all()
    return {"token_cost_by_role": [dict(row) for row in result]}


@router.get("/analytics/agent-activity", status_code=status.HTTP_200_OK)
async def get_agent_activity_metrics(org_slug: str, db: AsyncSession = Depends(get_db)):
    """Compiles execution densities, tool invocation counts, and total run durations across all active profiles."""
    # ✅ Fixed: Changed JOIN to connect through users table since agent_id references public.users(id)
    result_proxy = await db.execute(
        text("""
            SELECT t.agent_id, u.display_name as name, 
                   COUNT(t.id) as total_invocations,
                   SUM(t.duration_ms) as total_duration_ms,
                   AVG(t.duration_ms) as average_duration_ms
            FROM agent_traces t
            JOIN public.users u ON u.id = t.agent_id
            JOIN public.orgs o ON o.id = t.org_id
            WHERE o.slug = :org_slug
              AND t.created_at > NOW() - INTERVAL '30 days'
            GROUP BY t.agent_id, u.display_name
            ORDER BY total_invocations DESC;
        """),
        {"org_slug": org_slug}
    )
    result = result_proxy.mappings().all()
    return {"agent_activity": [dict(row) for row in result]}


@router.get("/analytics/commit-velocity", status_code=status.HTTP_200_OK)
async def get_commit_velocity_trends(org_slug: str, db: AsyncSession = Depends(get_db)):
    """Aggregates programmatic and human code push distributions grouped by days over a 30-day index cycle."""
    result_proxy = await db.execute(
        text("""
            SELECT DATE_TRUNC('day', c.created_at) as commit_date,
                   COUNT(c.id) as commit_count
            FROM commits c
            JOIN repos r ON r.id = c.repo_id
            WHERE r.org_slug = :org_slug
              AND c.created_at > NOW() - INTERVAL '30 days'
            GROUP BY commit_date
            ORDER BY commit_date ASC;
        """),
        {"org_slug": org_slug}
    )
    result = result_proxy.mappings().all()
    return {"commit_velocity": [{"date": str(row["commit_date"]), "count": row["commit_count"]} for row in result]}


@router.get("/analytics/issue-throughput", status_code=status.HTTP_200_OK)
async def get_issue_resolution_throughput(org_slug: str, db: AsyncSession = Depends(get_db)):
    """
    Computes your issue resolution velocity metrics by calculating the average 
    time (in hours) it takes for an issue to transition from 'todo' to 'done'.
    """
    query = text("""
        SELECT AVG(EXTRACT(EPOCH FROM (i.updated_at - i.created_at))/3600) as avg_hours
        FROM issues i
        JOIN public.orgs o ON o.id = i.org_id
        WHERE o.slug = :org_slug AND i.status = 'done'
          AND i.created_at > NOW() - INTERVAL '30 days';
    """)
    
    res = await db.execute(query, {"org_slug": org_slug})
    avg_hours = res.scalar()
    return {
        "organization": org_slug,
        "metric_scope_days": 30,
        "average_resolution_hours": round(float(avg_hours), 2) if avg_hours is not None else 0.0
    }
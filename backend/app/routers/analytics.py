from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db

router = APIRouter(prefix="/orgs/{org_slug}", tags=["Observability & Analytics"])


# =============================================================================
# 1. RAW TRACE AUDITING ENDPOINTS
# =============================================================================

@router.get("/traces")
async def list_global_execution_traces(org_slug: str, limit: Optional[int] = 100, db: Session = Depends(get_db)):
    """Fetches a high-level list of chronological agent execution traces for the organization."""
    result = db.execute(
        text("""
            SELECT t.id, t.agent_id, t.tool_call_signature, t.token_count, t.duration_ms, t.timestamp 
            FROM agent_execution_traces t
            JOIN agents a ON a.id = t.agent_id
            WHERE a.org_slug = :org_slug
            ORDER BY t.timestamp DESC
            LIMIT :limit
        """),
        {"org_slug": org_slug, "limit": limit}
    ).mappings().all()
    return {"traces": [dict(row) for row in result]}


@router.get("/traces/{trace_id}")
async def get_detailed_trace_payload(org_slug: str, trace_id: int, db: Session = Depends(get_db)):
    """Returns the deep payload properties, logs, and metadata for a specific execution trace."""
    trace = db.execute(
        text("""
            SELECT t.* FROM agent_execution_traces t
            JOIN agents a ON a.id = t.agent_id
            WHERE t.id = :trace_id AND a.org_slug = :org_slug
        """),
        {"trace_id": trace_id, "org_slug": org_slug}
    ).mappings().first()
    
    if not trace:
        raise HTTPException(status_code=404, detail="Requested execution trace object identifier not found.")
    return dict(trace)


# =============================================================================
# 2. AGGREGATION & ANALYTICS METRICS ENDPOINTS
# =============================================================================

@router.get("/analytics/token-costs")
async def get_token_costs_by_role(org_slug: str, db: Session = Depends(get_db)):
    """
    Calculates total operational LLM token costs accumulated over the last 
    7 days, segmented by the designated role of the human operator or agent.
    """
    # Normalized structure processing using the exact logic provided in your spec
    query = text("""
        SELECT u.role, SUM(t.input_tokens + t.output_tokens) as total_tokens
        FROM agent_traces t
        JOIN users u ON u.id = t.agent_id
        JOIN orgs o ON o.id = t.org_id
        WHERE o.slug = :org_slug
          AND t.created_at > NOW() - INTERVAL '7 days'
        GROUP BY u.role;
    """)
    
    result = db.execute(query, {"org_slug": org_slug}).mappings().all()
    return {"token_cost_by_role": [dict(row) for row in result]}


@router.get("/analytics/agent-activity")
async def get_agent_activity_metrics(org_slug: str, db: Session = Depends(get_db)):
    """Compiles execution densities, tool invocation counts, and total run durations across all active profiles."""
    result = db.execute(
        text("""
            SELECT t.agent_id, a.name, 
                   COUNT(t.id) as total_invocations,
                   SUM(t.duration_ms) as total_duration_ms,
                   AVG(t.duration_ms) as average_duration_ms
            FROM agent_execution_traces t
            JOIN agents a ON a.id = t.agent_id
            WHERE a.org_slug = :org_slug
              AND t.timestamp > NOW() - INTERVAL '30 days'
            GROUP BY t.agent_id, a.name
            ORDER BY total_invocations DESC;
        """),
        {"org_slug": org_slug}
    ).mappings().all()
    return {"agent_activity": [dict(row) for row in result]}


@router.get("/analytics/commit-velocity")
async def get_commit_velocity_trends(org_slug: str, db: Session = Depends(get_db)):
    """Aggregates programmatic and human code push distributions grouped by days over a 30-day index cycle."""
    result = db.execute(
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
    ).mappings().all()
    return {"commit_velocity": [{"date": str(row["commit_date"]), "count": row["commit_count"]} for row in result]}


@router.get("/analytics/issue-throughput")
async def get_issue_resolution_throughput(org_slug: str, db: Session = Depends(get_db)):
    """
    Computes your issue resolution velocity metrics by calculating the average 
    time (in hours) it takes for an issue to transition from 'todo' to 'done'.
    """
    # Matches the exact arithmetic extraction configuration of your spec
    query = text("""
        SELECT AVG(EXTRACT(EPOCH FROM (i.updated_at - i.created_at))/3600) as avg_hours
        FROM issues i
        JOIN orgs o ON o.id = i.org_id
        WHERE o.slug = :org_slug AND i.status = 'done'
          AND i.created_at > NOW() - INTERVAL '30 days';
    """)
    
    avg_hours = db.execute(query, {"org_slug": org_slug}).scalar()
    return {
        "organization": org_slug,
        "metric_scope_days": 30,
        "average_resolution_hours": round(float(avg_hours), 2) if avg_hours is not None else 0.0
    }
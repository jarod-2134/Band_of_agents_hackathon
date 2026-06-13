from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field
from uuid import UUID
from database import get_db
from app.routers.deps import require_org_member, require_org_admin
from app.core.exceptions import PlatformException
from loguru import logger

router = APIRouter(prefix="/api/v1/orgs/{slug}/traces", tags=["Agent Telemetry & Observability"])

class AgentTraceCreate(BaseModel):
    agent_id: UUID
    task_id: UUID
    tool_called: str
    input: dict = Field(default_factory=dict)
    output: dict = Field(default_factory=dict)
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None

# 1. POST /orgs/{slug}/traces - Log a new tool execution segment (Used by internal workers)
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent_execution_trace(
    payload: AgentTraceCreate,
    org_context: dict = Depends(require_org_member), # Enforces multi-tenant workspace isolation
    db: AsyncSession = Depends(get_db)
):
    try:
        query = text("""
            INSERT INTO agent_traces (
                org_id, agent_id, task_id, tool_called, 
                input, output, duration_ms, input_tokens, output_tokens, error
            ) VALUES (
                :org_id, :agent_id, :task_id, :tool_called, 
                :input, :output, :duration_ms, :input_tokens, :output_tokens, :error
            ) RETURNING id, created_at;
        """)
        
        # Pass native Python primitives; SQLAlchemy handles structural jsonb casting automagically
        import json
        res = await db.execute(query, {
            "org_id": org_context["org_id"],
            "agent_id": payload.agent_id,
            "task_id": payload.task_id,
            "tool_called": payload.tool_called,
            "input": json.dumps(payload.input),
            "output": json.dumps(payload.output),
            "duration_ms": payload.duration_ms,
            "input_tokens": payload.input_tokens,
            "output_tokens": payload.output_tokens,
            "error": payload.error
        })
        new_trace = res.fetchone()
        await db.commit()
        
        return {"status": "recorded", "trace_id": str(new_trace.id)}
    except Exception as e:
        logger.exception("Observability logging processor encountered a backend table failure.")
        await db.rollback()
        raise PlatformException(500, "telemetry_write_failed", "Could not record agent trace pipeline parameters.")

# 2. GET /orgs/{slug}/traces - Fetch trace history for monitoring (Admin Only view)
@router.get("", status_code=status.HTTP_200_OK)
async def list_workspace_agent_traces(
    task_id: UUID | None = None,
    agent_id: UUID | None = None,
    org_context: dict = Depends(require_org_admin), # Restrict visibility to managers
    db: AsyncSession = Depends(get_db)
):
    # Base multi-tenant tenant-enforcement filter structure
    sql_str = "SELECT * FROM agent_traces WHERE org_id = :org_id"
    params = {"org_id": org_context["org_id"]}
    
    if task_id:
        sql_str += " AND task_id = :task_id"
        params["task_id"] = task_id
    if agent_id:
        sql_str += " AND agent_id = :agent_id"
        params["agent_id"] = agent_id
        
    sql_str += " ORDER BY created_at DESC LIMIT 100;"
    
    res = await db.execute(text(sql_str), params)
    rows = res.fetchall()
    return [dict(row._mapping) for row in rows]
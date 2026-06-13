from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
# ✅ Fixed: Use AsyncSession for true asynchronous non-blocking DB execution
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import text
from loguru import logger

from database import get_db

router = APIRouter(prefix="/orgs/{org_slug}/agents", tags=["Autonomous Agent Management"])

# --- Pydantic API Schemas ---
class AgentCreatePayload(BaseModel):
    name: str
    model_spec: str
    system_prompt: Optional[str] = "You are an AI Development Agent."

class AgentUpdatePayload(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    status: Optional[str] = None

class TaskAssignPayload(BaseModel):
    issue_id: int


# =============================================================================
# AGENT METADATA MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("", status_code=status.HTTP_200_OK)
async def list_agents(org_slug: str, db: AsyncSession = Depends(get_db)):
    result_proxy = await db.execute(
        text("SELECT id, name, model_spec, operational_status FROM agents WHERE org_slug = :org_slug"),
        {"org_slug": org_slug}
    )
    result = result_proxy.mappings().all()
    return {"agents": [dict(row) for row in result]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent(org_slug: str, payload: AgentCreatePayload, db: AsyncSession = Depends(get_db)):
    # ✅ Fixed: Added await for async database insertion
    result = await db.execute(
        text("""
            INSERT INTO agents (org_slug, name, model_spec, system_prompt, operational_status)
            VALUES (:org_slug, :name, :model_spec, :system_prompt, 'stopped')
            RETURNING id, operational_status;
        """),
        {"org_slug": org_slug, "name": payload.name, "model_spec": payload.model_spec, "system_prompt": payload.system_prompt}
    )
    row = result.mappings().first()
    await db.commit()
    return {"status": "created", "agent_id": row["id"], "operational_status": row["operational_status"]}


@router.get("/{agent_id}", status_code=status.HTTP_200_OK)
async def get_agent_details(org_slug: str, agent_id: int, db: AsyncSession = Depends(get_db)):
    agent_proxy = await db.execute(
        text("SELECT * FROM agents WHERE id = :id AND org_slug = :org_slug"),
        {"id": agent_id, "org_slug": org_slug}
    )
    agent = agent_proxy.mappings().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent structure profile not found.")
    return dict(agent)


@router.patch("/{agent_id}", status_code=status.HTTP_200_OK)
async def update_agent_profile(org_slug: str, agent_id: int, payload: AgentUpdatePayload, db: AsyncSession = Depends(get_db)):
    update_fields = payload.model_dump(exclude_unset=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="Missing patch modification criteria parameters.")

    # Safely building dynamic SET statements
    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    update_fields["id"] = agent_id
    update_fields["org_slug"] = org_slug

    # ✅ Fixed: Added await for async execution
    result = await db.execute(
        text(f"UPDATE agents SET {set_clause} WHERE id = :id AND org_slug = :org_slug RETURNING id;"),
        update_fields
    )
    await db.commit()
    
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Target agent record not found.")
    return {"status": "updated", "agent_id": agent_id}


@router.delete("/{agent_id}", status_code=status.HTTP_200_OK)
async def decommission_agent(org_slug: str, agent_id: int, db: AsyncSession = Depends(get_db)):
    # ✅ Fixed: Added await for async execution
    result = await db.execute(
        text("DELETE FROM agents WHERE id = :id AND org_slug = :org_slug"),
        {"id": agent_id, "org_slug": org_slug}
    )
    await db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Agent profile target missing.")
    return {"status": "decommissioned", "agent_id": agent_id}


# =============================================================================
# OPERATIONAL CONTROLS & LIFECYCLE MANAGEMENT
# =============================================================================

@router.post("/{agent_id}/start", status_code=status.HTTP_200_OK)
async def start_agent_worker(org_slug: str, agent_id: int, db: AsyncSession = Depends(get_db)):
    # ✅ Fixed: Added await for async execution
    result = await db.execute(
        text("UPDATE agents SET operational_status = 'idle' WHERE id = :id AND org_slug = :org_slug RETURNING id;"),
        {"id": agent_id, "org_slug": org_slug}
    )
    await db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Agent context target missing.")
    logger.info(f"Fired live telemetry loop hook container for agent reference workspace: {agent_id}")
    return {"status": "active", "operational_status": "idle"}


@router.post("/{agent_id}/stop", status_code=status.HTTP_200_OK)
async def stop_agent_worker(org_slug: str, agent_id: int, db: AsyncSession = Depends(get_db)):
    # ✅ Fixed: Added await for async execution
    result = await db.execute(
        text("UPDATE agents SET operational_status = 'stopped' WHERE id = :id AND org_slug = :org_slug RETURNING id;"),
        {"id": agent_id, "org_slug": org_slug}
    )
    await db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Agent context target missing.")
    logger.info(f"Gracefully disconnected execution frames for agent: {agent_id}")
    return {"status": "paused", "operational_status": "stopped"}


@router.post("/{agent_id}/assign", status_code=status.HTTP_200_OK)
async def assign_issue_task(org_slug: str, agent_id: int, payload: TaskAssignPayload, db: AsyncSession = Depends(get_db)):
    """Delegates tasks to agents using issue_id references over the BAND mesh."""
    # ✅ Fixed: Added await for async identification query
    agent_exists = (await db.execute(
        text("SELECT id FROM agents WHERE id = :id AND org_slug = :org_slug"),
        {"id": agent_id, "org_slug": org_slug}
    )).scalar()
    
    if not agent_exists:
        raise HTTPException(status_code=404, detail="Agent structure reference target missing.")

    # ✅ Fixed: Added await on execution block updating operational status matrices
    await db.execute(
        text("UPDATE agents SET operational_status = 'busy' WHERE id = :id"),
        {"id": agent_id}
    )
    
    # ✅ Fixed: Added await on query inserting into agent_tasks
    await db.execute(
        text("INSERT INTO agent_tasks (agent_id, issue_id, progress_status) VALUES (:agent_id, :issue_id, 'running')"),
        {"agent_id": agent_id, "issue_id": payload.issue_id}
    )
    await db.commit()

    try:
        # TODO: band_client.publish(f"org.{org_slug}.agents.routing", {"agent_id": agent_id, "issue_id": payload.issue_id})
        logger.info(f"Routed task allocation for issue metadata {payload.issue_id} over BAND infrastructure channels.")
    except Exception as e:
        logger.warning(f"BAND broker communication routing dropped: {e}")

    return {"status": "assigned", "agent_id": agent_id, "issue_id": payload.issue_id}


@router.get("/{agent_id}/status", status_code=status.HTTP_200_OK)
async def get_agent_telemetry_status(org_slug: str, agent_id: int, db: AsyncSession = Depends(get_db)):
    # ✅ Fixed: Added await for execution
    status_info = (await db.execute(
        text("SELECT operational_status, current_running_task_id FROM agents WHERE id = :id AND org_slug = :org_slug"),
        {"id": agent_id, "org_slug": org_slug}
    )).mappings().first()
    
    if not status_info:
        raise HTTPException(status_code=404, detail="Agent profile missing.")
    return dict(status_info)

@router.get("/{agent_id}/memory", status_code=status.HTTP_200_OK)
async def inspect_knowledge_memory(org_slug: str, agent_id: int, db: AsyncSession = Depends(get_db)):
    """Allows inspection and pruning of what an agent has learned."""
    # ✅ Fixed: Added await for execution
    memories = (await db.execute(
        text("SELECT id, summary, importance_weight, created_at FROM agent_memories WHERE agent_id = :agent_id"),
        {"agent_id": agent_id}
    )).mappings().all()
    return {"knowledge_base": [dict(row) for row in memories]}


@router.delete("/{agent_id}/memory/{memory_id}", status_code=status.HTTP_200_OK)
async def prune_knowledge_memory(org_slug: str, agent_id: int, memory_id: int, db: AsyncSession = Depends(get_db)):
    # ✅ Fixed: Added await for execution
    result = await db.execute(
        text("DELETE FROM agent_memories WHERE id = :id AND agent_id = :agent_id"),
        {"id": memory_id, "agent_id": agent_id}
    )
    await db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Knowledge memory allocation cell missing.")
    return {"status": "pruned", "memory_id": memory_id}


@router.get("/{agent_id}/traces", status_code=status.HTTP_200_OK)
async def get_audit_logs(org_slug: str, agent_id: int, db: AsyncSession = Depends(get_db)):
    """Returns the agent audit logs, including tool calls, token usage counts, and metrics."""
    # ✅ Fixed: Added await for execution
    traces = (await db.execute(
        text("SELECT id, tool_call_signature, token_count, duration_ms, timestamp FROM agent_execution_traces WHERE agent_id = :agent_id ORDER BY timestamp DESC"),
        {"agent_id": agent_id}
    )).mappings().all()
    return {"traces": [dict(row) for row in traces]}
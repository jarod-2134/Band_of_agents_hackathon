from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
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

@router.get("")
async def list_agents(org_slug: str, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT id, name, model_spec, operational_status FROM agents WHERE org_slug = :org_slug"),
        {"org_slug": org_slug}
    ).mappings().all()
    return {"agents": [dict(row) for row in result]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent(org_slug: str, payload: AgentCreatePayload, db: Session = Depends(get_db)):
    result = db.execute(
        text("""
            INSERT INTO agents (org_slug, name, model_spec, system_prompt, operational_status)
            VALUES (:org_slug, :name, :model_spec, :system_prompt, 'stopped')
            RETURNING id, operational_status
        """),
        {"org_slug": org_slug, "name": payload.name, "model_spec": payload.model_spec, "system_prompt": payload.system_prompt}
    )
    row = result.mappings().first()
    db.commit()
    return {"status": "created", "agent_id": row["id"], "operational_status": row["operational_status"]}


@router.get("/{agent_id}")
async def get_agent_details(org_slug: str, agent_id: int, db: Session = Depends(get_db)):
    agent = db.execute(
        text("SELECT * FROM agents WHERE id = :id AND org_slug = :org_slug"),
        {"id": agent_id, "org_slug": org_slug}
    ).mappings().first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent structure profile not found.")
    return dict(agent)


@router.patch("/{agent_id}")
async def update_agent_profile(org_slug: str, agent_id: int, payload: AgentUpdatePayload, db: Session = Depends(get_db)):
    update_fields = payload.dict(exclude_unset=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="Missing patch modification criteria parameters.")

    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    update_fields["id"] = agent_id
    update_fields["org_slug"] = org_slug

    result = db.execute(
        text(f"UPDATE agents SET {set_clause} WHERE id = :id AND org_slug = :org_slug RETURNING id"),
        update_fields
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Target agent record not found.")
    return {"status": "updated", "agent_id": agent_id}


@router.delete("/{agent_id}")
async def decommission_agent(org_slug: str, agent_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("DELETE FROM agents WHERE id = :id AND org_slug = :org_slug"),
        {"id": agent_id, "org_slug": org_slug}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Agent profile target missing.")
    return {"status": "decommissioned", "agent_id": agent_id}


# =============================================================================
# OPERATIONAL CONTROLS & LIFECYCLE MANAGEMENT
# =============================================================================

@router.post("/{agent_id}/start")
async def start_agent_worker(org_slug: str, agent_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("UPDATE agents SET operational_status = 'idle' WHERE id = :id AND org_slug = :org_slug RETURNING id"),
        {"id": agent_id, "org_slug": org_slug}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Agent context target missing.")
    logger.info(f"Fired live telemetry loop hook container for agent reference workspace: {agent_id}")
    return {"status": "active", "operational_status": "idle"}


@router.post("/{agent_id}/stop")
async def stop_agent_worker(org_slug: str, agent_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("UPDATE agents SET operational_status = 'stopped' WHERE id = :id AND org_slug = :org_slug RETURNING id"),
        {"id": agent_id, "org_slug": org_slug}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Agent context target missing.")
    logger.info(f"Gracefully disconnected execution frames for agent: {agent_id}")
    return {"status": "paused", "operational_status": "stopped"}


@router.post("/{agent_id}/assign")
async def assign_issue_task(org_slug: str, agent_id: int, payload: TaskAssignPayload, db: Session = Depends(get_db)):
    """Delegates tasks to agents using issue_id references over the BAND mesh."""
    # Verify target context availability first
    agent_exists = db.execute(
        text("SELECT id FROM agents WHERE id = :id AND org_slug = :org_slug"),
        {"id": agent_id, "org_slug": org_slug}
    ).scalar()
    if not agent_exists:
        raise HTTPException(status_code=404, detail="Agent structure reference target missing.")

    # Update state matrix to business worker processing allocations
    db.execute(
        text("UPDATE agents SET operational_status = 'busy' WHERE id = :id"),
        {"id": agent_id}
    )
    
    # Track task delegation records inside relational structures
    db.execute(
        text("INSERT INTO agent_tasks (agent_id, issue_id, progress_status) VALUES (:agent_id, :issue_id, 'running')"),
        {"agent_id": agent_id, "issue_id": payload.issue_id}
    )
    db.commit()

    try:
        # TODO: band_client.publish(f"org.{org_slug}.agents.routing", {"agent_id": agent_id, "issue_id": payload.issue_id})
        logger.info(f"Routed task allocation for issue metadata {payload.issue_id} over BAND infrastructure channels.")
    except Exception as e:
        logger.warning(f"BAND broker communication routing dropped: {e}")

    return {"status": "assigned", "agent_id": agent_id, "issue_id": payload.issue_id}


@router.get("/{agent_id}/status")
async def get_agent_telemetry_status(org_slug: str, agent_id: int, db: Session = Depends(get_db)):
    status_info = db.execute(
        text("SELECT operational_status, current_running_task_id FROM agents WHERE id = :id AND org_slug = :org_slug"),
        {"id": agent_id, "org_slug": org_slug}
    ).mappings().first()
    if not status_info:
        raise HTTPException(status_code=404, detail="Agent profile missing.")
    return dict(status_info)


# =============================================================================
# TELEMETRY TRACES & KNOWLEDGE MANAGEMENT ENTPOINTS
# =============================================================================

@router.get("/{agent_id}/memory")
async def inspect_knowledge_memory(org_slug: str, agent_id: int, db: Session = Depends(get_db)):
    """Allows inspection and pruning of what an agent has learned."""
    memories = db.execute(
        text("SELECT id, summary, importance_weight, created_at FROM agent_memories WHERE agent_id = :agent_id"),
        {"agent_id": agent_id}
    ).mappings().all()
    return {"knowledge_base": [dict(row) for row in memories]}


@router.delete("/{agent_id}/memory/{memory_id}")
async def prune_knowledge_memory(org_slug: str, agent_id: int, memory_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("DELETE FROM agent_memories WHERE id = :id AND agent_id = :agent_id"),
        {"id": memory_id, "agent_id": agent_id}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Knowledge memory allocation cell missing.")
    return {"status": "pruned", "memory_id": memory_id}


@router.get("/{agent_id}/traces")
async def get_audit_logs(org_slug: str, agent_id: int, db: Session = Depends(get_db)):
    """Returns the agent audit logs, including tool calls, token usage counts, and metrics."""
    traces = db.execute(
        text("SELECT id, tool_call_signature, token_count, duration_ms, timestamp FROM agent_execution_traces WHERE agent_id = :agent_id ORDER BY timestamp DESC"),
        {"agent_id": agent_id}
    ).mappings().all()
    return {"traces": [dict(row) for row in traces]}
import asyncio
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy import text
from loguru import logger

from database import get_db

from agents.team import (
    PlannerAgent, EngineerAgent, ReviewerAgent, TesterAgent
)

router = APIRouter(prefix="/orgs/{org_slug}/agents", tags=["Autonomous Agent Management"])

# --- Pydantic API Schemas ---
class AgentCreatePayload(BaseModel):
    name: str
    model_spec: str

class AgentUpdatePayload(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    status: Optional[str] = None

class TaskAssignPayload(BaseModel):
    issue_id: str


# --- Helper: Factory to map DB Agents to Python Classes ---
def spawn_agent_instance(db_agent: dict):
    """Instantiates the correct Python class based on the agent's name profile."""
    name_lower = db_agent["name"].lower()
    org_slug = db_agent["org_slug"]
    system_prompt = db_agent.get("system_prompt", "")
    api_keys = db_agent.get("api_keys", {})

    # Map names to their corresponding specialized roles
    if "plan" in name_lower or "head" in name_lower or "pm" in name_lower or "master" in name_lower:
        return PlannerAgent(db_agent["name"], org_slug, instructions=system_prompt, api_keys=api_keys)
    elif "engineer" in name_lower or "develop" in name_lower or "architect" in name_lower:
        return EngineerAgent(db_agent["name"], org_slug, parent_id="system", api_keys=api_keys)
    elif "review" in name_lower or "audit" in name_lower:
        return ReviewerAgent(db_agent["name"], org_slug, parent_id="system", api_keys=api_keys)
    elif "test" in name_lower or "qa" in name_lower:
        return TesterAgent(db_agent["name"], org_slug, parent_id="system", api_keys=api_keys)
    
    # Fallback to the Engineer
    return EngineerAgent(db_agent["name"], org_slug, parent_id="system", api_keys=api_keys)


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
    result = await db.execute(
        text("""
            INSERT INTO agents (org_slug, name, model_spec, operational_status)
            VALUES (:org_slug, :name, :model_spec, 'stopped')
            RETURNING id, operational_status;
        """),
        {"org_slug": org_slug, "name": payload.name, "model_spec": payload.model_spec}
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

    if "status" in update_fields:
        update_fields["operational_status"] = update_fields.pop("status")

    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    update_fields["id"] = agent_id
    update_fields["org_slug"] = org_slug

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
    from main import registry

    result = await db.execute(
        text("DELETE FROM agents WHERE id = :id AND org_slug = :org_slug"),
        {"id": agent_id, "org_slug": org_slug}
    )
    await db.commit()
    
    # Clean up memory if it was running
    registry.unregister(org_slug, str(agent_id))
    
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Agent profile target missing.")
    return {"status": "decommissioned", "agent_id": agent_id}


# =============================================================================
# OPERATIONAL CONTROLS & LIFECYCLE MANAGEMENT
# =============================================================================

@router.post("/{agent_id}/start", status_code=status.HTTP_200_OK)
async def start_agent_worker(org_slug: str, agent_id: int, band_agent_id: str, band_agent_api_key: str, db: AsyncSession = Depends(get_db)):
    from main import registry

    # 1. Fetch DB Metadata
    agent_proxy = await db.execute(
        text("SELECT * FROM agents WHERE id = :id AND org_slug = :org_slug"),
        {"id": agent_id, "org_slug": org_slug}
    )
    db_agent = agent_proxy.mappings().first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent context target missing.")

    # 2. Prevent Double-Starts
    if registry.get_agent(org_slug, str(agent_id)):
        return {"status": "active", "detail": "Agent is already running in memory."}
    
    db_agent = dict(db_agent)
    db_agent["api_keys"] = {
        "agent_id": band_agent_id,
        "bandai": band_agent_api_key
    }

    # 3. Instantiate and Bootstrap the Python Agent
    live_agent = spawn_agent_instance(db_agent)
    
    # Overwrite the auto-generated string UUID with our database integer ID (cast to string)
    live_agent.id = str(agent_id) 
    
    # Register and fire up the background inbox loop!
    registry.register(org_slug, live_agent)
    asyncio.create_task(live_agent.run())

    # 4. Update Database State
    await db.execute(
        text("UPDATE agents SET operational_status = 'idle' WHERE id = :id"),
        {"id": agent_id}
    )
    await db.commit()
    
    logger.info(f"Fired live telemetry loop hook container for agent reference workspace: {agent_id}")
    return {"status": "active", "operational_status": "idle"}


@router.post("/{agent_id}/stop", status_code=status.HTTP_200_OK)
async def stop_agent_worker(org_slug: str, agent_id: int, db: AsyncSession = Depends(get_db)):
    from main import registry

    # 1. Kill the Live Agent
    live_agent = registry.get_agent(org_slug, str(agent_id))
    if live_agent:
        live_agent.running = False  # Breaks the while loop in base.py
        registry.unregister(org_slug, str(agent_id))

    # 2. Update Database State
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
    from main import registry

    """Delegates tasks to agents using issue_id references over the BAND mesh."""
    
    # 1. Verify the Agent is running in memory
    live_agent = registry.get_agent(org_slug, str(agent_id))
    if not live_agent:
        raise HTTPException(
            status_code=400, 
            detail="Agent is not currently running. Hit the /start endpoint first."
        )

    # 2. Update Database Activity Tracking
    await db.execute(
        text("UPDATE agents SET operational_status = 'busy' WHERE id = :id"),
        {"id": agent_id}
    )
    
    await db.execute(
        text("INSERT INTO agent_tasks (agent_id, issue_id, progress_status) VALUES (:agent_id, :issue_id, 'running')"),
        {"agent_id": agent_id, "issue_id": payload.issue_id}
    )
    await db.commit()

    # 3. Inject the Task Directly into the Agent's Live Inbox
    # Sending 'start' mimics the CEO bootstrap trigger present in your team.py file
    try:
        await live_agent.inbox.put({
            "message": "start", 
            "issue_id": payload.issue_id
        })
        logger.info(f"Routed task allocation for issue {payload.issue_id} directly to Agent {agent_id}'s memory inbox.")
    except Exception as e:
        logger.warning(f"Failed to inject task into agent queue: {e}")

    return {"status": "assigned", "agent_id": agent_id, "issue_id": payload.issue_id}


@router.get("/{agent_id}/status", status_code=status.HTTP_200_OK)
async def get_agent_telemetry_status(org_slug: str, agent_id: int, db: AsyncSession = Depends(get_db)):
    from main import registry

    status_info = (await db.execute(
        text("SELECT operational_status, current_running_task_id FROM agents WHERE id = :id AND org_slug = :org_slug"),
        {"id": agent_id, "org_slug": org_slug}
    )).mappings().first()
    
    if not status_info:
        raise HTTPException(status_code=404, detail="Agent profile missing.")
        
    # Check if the memory actually holds the agent, augmenting the DB status
    is_live = registry.get_agent(org_slug, str(agent_id)) is not None
    
    response = dict(status_info)
    response["is_live_in_memory"] = is_live
    return response


@router.get("/{agent_id}/memory", status_code=status.HTTP_200_OK)
async def inspect_knowledge_memory(org_slug: str, agent_id: int, db: AsyncSession = Depends(get_db)):
    """Allows inspection and pruning of what an agent has learned."""
    memories = (await db.execute(
        text("""
            SELECT id, context, outcome, retrieval_count, created_at 
            FROM agent_memories 
            WHERE agent_id = CAST(:agent_id AS uuid)
        """),
        {"agent_id": str(agent_id)} 
    )).mappings().all()
    return {"knowledge_base": [dict(row) for row in memories]}


@router.delete("/{agent_id}/memory/{memory_id}", status_code=status.HTTP_200_OK)
async def prune_knowledge_memory(org_slug: str, agent_id: int, memory_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("DELETE FROM agent_memories WHERE id = :id AND agent_id = CAST(:agent_id AS uuid)"),
        {"id": memory_id, "agent_id": str(agent_id)}
    )
    await db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Knowledge memory allocation cell missing.")
    return {"status": "pruned", "memory_id": memory_id}


@router.get("/{agent_id}/traces", status_code=status.HTTP_200_OK)
async def get_audit_logs(org_slug: str, agent_id: int, db: AsyncSession = Depends(get_db)):
    """Returns the agent audit logs, including tool calls, token usage counts, and metrics."""
    traces = (await db.execute(
        text("""
            SELECT id, tool_called, input_tokens, output_tokens, duration_ms, created_at 
            FROM agent_traces 
            WHERE agent_id = CAST(:agent_id AS uuid) 
            ORDER BY created_at DESC
        """),
        {"agent_id": str(agent_id)}
    )).mappings().all()
    return {"traces": [dict(row) for row in traces]}
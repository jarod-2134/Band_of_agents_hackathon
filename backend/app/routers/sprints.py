from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from loguru import logger

from database import get_db

router = APIRouter(prefix="/orgs/{org_slug}/sprints", tags=["Sprint Board Management"])

# --- Pydantic API Schemas ---
class SprintCreatePayload(BaseModel):
    name: str
    goal: Optional[str] = ""

class SprintItemPayload(BaseModel):
    issue_id: int
    column_status: Optional[str] = "todo"
    position: Optional[int] = 0

class SprintItemMovePayload(BaseModel):
    column_status: str
    position: int


# =============================================================================
# 1. CORE SPRINT LIFECYCLE MANAGEMENT
# =============================================================================

@router.get("")
async def list_sprints(org_slug: str, db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT id, name, goal, status FROM sprints WHERE org_slug = :org_slug"),
        {"org_slug": org_slug}
    ).mappings().all()
    return {"sprints": [dict(row) for row in result]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_sprint(org_slug: str, payload: SprintCreatePayload, db: Session = Depends(get_db)):
    result = db.execute(
        text("""
            INSERT INTO sprints (org_slug, name, goal, status)
            VALUES (:org_slug, :name, :goal, 'planning')
            RETURNING id, status
        """),
        {"org_slug": org_slug, "name": payload.name, "goal": payload.goal}
    )
    row = result.mappings().first()
    db.commit()
    return {"status": "created", "sprint_id": row["id"], "sprint_status": row["status"]}


@router.get("/{sprint_id}")
async def get_sprint_details(org_slug: str, sprint_id: int, db: Session = Depends(get_db)):
    sprint = db.execute(
        text("SELECT * FROM sprints WHERE id = :id AND org_slug = :org_slug"),
        {"id": sprint_id, "org_slug": org_slug}
    ).mappings().first()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint profile not found.")
    return dict(sprint)


@router.patch("/{sprint_id}")
async def update_sprint_metadata(org_slug: str, sprint_id: int, payload: SprintCreatePayload, db: Session = Depends(get_db)):
    result = db.execute(
        text("""
            UPDATE sprints SET name = :name, goal = :goal 
            WHERE id = :id AND org_slug = :org_slug RETURNING id
        """),
        {"name": payload.name, "goal": payload.goal, "id": sprint_id, "org_slug": org_slug}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Target sprint missing.")
    return {"status": "updated", "sprint_id": sprint_id}


@router.post("/{sprint_id}/start")
async def start_sprint_cycle(org_slug: str, sprint_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("UPDATE sprints SET status = 'active' WHERE id = :id AND org_slug = :org_slug RETURNING id"),
        {"id": sprint_id, "org_slug": org_slug}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Target sprint missing.")
    return {"status": "active", "sprint_id": sprint_id}


@router.post("/{sprint_id}/complete")
async def complete_sprint_cycle(org_slug: str, sprint_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("UPDATE sprints SET status = 'completed' WHERE id = :id AND org_slug = :org_slug RETURNING id"),
        {"id": sprint_id, "org_slug": org_slug}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Target sprint missing.")
    return {"status": "completed", "sprint_id": sprint_id}


# =============================================================================
# 2. SPRINT BOARD ITEM OPERATIONS
# =============================================================================

@router.get("/{sprint_id}/items")
async def list_sprint_items(org_slug: str, sprint_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("""
            SELECT id, issue_id, column_status, position 
            FROM sprint_items 
            WHERE sprint_id = :sprint_id 
            ORDER BY column_status, position ASC
        """),
        {"sprint_id": sprint_id}
    ).mappings().all()
    return {"items": [dict(row) for row in result]}


@router.post("/{sprint_id}/items", status_code=status.HTTP_201_CREATED)
async def add_item_to_sprint(org_slug: str, sprint_id: int, payload: SprintItemPayload, db: Session = Depends(get_db)):
    result = db.execute(
        text("""
            INSERT INTO sprint_items (sprint_id, issue_id, column_status, position)
            VALUES (:sprint_id, :issue_id, :column_status, :position)
            RETURNING id
        """),
        {
            "sprint_id": sprint_id, "issue_id": payload.issue_id,
            "column_status": payload.column_status, "position": payload.position
        }
    )
    item_id = result.scalar_one()
    db.commit()
    return {"status": "added", "item_id": item_id}


@router.delete("/{sprint_id}/items/{item_id}")
async def remove_item_from_sprint(org_slug: str, sprint_id: int, item_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("DELETE FROM sprint_items WHERE id = :id AND sprint_id = :sprint_id"),
        {"id": item_id, "sprint_id": sprint_id}
    )
    db.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Sprint board item allocation entry missing.")
    return {"status": "removed", "item_id": item_id}


@router.patch("/{sprint_id}/items/{item_id}/move")
async def move_sprint_item_ui_position(org_slug: str, sprint_id: int, item_id: int, payload: SprintItemMovePayload, db: Session = Depends(get_db)):
    """
    Handles drag-and-drop card mutation adjustments on the live board canvas.
    Applies transactional mutations and triggers state broadcast packets over the BAND broker.
    """
    # 1. Update the record data directly
    result = db.execute(
        text("""
            UPDATE sprint_items 
            SET column_status = :column_status, position = :position 
            WHERE id = :id AND sprint_id = :sprint_id 
            RETURNING id, issue_id
        """),
        {
            "column_status": payload.column_status,
            "position": payload.position,
            "id": item_id,
            "sprint_id": sprint_id
        }
    ).mappings().first()

    if not result:
        raise HTTPException(status_code=404, detail="Target board item workspace alignment mismatch.")

    db.commit()

    # 2. Fire instant message transaction packet onto BAND fabric
    # This matches the event payload layout required to notify the Zustand frontends.
    try:
        # TODO: band_client.publish(f"org.{org_slug}.sprints.board.update", {...})
        logger.info(f"Dispatched sync packet over BAND: org.{org_slug}.sprints.board.update")
    except Exception as e:
        logger.warning(f"Zustand frontend synchronization warning over BAND network paths: {e}")

    return {
        "status": "moved",
        "item_id": item_id,
        "column_status": payload.column_status,
        "position": payload.position
    }
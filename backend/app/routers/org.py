from fastapi import APIRouter, Depends, HTTPException, Response, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import re
from pydantic import BaseModel
from database import get_db
from app.routers.deps import get_current_user, require_org_member, require_org_owner
from loguru import logger

router = APIRouter(prefix="/api/v1/orgs", tags=["Multi-Tenant Organizations"])

class CreateOrgRequest(BaseModel):
    name: str
    slug: str | None = None

class UpdateOrgRequest(BaseModel):
    name: str | None = None
    plan: str | None = None

# 1. GET /orgs - List all orgs current user belongs to
@router.get("", status_code=status.HTTP_200_OK)
async def list_user_organizations(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = text("""
        SELECT o.id, o.slug, o.name, om.member_role
        FROM org_members om
        JOIN orgs o ON om.org_id = o.id
        WHERE om.user_id = :user_id;
    """)
    res = await db.execute(query, {"user_id": current_user["id"]})
    org_rows = res.fetchall()
    
    return [
        {
            "id": str(r.id),
            "slug": r.slug,
            "name": r.name,
            "plan": "pro",
            "member_role": r.member_role
        } for r in org_rows
    ]

# 2. POST /orgs - Create a new org (User becomes owner)
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: CreateOrgRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    slug = payload.slug or re.sub(r'[^a-zA-Z0-9-]', '-', payload.name.lower()).strip("-")
    
    try:
        # Step A: Provision the unique organization context
        org_res = await db.execute(text("""
            INSERT INTO orgs (name, slug) VALUES (:name, :slug)
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
            RETURNING id, name, slug;
        """), {"name": payload.name, "slug": slug})
        new_org = org_res.fetchone()
        
        # Step B: Insert relational linkage inside the org_members matrix as 'owner'
        await db.execute(text("""
            INSERT INTO org_members (org_id, user_id, member_role)
            VALUES (:org_id, :user_id, 'owner');
        """), {"org_id": new_org.id, "user_id": current_user["id"]})
        
        await db.commit()
        logger.info(f"EMIT EVENT: org.{slug}.org.created")
        
        return {
            "id": str(new_org.id),
            "slug": new_org.slug,
            "name": new_org.name,
            "plan": "pro",
            "member_role": "owner"
        }
    except Exception as e:
        logger.exception("Failed creating a new workspace tenant partition.")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to build organization context.")

# 3. GET /orgs/{slug} - Detailed view with aggregations (member count, repo count, plan)
@router.get("/{slug}", status_code=status.HTTP_200_OK)
async def get_organization_details(
    slug: str,
    org_context: dict = Depends(require_org_member),
    db: AsyncSession = Depends(get_db)
):
    # Aggregation layer pulling structural summary analytics
    counts_query = text("""
        SELECT 
            (SELECT COUNT(*) FROM org_members WHERE org_id = :org_id) AS member_count,
            (SELECT COUNT(*) FROM repos WHERE org_id = :org_id) AS repo_count;
    """)
    # Note: If your repos table doesn't exist yet, swap it with an internal mock count or integer parameter
    try:
        res = await db.execute(counts_query, {"org_id": org_context["org_id"]})
        counts = res.fetchone()
        member_count = counts.member_count if counts else 1
        repo_count = counts.repo_count if counts else 0
    except Exception:
        member_count, repo_count = 1, 0  # Fallback for dynamic MVP schemas

    return {
        "id": str(org_context["org_id"]),
        "slug": org_context["slug"],
        "name": org_context["name"],
        "plan": "pro",
        "member_count": member_count,
        "repo_count": repo_count
    }

# 4. PATCH /orgs/{slug} - Update metadata parameters (Owner Only)
@router.patch("/{slug}", status_code=status.HTTP_200_OK)
async def update_organization_metadata(
    payload: UpdateOrgRequest,
    org_context: dict = Depends(require_org_owner),
    db: AsyncSession = Depends(get_db)
):
    if not payload.name:
        raise HTTPException(status_code=400, detail="No valid transformation properties provided.")
        
    await db.execute(text("""
        UPDATE orgs SET name = :name WHERE id = :org_id;
    """), {"name": payload.name, "org_id": org_context["org_id"]})
    await db.commit()
    
    return {
        "id": str(org_context["org_id"]),
        "slug": org_context["slug"],
        "name": payload.name,
        "plan": payload.plan or "pro"
    }

# --- 5. ASYNC BACKGROUND WORKER PIPELINE FOR TENANT DELETION ---
async def cascade_purge_tenant_worker(org_id: str, slug: str, user_id: str):
    """Executes the strict system sequence ordering to drop data blocks cleanly."""
    logger.warning(f"WORKER STARTING: Full cascade deletion pipeline engaged for Org ID: {org_id}")
    # Using an explicit, non-pooled connection context to execute manual DDL steps if needed
    from database import engine
    async with engine.begin() as conn:
        # Step 1 & 2: Wipe file tracking parameters and system vectors
        logger.info("Worker Step 1/5: Purging workspace commit/issue vector embeddings matrix collections...")
        await conn.execute(text("DELETE FROM commit_embeddings WHERE org_id = :id;"), {"id": org_id})
        await conn.execute(text("DELETE FROM issue_embeddings WHERE org_id = :id;"), {"id": org_id})
        await conn.execute(text("DELETE FROM agent_memory WHERE org_id = :id;"), {"id": org_id})
        
        # Step 3: Nuke direct operational components
        logger.info("Worker Step 3/5: Purging repos, issues, and agents structures...")
        await conn.execute(text("DELETE FROM repos WHERE org_id = :id;"), {"id": org_id})
        await conn.execute(text("DELETE FROM issues WHERE org_id = :id;"), {"id": org_id})
        await conn.execute(text("DELETE FROM agents WHERE org_id = :id;"), {"id": org_id})
        
        # Step 4: Drop core organization row definition
        logger.info("Worker Step 4/5: Wiping root tenant structural configuration mapping rules...")
        await conn.execute(text("DELETE FROM orgs WHERE id = :id;"), {"id": org_id})
        
    logger.success(f"EMIT EVENT: org.{slug}.deleted")

# DELETE /orgs/{slug} - Trigger asynchronous teardown queue (Owner Only)
@router.delete("/{slug}", status_code=status.HTTP_202_ACCEPTED)
async def delete_organization_trigger(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(require_org_owner)
):
    # Delegate the heavy operation to FastAPI's built-in background task thread worker
    background_tasks.add_task(
        cascade_purge_tenant_worker,
        org_id=org_context["org_id"],
        slug=org_context["slug"],
        user_id=current_user["id"]
    )
    
    return {
        "job_id": f"job_purge_{org_context['slug']}",
        "status": "queued"
    }
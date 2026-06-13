import secrets
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, EmailStr
from database import get_db
from app.routers.deps import get_current_user, require_org_admin, require_org_member
from datetime import datetime, timedelta, timezone
from loguru import logger

router = APIRouter(prefix="/api/v1/orgs/{slug}/users", tags=["Organization Memberships"])

class InviteRequest(BaseModel):
    email: EmailStr
    role: str  # admin | member | viewer

class UpdateRoleRequest(BaseModel):
    role: str


# 1. GET /orgs/{slug}/users - List all members (including agents)
@router.get("", status_code=status.HTTP_200_OK)
async def list_org_members(
    request: Request,
    org_context: dict = Depends(require_org_member),
    db: AsyncSession = Depends(get_db)
):
    query = text("""
        SELECT u.id, u.email, u.display_name, om.member_role as role, 
               'active' as status, NOW() as last_active, om.org_slug
        FROM org_members om
        JOIN users u ON om.user_id = u.id
        WHERE om.org_id = :org_id;
    """)
    res = await db.execute(query, {"org_id": org_context["org_id"]})
    return [dict(row._mapping) for row in res.fetchall()]


# Dummy email sender background worker stub
async def send_invite_email_worker(email: str, invite_url: str):
    logger.info(f"ASYNC DISPATCH: Sending invitation email to {email}. Link: {invite_url}")


# 2. POST /orgs/{slug}/users/invite - Invite a new user
@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_user_to_org(
    payload: InviteRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(require_org_admin),
    db: AsyncSession = Depends(get_db)
):
    clean_email = payload.email.lower().strip()

    # Pre-flight Check: Guard against duplicate active organization memberships
    check_membership = await db.execute(text("""
        SELECT 1 FROM org_members om JOIN users u ON om.user_id = u.id
        WHERE om.org_id = :org_id AND LOWER(u.email) = :email;
    """), {"org_id": org_context["org_id"], "email": clean_email})
    
    if check_membership.fetchone():
        raise HTTPException(status_code=400, detail="User is already an active member of this organization.")

    # Generate secure sign-up invitation tokens
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expiration = datetime.now(timezone.utc) + timedelta(hours=48)

    # Note: If your registration flow automatically inserts accepted invitations 
    # into org_members, pass org_context["org_slug"] during that downstream step as well!
    await db.execute(text("""
        INSERT INTO invites (org_id, email, role, token_hash, invited_by, expires_at)
        VALUES (:org_id, :email, :role, :hash, :inviter, :exp);
    """), {
        "org_id": org_context["org_id"], "email": clean_email, "role": payload.role,
        "hash": token_hash, "inviter": current_user["id"], "exp": expiration
    })
    await db.commit()

    invite_link = f"http://localhost:8000/api/v1/auth/invite/{raw_token}"
    background_tasks.add_task(send_invite_email_worker, clean_email, invite_link)

    return {"message": "Invitation dispatched successfully.", "expires_at": expiration}


# 3. PATCH /orgs/{slug}/users/{id} - Change a member's role
@router.patch("/{id}", status_code=status.HTTP_200_OK)
async def change_member_role(
    id: str,
    payload: UpdateRoleRequest,
    org_context: dict = Depends(require_org_admin),
    db: AsyncSession = Depends(get_db)
):
    # Check target member's existing role metadata properties
    target = await db.execute(text("""
        SELECT member_role FROM org_members 
        WHERE org_id = :org_id AND user_id = :user_id;
    """), {"org_id": org_context["org_id"], "user_id": id})
    target_row = target.fetchone()
    
    if not target_row:
        raise HTTPException(status_code=404, detail="Target member not found in this organization.")

    # Keep org_slug updated contextually if needed
    await db.execute(text("""
        UPDATE org_members 
        SET member_role = :role, org_slug = :org_slug 
        WHERE org_id = :org_id AND user_id = :user_id;
    """), {
        "role": payload.role, 
        "org_id": org_context["org_id"], 
        "org_slug": org_context["org_slug"], 
        "user_id": id
    })
    await db.commit()

    return {"status": "updated", "user_id": id, "new_role": payload.role}


# 4. DELETE /orgs/{slug}/users/{id} - Remove a member
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member_from_org(
    id: str,
    current_user: dict = Depends(get_current_user),
    org_context: dict = Depends(require_org_admin),
    db: AsyncSession = Depends(get_db)
):
    if id == str(current_user["id"]):
        raise HTTPException(status_code=400, detail="Cannot remove yourself from an organization directly. Delete or leave explicitly.")

    target = await db.execute(text("""
        SELECT member_role FROM org_members 
        WHERE org_id = :org_id AND user_id = :user_id;
    """), {"org_id": org_context["org_id"], "user_id": id})
    target_row = target.fetchone()

    if not target_row:
        raise HTTPException(status_code=404, detail="Target user is not a member of this workspace environment.")

    await db.execute(text("""
        DELETE FROM org_members 
        WHERE org_id = :org_id AND user_id = :user_id;
    """), {"org_id": org_context["org_id"], "user_id": id})
    
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
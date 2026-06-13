from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import jwt
from database import get_db
from app.core.security import JWT_SECRET, ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

ROLE_WEIGHTS = {
    "owner": 4,
    "admin": 3,
    "member": 2,
    "viewer": 1
}

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    query = text("""
        SELECT 
            u.id, u.email, u.display_name, u.role,
            o.id AS org_id, o.slug AS org_slug, o.name AS org_name
        FROM users u
        LEFT JOIN orgs o ON u.org_id = o.id
        WHERE u.id = :user_id;
    """)

    res = await db.execute(query, {"user_id": user_id})
    user = res.fetchone()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "orgs": [
            {
                "id": str(user.org_id),
                "slug": user.org_slug,
                "name": user.org_name,
                "plan": "pro",            # Default fallback for hackathon MVP requirements
                "member_role": "owner"    # Default initial fallback role
            }
        ] if user.org_id else []
    }

async def require_org_member(
    slug: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Verifies the logged-in user belongs to the requested organization via slug."""
    query = text("""
        SELECT om.member_role, o.id AS org_id, o.name, o.slug
        FROM org_members om
        JOIN orgs o ON om.org_id = o.id
        WHERE o.slug = :slug AND om.user_id = :user_id;
    """)
    res = await db.execute(query, {"slug": slug, "user_id": current_user["id"]})
    membership = res.fetchone()
    
    if not membership:
        raise HTTPException(status_code=403, detail="Access denied: Not a member of this organization.")
    
    return {
        "org_id": membership.org_id,
        "slug": membership.slug,
        "name": membership.name,
        "user_role": membership.member_role
    }

async def require_org_owner(org_context: dict = Depends(require_org_member)) -> dict:
    """Restricts operations exclusively to users holding the 'owner' permission level."""
    if org_context["user_role"] != "owner":
        raise HTTPException(status_code=403, detail="Operation restricted to organization owners only.")
    return org_context

async def require_role_min(min_role: str, org_context: dict):
    """Enforces a baseline access floor for a route based on member roles."""
    user_role = org_context["user_role"]
    if ROLE_WEIGHTS.get(user_role, 0) < ROLE_WEIGHTS.get(min_role, 0):
        raise HTTPException(
            status_code=403, 
            detail=f"Operation requires minimum role privilege tier: {min_role}"
        )
    
async def require_member_plus(org_context: dict = Depends(require_org_member)):
    await require_role_min("member", org_context)
    return org_context

async def require_admin_plus(org_context: dict = Depends(require_org_member)):
    await require_role_min("admin", org_context)
    return org_context
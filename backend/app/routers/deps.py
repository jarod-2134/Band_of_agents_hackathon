import jwt
from fastapi import Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import ALGORITHM, JWT_SECRET

# 1. Instantiate the OAuth2 scheme, pointing to your password token endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Decodes the JWT token and returns the underlying user payload."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token claims.")
        
        return {
            "id": user_id, 
            "email": payload.get("email"), 
            "orgs": payload.get("orgs", [])  # Expecting: [{"org_id": "...", "role": "..."}]
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_org_member(
    slug: str,
    request: Request, 
    user: dict = Depends(get_current_user)
) -> dict:
    """
    Validates that the authenticated user belongs to the target organization 
    passed via the URL path context string.
    """
    # Fix parameter mismatch by safely checking both 'org_slug' and 'slug' keys
    target_org_slug = request.path_params.get("org_slug") or request.path_params.get("slug")
    print(target_org_slug)
    
    # Fallback lookup in case your routing schemas use "org_id" parameters instead
    target_org_id = request.path_params.get("org_id") or request.query_params.get("org_id")

    if not target_org_slug and not target_org_id:
        raise HTTPException(
            status_code=400, 
            detail="Missing organization context payload identifier in route request path."
        )

    user_orgs = user.get("orgs") or []
    
    # Scan token permissions to verify membership match
    matched_membership = None
    for org_membership in user_orgs:
        if org_membership.get("org_id") == target_org_id or org_membership.get("org_slug") == target_org_slug:
            matched_membership = org_membership
            return org_membership

    if not matched_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access Denied: You are not an active member of this organization partition."
        )


async def require_org_admin(membership: dict = Depends(require_org_member)) -> dict:
    """Asserts that the organization member is an admin or owner."""
    if membership.get("role") not in ["admin", "owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access Denied: Administrative tier authority required."
        )
    return membership


async def require_org_owner(membership: dict = Depends(require_org_member)) -> dict:
    """Asserts that the organization member holds explicit owner access levels."""
    if membership.get("role") != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access Denied: Organization Owner clearance required."
        )
    return membership
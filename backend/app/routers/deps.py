from fastapi import Depends, HTTPException, Request

async def get_current_user(request: Request) -> dict:
    """Reads pre-fetched user details attached by the authentication middleware context."""
    if not hasattr(request.state, "user") or request.state.user is None:
        raise HTTPException(status_code=401, detail="Invalid token session credentials")
    return request.state.user

async def require_org_member(request: Request) -> dict:
    """Reads pre-verified tenant context attached by the organization middleware."""
    if not hasattr(request.state, "org") or request.state.org is None:
        raise HTTPException(status_code=403, detail="Not a member of this org")
    return request.state.org

async def require_org_admin(m: dict = Depends(require_org_member)) -> dict:
    """Asserts that the pre-verified organization member is an admin or owner."""
    if m["member_role"] not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Admin role required")
    return m

async def require_org_owner(m: dict = Depends(require_org_member)) -> dict:
    """Asserts that the pre-verified organization member holds the explicit owner level."""
    if m["member_role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner role required")
    return m
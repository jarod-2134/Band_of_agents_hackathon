import re
import time
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from cachetools import TTLCache
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import engine  # Direct engine to spawn independent short-lived sessions
from loguru import logger

# 1. 30-second TTL Cache for User + Org contexts to optimize DB overhead
user_cache = TTLCache(maxsize=1024, ttl=30)

class LifecycleSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Always inject X-Request-Id tracking headers into downstream contexts
        request_id = request.headers.get("x-request-id", "req-" + str(time.time()))

        request.state.request_id = request_id
        
        # --- PHASE 4: FASTAPI AUTH MIDDLEWARE ---
        # Caddy validates the JWT and hands us a validated X-User-Id header
        x_user_id = request.headers.get("x-user-id")
        
        if not x_user_id:
            # Fallback path if an unauthenticated route (like /login or docs) is targeted
            request.state.user = None
        else:
            # Try loading user profile payload from the 30s local memory cache
            cached_user = user_cache.get(x_user_id)
            if cached_user:
                request.state.user = cached_user
            else:
                # Cache miss: Instantiate a thread-safe atomic session to lookup the ID
                async with AsyncSession(engine) as session:
                    res = await session.execute(
                        text("SELECT id, email, display_name, role FROM users WHERE id = :id;"),
                        {"id": x_user_id}
                    )
                    user_row = res.fetchone()
                    if not user_row:
                        return JSONResponse(status_code=401, content={"detail": "Context user not found"})
                    
                    user_data = dict(user_row._mapping)
                    user_cache[x_user_id] = user_data
                    request.state.user = user_data

        # --- PHASE 5: FASTAPI ORG MIDDLEWARE ---
        # Match routes matching the multi-tenant scope pattern: /api/v1/orgs/{slug}/...
        org_match = re.match(r"^/api/v1/orgs/([^/]+)", request.url.path)
        
        if org_match:
            slug = org_match.group(1)
            
            if not request.state.user:
                return JSONResponse(status_code=401, content={"detail": "Authentication required for tenant spaces"})
            
            user_id = request.state.user["id"]
            cache_key = f"member:{user_id}:{slug}"
            cached_membership = user_cache.get(cache_key)
            
            if cached_membership:
                request.state.org = cached_membership
            else:
                async with AsyncSession(engine) as session:
                    query = text("""
                        SELECT o.id AS org_id, o.name, o.slug, om.member_role
                        FROM org_members om
                        JOIN orgs o ON om.org_id = o.id
                        WHERE o.slug = :slug AND om.user_id = :user_id;
                    """)
                    res = await session.execute(query, {"slug": slug, "user_id": user_id})
                    membership = res.fetchone()
                    
                    if not membership:
                        return JSONResponse(
                            status_code=403, 
                            content={"detail": f"Not a member of organization: {slug}"}
                        )
                    
                    org_data = dict(membership._mapping)
                    user_cache[cache_key] = org_data
                    request.state.org = org_data
        else:
            request.state.org = None

        # Execute downstream route business handler logic
        response: Response = await call_next(request)
        
        # Step 7: Always ensure X-Request-Id header returns with the final response
        response.headers["X-Request-Id"] = request_id
        return response
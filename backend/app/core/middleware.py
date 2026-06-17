from fastapi import Request
from fastapi.responses import JSONResponse
import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.security import ALGORITHM, JWT_SECRET

class LifecycleSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        exempt_paths = [
            "/docs",          # Swagger UI
            "/redoc",         # ReDoc
            "/openapi.json",  # OpenAPI Schema
            "/api/v1/auth/login" # Login page
        ]
        
        if request.url.path in exempt_paths or request.url.path.startswith("/auth/login"):
            return await call_next(request)
        
        # 1. Get the Authorization Header
        auth_header = request.headers.get("Authorization")
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                # 2. Verify the JWT directly in Python
                payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
                request.state.user = payload # Inject user directly
            except jwt.ExpiredSignatureError:
                return JSONResponse(status_code=401, content={"detail": "Token expired"})
            except jwt.InvalidTokenError:
                return JSONResponse(status_code=401, content={"detail": "Invalid token"})
        else:
            request.state.user = None
            
        return await call_next(request)
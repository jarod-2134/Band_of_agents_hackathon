from fastapi import Request
from fastapi.responses import JSONResponse
import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.security import ALGORITHM, JWT_SECRET

class LifecycleSecurityMiddleware(BaseHTTPMiddleware):
    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)

    async def dispatch(self, request: Request, call_next):

        exempt_paths = [
            "/docs",          # Swagger UI
            "/redoc",         # ReDoc
            "/openapi.json",  # OpenAPI Schema
            "/api/v1/auth/login", # Login page
            "/api/v1/auth/register",
            "/api/v1/auth/token",
            "/api/v1/auth/refresh",
        ]
        
        path = request.url.path
        if path in exempt_paths or path.startswith("/ws/") or request.method == "OPTIONS":
            return await call_next(request)
        
        # Get the Authorization Header
        auth_header = request.headers.get("Authorization")
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                # Verify the JWT directly in Python
                payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
                request.state.user = payload # Inject user directly
                return await call_next(request)
            except jwt.ExpiredSignatureError:
                return JSONResponse(status_code=401, content={"detail": "Token expired"})
            except jwt.InvalidTokenError:
                return JSONResponse(status_code=401, content={"detail": "Invalid token"})
        else:
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
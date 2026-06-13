from fastapi import APIRouter, Cookie, Depends, Request, Response, status, BackgroundTasks
from starlette.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import re
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from app.routers.deps import get_current_user
from database import get_db
from app.core.security import hash_password, verify_password, blind_compare
# Assuming generate_tokens is imported from your core security modules
from app.core.security import generate_tokens 
from app.core.exceptions import PlatformException
from datetime import datetime, timedelta, timezone
from loguru import logger
import hashlib

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

class RegisterSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12, description="Password must be at least 12 characters long.")
    display_name: str
    org_name: str
    org_slug: str | None = None

    # Enforce bcrypt bounds defensively before the engine touches hashes
    @property
    def check_password_bytes(self) -> str:
        if len(self.password.encode("utf-8")) > 72:
            raise PlatformException(
                status_code=422,
                code="validation_error",
                message="Password cannot exceed 72 bytes.",
                field="body.password"
            )
        return self.password

class LoginSchema(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = Field(default=False, description="Extend session lifetimes if checked.")

# --- 1. LOGIN USER ENDPOINT ---
@router.post("/login")
async def login_user(
    payload: LoginSchema, 
    response: Response, 
    request: Request, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    email_clean = payload.email.strip().lower()
    logger.info(f"Processing identity lookup challenge for: {email_clean}")

    user_query = text(
        "SELECT id, email, password_hash, display_name, role, org_id FROM users WHERE email = :email"
    )
    res = await db.execute(user_query, {"email": email_clean})
    user = res.fetchone()

    if not user:
        blind_compare(payload.password)
        raise PlatformException(401, "invalid_credentials", "Email or password incorrect.")
    
    if not verify_password(payload.password, user.password_hash):
        raise PlatformException(401, "invalid_credentials", "Email or password incorrect.")
    
    try:
        # Prevent token bloat by cleaning old items matching this user id
        await db.execute(
            text("DELETE FROM refresh_tokens WHERE user_id = :user_id;"),
            {"user_id": user.id}
        )

        access_token, raw_refresh_token, refresh_token_hash = generate_tokens(user.id, email_clean)
        days_ttl = 90 if payload.remember_me else 7
        expires_at = datetime.now(timezone.utc) + timedelta(days=days_ttl)

        await db.execute(text("""
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at, ip_address, user_agent)
            VALUES (:user_id, :hash, :exp, :ip, :ua);
        """), {
            "user_id": user.id,
            "hash": refresh_token_hash,
            "exp": expires_at,
            "ip": request.client.host if request.client else None,
            "ua": request.headers.get("user-agent", "unknown")
        })

        await db.commit()

        response.set_cookie(
            key="refresh_token",
            value=raw_refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=days_ttl * 24 * 60 * 60
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 15 * 60,
            "user": {
                "id": str(user.id),
                "email": email_clean,
                "display_name": user.display_name,
                "role": user.role,
                "orgs": [
                    {
                        "id": str(user.org_id),
                        "slug": "default-org",
                        "name": "Default Partition",
                        "plan": "pro",
                        "member_role": "owner"
                    }
                ] if user.org_id else []
            }
        }
    except Exception as e:
        logger.error(f"Error during login pipeline: {e}")
        await db.rollback()
        raise PlatformException(500, "internal_error", "An unexpected tracking problem occurred.")

# --- 2. CURRENT USER RETRIEVAL ---
@router.get("/me", response_model=None)
async def get_authenticated_profile(current_user: dict = Depends(get_current_user)):
    return current_user

# --- 3. REFRESH TOKEN ROTATION ---
@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_token_rotation(
    response: Response,
    request: Request,
    background_tasks: BackgroundTasks,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):
    if not refresh_token:
        raise PlatformException(401, "missing_session_token", "Session cookie missing or empty.")

    incoming_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    
    token_query = text("""
        SELECT id, user_id, token_hash, expires_at, used_at 
        FROM refresh_tokens WHERE token_hash = :hash;
    """)
    res = await db.execute(token_query, {"hash": incoming_hash})
    token_record = res.fetchone()

    if not token_record:
        raise PlatformException(401, "invalid_session", "Session details are invalid.")

    if token_record.used_at is not None:
        logger.warning(f"REUSE DETECTION ALERT: Token ID {token_record.id} reused! Purging user tokens.")
        await db.execute(text("DELETE FROM refresh_tokens WHERE user_id = :user_id;"), {"user_id": token_record.user_id})
        await db.commit()
        response.delete_cookie(key="refresh_token")
        raise PlatformException(401, "compromised_session", "Session compromised. Re-authentication required.")

    now_utc = datetime.now(timezone.utc)
    expires_at_utc = token_record.expires_at.replace(tzinfo=timezone.utc) if token_record.expires_at.tzinfo is None else token_record.expires_at

    if now_utc > expires_at_utc:
        raise PlatformException(401, "expired_session", "Your active session context has expired.")

    try:
        await db.execute(
            text("UPDATE refresh_tokens SET used_at = :now WHERE id = :id;"),
            {"now": now_utc, "id": token_record.id}
        )

        user_email_query = text("SELECT email FROM users WHERE id = :user_id;")
        user_res = await db.execute(user_email_query, {"user_id": token_record.user_id})
        user_email = user_res.scalar()

        access_token, raw_refresh, new_refresh_hash = generate_tokens(token_record.user_id, user_email)
        expiration = now_utc + timedelta(days=7)

        await db.execute(text("""
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at, ip_address, user_agent)
            VALUES (:user_id, :hash, :exp, :ip, :ua);
        """), {
            "user_id": token_record.user_id,
            "hash": new_refresh_hash,
            "exp": expiration,
            "ip": request.client.host if request.client else None,
            "ua": request.headers.get("user-agent", "unknown")
        })
        
        await db.commit()

        response.set_cookie(
            key="refresh_token", value=raw_refresh, httponly=True, secure=True, samesite="strict", max_age=60*60*24*7
        )

        return {"access_token": access_token, "expires_in": 900}
    except Exception as e:
        await db.rollback()
        raise PlatformException(500, "rotation_failed", "Token conversion step failed.")

# --- 4. SIGNUP / REGISTER USER (ALIGNED TO AGENT-ORCHESTRATED USERS SCHEMA) ---
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(payload: RegisterSchema, response: Response, db: AsyncSession = Depends(get_db)):
    # Run structural payload pre-checks (Password length boundaries)
    payload.check_password_bytes
    
    email_clean = payload.email.strip().lower()
    slug = payload.org_slug or re.sub(r'[^a-z0-9]+', '-', payload.org_name.strip().lower()).strip('-')

    logger.info(f"Attempting to register user: {email_clean} within org compartment: {slug}")
    
    # 1. Pre-flight isolation verification
    uniqueness_query = text("SELECT id FROM users WHERE email = :email;")
    existing_check = await db.execute(uniqueness_query, {"email": email_clean})
    if existing_check.fetchone():
        raise PlatformException(400, "user_exists", "Email already registered.")
    
    # Generate password hash for verification if you maintain a separate vault table, 
    # or to be bound to refresh token signatures.
    hashed_password = hash_password(payload.password)

    try:
        # Step A: Provision the organization first because users require a non-null org_id!
        org_res = await db.execute(
            text("""
            INSERT INTO orgs (name, slug, plan)
            VALUES (:name, :slug, 'pro') RETURNING id;
            """),
            {"name": payload.org_name, "slug": slug}
        )
        org_id = org_res.scalar()

        # Step B: Provision the user profile, binding the new org_id and matching role parameters.
        user_res = await db.execute(
            text("""
            INSERT INTO users (email, password_hash, display_name, role, org_id, status)
            VALUES (:email, :password_hash, :display_name, 'human', :org_id, 'idle') RETURNING id;
            """),
            {
                "email": email_clean, 
                "password_hash": hashed_password,
                "display_name": payload.display_name,
                "org_id": org_id
            }
        )
        user_id = user_res.scalar()

        # Step C: Map the multi-tenant relational entry inside your org_members junction table
        await db.execute(
            text("""
            INSERT INTO org_members (org_id, user_id, member_role)
            VALUES (:org_id, :user_id, 'owner');
            """),
            {"org_id": org_id, "user_id": user_id}
        )

        # Step D: Handle active token credentials generation and session persistence mapping
        access_token, raw_refresh_token, refresh_token_hash = generate_tokens(user_id, email_clean)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        # Store the credential verification anchor right inside the session vault row
        await db.execute(
            text("""
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES (:user_id, :refresh_token_hash, :expires_at);
            """),
            {"user_id": user_id, "refresh_token_hash": refresh_token_hash, "expires_at": expires_at}
        )
        
        # ONE ATOMIC COMMIT TO CONCLUDE ALL STEPS SUCCESSFULLY
        await db.commit()
        logger.success(f"User {email_clean} registered successfully! IDs: User={user_id}, Org={org_id}")

        response.set_cookie(
            key="refresh_token", 
            value=raw_refresh_token, 
            httponly=True, 
            secure=True, 
            samesite="strict", 
            max_age=7*24*60*60
        )

        return {
            "access_token": access_token,
            "user": {
                "id": str(user_id),
                "email": email_clean,
                "display_name": payload.display_name,
                "role": "human",
                "org_id": str(org_id),
                "status": "idle"
            }
        }

    except Exception as e:
        logger.error(f"Error during registration pipeline workflow execution: {e}")
        await db.rollback()
        raise PlatformException(500, "registration_failed", "Could not instantiate user and organizational schema ties.")
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import re
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from backend.app.routers.deps import get_current_user
from database import get_db
from app.core.security import blind_compare, hash_password, generate_tokens, verify_password
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

class LoginSchema(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = Field(default=False, description="If true, the refresh token will have a longer expiration.")

@router.post("/login")
async def login_user(payload: LoginSchema, response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    email_clean = payload.email.strip().lower()
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "unknown")

    logger.info(f"Processing identity lookup challenge for: {email_clean}")

    user_query = text(
        "SELECT id, password_hash, display_name, role, org_id FROM users WHERE email = :email"
    )
    res = await db.execute(user_query, {"email": email_clean})
    user = res.fetchone()

    if not user:
        blind_compare(payload.password)
        logger.warning(f"Login failed: User with email {email_clean} not found.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    
    is_valid = verify_password(payload.password, user.password_hash)
    if not is_valid:
        logger.warning(f"Login failed: Invalid password for user {email_clean}.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    
    try:
        logger.warning(f"Generating tokens for user {email_clean} (ID: {user.id})")
        await db.execute(
            text("DELETE FROM refresh_tokens WHERE user_id = :user_id;"),
            {"user_id": user.id}
        )

        access_token, raw_refresh_token, refresh_token_hash = generate_tokens(user.id, email_clean)
        days_ttl = 90 if payload.remember_me else 7
        expires_at = datetime.now(timezone.utc) + timedelta(days=days_ttl)

        await db.execute(text("""
            INSERT INTO refresh_tokens (user_id, refresh_token_hash, expires_at, ip_address, user_agent)
            VALUES (:user_id, :hash, :exp, :ip, :ua);
        """), {
            "user_id": user.id,
            "hash": refresh_token_hash,
            "exp": expires_at,
            "ip": client_ip,
            "ua": user_agent
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
                "orgs": [str(user.org_id) if user.org_id else None]
            }
        }
    except Exception as e:
        logger.error(f"Error during login: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")
    
@router.get("/me", response_model=None)
async def get_authenticated_profile(current_user: dict = Depends(get_current_user)):
    return current_user
    
router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_token_rotation(
    response: Response,
    request: Request,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db)
):

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    incoming_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    token_query = text("""
        SELECT id, user_id, token_hash, expires_at, used_at 
        FROM refresh_tokens WHERE token_hash = :hash;
    """)
    res = await db.execute(token_query, {"hash": incoming_hash})
    token_record = res.fetchone()

    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid session status")

    if token_record.used_at is not None:
        logger.warning(
            f"REUSE DETECTION ALERT: Token ID {token_record.id} reused! "
            f"Breach mitigation strategy initialized: Revoking ALL active sessions for User: {token_record.user_id}."
        )
        await db.execute(text("DELETE FROM refresh_tokens WHERE user_id = :user_id;"), {"user_id": token_record.user_id})
        await db.commit()
        
        response.delete_cookie(key="refresh_token")
        raise HTTPException(status_code=401, detail="Session compromised. Re-authentication required.")

    now_utc = datetime.now(timezone.utc)
    if token_record.expires_at.tzinfo is None:
        expires_at_utc = token_record.expires_at.replace(tzinfo=timezone.utc)
    else:
        expires_at_utc = token_record.expires_at

    if now_utc > expires_at_utc:
        raise HTTPException(status_code=401, detail="Session signature expired")

    try:
        # 6. Mark old token as used now to prevent double-dipping replays
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
            "ip": client_ip,
            "ua": user_agent
        })
        
        await db.commit()

        response.set_cookie(
            key="refresh_token",
            value=raw_refresh,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=60 * 60 * 24 * 7
        )

        return {
            "access_token": access_token,
            "expires_in": 900
        }

    except Exception as e:
        logger.exception("An exception crippled token rotation execution loops.")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Rotation interface processing failure.")

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(payload: RegisterSchema, response: Response, db: AsyncSession = Depends(get_db)):
    email_clean = payload.email.strip().lower()
    slug = payload.org_slug or re.sub(r'[^a-z0-9]+', '-', payload.org_name.strip().lower()).strip('-')

    try:
        logger.info(f"Attempting to register user: {email_clean} with org: {slug}")
        uniqueness_query = text("SELECT id FROM users WHERE email = :email FOR UPDATE;")
        existing_check = await db.execute(uniqueness_query, {"email": email_clean})
        if existing_check.fetchone():
            logger.warning(f"Registration failed: Email {email_clean} already exists.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered.")
        
        hashed_password = hash_password(payload.password)

        async with db.begin():
            user_res = await db.execute(
                text("""
                INSERT INTO users (email, password_hash, display_name, role)
                VALUES (:email, :password_hash, :display_name, 'human') RETURNING id;
                """),
                {"email": email_clean, "password_hash": hashed_password, "display_name": payload.display_name}
            )
            user_id = user_res.scalar()

            org_res = await db.execute(
                text("""
                INSERT INTO orgs (name, slug)
                VALUES (:name, :slug) RETURNING id;
                """),
                {"name": payload.org_name, "slug": slug}
            )
            org_id = org_res.scalar()

            await db.execute(
                text("""
                UPDATE users SET org_id = :org_id WHERE id = :user_id;
                """),
                {"org_id": org_id, "user_id": user_id}
            )

            logger.info(f"User {email_clean} registered successfully with org {slug}. User ID: {user_id}, Org ID: {org_id}")

        access_token, raw_refresh_token, refresh_token_hash = generate_tokens(user_id, email_clean)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        await db.execute(
            text("""
            INSERT INTO refresh_tokens (user_id, refresh_token_hash, expires_at)
            VALUES (:user_id, :refresh_token_hash, :expires_at);
            """),
            {"user_id": user_id, "refresh_token_hash": refresh_token_hash, "expires_at": expires_at}
        )
        await db.commit()

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
                "org_id": str(org_id),
            }
        }

    except Exception as e:
        logger.error(f"Error during registration: {e}")
        await db.rollback()
        if not isinstance(e, HTTPException):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")
        raise e
    
@router.get("/invite/{token}", status_code=status.HTTP_200_OK)
async def accept_organization_invitation(
    token: str,
    current_user: dict = Depends(get_current_user), # The user landing on the link must be logged in
    db: AsyncSession = Depends(get_db)
):
    # Hash the raw path token parameters to look up the invitation record securely
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    invite_query = text("""
        SELECT id, org_id, email, role, expires_at, accepted_at 
        FROM invites WHERE token_hash = :hash;
    """)
    res = await db.execute(invite_query, {"hash": token_hash})
    invite = res.fetchone()

    if not invite:
        raise HTTPException(status_code=404, detail="Invitation reference signature invalid or expired.")
        
    if invite.accepted_at is not None:
        raise HTTPException(status_code=400, detail="This invitation link has already been used.")

    if datetime.now(timezone.utc) > invite.expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=400, detail="This invitation link has expired (48h timeline limit exceeded).")

    try:
        # Link the logged-in user to the organization with the role specified in the invitation
        await db.execute(text("""
            INSERT INTO org_members (org_id, user_id, member_role)
            VALUES (:org_id, :user_id, :role)
            ON CONFLICT (org_id, user_id) DO NOTHING;
        """), {"org_id": invite.org_id, "user_id": current_user["id"], "role": invite.role})

        # Mark the invitation as accepted to prevent replays
        await db.execute(text(
            "UPDATE invites SET accepted_at = NOW() WHERE id = :id;"
        ), {"id": invite.id})

        await db.commit()
        return {"status": "success", "message": "Successfully joined organization workspace."}
        
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed processing membership onboarding assignment records.")
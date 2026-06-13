from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import re
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from database import get_db
from app.core.security import hash_password, generate_tokens
from datetime import datetime, timedelta, timezone
from loguru import logger

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

class RegisterSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12, description="Password must be at least 12 characters long.")
    display_name: str
    org_name: str
    org_slug: str | None = None

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
            INSERT INTO user_tokens (user_id, refresh_token_hash, expires_at)
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
        if not isinstance(e, HTTPException):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error.")
        raise e
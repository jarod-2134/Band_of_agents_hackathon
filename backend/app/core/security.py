import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)
JWT_SECRET = os.getenv("JWT_SECRET", "<JWT_SECRET>")
ALGORITHM = "HS256"
DUMMY_HASH = "$2b$12$K8M9V3bV7eH2vM6S9zR4eOq1GZ2X2v7M2S9zR4eOq1GZ2X2v7M2S2"

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def blind_compare(a: str) -> bool:
    """Perform a constant-time comparison to prevent timing attacks."""
    return pwd_context.verify(a, DUMMY_HASH)

def generate_tokens(user_id: str, email: str):
    now = datetime.now(timezone.utc)

    access_payload = {
        "sub": str(user_id),
        "email": email,
        "exp": now + timedelta(minutes=15)
    }
    access_token = jwt.encode(access_payload, JWT_SECRET, algorithm=ALGORITHM)

    raw_refresh_token = secrets.token_hex(32)
    refresh_token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()

    return access_token, raw_refresh_token, refresh_token_hash
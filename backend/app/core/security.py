import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)
JWT_SECRET = os.getenv("JWT_SECRET", "<JWT_SECRET>")
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

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
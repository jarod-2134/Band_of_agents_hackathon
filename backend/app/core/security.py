import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt

JWT_SECRET = os.getenv("JWT_SECRET", "<JWT_SECRET>")
ALGORITHM = "HS256"
DUMMY_HASH = "$2b$12$K8M9V3bV7eH2vM6S9zR4eOq1GZ2X2v7M2S9zR4eOq1GZ2X2v7M2S"

def hash_password(password: str) -> str:
    # Convert text to raw bytes for the bcrypt engine
    password_bytes = password.encode("utf-8")
    
    # Generate salt with an explicit work factor of 12
    salt = bcrypt.gensalt(rounds=12)
    
    # Hash and decode back to a clean string for database storage
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_bytes.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), 
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def blind_compare(a: str) -> bool:
    """Executes a dummy verification check to mitigate timing-based user enumeration."""
    # Always burns identical CPU cycles regardless of whether the email was found
    bcrypt.checkpw(a.encode("utf-8"), DUMMY_HASH)

def generate_tokens(user_id: str, email: str, orgs: list):
    now = datetime.now(timezone.utc)

    access_payload = {
        "sub": str(user_id),
        "email": email,
        "orgs": orgs,
        "exp": now + timedelta(minutes=15)
    }
    access_token = jwt.encode(access_payload, JWT_SECRET, algorithm=ALGORITHM)

    raw_refresh_token = secrets.token_hex(32)
    refresh_token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()

    return access_token, raw_refresh_token, refresh_token_hash
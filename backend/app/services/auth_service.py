"""
Authentication Service - Owner Dashboard V2
JWT-based auth with bcrypt password hashing.
"""
import os
import time
import bcrypt
import jwt
from typing import Optional, Dict, Any

# JWT secret — from env or generate a fallback (set JWT_SECRET in .env for production)
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    from pathlib import Path
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("JWT_SECRET="):
                JWT_SECRET = line.split("=", 1)[1].strip()
                break
    if not JWT_SECRET:
        JWT_SECRET = "owner-dash-v2-jwt-secret-change-me"

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = 86400  # 24 hours

# User registry — passwords are bcrypt hashed, NEVER stored in plaintext
USERS: Dict[str, Dict[str, Any]] = {
    "PHH": {
        "password_hash": "$2b$12$IIgzab3L79.HsrJLyTpLlOLOXwjD.Cocf7YXnjkHlhKX9j/1bxvlO",
        "owner_group": "PHH",
        "display_name": "PHH Group",
    },
    "Kairoi": {
        "password_hash": "$2b$12$luZ9TaR3qdm4R4fpYMg2WuQrsvaONvW.K.F.GC/i4X6YY9jGyIwDe",
        "owner_group": "Kairoi",
        "display_name": "Kairoi Residential",
    },
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user. Returns user info dict or None."""
    user = USERS.get(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {
        "username": username,
        "owner_group": user["owner_group"],
        "display_name": user["display_name"],
    }


def create_token(user_info: Dict[str, Any]) -> str:
    """Create a JWT token for an authenticated user."""
    payload = {
        "sub": user_info["username"],
        "group": user_info["owner_group"],
        "display_name": user_info["display_name"],
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRATION,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify a JWT token. Returns decoded payload or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

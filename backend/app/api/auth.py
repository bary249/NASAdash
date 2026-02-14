"""
Auth API routes - Owner Dashboard V2
Login endpoint and JWT token verification.
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional
from app.services.auth_service import authenticate_user, create_token, verify_token

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    owner_group: str
    display_name: str


class UserInfo(BaseModel):
    username: str
    owner_group: str
    display_name: str


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Authenticate and return a JWT token."""
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    token = create_token(user)
    return LoginResponse(
        token=token,
        username=user["username"],
        owner_group=user["owner_group"],
        display_name=user["display_name"],
    )


async def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """Dependency: extract and verify JWT from Authorization header.
    Returns None if no token (allows unauthenticated access for backward compat).
    Raises 401 if token is invalid/expired."""
    if not authorization:
        return None
    
    # Accept "Bearer <token>" format
    token = authorization
    if token.startswith("Bearer "):
        token = token[7:]
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return {
        "username": payload.get("sub"),
        "owner_group": payload.get("group"),
        "display_name": payload.get("display_name"),
    }


@router.get("/me", response_model=UserInfo)
async def get_me(user: dict = Depends(get_current_user)):
    """Return current user info from JWT token."""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return UserInfo(**user)

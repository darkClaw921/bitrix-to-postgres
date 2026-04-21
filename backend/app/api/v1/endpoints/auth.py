"""Authentication endpoints."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.core.auth import create_access_token

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    user: dict
    token: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """Authenticate with email and password from .env."""
    settings = get_settings()

    if not settings.auth_login or not settings.auth_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured. Set AUTH_LOGIN and AUTH_PASSWORD in .env",
        )

    if body.email != settings.auth_login or body.password != settings.auth_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(body.email)

    return LoginResponse(
        user={"id": body.email, "email": body.email},
        token=token,
    )

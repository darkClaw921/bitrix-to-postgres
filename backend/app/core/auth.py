"""JWT authentication utilities."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import get_settings

security = HTTPBearer(auto_error=True)


def create_access_token(email: str) -> str:
    """Create a JWT access token for the given email."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.auth_token_expiry_minutes
    )
    payload = {
        "sub": email,
        "email": email,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.dashboard_secret_key, algorithm="HS256")


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict[str, Any]:
    """Validate JWT token and return user data.

    Raises:
        HTTPException: If token is invalid, expired, or wrong type
    """
    settings = get_settings()
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.dashboard_secret_key,
            algorithms=["HS256"],
        )

        token_type = payload.get("type")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        email = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: no subject claim",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {
            "id": email,
            "email": email,
        }

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Dependency for protected routes
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]

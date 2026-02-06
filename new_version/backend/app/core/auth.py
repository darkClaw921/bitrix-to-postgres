"""JWT authentication utilities."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import get_settings
from app.core.exceptions import AuthenticationError


security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict[str, Any]:
    """Validate JWT token and return user data.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        User data from JWT claims

    Raises:
        HTTPException: If token is invalid or expired
    """
    # If no auth configured, return a default user
    if credentials is None:
        return {
            "id": "anonymous",
            "email": None,
            "role": "admin",
        }

    settings = get_settings()
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.bitrix_webhook_url,  # Use as JWT secret fallback
            algorithms=["HS256"],
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise AuthenticationError("Invalid token: no subject claim")

        return {
            "id": user_id,
            "email": payload.get("email"),
            "role": payload.get("role"),
        }

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Dependency for protected routes
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]

"""Common Pydantic schemas."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="healthy or unhealthy")
    version: str
    database: Optional[str] = Field(None, description="Database connection status")
    bitrix: Optional[str] = Field(None, description="Bitrix connection status")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[dict[str, Any]] = None


class SuccessResponse(BaseModel):
    """Generic success response."""

    status: str = Field("success")
    message: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class PaginationParams(BaseModel):
    """Common pagination parameters."""

    page: int = Field(1, ge=1)
    per_page: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)

    @property
    def skip(self) -> int:
        """Calculate skip for database query."""
        return self.offset or (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        """Get limit for database query."""
        return self.per_page

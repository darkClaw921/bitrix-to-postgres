"""Application exceptions."""

from typing import Any


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class BitrixAPIError(AppException):
    """Bitrix24 API error."""

    pass


class BitrixRateLimitError(BitrixAPIError):
    """Bitrix24 rate limit exceeded."""

    pass


class BitrixAuthError(BitrixAPIError):
    """Bitrix24 authentication error."""

    pass


class DatabaseError(AppException):
    """Database operation error."""

    pass


class SyncError(AppException):
    """Synchronization error."""

    pass


class AuthenticationError(AppException):
    """Authentication error."""

    pass


class AuthorizationError(AppException):
    """Authorization error."""

    pass


class AIServiceError(AppException):
    """Ошибки взаимодействия с OpenAI API: таймаут, невалидный ответ, превышение лимита токенов."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, details)
        self.status_code = 502


class ChartServiceError(AppException):
    """Ошибки сервиса чартов: невалидный SQL, запрещённые таблицы, таймаут выполнения запроса."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, details)
        self.status_code = 400

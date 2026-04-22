"""Shared exception hierarchy for consumer API clients."""

from __future__ import annotations

from .logging import log_file_hint


class LawToolsCoreError(Exception):
    """Base exception for all any library using this base."""


class ApiError(LawToolsCoreError):
    """Base for API-related errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        parts = [super(Exception, self).__str__()]
        if self.status_code:
            parts.append(f"HTTP {self.status_code}")
        hint = log_file_hint()
        if hint:
            parts.append(hint)
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]} ({', '.join(parts[1:])})"


class NotFoundError(ApiError):
    """Resource not found (404)."""


class RateLimitError(ApiError):
    """Rate limit exceeded (429)."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
        *,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code, response_body)
        self.retry_after = retry_after


class AuthenticationError(ApiError):
    """Authentication failed (401/403)."""


class ServerError(ApiError):
    """Server-side error (5xx)."""


class ValidationError(LawToolsCoreError, ValueError):
    """Input validation failed.

    Inherits from ValueError for backward compatibility with code
    that catches ValueError for validation errors.
    """


class ConfigurationError(LawToolsCoreError):
    """Missing or invalid configuration (e.g., API keys)."""


class ParseError(LawToolsCoreError):
    """Failed to parse response data (XML, JSON, HTML, etc.)."""

    def __init__(
        self,
        message: str,
        source: str | None = None,
        raw_content: str | None = None,
    ) -> None:
        super().__init__(message)
        self.source = source
        self.raw_content = raw_content


__all__ = [
    "LawToolsCoreError",
    "ApiError",
    "NotFoundError",
    "RateLimitError",
    "AuthenticationError",
    "ServerError",
    "ValidationError",
    "ConfigurationError",
    "ParseError",
]

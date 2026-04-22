"""Shared HTTP and MCP scaffolding for consumer libraries.

Provides the infrastructure that consumers build on:

- Exception hierarchy for API errors (``LawToolsCoreError`` and subclasses)
- ``BaseAsyncClient`` with caching and retry support
- HTTP caching utilities (``CacheManager``, ``build_cached_http_client``)
- Resilience utilities (``default_retryer``, ``with_retry``)
- File-based logging configured per consumer app (``configure``)
- Agent tooling decorator (``agent_tool``)
"""

from .base_client import BaseAsyncClient
from .cache import CacheManager, CacheStats, build_cached_http_client
from .exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    LawToolsCoreError,
    NotFoundError,
    ParseError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .logging import configure, log_file_hint
from .resilience import (
    RETRYABLE_STATUS_CODES,
    default_retryer,
    is_retryable_error,
    with_retry,
)
from .tooling import agent_tool

__all__ = [
    # Base client
    "BaseAsyncClient",
    # Caching
    "build_cached_http_client",
    "CacheManager",
    "CacheStats",
    # Exceptions
    "LawToolsCoreError",
    "ApiError",
    "NotFoundError",
    "RateLimitError",
    "AuthenticationError",
    "ServerError",
    "ValidationError",
    "ConfigurationError",
    "ParseError",
    # Logging
    "configure",
    "log_file_hint",
    # Resilience
    "RETRYABLE_STATUS_CODES",
    "is_retryable_error",
    "default_retryer",
    "with_retry",
    # Tooling
    "agent_tool",
]

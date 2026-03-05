"""Core utilities for ip_tools.

This module provides shared infrastructure used across all ip_tools packages:
- Exception hierarchy for API errors
- Base async client with caching and retry support
- HTTP caching utilities
- Resilience/retry utilities
- Agent tooling decorators
- File-based logging configuration
"""

from .base_client import BaseAsyncClient
from .cache import CacheManager, CacheStats, build_cached_http_client
from .exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    IpToolsError,
    NotFoundError,
    ParseError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .logging import LOG_FILE, configure_logging
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
    "IpToolsError",
    "ApiError",
    "NotFoundError",
    "RateLimitError",
    "AuthenticationError",
    "ServerError",
    "ValidationError",
    "ConfigurationError",
    "ParseError",
    # Logging
    "LOG_FILE",
    "configure_logging",
    # Resilience
    "RETRYABLE_STATUS_CODES",
    "is_retryable_error",
    "default_retryer",
    "with_retry",
    # Tooling
    "agent_tool",
]

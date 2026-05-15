"""Shared HTTP and MCP scaffolding for consumer libraries.

Provides the infrastructure that consumers build on:

- Exception hierarchy for API errors (``LawToolsCoreError`` and subclasses)
- ``BaseAsyncClient`` with caching and retry support
- HTTP caching utilities (``CacheManager``, ``build_cached_http_client``)
- Resilience utilities (``default_retryer``, ``with_retry``)
- File-based logging configured per consumer app (``configure``)
"""

from .base_client import BaseAsyncClient
from .cache import CacheManager, CacheStats, build_cached_http_client
from .envelope import (
    ListEnvelope,
    Provenance,
    ResponseEnvelope,
    decode_cursor,
    encode_cursor,
    make_provenance,
)
from .envelope import configure as configure_envelope
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
from .oauth2 import OAuth2ClientCredentialsAuth
from .resilience import (
    RETRYABLE_STATUS_CODES,
    default_retryer,
    is_retryable_error,
    with_retry,
)

__all__ = [
    # Base client
    "BaseAsyncClient",
    # Caching
    "build_cached_http_client",
    "CacheManager",
    "CacheStats",
    # Envelope
    "Provenance",
    "ResponseEnvelope",
    "ListEnvelope",
    "configure_envelope",
    "make_provenance",
    "encode_cursor",
    "decode_cursor",
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
    # OAuth2
    "OAuth2ClientCredentialsAuth",
    # Resilience
    "RETRYABLE_STATUS_CODES",
    "is_retryable_error",
    "default_retryer",
    "with_retry",
]

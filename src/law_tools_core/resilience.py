"""Standardized retry and resilience utilities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .exceptions import RateLimitError

T = TypeVar("T")
P = ParamSpec("P")

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def is_retryable_error(exc: BaseException) -> bool:
    """Check if an exception should trigger a retry."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    if isinstance(exc, httpx.TransportError | RateLimitError):
        return True
    return False


def default_retryer(
    *,
    max_attempts: int = 4,
    initial_wait: float = 1.0,
    max_wait: float = 20.0,
) -> AsyncRetrying:
    """Create a standard retryer for API calls.

    Args:
        max_attempts: Maximum number of attempts (including initial).
        initial_wait: Initial wait time in seconds.
        max_wait: Maximum wait time in seconds.

    Returns:
        Configured AsyncRetrying instance.
    """
    return AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=initial_wait, max=max_wait),
        retry=retry_if_exception(is_retryable_error),
        reraise=True,
    )


def with_retry(
    *,
    max_attempts: int = 4,
    initial_wait: float = 1.0,
    max_wait: float = 20.0,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator to add retry logic to async functions.

    Args:
        max_attempts: Maximum number of attempts.
        initial_wait: Initial wait time in seconds.
        max_wait: Maximum wait time in seconds.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            retryer = default_retryer(
                max_attempts=max_attempts,
                initial_wait=initial_wait,
                max_wait=max_wait,
            )
            async for attempt in retryer:
                with attempt:
                    return await func(*args, **kwargs)
            # Should not reach here due to reraise=True
            raise RuntimeError("Unexpected retry exhaustion")

        return wrapper

    return decorator


__all__ = [
    "RETRYABLE_STATUS_CODES",
    "is_retryable_error",
    "default_retryer",
    "with_retry",
]

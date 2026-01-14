"""Retry utilities for multi-agent framework.

This module provides retry decorators with exponential backoff.
"""

import asyncio
import functools
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_exponential_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_errors: tuple[type[Exception], ...] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retry with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delay
        retryable_errors: Tuple of exception types that are retryable

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 0
            current_delay = base_delay

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempt += 1

                    # Check if error is retryable
                    if retryable_errors and not isinstance(e, retryable_errors):
                        raise

                    # Check if we've exhausted attempts
                    if attempt >= max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(current_delay, max_delay)
                    if jitter:
                        import random

                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    import time

                    time.sleep(delay)

                    # Increase delay for next attempt
                    current_delay *= exponential_base

            # Should never reach here
            raise RuntimeError(f"Retry logic failed for {func.__name__}")

        return wrapper

    return decorator


def async_retry_with_exponential_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_errors: tuple[type[Exception], ...] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Async decorator for retry with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delay
        retryable_errors: Tuple of exception types that are retryable

    Returns:
        Decorated async function with retry logic
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            current_delay = base_delay

            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    attempt += 1

                    # Check if error is retryable
                    if retryable_errors and not isinstance(e, retryable_errors):
                        raise

                    # Check if we've exhausted attempts
                    if attempt >= max_attempts:
                        logger.error(
                            f"Async function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(current_delay, max_delay)
                    if jitter:
                        import random

                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"Async function {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    await asyncio.sleep(delay)

                    # Increase delay for next attempt
                    current_delay *= exponential_base

            # Should never reach here
            raise RuntimeError(f"Retry logic failed for {func.__name__}")

        return wrapper

    return decorator


def is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable.

    Common retryable errors include:
    - Connection errors
    - Timeout errors
    - Rate limit errors (429)
    - Server errors (5xx)

    Args:
        error: The exception to check

    Returns:
        True if the error is retryable
    """
    # Check for specific error types
    error_type = type(error).__name__
    error_message = str(error).lower()

    # Connection errors
    if "connection" in error_type.lower() or "connect" in error_message:
        return True

    # Timeout errors
    if "timeout" in error_type.lower() or "timeout" in error_message:
        return True

    # Rate limit errors
    if "429" in error_message or "rate limit" in error_message:
        return True

    # Server errors (5xx)
    if "5" in error_message and "error" in error_message:
        return True

    # Temporary failures
    if "temporary" in error_message or "unavailable" in error_message:
        return True

    return False

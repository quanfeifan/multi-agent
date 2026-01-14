"""Timeout utilities for multi-agent framework.

This module provides timeout decorators and context managers.
"""

import asyncio
import functools
import signal
from typing import Any, Callable, TypeVar

from .retry import is_retryable_error

T = TypeVar("T")


class TimeoutError(Exception):
    """Exception raised when a timeout occurs."""

    pass


def timeout(seconds: int | float) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to add timeout to a function.

    Args:
        seconds: Timeout in seconds

    Returns:
        Decorated function with timeout

    Example:
        @timeout(30)
        def my_function():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            import threading

            result: T | None = None
            exception: Exception | None = None

            def target() -> None:
                nonlocal result, exception
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    exception = e

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=seconds)

            if thread.is_alive():
                # Thread is still running - timeout
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")

            if exception is not None:
                raise exception

            return result  # type: ignore

        return wrapper

    return decorator


def async_timeout(seconds: int | float) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Async decorator to add timeout to an async function.

    Args:
        seconds: Timeout in seconds

    Returns:
        Decorated async function with timeout

    Example:
        @async_timeout(30)
        async def my_async_function():
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Async function {func.__name__} timed out after {seconds} seconds")

        return wrapper

    return decorator


class TimeoutContext:
    """Context manager for timeout.

    Uses signal.SIGALRM on Unix systems.

    Args:
        seconds: Timeout in seconds

    Example:
        with TimeoutContext(30):
            # Code that must complete within 30 seconds
            ...
    """

    def __init__(self, seconds: int | float) -> None:
        """Initialize the timeout context.

        Args:
            seconds: Timeout in seconds
        """
        self.seconds = seconds
        self._old_handler: Any | None = None

    def __enter__(self) -> "TimeoutContext":
        """Enter the timeout context.

        Returns:
            Self
        """
        import platform

        if platform.system() != "Windows":
            # Set signal alarm
            self._old_handler = signal.signal(signal.SIGALRM, self._handle_timeout)
            signal.alarm(int(self.seconds))
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the timeout context.

        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        import platform

        if platform.system() != "Windows":
            # Cancel alarm and restore handler
            signal.alarm(0)
            if self._old_handler is not None:
                signal.signal(signal.SIGALRM, self._old_handler)

    def _handle_timeout(self, signum: int, frame: Any) -> None:
        """Handle timeout signal.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        raise TimeoutError(f"Operation timed out after {self.seconds} seconds")


async def wait_with_timeout(
    coro: Any,
    timeout_seconds: int | float,
    check_interval: float = 0.1,
) -> Any:
    """Wait for a coroutine with timeout and optional retryable error checking.

    Args:
        coro: Coroutine to wait for
        timeout_seconds: Timeout in seconds
        check_interval: Interval to check for completion

    Returns:
        Result of the coroutine

    Raises:
        TimeoutError: If timeout is reached
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds")


def execute_with_timeout_retry(
    func: Callable[..., T],
    timeout_seconds: int | float,
    max_attempts: int = 3,
    *args: Any,
    **kwargs: Any,
) -> T:
    """Execute a function with timeout and retry logic.

    Combines timeout and retry for operations that may temporarily fail.

    Args:
        func: Function to execute
        timeout_seconds: Timeout in seconds
        max_attempts: Maximum number of attempts
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        TimeoutError: If all attempts timeout
    """
    import time

    last_exception: Exception | None = None

    for attempt in range(max_attempts):
        try:
            # Use timeout decorator
            timeout_decorator = timeout(int(timeout_seconds))
            timeout_func = timeout_decorator(func)
            return timeout_func(*args, **kwargs)
        except TimeoutError as e:
            last_exception = e
            if attempt < max_attempts - 1:
                # Wait before retry
                wait_time = 2**attempt
                time.sleep(wait_time)

    raise TimeoutError(
        f"Function {func.__name__} timed out after {max_attempts} attempts of {timeout_seconds}s each"
    )

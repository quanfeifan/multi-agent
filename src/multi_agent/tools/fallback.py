"""Fallback mechanism for multi-agent framework.

This module provides automatic fallback and retry logic for tool failures.
"""

import asyncio
from typing import Any, TYPE_CHECKING, Optional

from pydantic import BaseModel

from ..models import Tool
from ..utils import get_logger, is_retryable_error
from ..utils.retry import retry_with_exponential_backoff
from ..utils.timeout import TimeoutError

if TYPE_CHECKING:
    from ..tools import ToolExecutor

logger = get_logger(__name__)


class FallbackConfig(BaseModel):
    """Configuration for tool fallback.

    Attributes:
        timeout_seconds: Tool execution timeout
        fallback_tools: List of fallback tool identifiers
        max_retries: Maximum retry attempts
        retryable_errors: Error patterns that trigger retry
    """

    timeout_seconds: int = 300
    fallback_tools: list[tuple[str, str]] = []
    max_retries: int = 3
    retryable_errors: list[str] = ["timeout", "rate_limit", "connection"]


class FallbackManager:
    """Manages fallback and retry logic for tool execution.

    Provides automatic timeout enforcement, fallback tool invocation,
    and retry with exponential backoff.
    """

    def __init__(
        self,
        tool_executor: "ToolExecutor",
    ) -> None:
        """Initialize the fallback manager.

        Args:
            tool_executor: Tool executor for running tools
        """
        self.tool_executor = tool_executor
        self.fallback_configs: dict[str, FallbackConfig] = {}
        self.tool_overrides: dict[str, dict[str, Any]] = {}

    def load_tool_overrides(self, overrides: dict[str, Any]) -> None:
        """Load tool override configuration.

        Args:
            overrides: Tool override configuration from YAML
        """
        self.tool_overrides = overrides

        # Parse fallback configs
        if "tool_overrides" in overrides:
            for tool_key, config in overrides["tool_overrides"].items():
                # tool_key format: "server:tool"
                server, tool_name = tool_key.split(":") if ":" in tool_key else ("*", tool_name)

                fallback_tools = []
                if "fallback_tools" in config:
                    for fb in config["fallback_tools"]:
                        if ":" in fb:
                            fb_server, fb_tool = fb.split(":")
                            fallback_tools.append((fb_server, fb_tool))

                self.fallback_configs[tool_key] = FallbackConfig(
                    timeout_seconds=config.get("timeout_seconds", 300),
                    fallback_tools=fallback_tools,
                    max_retries=config.get("max_retries", 3),
                    retryable_errors=config.get("retry_on_errors", []),
                )

    def get_fallback_config(self, server: str, tool_name: str) -> FallbackConfig:
        """Get fallback configuration for a tool.

        Args:
            server: Server name
            tool_name: Tool name

        Returns:
            Fallback configuration
        """
        tool_key = f"{server}:{tool_name}"
        wildcard_key = f"*:{tool_name}"

        if tool_key in self.fallback_configs:
            return self.fallback_configs[tool_key]

        if wildcard_key in self.fallback_configs:
            return self.fallback_configs[wildcard_key]

        return FallbackConfig()  # Default config

    async def execute_with_fallback(
        self,
        server: str,
        tool_name: str,
        arguments: dict[str, Any],
        agent_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute a tool with fallback and retry logic.

        Args:
            server: Server name
            tool_name: Tool name
            arguments: Tool arguments
            agent_name: Optional agent name for access control

        Returns:
            Tool result

        Raises:
            RuntimeError: If all attempts fail
        """
        config = self.get_fallback_config(server, tool_name)

        # Build attempt list
        attempts = [(server, tool_name)] + config.fallback_tools

        for attempt_server, attempt_tool in attempts:
            try:
                logger.debug(f"Attempting tool: {attempt_server}:{attempt_tool}")

                # Check agent access if specified
                if agent_name:
                    if not self.tool_executor.manager.check_tool_access(agent_name, attempt_tool):
                        logger.warning(
                            f"Agent {agent_name} not allowed to access {attempt_tool}, skipping"
                        )
                        continue

                # Execute with retry
                result = await self._execute_with_retry(
                    attempt_server,
                    attempt_tool,
                    arguments,
                    config,
                )

                return result

            except (TimeoutError, RuntimeError) as e:
                logger.warning(f"Tool attempt failed: {attempt_server}:{attempt_tool} - {e}")

                # Check if error is retryable
                if config.retryable_errors:
                    error_str = str(e).lower()
                    if not any(pattern in error_str for pattern in config.retryable_errors):
                        # Not a retryable error, don't try more attempts
                        break

                continue

        raise RuntimeError(f"All tool execution attempts failed: {server}:{tool_name}")

    async def _execute_with_retry(
        self,
        server: str,
        tool_name: str,
        arguments: dict[str, Any],
        config: FallbackConfig,
    ) -> dict[str, Any]:
        """Execute a tool with retry logic.

        Args:
            server: Server name
            tool_name: Tool name
            arguments: Tool arguments
            config: Fallback configuration

        Returns:
            Tool result
        """
        if config.max_retries <= 1:
            # No retry, execute directly
            return await self.tool_executor.execute(
                server,
                tool_name,
                arguments,
                timeout=config.timeout_seconds,
            )

        # Execute with retry decorator
        @retry_with_exponential_backoff(
            max_attempts=config.max_retries,
            base_delay=1.0,
            max_delay=30.0,
        )
        async def execute_with_retry() -> dict[str, Any]:
            return await self.tool_executor.execute(
                server,
                tool_name,
                arguments,
                timeout=config.timeout_seconds,
            )

        try:
            return await execute_with_retry()
        except Exception as e:
            # Check if last error is retryable
            if is_retryable_error(e):
                # Retryable error but max retries exceeded
                raise
            # Non-retryable error, raise immediately
            raise

    def should_use_fallback(self, error: Exception, tool_name: str) -> bool:
        """Check if fallback should be used for an error.

        Args:
            error: The error that occurred
            tool_name: Tool that failed

        Returns:
            True if fallback should be attempted
        """
        # Always use fallback for timeout
        if isinstance(error, TimeoutError):
            return True

        # Check error type
        error_str = str(error).lower()

        # Check for retryable patterns
        retryable_patterns = ["timeout", "rate limit", "connection", "unavailable"]
        if any(pattern in error_str for pattern in retryable_patterns):
            return True

        return False

    async def execute_timeout_enforced(
        self,
        server: str,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        """Execute a tool with enforced timeout.

        Args:
            server: Server name
            tool_name: Tool name
            arguments: Tool arguments
            timeout_seconds: Timeout in seconds

        Returns:
            Tool result

        Raises:
            TimeoutError: If execution times out
        """
        try:
            return await asyncio.wait_for(
                self.tool_executor.manager.execute_tool(server, tool_name, arguments),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Tool execution timed out after {timeout_seconds}s: {server}:{tool_name}")

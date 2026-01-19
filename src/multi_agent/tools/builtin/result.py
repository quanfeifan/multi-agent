"""ToolResult class for built-in tool library.

This module defines the ToolResult class which provides a standardized
result format for all tool executions.
"""

from typing import Optional


class ToolResult:
    """Result of tool execution.

    Attributes:
        success: Whether the tool execution succeeded
        data: Result data (if successful)
        error: Error message (if failed)
        truncated: Whether output was truncated due to size limit
    """

    # Maximum result size (100KB)
    MAX_SIZE = 100 * 1024

    def __init__(
        self,
        success: bool,
        data: Optional[str] = None,
        error: Optional[str] = None,
        truncated: bool = False,
    ):
        """Initialize a ToolResult.

        Args:
            success: Whether the tool execution succeeded
            data: Result data (if successful)
            error: Error message (if failed)
            truncated: Whether output was truncated due to size limit
        """
        self.success = success
        self.data = data
        self.error = error
        self.truncated = truncated

    def to_content(self) -> str:
        """Format for LLM consumption.

        Returns:
            Formatted content string
        """
        if self.success:
            result = self.data or ""
            if self.truncated:
                result += "\n\n[Warning: Output truncated due to size limit]"
            return result
        return f"Error: {self.error}"

    @classmethod
    def from_string(cls, content: str, enforce_limit: bool = True) -> "ToolResult":
        """Create a ToolResult from a string, enforcing size limit.

        Args:
            content: The content string
            enforce_limit: Whether to enforce MAX_SIZE limit

        Returns:
            ToolResult with appropriate truncation
        """
        if enforce_limit and len(content.encode("utf-8")) > cls.MAX_SIZE:
            # Truncate to byte limit
            truncated = cls._truncate_to_size(content, cls.MAX_SIZE)
            return cls(success=True, data=truncated, truncated=True)
        return cls(success=True, data=content, truncated=False)

    @staticmethod
    def _truncate_to_size(text: str, max_bytes: int) -> str:
        """Truncate text to fit within max_bytes.

        Args:
            text: Text to truncate
            max_bytes: Maximum size in bytes

        Returns:
            Truncated text
        """
        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text

        # Truncate and decode safely
        truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
        return truncated

    def __repr__(self) -> str:
        """String representation of the result."""
        if self.success:
            return f"ToolResult(success={self.success}, truncated={self.truncated}, len={len(self.data) if self.data else 0})"
        return f"ToolResult(success={self.success}, error={self.error})"

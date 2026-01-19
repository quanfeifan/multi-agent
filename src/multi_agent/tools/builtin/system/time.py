"""System get time tool for built-in tool library."""

from datetime import datetime, timezone
from typing import Dict, Any

from ..result import ToolResult


class SystemGetTimeTool:
    """Tool for getting current system time."""

    @property
    def name(self) -> str:
        return "system_get_time"

    @property
    def description(self) -> str:
        return "Get the current date and time in ISO 8601 format."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **kwargs) -> ToolResult:
        """Get current time.

        Returns:
            ToolResult with current time in ISO 8601 format
        """
        try:
            now = datetime.now(timezone.utc)
            time_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            return ToolResult(success=True, data=time_str)
        except Exception as e:
            return ToolResult(success=False, error=f"Error getting time: {e}")

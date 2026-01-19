"""System get environment variable tool for built-in tool library."""

import os
from typing import Dict, Any

from ..result import ToolResult


class SystemGetEnvTool:
    """Tool for getting environment variable values."""

    @property
    def name(self) -> str:
        return "system_get_env"

    @property
    def description(self) -> str:
        return "Get the value of an environment variable."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the environment variable",
                }
            },
            "required": ["name"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        """Get environment variable value.

        Args:
            name: Environment variable name

        Returns:
            ToolResult with variable value or indication of missing variable
        """
        name = kwargs.get("name", "")
        if not name:
            return ToolResult(success=False, error="Name parameter is required")

        value = os.environ.get(name)
        if value is None:
            return ToolResult(
                success=True,
                data=f"Environment variable '{name}' is not set"
            )

        # Truncate if too large
        return ToolResult.from_string(value, enforce_limit=True)

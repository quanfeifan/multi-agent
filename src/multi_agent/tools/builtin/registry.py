"""Tool registry for built-in tool library.

This module provides the BuiltinRegistry class for managing tool
registration, discovery, retrieval, and LLM integration.
"""

import asyncio
from typing import Any, Dict, List, Optional


class BuiltinRegistry:
    """Simple registry for builtin tools.

    Provides tool registration, discovery, LLM integration,
    and parallel execution support.
    """

    def __init__(self):
        """Initialize an empty registry."""
        self._tools: Dict[str, Any] = {}

    def register(self, tool: Any) -> None:
        """Register a tool instance.

        Args:
            tool: Tool instance with name, description, parameters, and execute method

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        if not hasattr(tool, "name"):
            raise ValueError("Tool must have a 'name' property")
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Any]:
        """Get tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Check if a tool is registered.

        Args:
            name: Tool name

        Returns:
            True if tool exists, False otherwise
        """
        return name in self._tools

    def list_all(self) -> List[Any]:
        """List all registered tools.

        Returns:
            List of all registered Tool instances
        """
        return list(self._tools.values())

    def to_llm_list(self) -> List[Dict[str, Any]]:
        """Export all tools in LLM function calling format (OpenAI compatible).

        Returns:
            List of dictionaries in OpenAI function calling format:
            [
                {
                    "type": "function",
                    "function": {
                        "name": "tool_name",
                        "description": "Tool description",
                        "parameters": {...JSON Schema...}
                    }
                },
                ...
            ]
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    async def execute_batch(
        self, calls: List[tuple[str, Dict[str, Any]]]
    ) -> List[Any]:
        """Execute multiple builtin tools in parallel.

        Args:
            calls: List of (tool_name, arguments) tuples

        Returns:
            List of ToolResult objects in same order as calls.
            Failed executions return ToolResult with success=False.
        """
        from .result import ToolResult

        async def execute_one(name: str, args: Dict[str, Any]) -> Any:
            tool = self.get(name)
            if not tool:
                return ToolResult(success=False, error=f"Tool not found: {name}")
            try:
                return await tool.execute(**args)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        tasks = [execute_one(name, args) for name, args in calls]
        return await asyncio.gather(*tasks, return_exceptions=True)


# Global registry instance (initialized lazily)
_builtin_registry: Optional[BuiltinRegistry] = None


def get_builtin_registry() -> BuiltinRegistry:
    """Get the global built-in tool registry.

    Note: This returns an empty registry on first call.
    Use register_builtin_tools() to populate it with tools.

    Returns:
        The global BuiltinRegistry instance
    """
    global _builtin_registry
    if _builtin_registry is None:
        _builtin_registry = BuiltinRegistry()
    return _builtin_registry

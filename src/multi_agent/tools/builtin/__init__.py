"""Built-in tool library for multi-agent framework.

This module provides ready-to-use tools organized by category:
- file: File system operations (read, write, list, info)
- programming: Code execution and calculations
- network: Web content fetching
- system: System information retrieval

Example:
    >>> from multi_agent.tools.builtin import register_builtin_tools, get_builtin_registry
    >>> registry = register_builtin_tools()
    >>> tools = registry.to_llm_list()
    >>> print([t['function']['name'] for t in tools])
"""

from .file import register_file_tools
from .programming import register_programming_tools
from .network import register_network_tools
from .registry import BuiltinRegistry, get_builtin_registry
from .result import ToolResult
from .system import register_system_tools

__all__ = [
    # Core classes
    "ToolResult",
    "BuiltinRegistry",
    "get_builtin_registry",
    # Registration functions
    "register_builtin_tools",
    "register_file_tools",
    "register_programming_tools",
    "register_network_tools",
    "register_system_tools",
]

# Tool name constants for easy reference
FILE_READ = "file_read"
FILE_WRITE = "file_write"
FILE_LIST = "file_list"
FILE_INFO = "file_info"

PROGRAMMING_CALCULATE = "calculate"
PROGRAMMING_EXECUTE = "execute"

NETWORK_FETCH = "network_fetch"

SYSTEM_GET_TIME = "system_get_time"
SYSTEM_GET_ENV = "system_get_env"
SYSTEM_LIST_PROCESSES = "system_list_processes"


def register_builtin_tools() -> BuiltinRegistry:
    """Register all built-in tools and return the registry.

    This is a convenience function that registers all tool categories
    and returns the populated registry.

    Returns:
        BuiltinRegistry instance with all tools registered
    """
    registry = BuiltinRegistry()

    # Register all tools from each category
    for tool in register_file_tools():
        registry.register(tool)
    for tool in register_programming_tools():
        registry.register(tool)
    for tool in register_network_tools():
        registry.register(tool)
    for tool in register_system_tools():
        registry.register(tool)

    return registry

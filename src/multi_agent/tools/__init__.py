"""Tool integration for multi-agent framework.

This module provides both MCP (external) tools and builtin (local) tools.
- MCP tools: External tools accessed via JSON-RPC protocol
- Builtin tools: Local tools for file, programming, network, and system operations
"""

from .fallback import FallbackConfig, FallbackManager
from .mcp_client import MCPMessage, MCPSSETransport, MCPStdioTransport, MCPTransport, create_mcp_transport
from .mcp_manager import MCPToolManager, ToolExecutor

# Builtin tools
from .builtin import (
    BuiltinRegistry,
    ToolResult,
    get_builtin_registry,
    register_builtin_tools,
    register_file_tools,
    register_network_tools,
    register_programming_tools,
    register_system_tools,
)

__all__ = [
    # Client
    "MCPTransport",
    "MCPStdioTransport",
    "MCPSSETransport",
    "MCPMessage",
    "create_mcp_transport",
    # Manager
    "MCPToolManager",
    "ToolExecutor",
    # Fallback
    "FallbackManager",
    "FallbackConfig",
    # Builtin
    "BuiltinRegistry",
    "ToolResult",
    "get_builtin_registry",
    "register_builtin_tools",
    "register_file_tools",
    "register_network_tools",
    "register_programming_tools",
    "register_system_tools",
]

"""MCP tool manager for multi-agent framework.

This module provides tool discovery, execution, and management.
"""

import asyncio
from typing import Any, Optional

from pydantic import BaseModel

from ..models import MCPServer, Tool
from ..utils.logging import get_logger
from .mcp_client import MCPMessage, create_mcp_transport, MCPTransport

logger = get_logger(__name__)


class MCPToolManager:
    """Manages MCP tools and server connections.

    Handles tool discovery, execution, and automatic server correction.
    Supports per-agent tool access control.
    """

    def __init__(self) -> None:
        """Initialize the MCP tool manager."""
        self.servers: dict[str, MCPServer] = {}
        self.transports: dict[str, MCPTransport] = {}
        self.tools: dict[str, Tool] = {}  # server:tool -> Tool
        self.agent_tools: dict[str, list[str]] = {}  # agent -> list of allowed tools
        self._initialized = False

    def set_agent_tools(self, agent_name: str, tools: list[str]) -> None:
        """Set the tools that an agent is allowed to access.

        Args:
            agent_name: Name of the agent
            tools: List of tool names the agent can use
        """
        self.agent_tools[agent_name] = tools
        logger.debug(f"Set tools for agent {agent_name}: {tools}")

    def get_agent_tools(self, agent_name: str) -> list[str]:
        """Get the tools an agent is allowed to access.

        Args:
            agent_name: Name of the agent

        Returns:
            List of tool names (empty if no restriction)
        """
        return self.agent_tools.get(agent_name, [])

    def filter_tools_for_agent(self, agent_name: str) -> list[Tool]:
        """Get all tools accessible to a specific agent.

        Args:
            agent_name: Name of the agent

        Returns:
            List of tools the agent can access
        """
        allowed_tools = self.get_agent_tools(agent_name)

        if not allowed_tools:
            # No restriction - return all tools
            return list(self.tools.values())

        # Filter by allowed tool names
        return [
            tool
            for tool in self.tools.values()
            if tool.name in allowed_tools
        ]

    def check_tool_access(self, agent_name: str, tool_name: str) -> bool:
        """Check if an agent has access to a specific tool.

        Args:
            agent_name: Name of the agent
            tool_name: Name of the tool

        Returns:
            True if agent has access
        """
        allowed_tools = self.get_agent_tools(agent_name)

        if not allowed_tools:
            # No restriction
            return True

        return tool_name in allowed_tools

    async def add_server(self, server: MCPServer) -> None:
        """Add an MCP server and connect to it.

        Args:
            server: MCP server configuration
        """
        if not server.enabled:
            logger.info(f"Skipping disabled MCP server: {server.name}")
            return

        logger.info(f"Adding MCP server: {server.name}")
        self.servers[server.name] = server

        # Create and connect transport
        transport = create_mcp_transport(server)
        await transport.connect()
        self.transports[server.name] = transport

        # Discover tools
        await self._discover_tools(server.name)

    async def _discover_tools(self, server_name: str) -> None:
        """Discover tools from an MCP server.

        Args:
            server_name: Name of the server
        """
        transport = self.transports.get(server_name)
        if not transport:
            logger.warning(f"Cannot discover tools: transport not found for {server_name}")
            return

        try:
            # List tools request
            message = MCPMessage(method="tools/list")
            response = await transport.send_message(message)

            if response.result and "tools" in response.result:
                for tool_def in response.result["tools"]:
                    tool = Tool(
                        name=tool_def["name"],
                        server=server_name,
                        description=tool_def.get("description", ""),
                        input_schema=tool_def.get("inputSchema", {}),
                        output_schema=tool_def.get("outputSchema"),
                    )
                    key = f"{server_name}:{tool.name}"
                    self.tools[key] = tool
                    logger.debug(f"Discovered tool: {key}")

            logger.info(f"Discovered {len(response.result.get('tools', []))} tools from {server_name}")

        except Exception as e:
            logger.error(f"Error discovering tools from {server_name}: {e}")

    async def execute_tool(
        self,
        server: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a tool on an MCP server.

        Args:
            server: Server name
            tool_name: Tool name
            arguments: Tool arguments

        Returns:
            Tool execution result

        Raises:
            RuntimeError: If server not found or not connected
            TimeoutError: If tool execution times out
        """
        # Check if server exists
        if server not in self.servers:
            # Try automatic correction
            corrected_server = await self._correct_server(server, tool_name)
            if corrected_server:
                logger.info(f"Auto-corrected tool call from {server} to {corrected_server}")
                server = corrected_server
            else:
                raise RuntimeError(f"MCP server not found: {server}")

        transport = self.transports.get(server)
        if not transport or not transport.is_connected():
            raise RuntimeError(f"Not connected to MCP server: {server}")

        try:
            # Call tool request
            message = MCPMessage(
                method="tools/call",
                params={
                    "name": tool_name,
                    "arguments": arguments,
                },
            )

            response = await transport.send_message(message)

            if response.error:
                error_msg = response.error.get("message", "Unknown error")
                raise RuntimeError(f"Tool execution failed: {error_msg}")

            return response.result or {}

        except asyncio.TimeoutError:
            raise TimeoutError(f"Tool execution timed out: {server}:{tool_name}")

    async def _correct_server(self, server: str, tool_name: str) -> Optional[str]:
        """Attempt to correct the server for a tool.

        Searches for the tool on all connected servers.

        Args:
            server: Original server name
            tool_name: Tool name to find

        Returns:
            Corrected server name or None
        """
        # Search for tool on all servers
        for other_server in self.servers:
            if other_server == server:
                continue

            key = f"{other_server}:{tool_name}"
            if key in self.tools:
                return other_server

        return None

    def list_tools(self, server: Optional[str] = None) -> list[Tool]:
        """List available tools.

        Args:
            server: Optional server name to filter by

        Returns:
            List of tools
        """
        if server:
            return [t for t in self.tools.values() if t.server == server]
        return list(self.tools.values())

    def get_tool(self, server: str, tool_name: str) -> Optional[Tool]:
        """Get a tool by server and name.

        Args:
            server: Server name
            tool_name: Tool name

        Returns:
            Tool or None if not found
        """
        key = f"{server}:{tool_name}"
        return self.tools.get(key)

    def has_tool(self, server: str, tool_name: str) -> bool:
        """Check if a tool exists.

        Args:
            server: Server name
            tool_name: Tool name

        Returns:
            True if tool exists
        """
        key = f"{server}:{tool_name}"
        return key in self.tools

    async def close(self) -> None:
        """Close all server connections."""
        logger.info("Closing all MCP server connections")

        for name, transport in self.transports.items():
            try:
                await transport.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting from {name}: {e}")

        self.transports.clear()
        self.tools.clear()


class ToolExecutor:
    """Unified executor for both builtin and MCP tools with parallel execution support.

    Provides a single interface for executing local builtin tools (high performance)
    and external MCP tools (extensible via JSON-RPC).
    """

    def __init__(
        self,
        manager: Optional[MCPToolManager] = None,
        builtin_registry: Optional["BuiltinRegistry"] = None,
        default_timeout: int = 300,
    ) -> None:
        """Initialize the tool executor.

        Args:
            manager: Optional MCP tool manager for external tools
            builtin_registry: Optional builtin registry for local tools
            default_timeout: Default timeout in seconds
        """
        from .builtin import get_builtin_registry

        self.manager = manager
        self.builtin_registry = builtin_registry or get_builtin_registry()
        self.default_timeout = default_timeout
        self._tool_server_cache: dict[str, str] = {}  # tool_name -> server

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        server: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> dict[str, Any]:
        """Execute a single tool (builtin or MCP).

        Args:
            tool_name: Tool name
            arguments: Tool arguments
            server: Optional server hint for MCP tools
            timeout: Execution timeout in seconds

        Returns:
            Result in MCP format: {"content": [{"type": "text", "text": "..."}]}

        Raises:
            TimeoutError: If execution times out
            RuntimeError: If tool not found or execution fails
        """
        timeout = timeout or self.default_timeout

        # Check if it's a builtin tool
        if self.builtin_registry.has(tool_name):
            return await self._execute_builtin(tool_name, arguments)

        # Otherwise, use MCP manager
        if not self.manager:
            return {
                "content": [{"type": "text", "text": f"Tool not found: {tool_name}"}]
            }

        if server:
            return await asyncio.wait_for(
                self.manager.execute_tool(server, tool_name, arguments),
                timeout=timeout,
            )
        else:
            # Auto-detect server
            server = await self._find_server_for_tool(tool_name)
            if server:
                return await asyncio.wait_for(
                    self.manager.execute_tool(server, tool_name, arguments),
                    timeout=timeout,
                )
            else:
                return {
                    "content": [{"type": "text", "text": f"Tool not found: {tool_name}"}]
                }

    async def execute_batch(
        self,
        tool_calls: list[dict[str, Any]],
        timeout: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Execute multiple tools in parallel.

        Args:
            tool_calls: List of tool call dicts from LLM
                [{"id": "call_1", "function": {"name": "...", "arguments": "..."}}]
            timeout: Timeout per tool in seconds

        Returns:
            List of results in same order as tool_calls
        """
        import json

        timeout = timeout or self.default_timeout

        # Separate builtin and MCP tools
        builtin_tasks = []
        mcp_tasks = []
        task_mapping = []  # (index, call_id, tool_name)

        for idx, call in enumerate(tool_calls):
            func = call.get("function", {})
            tool_name = func.get("name", "")
            arguments_str = func.get("arguments", "{}")

            try:
                arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
            except json.JSONDecodeError:
                arguments = {}

            task_mapping.append((idx, call.get("id", ""), tool_name))

            if self.builtin_registry.has(tool_name):
                # Builtin tool
                task = self._execute_builtin_wrapper(tool_name, arguments, call.get("id", ""))
                builtin_tasks.append(task)
            else:
                # MCP tool
                task = self._execute_mcp_wrapper(tool_name, arguments, call.get("id", ""), timeout)
                mcp_tasks.append(task)

        # Execute all in parallel
        all_tasks = builtin_tasks + mcp_tasks
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Order results by original index
        ordered_results = [None] * len(tool_calls)
        for (idx, call_id, tool_name), result in zip(task_mapping, results):
            if isinstance(result, Exception):
                ordered_results[idx] = {
                    "tool_call_id": call_id,
                    "content": [{"type": "text", "text": f"Error: {result}"}]
                }
            else:
                ordered_results[idx] = result

        return ordered_results

    async def _execute_builtin(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a builtin tool.

        Args:
            tool_name: Tool name
            arguments: Tool arguments

        Returns:
            Result in MCP format
        """
        from .builtin.result import ToolResult

        try:
            tool = self.builtin_registry.get(tool_name)
            result = await tool.execute(**arguments)
            if isinstance(result, ToolResult):
                return {
                    "content": [{"type": "text", "text": result.to_content()}]
                }
            return {
                "content": [{"type": "text", "text": str(result)}]
            }
        except Exception as e:
            logger.error(f"Error executing builtin tool {tool_name}: {e}")
            return {
                "content": [{"type": "text", "text": f"Error: {e}"}]
            }

    async def _execute_mcp(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: Optional[int] = None,
    ) -> dict[str, Any]:
        """Execute an MCP tool.

        Args:
            tool_name: Tool name
            arguments: Tool arguments
            timeout: Execution timeout

        Returns:
            Result in MCP format
        """
        if not self.manager:
            return {
                "content": [{"type": "text", "text": f"Tool not found: {tool_name}"}]
            }

        try:
            server = await self._find_server_for_tool(tool_name)
            if not server:
                return {
                    "content": [{"type": "text", "text": f"Tool not found: {tool_name}"}]
                }

            result = await asyncio.wait_for(
                self.manager.execute_tool(server, tool_name, arguments),
                timeout=timeout or self.default_timeout,
            )
            return {
                "content": result.get("content", [{"type": "text", "text": str(result)}])
            }
        except asyncio.TimeoutError:
            return {
                "content": [{"type": "text", "text": f"Timeout executing {tool_name}"}]
            }
        except Exception as e:
            logger.error(f"Error executing MCP tool {tool_name}: {e}")
            return {
                "content": [{"type": "text", "text": f"Error: {e}"}]
            }

    async def _find_server_for_tool(self, tool_name: str) -> Optional[str]:
        """Find which MCP server provides this tool.

        Args:
            tool_name: Tool name to find

        Returns:
            Server name or None
        """
        if not self.manager:
            return None

        # Check cache
        if tool_name in self._tool_server_cache:
            return self._tool_server_cache[tool_name]

        # Search all servers
        for server_name in self.manager.servers:
            key = f"{server_name}:{tool_name}"
            if key in self.manager.tools:
                self._tool_server_cache[tool_name] = server_name
                return server_name

        return None

    async def _execute_builtin_wrapper(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        call_id: str,
    ) -> dict[str, Any]:
        """Wrapper for builtin tool execution in batch.

        Args:
            tool_name: Tool name
            arguments: Tool arguments
            call_id: Tool call ID

        Returns:
            Result with tool_call_id
        """
        result = await self._execute_builtin(tool_name, arguments)
        result["tool_call_id"] = call_id
        return result

    async def _execute_mcp_wrapper(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        call_id: str,
        timeout: Optional[int],
    ) -> dict[str, Any]:
        """Wrapper for MCP tool execution in batch.

        Args:
            tool_name: Tool name
            arguments: Tool arguments
            call_id: Tool call ID
            timeout: Execution timeout

        Returns:
            Result with tool_call_id
        """
        result = await self._execute_mcp(tool_name, arguments, timeout)
        result["tool_call_id"] = call_id
        return result

    # Legacy methods for backward compatibility

    async def execute_with_fallback(
        self,
        server: str,
        tool_name: str,
        arguments: dict[str, Any],
        fallback_tools: list[tuple[str, str]],
        timeout: Optional[int] = None,
    ) -> dict[str, Any]:
        """Execute a tool with fallback options (legacy MCP-only method).

        Args:
            server: Server name
            tool_name: Tool name
            arguments: Tool arguments
            fallback_tools: List of (server, tool_name) fallbacks
            timeout: Timeout in seconds

        Returns:
            Tool result

        Raises:
            RuntimeError: If all attempts fail
        """
        if not self.manager:
            raise RuntimeError(f"Cannot execute MCP tool: no MCP manager configured")

        attempts = [(server, tool_name)] + fallback_tools

        for attempt_server, attempt_tool in attempts:
            try:
                logger.debug(f"Attempting tool: {attempt_server}:{attempt_tool}")
                result = await asyncio.wait_for(
                    self.manager.execute_tool(attempt_server, attempt_tool, arguments),
                    timeout=timeout or self.default_timeout,
                )
                return result
            except (TimeoutError, RuntimeError) as e:
                logger.warning(f"Tool attempt failed: {attempt_server}:{attempt_tool} - {e}")
                continue

        raise RuntimeError(f"All tool execution attempts failed: {server}:{tool_name}")

"""MCP (Model Context Protocol) client for multi-agent framework.

This module provides MCP protocol client implementations for stdio and SSE transports.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Optional

import aiohttp
from pydantic import BaseModel

from ..models import MCPServer, MCPServerConfigSSE, MCPServerConfigStdio
from ..utils.logging import get_logger

logger = get_logger(__name__)


class MCPMessage(BaseModel):
    """MCP protocol message.

    Attributes:
        jsonrpc: JSON-RPC version (always "2.0")
        id: Request ID
        method: Method name
        params: Method parameters
        result: Result (for responses)
        error: Error (for error responses)
    """

    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str | None = None
    params: dict[str, Any] | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None


class MCPTransport(ABC):
    """Abstract base class for MCP transports."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to MCP server."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to MCP server."""

    @abstractmethod
    async def send_message(self, message: MCPMessage) -> MCPMessage:
        """Send a message and receive response.

        Args:
            message: Message to send

        Returns:
            Response message
        """

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is connected.

        Returns:
            True if connected
        """


class MCPStdioTransport(MCPTransport):
    """MCP stdio transport using subprocess.

    Communicates with MCP server via standard input/output.
    """

    def __init__(self, config: MCPServerConfigStdio, server_name: str) -> None:
        """Initialize the stdio transport.

        Args:
            config: Stdio configuration
            server_name: Server name for logging
        """
        self.config = config
        self.server_name = server_name
        self.process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._read_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Start the MCP server subprocess."""
        logger.info(f"Connecting to MCP server '{self.server_name}' via stdio")

        # Prepare environment
        env = self.config.env.copy()
        import os

        env.update(os.environ)

        # Start subprocess
        self.process = await asyncio.create_subprocess_exec(
            self.config.command,
            *self.config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Start reading messages
        self._read_task = asyncio.create_task(self._read_messages())

        # Send initialize request
        await self._initialize()

    async def disconnect(self) -> None:
        """Stop the MCP server subprocess."""
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()

        # Cancel pending requests
        for future in self._pending_requests.values():
            future.cancel()
        self._pending_requests.clear()

    async def send_message(self, message: MCPMessage) -> MCPMessage:
        """Send a message and wait for response.

        Args:
            message: Message to send

        Returns:
            Response message
        """
        if not self.process or not self.process.stdin:
            raise RuntimeError("Not connected to MCP server")

        # Generate request ID
        self._request_id += 1
        request_id = self._request_id
        message.id = request_id

        # Create future for response
        future: asyncio.Future = asyncio.Future()
        self._pending_requests[request_id] = future

        # Send message
        data = message.model_dump_json(exclude_none=True)
        self.process.stdin.write((data + "\n").encode())
        await self.process.stdin.drain()

        # Wait for response
        try:
            response_data = await asyncio.wait_for(future, timeout=30.0)
            return MCPMessage(**response_data)
        except asyncio.TimeoutError:
            del self._pending_requests[request_id]
            raise TimeoutError(f"MCP request timed out: {message.method}")

    def is_connected(self) -> bool:
        """Check if connected.

        Returns:
            True if process is running
        """
        return self.process is not None and self.process.returncode is None

    async def _initialize(self) -> None:
        """Send initialize request."""
        init_message = MCPMessage(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "multi-agent-framework",
                    "version": "0.1.0",
                },
            },
        )
        await self.send_message(init_message)

        # Send initialized notification
        initialized_message = MCPMessage(method="notifications/initialized")
        await self._send_notification(initialized_message)

    async def _send_notification(self, message: MCPMessage) -> None:
        """Send a notification (no response expected).

        Args:
            message: Notification message
        """
        if not self.process or not self.process.stdin:
            raise RuntimeError("Not connected to MCP server")

        data = message.model_dump_json(exclude_none=True)
        self.process.stdin.write((data + "\n").encode())
        await self.process.stdin.drain()

    async def _read_messages(self) -> None:
        """Read messages from stdout."""
        if not self.process or not self.process.stdout:
            return

        while True:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break

                data = json.loads(line.decode())
                message = MCPMessage(**data)

                # Handle response
                if message.id is not None and message.id in self._pending_requests:
                    future = self._pending_requests.pop(message.id)
                    if not future.cancelled():
                        future.set_result(message.model_dump())

            except Exception as e:
                logger.error(f"Error reading MCP message: {e}")
                break


class MCPSSETransport(MCPTransport):
    """MCP SSE transport using HTTP Server-Sent Events.

    Communicates with MCP server via SSE HTTP endpoint.
    """

    def __init__(self, config: MCPServerConfigSSE, server_name: str) -> None:
        """Initialize the SSE transport.

        Args:
            config: SSE configuration
            server_name: Server name for logging
        """
        self.config = config
        self.server_name = server_name
        self.session: aiohttp.ClientSession | None = None
        self._request_id = 0
        self._connected = False

    async def connect(self) -> None:
        """Connect to SSE endpoint."""
        logger.info(f"Connecting to MCP server '{self.server_name}' via SSE at {self.config.url}")

        self.session = aiohttp.ClientSession()

        # Initialize connection
        init_message = MCPMessage(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "multi-agent-framework",
                    "version": "0.1.0",
                },
            },
        )
        await self.send_message(init_message)

        self._connected = True

    async def disconnect(self) -> None:
        """Close SSE connection."""
        if self.session:
            await self.session.close()
        self._connected = False

    async def send_message(self, message: MCPMessage) -> MCPMessage:
        """Send a message via HTTP POST.

        Args:
            message: Message to send

        Returns:
            Response message
        """
        if not self.session or not self._connected:
            raise RuntimeError("Not connected to MCP server")

        # Generate request ID
        self._request_id += 1
        message.id = self._request_id

        # Prepare headers
        headers = {"Content-Type": "application/json"}
        headers.update(self.config.headers)

        # Send POST request
        data = message.model_dump_json(exclude_none=True)
        try:
            async with self.session.post(
                self.config.url,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30.0),
            ) as response:
                response_data = await response.json()
                return MCPMessage(**response_data)
        except asyncio.TimeoutError:
            raise TimeoutError(f"MCP request timed out: {message.method}")

    def is_connected(self) -> bool:
        """Check if connected.

        Returns:
            True if session is active
        """
        return self._connected and self.session is not None and not self.session.closed


def create_mcp_transport(server: MCPServer) -> MCPTransport:
    """Create MCP transport for a server configuration.

    Args:
        server: MCP server configuration

    Returns:
        MCP transport instance

    Raises:
        ValueError: If transport type is unsupported
    """
    if server.is_stdio:
        return MCPStdioTransport(server.config, server.name)  # type: ignore
    elif server.is_sse:
        return MCPSSETransport(server.config, server.name)  # type: ignore
    else:
        raise ValueError(f"Unsupported transport type: {server.transport}")

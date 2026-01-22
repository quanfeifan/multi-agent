"""MCP (Model Context Protocol) client for multi-agent framework.

This module provides MCP protocol client implementations for stdio and SSE transports.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Optional

import aiohttp
from pydantic import BaseModel

from ..models import MCPServer, MCPServerConfigSSE, MCPServerConfigStdio, MCPServerConfigStreamableHTTP
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
            except Exception:
                pass  # Ignore errors during cleanup

        if self.process:
            # Close stdin/stdout/stderr before terminating
            try:
                if self.process.stdin and not self.process.stdin.is_closing():
                    self.process.stdin.close()
            except Exception:
                pass  # Ignore errors during cleanup

            try:
                if self.process.stdout and not self.process.stdout.is_closing():
                    self.process.stdout.close()
            except Exception:
                pass

            try:
                if self.process.stderr and not self.process.stderr.is_closing():
                    self.process.stderr.close()
            except Exception:
                pass

            # Terminate the process
            try:
                if self.process.returncode is None:  # Only if still running
                    self.process.terminate()
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                try:
                    self.process.kill()
                    await self.process.wait()
                except Exception:
                    pass
            except Exception:
                pass

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
    Supports two modes:
    - POST-based: Standard JSON-RPC over HTTP POST (MCP spec)
    - SSE-based: GET for connection + POST for messages, responses via SSE stream (Zhipu style)
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
        self._use_sse_mode = False  # Will be detected during connect
        self._message_endpoint: str | None = None  # Dynamic endpoint for SSE mode
        self._sse_response: aiohttp.ClientResponse | None = None  # Keep SSE connection open
        self._sse_read_task: asyncio.Task | None = None  # Task to read SSE stream
        self._pending_requests: dict[int, asyncio.Future] = {}  # Pending requests for SSE mode
        self._sse_stream_active: bool = False  # Track if SSE stream is still active

    async def connect(self) -> None:
        """Connect to SSE endpoint."""
        logger.info(f"Connecting to MCP server '{self.server_name}' via SSE at {self.config.url}")

        self.session = aiohttp.ClientSession()

        # Try to detect which mode the server supports
        # First try POST (standard MCP over HTTP)
        try:
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
            await self._send_post(init_message)
            self._use_sse_mode = False
            self._connected = True
            logger.info(f"Connected to '{self.server_name}' using POST mode")
        except Exception as e:
            logger.debug(f"POST mode failed: {e}, trying SSE mode...")
            # Try SSE mode (GET for connection + keep alive for responses)
            try:
                await self._send_get_init()
                self._use_sse_mode = True
                # Start listening for SSE responses in background
                self._sse_read_task = asyncio.create_task(self._read_sse_stream())
                # Now send the initialize request to the message endpoint
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
                await self._send_post_to_sse_endpoint(init_message)
                self._connected = True
                logger.info(f"Connected to '{self.server_name}' using SSE mode")
            except Exception as e2:
                logger.error(f"SSE mode also failed: {e2}")
                raise RuntimeError(f"Failed to connect to MCP server: {e2}")

    async def disconnect(self) -> None:
        """Close SSE connection."""
        # Cancel SSE read task
        if self._sse_read_task:
            self._sse_read_task.cancel()
            try:
                await self._sse_read_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass  # Ignore errors during cleanup

        # Close SSE response
        if self._sse_response:
            try:
                self._sse_response.close()
            except Exception:
                pass  # Ignore errors during cleanup

        # Close session
        if self.session:
            await self.session.close()

        # Cancel pending requests
        for future in self._pending_requests.values():
            future.cancel()
        self._pending_requests.clear()

        self._connected = False

    async def send_message(self, message: MCPMessage) -> MCPMessage:
        """Send a message.

        Args:
            message: Message to send

        Returns:
            Response message
        """
        if not self.session or not self._connected:
            raise RuntimeError("Not connected to MCP server")

        if self._use_sse_mode:
            return await self._send_post_to_sse_endpoint(message)
        else:
            return await self._send_post(message)

    async def _send_post(self, message: MCPMessage) -> MCPMessage:
        """Send message via HTTP POST.

        Args:
            message: Message to send

        Returns:
            Response message
        """
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
                text = await response.text()
                response_data = json.loads(text) if text.strip() else {}
                return MCPMessage(**response_data)
        except asyncio.TimeoutError:
            raise TimeoutError(f"MCP request timed out: {message.method}")

    async def _send_get_init(self) -> None:
        """Send GET request to establish SSE connection (for SSE mode servers like Zhipu).

        This is used for servers that require GET to establish SSE connection.
        Parses SSE response to extract the message endpoint URL.
        Keeps the SSE connection open for reading responses.
        """
        headers = self.config.headers.copy()

        # Don't use async with - we need to keep the connection open
        response = await self.session.get(
            self.config.url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=300.0, sock_connect=10.0, sock_read=300.0),
        )

        if response.status != 200:
            text = await response.text()
            await response.close()
            raise RuntimeError(f"SSE connection failed: {response.status} - {text}")

        # Store the response for later reading
        self._sse_response = response

        # SSE is a streaming protocol - read initial content only
        # Expected format: "event:endpoint\ndata:/api/mcp/wikipedia/message?sessionId=xxx\n\n"
        content = await asyncio.wait_for(response.content.read(1024), timeout=5.0)
        text = content.decode('utf-8', errors='ignore')
        logger.debug(f"SSE response text: {text[:200]}")

        # Look for the data field containing the endpoint URL
        for line in text.split('\n'):
            if line.startswith('data:'):
                endpoint_path = line[5:].strip()
                logger.debug(f"Found data line: {endpoint_path[:100]}")
                # Construct full URL from the path
                if endpoint_path.startswith('/'):
                    # Extract base URL from config
                    from urllib.parse import urlparse
                    parsed = urlparse(self.config.url)
                    base_url = f"{parsed.scheme}://{parsed.netloc}"
                    self._message_endpoint = base_url + endpoint_path
                else:
                    self._message_endpoint = endpoint_path
                logger.info(f"Extracted message endpoint: {self._message_endpoint}")
                break

        if not self._message_endpoint:
            logger.error(f"Could not extract endpoint from SSE response. Response: {text[:500]}")
            await response.close()
            raise RuntimeError(f"Failed to extract message endpoint from SSE response. Response: {text[:200]}")

    async def _send_post_to_sse_endpoint(self, message: MCPMessage) -> MCPMessage:
        """Send message to SSE endpoint via POST (for SSE mode servers).

        The response will come through the SSE stream, not as the HTTP response.
        This method sends the POST request and waits for the response via the SSE stream.

        Args:
            message: Message to send

        Returns:
            Response message
        """
        # Ensure SSE connection is active before sending
        await self._ensure_sse_connection()

        # Use the extracted message endpoint URL
        if not self._message_endpoint:
            raise RuntimeError("Message endpoint not available - connection may not be properly initialized")

        # Generate request ID
        self._request_id += 1
        request_id = self._request_id
        message.id = request_id

        # Create a future for the response
        future: asyncio.Future = asyncio.Future()
        self._pending_requests[request_id] = future

        # Prepare headers
        headers = {"Content-Type": "application/json"}
        headers.update(self.config.headers)

        # Send POST request to the message endpoint (fire and forget - response comes via SSE)
        data = message.model_dump_json(exclude_none=True)
        logger.debug(f"Sending to {self._message_endpoint}: {data[:200]}")
        try:
            async with self.session.post(
                self._message_endpoint,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10.0),
            ) as response:
                # For SSE mode, the HTTP response is usually empty - the real response comes via SSE stream
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"POST request failed: {response.status} - {text}")
                    del self._pending_requests[request_id]
                    future.cancel()
                    raise RuntimeError(f"POST request failed: {response.status} - {text}")
                logger.debug(f"POST request sent, status: {response.status}")
        except asyncio.TimeoutError:
            del self._pending_requests[request_id]
            future.cancel()
            raise TimeoutError(f"MCP POST request timed out: {message.method}")

        # Wait for response via SSE stream
        try:
            response_data = await asyncio.wait_for(future, timeout=30.0)
            return MCPMessage(**response_data)
        except asyncio.TimeoutError:
            del self._pending_requests[request_id]
            raise TimeoutError(f"MCP request timed out waiting for SSE response: {message.method}")

    async def _ensure_sse_connection(self) -> None:
        """Ensure SSE connection is active, reconnect if needed.

        This checks if the SSE stream reader is still running and reconnects if it has stopped.
        Only reconnects if we had an established connection before (i.e., _sse_read_task exists).
        """
        # Only check if we've had a connection before
        if self._sse_read_task is not None:
            if self._sse_read_task.done() or not self._sse_stream_active:
                logger.debug("SSE connection inactive, reconnecting...")
                # Close existing connection if any
                if self._sse_response:
                    try:
                        self._sse_response.close()
                    except Exception:
                        pass
                if self._sse_read_task and not self._sse_read_task.done():
                    self._sse_read_task.cancel()
                    try:
                        await self._sse_read_task
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        pass

                # Re-establish SSE connection
                await self._send_get_init()
                self._sse_read_task = asyncio.create_task(self._read_sse_stream())
                logger.debug("SSE connection re-established")

    async def _read_sse_stream(self) -> None:
        """Read SSE stream and dispatch responses to pending requests.

        This runs in a background task and keeps reading from the SSE connection.
        When a response arrives, it matches the request ID and delivers it to the waiting future.
        """
        if not self._sse_response:
            logger.error("SSE response not available for reading")
            return

        logger.debug("Starting SSE stream reader")
        self._sse_stream_active = True
        buffer = ""

        try:
            async for chunk in self._sse_response.content:
                # Decode chunk
                chunk_text = chunk.decode("utf-8", errors="ignore")
                buffer += chunk_text

                # Process buffer for complete SSE events
                # SSE format: "event: xxx\ndata: {...}\n\n"
                while '\n\n' in buffer:
                    # Extract one complete event
                    event_text, buffer = buffer.split('\n\n', 1)

                    # Parse the event
                    lines = event_text.split('\n')
                    event_type = "message"
                    data_json = None

                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue

                        if line.startswith('event:'):
                            event_type = line[6:].strip()
                        elif line.startswith('data:'):
                            json_str = line[5:].strip()
                            if json_str:
                                try:
                                    data_json = json.loads(json_str)
                                except json.JSONDecodeError:
                                    pass  # Skip invalid JSON

                    # If we have data, dispatch to pending request
                    if data_json:
                        response_id = data_json.get('id')
                        if response_id is not None and response_id in self._pending_requests:
                            future = self._pending_requests.pop(response_id)
                            if not future.cancelled():
                                future.set_result(data_json)

        except asyncio.CancelledError:
            logger.debug("SSE stream reader cancelled")
        except Exception as e:
            logger.error(f"Error reading SSE stream: {e}", exc_info=True)
        finally:
            self._sse_stream_active = False
            logger.debug("SSE stream reader ended")

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
    elif server.is_streamable_http:
        # Import here to avoid circular dependency
        from .mcp_streamable_http import MCPStreamableHTTPTransport
        return MCPStreamableHTTPTransport(server.config, server.name)  # type: ignore
    else:
        raise ValueError(f"Unsupported transport type: {server.transport}")

"""Streamable HTTP transport for MCP (Model Context Protocol) client.

This module provides MCP protocol client implementation for Streamable HTTP transport.
Streamable HTTP is the modern standard for remote MCP servers (March 2025+), replacing
the legacy HTTP+SSE transport. It uses a unified /message endpoint with support for both
simple HTTP responses and SSE streaming responses.

Key features:
- Unified /message endpoint for all communications
- Support for simple HTTP 200 responses
- Support for SSE streaming responses with event aggregation
- Session ID management for stateful conversations
- Retry logic with exponential backoff
- 2-minute timeout for SSE streams
- Automatic re-initialization on session expiration (HTTP 410)
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp

from .mcp_client import MCPMessage
from ..models import MCPServerConfigStreamableHTTP
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SSEEvent:
    """Represents a single Server-Sent Event from a streaming response.

    Attributes:
        event_type: Event type (message, end, error)
        data: Parsed JSON data from event
        raw_data: Raw data string before parsing
        timestamp: When event was received
    """

    event_type: str
    data: dict[str, Any]
    raw_data: str
    timestamp: datetime

    @classmethod
    def parse(cls, raw_line: str) -> "SSEEvent":
        """Parse an SSE line into an SSEEvent.

        Args:
            raw_line: Raw SSE line (e.g., "event: message" or "data: {...}")

        Returns:
            Parsed SSEEvent
        """
        timestamp = datetime.now()
        event_type = "message"  # Default event type
        data = {}
        raw_data = ""

        # Strip whitespace and handle multi-line input
        raw_line = raw_line.strip()

        # Split by newlines to handle multi-line SSE format
        lines = raw_line.split('\n') if '\n' in raw_line else [raw_line]

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Parse event type
            if line.startswith("event:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    event_type = parts[1].strip()

            # Parse data
            elif line.startswith("data:"):
                raw_data = line[5:].strip()
                if raw_data:
                    try:
                        data = json.loads(raw_data)
                    except json.JSONDecodeError:
                        data = {"raw": raw_data}

        return cls(
            event_type=event_type,
            data=data,
            raw_data=raw_data,
            timestamp=timestamp,
        )


class SSEEventAggregator:
    """Aggregates SSE events into complete tool results.

    Handles end-of-stream detection and timeout enforcement.
    """

    def __init__(self, stream_timeout: int = 120) -> None:
        """Initialize the aggregator.

        Args:
            stream_timeout: Maximum time to wait for stream completion in seconds
        """
        self.stream_timeout = stream_timeout

    async def aggregate_sse_stream(
        self,
        response: aiohttp.ClientResponse,
    ) -> dict[str, Any]:
        """Aggregate SSE events from a streaming response.

        Args:
            response: aiohttp response object

        Returns:
            Aggregated result from all events

        Raises:
            TimeoutError: If stream exceeds timeout
            RuntimeError: If error event received
        """
        events = []
        start_time = datetime.now()

        # State for building events from multiple lines
        current_event_type = "message"
        current_data = {}
        event_pending = False
        stream_ended = False

        try:
            async for chunk in response.content:
                # Check timeout
                if (datetime.now() - start_time).total_seconds() > self.stream_timeout:
                    raise TimeoutError(f"SSE stream timeout after {self.stream_timeout} seconds")

                # Decode and split chunk into individual lines
                chunk_text = chunk.decode("utf-8", errors="ignore")
                for line in chunk_text.split('\n'):
                    line = line.strip()
                    if not line:
                        # Empty line marks end of current event
                        if event_pending:
                            event = SSEEvent(
                                event_type=current_event_type,
                                data=current_data,
                                raw_data="",
                                timestamp=datetime.now()
                            )
                            events.append(event)

                            # Check if this was an end or error event
                            if current_event_type == "end":
                                logger.debug("SSE end marker received")
                                stream_ended = True
                                break
                            elif current_event_type == "error":
                                error_msg = current_data.get("message", "Unknown SSE error")
                                raise RuntimeError(f"SSE error event: {error_msg}")

                            # Reset for next event
                            current_event_type = "message"
                            current_data = {}
                            event_pending = False
                        continue

                    # Parse SSE line
                    if line.startswith("event:"):
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            current_event_type = parts[1].strip()
                        event_pending = True
                    elif line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str:
                            try:
                                current_data = json.loads(data_str)
                            except json.JSONDecodeError:
                                current_data = {"raw": data_str}
                        event_pending = True

                # Break outer loop if end was reached
                if stream_ended:
                    break

        except asyncio.TimeoutError:
            raise TimeoutError(f"SSE stream read timeout after {self.stream_timeout} seconds")

        # Add any pending event
        if event_pending and not stream_ended:
            event = SSEEvent(
                event_type=current_event_type,
                data=current_data,
                raw_data="",
                timestamp=datetime.now()
            )
            events.append(event)

        # Merge events into single result
        return self._merge_events(events)

    def _parse_sse_line(self, line: str) -> tuple[str, dict[str, Any]]:
        """Parse a single SSE line into event type and data.

        Args:
            line: Raw SSE line

        Returns:
            Tuple of (event_type, data)
        """
        event_type = "message"
        data = {}

        # Strip and handle multi-line input
        line = line.strip()
        lines = line.split('\n') if '\n' in line else [line]

        for l in lines:
            l = l.strip()
            if not l:
                continue

            if l.startswith("event:"):
                parts = l.split(":", 1)
                if len(parts) == 2:
                    event_type = parts[1].strip()
            elif l.startswith("data:"):
                data_str = l[5:].strip()
                if data_str:
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        data = {"raw": data_str}

        return event_type, data

    def _detect_end_of_stream(self, events: list[SSEEvent]) -> bool:
        """Detect if we've reached end of stream.

        Args:
            events: List of received events

        Returns:
            True if end of stream detected
        """
        if not events:
            return False

        # Check for end event
        for event in events:
            if event.event_type == "end":
                return True

        # Check for done flag in data
        if events[-1].data.get("done") is True:
            return True

        return False

    def _merge_events(self, events: list[SSEEvent]) -> dict[str, Any]:
        """Merge multiple SSE events into a single result.

        Args:
            events: List of SSE events

        Returns:
            Merged result dictionary
        """
        if not events:
            return {}

        # Filter for message events only
        message_events = [e for e in events if e.event_type == "message"]

        if not message_events:
            return {}

        # If only one message event, return its data directly
        if len(message_events) == 1:
            return message_events[0].data

        # Multiple events - merge content arrays
        result = message_events[0].data
        if "result" in result and isinstance(result["result"], dict):
            content_list = result["result"].get("content", [])
            if not isinstance(content_list, list):
                content_list = [content_list]

            # Collect content from all events
            all_content = []
            for event in message_events[1:]:
                event_content = event.data.get("result", {}).get("content", [])
                if isinstance(event_content, list):
                    all_content.extend(event_content)

            # Update content list
            result["result"]["content"] = content_list + all_content

        return result


@dataclass
class StreamableHTTPSession:
    """Represents an active session with a Streamable HTTP MCP server.

    Attributes:
        session_id: Unique session identifier from server
        server_url: URL of the MCP server
        created_at: Timestamp when session was created
        last_used: Timestamp of last request using this session
        request_count: Number of requests made using this session
    """

    session_id: str
    server_url: str
    created_at: datetime
    last_used: datetime
    request_count: int = 0

    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if session has expired.

        Args:
            ttl_seconds: Session TTL in seconds

        Returns:
            True if session has expired
        """
        age = (datetime.now() - self.last_used).total_seconds()
        return age > ttl_seconds

    def touch(self) -> None:
        """Update last_used timestamp and increment request count."""
        self.last_used = datetime.now()
        self.request_count += 1


class SessionStore:
    """Manages session storage for Streamable HTTP MCP servers.

    Thread-safe in-memory storage with cleanup support.
    """

    def __init__(self) -> None:
        """Initialize the session store."""
        self._sessions: dict[str, StreamableHTTPSession] = {}
        self._lock = asyncio.Lock()

    async def get(self, session_id: str) -> StreamableHTTPSession | None:
        """Get a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session if found, None otherwise
        """
        async with self._lock:
            return self._sessions.get(session_id)

    async def set(self, session: StreamableHTTPSession) -> None:
        """Store a session.

        Args:
            session: Session to store
        """
        async with self._lock:
            self._sessions[session.session_id] = session

    async def delete(self, session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: Session identifier
        """
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def cleanup_expired(self, ttl_seconds: int) -> int:
        """Remove expired sessions.

        Args:
            ttl_seconds: Session TTL in seconds

        Returns:
            Number of sessions removed
        """
        async with self._lock:
            expired = [
                sid
                for sid, sess in self._sessions.items()
                if sess.is_expired(ttl_seconds)
            ]
            for sid in expired:
                del self._sessions[sid]
            return len(expired)

    async def get_all(self) -> list[StreamableHTTPSession]:
        """Get all sessions.

        Returns:
            List of all sessions
        """
        async with self._lock:
            return list(self._sessions.values())


class MCPStreamableHTTPTransport:
    """MCP Streamable HTTP transport implementation.

    Uses the modern Streamable HTTP protocol (March 2025+) for remote MCP servers.
    Supports both simple HTTP responses and SSE streaming responses.

    Key features:
    - Unified /message endpoint for all communications
    - Session ID management for stateful conversations
    - Automatic re-initialization on session expiration
    - Retry logic with exponential backoff
    - 2-minute timeout for SSE streams
    """

    def __init__(
        self,
        config: MCPServerConfigStreamableHTTP,
        server_name: str,
    ) -> None:
        """Initialize the Streamable HTTP transport.

        Args:
            config: Streamable HTTP configuration
            server_name: Server name for logging
        """
        self.config = config
        self.server_name = server_name
        self.session: aiohttp.ClientSession | None = None
        self._session_store = SessionStore()
        self._current_session_id: str | None = None
        self._request_id = 0
        self._connected = False

    async def connect(self) -> None:
        """Connect to Streamable HTTP endpoint and initialize session.

        Sends initialize request and establishes session if server supports it.
        """
        logger.info(f"Connecting to MCP server '{self.server_name}' via Streamable HTTP at {self.config.url}")

        self.session = aiohttp.ClientSession()

        # Send initialize request
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

        try:
            response = await self._send_post_request(init_message)
            # Extract session ID if returned
            self._extract_session_id(response)

            self._connected = True
            logger.info(f"Connected to '{self.server_name}' via Streamable HTTP")
        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{self.server_name}': {e}")
            raise

    async def disconnect(self) -> None:
        """Close connection and cleanup sessions.

        Cleans up expired sessions before closing.
        """
        if self.session:
            await self.session.close()

        # Cleanup expired sessions
        await self._session_store.cleanup_expired(self.config.session_ttl)

        self._connected = False
        logger.info(f"Disconnected from '{self.server_name}'")

    async def send_message(self, message: MCPMessage) -> MCPMessage:
        """Send a message via Streamable HTTP.

        Handles:
        - Simple HTTP responses
        - SSE streaming responses
        - Session ID management
        - Retry logic for transient errors
        - Automatic re-initialization on HTTP 410

        Args:
            message: Message to send

        Returns:
            Response message

        Raises:
            RuntimeError: If not connected
            TimeoutError: If request times out
        """
        if not self.session or not self._connected:
            raise RuntimeError(f"Not connected to MCP server '{self.server_name}'")

        max_attempts = self.config.retry_max_attempts + 1  # +1 for initial attempt
        base_delay = self.config.retry_base_delay

        for attempt in range(max_attempts):
            try:
                response = await self._send_post_request(message)

                # Check for session expiration (HTTP 410)
                if response.error and response.error.get("code") == 410:
                    logger.info(f"Session expired for '{self.server_name}', re-initializing...")

                    # Clear current session
                    self._current_session_id = None

                    # Re-connect
                    await self.connect()

                    # Retry the request once
                    response = await self._send_post_request(message)

                return response

            except (asyncio.TimeoutError, TimeoutError) as e:
                if attempt < max_attempts - 1:
                    delay = min(base_delay * (2**attempt), 60.0)
                    logger.warning(
                        f"Request to '{self.server_name}' timed out (attempt {attempt + 1}/{max_attempts}), "
                        f"retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise TimeoutError(f"Request to '{self.server_name}' timed out after {max_attempts} attempts")

            except aiohttp.ClientResponseError as e:
                # Handle HTTP status codes
                if hasattr(e, "status") and e.status:
                    # Rate limited (429)
                    if e.status == 429:
                        retry_after = self._extract_retry_after(e)
                        if attempt < max_attempts - 1 and retry_after is not None:
                            logger.warning(f"Rate limited by '{self.server_name}', waiting {retry_after}s...")
                            await asyncio.sleep(retry_after)
                            continue
                        elif attempt < max_attempts - 1:
                            delay = min(base_delay * (2**attempt), 60.0)
                            logger.warning(f"Rate limited, retrying in {delay}s...")
                            await asyncio.sleep(delay)
                            continue

                    # Unauthorized (401)
                    elif e.status == 401:
                        logger.error(f"Authentication failed for '{self.server_name}'")
                        raise RuntimeError(f"Authentication failed for '{self.server_name}'")

                    # Request timeout (408)
                    elif e.status == 408:
                        if attempt < max_attempts - 1:
                            delay = min(base_delay * (2**attempt), 60.0)
                            logger.warning(f"Request timeout (attempt {attempt + 1}/{max_attempts}), retrying...")
                            await asyncio.sleep(delay)
                            continue

                # Other errors - raise
                if attempt == max_attempts - 1:
                    raise RuntimeError(f"HTTP error {e.status} for '{self.server_name}': {e}")
                logger.warning(f"HTTP error for '{self.server_name}' (attempt {attempt + 1}/{max_attempts}): {e}")
                await asyncio.sleep(base_delay)
                continue

            except Exception as e:
                if attempt == max_attempts - 1:
                    raise RuntimeError(f"Error sending to '{self.server_name}': {e}")
                logger.warning(f"Error for '{self.server_name}' (attempt {attempt + 1}/{max_attempts}): {e}")
                await asyncio.sleep(base_delay)
                continue

        raise RuntimeError(f"Failed to send message to '{self.server_name}' after {max_attempts} attempts")

    def is_connected(self) -> bool:
        """Check if connected.

        Returns:
            True if session is active
        """
        return self._connected and self.session is not None and not self.session.closed

    async def _send_post_request(
        self,
        message: MCPMessage,
    ) -> MCPMessage:
        """Send HTTP POST request to /message endpoint.

        Args:
            message: Message to send

        Returns:
            Response message

        Raises:
            RuntimeError: If session not available
            TimeoutError: If request times out
        """
        if not self.session:
            raise RuntimeError("Session not available")

        # Generate request ID
        self._request_id += 1
        message.id = self._request_id

        # Prepare headers
        headers = {"Content-Type": "application/json"}
        headers.update(self.config.headers)

        # Add session ID if available
        if self._current_session_id:
            headers["X-Session-ID"] = self._current_session_id

        # Send POST request
        data = message.model_dump_json(exclude_none=True)
        logger.debug(f"Sending to {self.config.url}: {data[:200]}")

        try:
            async with self.session.post(
                self.config.url,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(
                    total=self.config.timeout,
                    sock_read=self.config.timeout,
                ),
            ) as response:
                # Check content type for streaming
                content_type = response.headers.get("Content-Type", "")

                if "text/event-stream" in content_type:
                    # Handle SSE streaming response
                    result = await self._handle_streaming_response(response)
                else:
                    # Handle simple HTTP response
                    result = await self._handle_simple_response(response)

                # Extract session ID from response headers
                self._extract_session_id_from_response(response)

                return MCPMessage(**result)

        except asyncio.TimeoutError:
            raise TimeoutError(f"Request to '{self.server_name}' timed out after {self.config.timeout} seconds")

    async def _handle_simple_response(
        self,
        response: aiohttp.ClientResponse,
    ) -> dict[str, Any]:
        """Handle simple HTTP 200 response.

        Args:
            response: aiohttp response object

        Returns:
            Response data dictionary
        """
        text = await response.text()

        if not text.strip():
            return {}

        try:
            return json.loads(text) if text.strip() else {}
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON response: {text[:200]}")
            return {"raw": text}

    async def _handle_streaming_response(
        self,
        response: aiohttp.ClientResponse,
    ) -> dict[str, Any]:
        """Handle SSE streaming response.

        Args:
            response: aiohttp response object

        Returns:
            Aggregated result from all SSE events

        Raises:
            TimeoutError: If stream timeout
        """
        aggregator = SSEEventAggregator(stream_timeout=120)  # 2 minutes
        result = await aggregator.aggregate_sse_stream(response)
        return result

    def _extract_session_id(self, response: MCPMessage) -> None:
        """Extract session ID from response message.

        Args:
            response: Response message
        """
        # Session IDs are typically in response headers, not in the JSON-RPC body
        # This is a placeholder for header-based extraction
        pass

    def _extract_session_id_from_response(
        self,
        response: aiohttp.ClientResponse,
    ) -> None:
        """Extract session ID from HTTP response headers.

        Args:
            response: aiohttp response object
        """
        session_id = response.headers.get("X-Session-ID")
        if session_id:
            self._current_session_id = session_id
            logger.debug(f"Received session ID: {session_id[:20]}...")

            # Store session
            session = StreamableHTTPSession(
                session_id=session_id,
                server_url=self.config.url,
                created_at=datetime.now(),
                last_used=datetime.now(),
                request_count=1,
            )
            asyncio.create_task(self._session_store.set(session))

    def _extract_retry_after(self, error: aiohttp.ClientResponseError) -> float | None:
        """Extract Retry-After delay from rate limit error.

        Args:
            error: ClientResponseError

        Returns:
            Retry delay in seconds, or None if not specified
        """
        headers = getattr(error, "headers", {})
        retry_after = headers.get("Retry-After")

        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                return None
        return None

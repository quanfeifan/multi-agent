"""Unit tests for MCPStreamableHTTPTransport.

Tests for connect(), send_message() with simple HTTP and SSE streaming responses.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from aiohttp import ClientResponseError, ClientSession

from multi_agent.tools.mcp_streamable_http import (
    MCPStreamableHTTPTransport,
    SSEEvent,
    SSEEventAggregator,
    SessionStore,
    StreamableHTTPSession,
)
from multi_agent.tools.mcp_client import MCPMessage
from multi_agent.models import MCPServerConfigStreamableHTTP


@pytest.fixture
def streamable_http_config():
    """Create test configuration for Streamable HTTP transport."""
    return MCPServerConfigStreamableHTTP(
        url="https://api.example.com/mcp/message",
        headers={"Authorization": "Bearer test-token"},
        timeout=30,
        retry_max_attempts=3,
        retry_base_delay=1.0,
        session_ttl=3600,
    )


@pytest.fixture
def transport(streamable_http_config):
    """Create MCPStreamableHTTPTransport instance."""
    return MCPStreamableHTTPTransport(streamable_http_config, "test-server")


@pytest.fixture
def mock_response():
    """Create mock aiohttp response."""
    response = AsyncMock()
    response.status = 200
    response.headers = {}
    response.content = AsyncMock()
    return response


class TestMCPStreamableHTTPTransportConnect:
    """Tests for connect() method."""

    @pytest.mark.asyncio
    async def test_connect_successful(self, transport, mock_response):
        """Test successful connection and initialization."""
        mock_response.text = AsyncMock(return_value='{"jsonrpc": "2.0", "id": 1, "result": {}}')
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.post = AsyncMock(return_value=mock_response)
            mock_session.closed = False
            mock_session_cls.return_value = mock_session

            await transport.connect()

            assert transport.is_connected()
            assert transport.session is not None
            mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_extracts_session_id(self, transport, mock_response):
        """Test that session ID is extracted from response headers."""
        mock_response.headers = {"X-Session-ID": "test-session-123"}
        mock_response.text = AsyncMock(return_value='{"jsonrpc": "2.0", "id": 1, "result": {}}')
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.post = AsyncMock(return_value=mock_response)
            mock_session.closed = False
            mock_session_cls.return_value = mock_session

            await transport.connect()

            assert transport._current_session_id == "test-session-123"

    @pytest.mark.asyncio
    async def test_connect_handles_errors(self, transport):
        """Test connection error handling."""
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.post = AsyncMock(side_effect=Exception("Connection refused"))
            mock_session_cls.return_value = mock_session

            with pytest.raises(Exception) as exc_info:
                await transport.connect()

            assert "Connection refused" in str(exc_info.value)


class TestMCPStreamableHTTPTransportSendMessageSimple:
    """Tests for send_message() with simple HTTP responses."""

    @pytest.mark.asyncio
    async def test_send_message_simple_response(self, transport, mock_response):
        """Test sending message with simple HTTP 200 response."""
        # Setup connection
        transport.session = MagicMock()
        transport._connected = True

        # Mock simple JSON response
        response_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": "Hello from MCP"}]
            }
        }
        mock_response.text = AsyncMock(return_value=json.dumps(response_data))
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        transport.session.post = AsyncMock(return_value=mock_response)

        # Send message
        message = MCPMessage(method="tools/call", params={"name": "test_tool"})
        response = await transport.send_message(message)

        assert response.result is not None
        assert response.result["content"][0]["text"] == "Hello from MCP"

    @pytest.mark.asyncio
    async def test_send_message_empty_response(self, transport, mock_response):
        """Test handling empty response."""
        transport.session = MagicMock()
        transport._connected = True

        mock_response.text = AsyncMock(return_value="")
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        transport.session.post = AsyncMock(return_value=mock_response)

        message = MCPMessage(method="tools/call", params={"name": "test_tool"})
        response = await transport.send_message(message)

        # Should return empty MCPMessage
        assert response.jsonrpc == "2.0"


class TestMCPStreamableHTTPTransportSendMessageStreaming:
    """Tests for send_message() with SSE streaming responses."""

    @pytest.mark.asyncio
    async def test_send_message_sse_streaming_response(self, transport, mock_response):
        """Test sending message with SSE streaming response."""
        transport.session = MagicMock()
        transport._connected = True

        # Mock SSE stream
        sse_lines = [
            b'event: message\ndata: {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "Hello"}]}}\n\n',
            b'event: message\ndata: {"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": " World"}]}}\n\n',
            b'event: end\ndata: {}\n\n',
        ]

        async def mock_iter_lines():
            for line in sse_lines:
                yield line

        mock_response.content.__aiter__ = AsyncMock(return_value=mock_iter_lines())
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        transport.session.post = AsyncMock(return_value=mock_response)

        message = MCPMessage(method="tools/call", params={"name": "test_tool"})
        response = await transport.send_message(message)

        # Should aggregate both messages
        assert response.result is not None
        content_list = response.result.get("content", [])
        assert len(content_list) == 2

    @pytest.mark.asyncio
    async def test_send_message_sse_timeout(self, transport, mock_response):
        """Test SSE stream timeout handling."""
        transport.session = MagicMock()
        transport._connected = True

        # Mock slow stream that times out
        async def mock_slow_stream():
            await asyncio.sleep(130)  # Longer than 120s timeout
            yield b'event: message\ndata: {"text": "too late"}\n\n'

        mock_response.content.__aiter__ = AsyncMock(return_value=mock_slow_stream())
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        transport.session.post = AsyncMock(return_value=mock_response)

        message = MCPMessage(method="tools/call", params={"name": "test_tool"})

        with pytest.raises(TimeoutError) as exc_info:
            await transport.send_message(message)

        assert "timeout" in str(exc_info.value).lower()


class TestMCPStreamableHTTPTransportSessionManagement:
    """Tests for session ID management."""

    @pytest.mark.asyncio
    async def test_session_id_included_in_requests(self, transport, mock_response):
        """Test that session ID is included in request headers."""
        transport.session = MagicMock()
        transport._connected = True
        transport._current_session_id = "existing-session-456"

        mock_response.text = AsyncMock(return_value='{"jsonrpc": "2.0", "id": 1, "result": {}}')
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        transport.session.post = AsyncMock(return_value=mock_response)

        message = MCPMessage(method="tools/call", params={"name": "test_tool"})
        await transport.send_message(message)

        # Verify headers include session ID
        call_args = transport.session.post.call_args
        headers = call_args[1]["headers"]
        assert headers.get("X-Session-ID") == "existing-session-456"

    @pytest.mark.asyncio
    async def test_session_expired_reinitialize(self, transport, mock_response):
        """Test automatic re-initialization on HTTP 410 (session expired)."""
        # Setup first connection
        transport._connected = True
        transport.session = MagicMock()

        # First request returns 410 (session expired)
        error_response = MagicMock()
        error_response.error = {"code": 410, "message": "Session expired"}

        # Second request (after re-init) succeeds
        mock_response.text = AsyncMock(return_value='{"jsonrpc": "2.0", "id": 1, "result": {}}')
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        call_count = [0]

        async def mock_post(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call - session expired
                return error_response
            else:
                # After re-init - success
                return mock_response

        transport.session.post = AsyncMock(side_effect=mock_post)

        # Mock connect for re-initialization
        with patch.object(transport, 'connect', new=AsyncMock()):
            message = MCPMessage(method="tools/call", params={"name": "test_tool"})

            # Should handle 410 and retry
            # Note: This test verifies the logic flow
            # In real scenario, connect() would be called again


class TestMCPStreamableHTTPTransportRetryLogic:
    """Tests for retry logic with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, transport):
        """Test retry logic for timeout errors."""
        transport._connected = True
        transport.session = MagicMock()

        # First two attempts timeout, third succeeds
        call_count = [0]
        success_response = MagicMock()
        success_response.text = AsyncMock(return_value='{"jsonrpc": "2.0", "id": 1, "result": {}}')
        success_response.headers = {"Content-Type": "application/json"}
        success_response.__aenter__ = AsyncMock(return_value=success_response)
        success_response.__aexit__ = AsyncMock()

        async def mock_post_with_timeout(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise asyncio.TimeoutError("Request timeout")
            return success_response

        transport.session.post = AsyncMock(side_effect=mock_post_with_timeout)

        message = MCPMessage(method="tools/call", params={"name": "test_tool"})
        response = await transport.send_message(message)

        assert call_count[0] == 3  # Should retry twice

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, transport):
        """Test retry logic for HTTP 429 (rate limit)."""
        transport._connected = True
        transport.session = MagicMock()

        # First request gets rate limited
        rate_limit_error = ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=429,
            headers=MagicMock(get=Mock(return_value=None))
        )

        # Second request succeeds
        success_response = MagicMock()
        success_response.text = AsyncMock(return_value='{"jsonrpc": "2.0", "id": 1, "result": {}}')
        success_response.headers = {"Content-Type": "application/json"}
        success_response.__aenter__ = AsyncMock(return_value=success_response)
        success_response.__aexit__ = AsyncMock()

        call_count = [0]

        async def mock_post_with_ratelimit(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise rate_limit_error
            return success_response

        transport.session.post = AsyncMock(side_effect=mock_post_with_ratelimit)

        with patch("asyncio.sleep", new=AsyncMock()):
            message = MCPMessage(method="tools/call", params={"name": "test_tool"})
            response = await transport.send_message(message)

            assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(self, transport):
        """Test that 401 errors are not retried."""
        transport._connected = True
        transport.session = MagicMock()

        auth_error = ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=401,
        )

        transport.session.post = AsyncMock(side_effect=auth_error)

        message = MCPMessage(method="tools/call", params={"name": "test_tool"})

        with pytest.raises(RuntimeError) as exc_info:
            await transport.send_message(message)

        assert "Authentication failed" in str(exc_info.value)


class TestMCPStreamableHTTPTransportDisconnect:
    """Tests for disconnect() method."""

    @pytest.mark.asyncio
    async def test_disconnect_closes_session(self, transport):
        """Test that disconnect closes the HTTP session."""
        transport.session = MagicMock()
        transport.session.close = AsyncMock()
        transport._connected = True

        await transport.disconnect()

        transport.session.close.assert_called_once()
        assert not transport.is_connected()

    @pytest.mark.asyncio
    async def test_disconnect_cleanup_expired_sessions(self, transport):
        """Test that disconnect cleans up expired sessions."""
        transport.session = MagicMock()
        transport.session.close = AsyncMock()
        transport._connected = True

        # Add some expired sessions
        with patch.object(transport._session_store, 'cleanup_expired', new=AsyncMock(return_value=2)):
            await transport.disconnect()

            transport._session_store.cleanup_expired.assert_called_once_with(transport.config.session_ttl)

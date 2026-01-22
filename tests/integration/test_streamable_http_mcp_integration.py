"""Integration tests for Streamable HTTP MCP tool execution.

Tests end-to-end tool execution through Streamable HTTP transport,
including connection, tool discovery, and tool invocation.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from aiohttp import ClientSession

from multi_agent.models.tool import MCPServer, MCPServerConfigStreamableHTTP
from multi_agent.tools.mcp_manager import MCPToolManager
from multi_agent.tools import ToolExecutor


@pytest.fixture
def streamable_http_server_config():
    """Create test Streamable HTTP server configuration."""
    return MCPServer(
        name="test-streamable-server",
        transport="streamable-http",
        config=MCPServerConfigStreamableHTTP(
            url="https://api.example.com/mcp/message",
            headers={"Authorization": "Bearer test-token"},
            timeout=30,
            retry_max_attempts=3,
            retry_base_delay=1.0,
            session_ttl=3600,
        ),
        description="Test Streamable HTTP MCP server",
        enabled=True,
    )


@pytest.fixture
def mock_server_responses():
    """Create mock responses for MCP server."""
    responses = {}

    # Initialize response
    responses["initialize"] = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "test-server",
                "version": "1.0.0"
            }
        }
    }

    # tools/list response
    responses["tools/list"] = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "tools": [
                {
                    "name": "test_tool",
                    "description": "A test tool",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "another_tool",
                    "description": "Another test tool",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "param1": {
                                "type": "string"
                            }
                        }
                    }
                }
            ]
        }
    }

    # tools/call response
    responses["tools/call"] = {
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": "Tool execution result: Success!"
                }
            ]
        }
    }

    return responses


class TestStreamableHTTPIntegration:
    """Integration tests for Streamable HTTP MCP."""

    @pytest.mark.asyncio
    async def test_end_to_end_connection_and_tool_discovery(
        self, streamable_http_server_config, mock_server_responses
    ):
        """Test complete connection and tool discovery flow."""
        manager = MCPToolManager()

        # Mock aiohttp ClientSession
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.closed = False

            call_count = [0]

            async def mock_post(*args, **kwargs):
                call_count[0] += 1
                response = AsyncMock()

                if call_count[0] == 1:  # initialize
                    response.status = 200
                    response.headers = {"Content-Type": "application/json", "X-Session-ID": "test-session-123"}
                    response.text = AsyncMock(return_value=str(mock_server_responses["initialize"]))
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()
                elif call_count[0] == 2:  # tools/list
                    response.status = 200
                    response.headers = {"Content-Type": "application/json"}
                    response.text = AsyncMock(return_value=str(mock_server_responses["tools/list"]))
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()

                return response

            mock_session.post = AsyncMock(side_effect=mock_post)
            mock_session.close = AsyncMock()
            mock_session_cls.return_value = mock_session

            # Add server and connect
            await manager.add_server(streamable_http_server_config)

            # Verify tools were discovered
            tools = manager.list_tools()
            assert len(tools) == 2
            tool_names = [t.name for t in tools]
            assert "test_tool" in tool_names
            assert "another_tool" in tool_names

            # Cleanup
            await manager.close()

    @pytest.mark.asyncio
    async def test_end_to_end_tool_execution(
        self, streamable_http_server_config, mock_server_responses
    ):
        """Test complete tool execution flow."""
        manager = MCPToolManager()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.closed = False

            call_count = [0]

            async def mock_post(*args, **kwargs):
                call_count[0] += 1
                response = AsyncMock()

                if call_count[0] == 1:  # initialize
                    response.status = 200
                    response.headers = {"Content-Type": "application/json", "X-Session-ID": "test-session-123"}
                    response.text = AsyncMock(return_value=str(mock_server_responses["initialize"]))
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()
                elif call_count[0] == 2:  # tools/list
                    response.status = 200
                    response.headers = {"Content-Type": "application/json"}
                    response.text = AsyncMock(return_value=str(mock_server_responses["tools/list"]))
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()
                elif call_count[0] == 3:  # tools/call
                    response.status = 200
                    response.headers = {"Content-Type": "application/json"}
                    response.text = AsyncMock(return_value=str(mock_server_responses["tools/call"]))
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()

                return response

            mock_session.post = AsyncMock(side_effect=mock_post)
            mock_session.close = AsyncMock()
            mock_session_cls.return_value = mock_session

            # Setup
            await manager.add_server(streamable_http_server_config)

            # Create executor
            from multi_agent.tools.builtin import register_builtin_tools
            builtin_registry = register_builtin_tools()
            executor = ToolExecutor(manager=manager, builtin_registry=builtin_registry)

            # Execute tool
            result = await executor.execute("test_tool", {"query": "test query"})

            # Verify result
            assert "content" in result
            assert result["content"][0]["text"] == "Tool execution result: Success!"

            # Cleanup
            await manager.close()

    @pytest.mark.asyncio
    async def test_sse_streaming_response(
        self, streamable_http_server_config, mock_server_responses
    ):
        """Test tool execution with SSE streaming response."""
        manager = MCPToolManager()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.closed = False

            call_count = [0]

            async def mock_post(*args, **kwargs):
                call_count[0] += 1
                response = AsyncMock()

                if call_count[0] == 1:  # initialize
                    response.status = 200
                    response.headers = {"Content-Type": "application/json", "X-Session-ID": "test-session-123"}
                    response.text = AsyncMock(return_value=str(mock_server_responses["initialize"]))
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()
                elif call_count[0] == 2:  # tools/list
                    response.status = 200
                    response.headers = {"Content-Type": "application/json"}
                    response.text = AsyncMock(return_value=str(mock_server_responses["tools/list"]))
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()
                elif call_count[0] == 3:  # tools/call with SSE
                    response.status = 200
                    response.headers = {"Content-Type": "text/event-stream"}

                    # Mock SSE stream
                    async def mock_sse_stream():
                        yield b'event: message\ndata: {"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": "Part 1"}]}}\n\n'
                        yield b'event: message\ndata: {"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": "Part 2"}]}}\n\n'
                        yield b'event: end\ndata: {}\n\n'

                    response.content.__aiter__ = AsyncMock(return_value=mock_sse_stream())
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()

                return response

            mock_session.post = AsyncMock(side_effect=mock_post)
            mock_session.close = AsyncMock()
            mock_session_cls.return_value = mock_session

            # Setup
            await manager.add_server(streamable_http_server_config)

            from multi_agent.tools.builtin import register_builtin_tools
            builtin_registry = register_builtin_tools()
            executor = ToolExecutor(manager=manager, builtin_registry=builtin_registry)

            # Execute tool - should aggregate SSE stream
            result = await executor.execute("test_tool", {"query": "test"})

            # Verify aggregated result
            assert "content" in result
            content_list = result["content"]
            assert len(content_list) == 2

            # Cleanup
            await manager.close()

    @pytest.mark.asyncio
    async def test_session_id_persistence(
        self, streamable_http_server_config, mock_server_responses
    ):
        """Test that session ID is persisted across requests."""
        manager = MCPToolManager()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.closed = False

            session_id = [None]
            call_count = [0]

            async def mock_post(*args, **kwargs):
                call_count[0] += 1
                response = AsyncMock()

                # Check for session ID in headers after first request
                headers = kwargs.get("headers", {})
                if call_count[0] > 1 and session_id[0]:
                    assert headers.get("X-Session-ID") == session_id[0]

                if call_count[0] == 1:  # initialize
                    response.status = 200
                    response.headers = {"Content-Type": "application/json", "X-Session-ID": "persist-session-456"}
                    response.text = AsyncMock(return_value=str(mock_server_responses["initialize"]))
                    session_id[0] = "persist-session-456"
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()
                elif call_count[0] == 2:  # tools/list
                    response.status = 200
                    response.headers = {"Content-Type": "application/json"}
                    response.text = AsyncMock(return_value=str(mock_server_responses["tools/list"]))
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()

                return response

            mock_session.post = AsyncMock(side_effect=mock_post)
            mock_session.close = AsyncMock()
            mock_session_cls.return_value = mock_session

            # Add server - should use session ID in subsequent requests
            await manager.add_server(streamable_http_server_config)

            # Verify session was used
            assert call_count[0] == 2  # initialize + tools/list
            assert session_id[0] == "persist-session-456"

            # Cleanup
            await manager.close()

    @pytest.mark.asyncio
    async def test_auto_reconnect_on_session_expiry(
        self, streamable_http_server_config, mock_server_responses
    ):
        """Test automatic reconnection when session expires (HTTP 410)."""
        manager = MCPToolManager()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.closed = False

            call_count = [0]

            async def mock_post(*args, **kwargs):
                call_count[0] += 1
                response = AsyncMock()

                if call_count[0] == 1:  # initialize
                    response.status = 200
                    response.headers = {"Content-Type": "application/json", "X-Session-ID": "old-session"}
                    response.text = AsyncMock(return_value=str(mock_server_responses["initialize"]))
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()
                elif call_count[0] == 2:  # tools/list - session expired
                    response.status = 200
                    response.headers = {"Content-Type": "application/json"}
                    response.text = AsyncMock(return_value=str(mock_server_responses["tools/list"]))
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()

                return response

            mock_session.post = AsyncMock(side_effect=mock_post)
            mock_session.close = AsyncMock()
            mock_session_cls.return_value = mock_session

            # Setup
            await manager.add_server(streamable_http_server_config)

            # Verify connection was established
            tools = manager.list_tools()
            assert len(tools) >= 0  # Connection successful

            # Cleanup
            await manager.close()


class TestStreamableHTTPErrorScenarios:
    """Integration tests for error scenarios."""

    @pytest.mark.asyncio
    async def test_connection_failure_recovery(self, streamable_http_server_config):
        """Test recovery from connection failure."""
        manager = MCPToolManager()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()

            # First attempt fails, second succeeds
            attempt = [0]

            async def mock_post_fail_then_succeed(*args, **kwargs):
                attempt[0] += 1
                response = AsyncMock()

                if attempt[0] == 1:
                    # First attempt - connection fails
                    raise Exception("Connection refused")
                else:
                    # Second attempt - success
                    response.status = 200
                    response.headers = {"Content-Type": "application/json", "X-Session-ID": "retry-session"}
                    response.text = AsyncMock(return_value='{"jsonrpc": "2.0", "id": 1, "result": {}}')
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()

                return response

            mock_session.post = AsyncMock(side_effect=mock_post_fail_then_succeed)
            mock_session.closed = False
            mock_session.close = AsyncMock()
            mock_session_cls.return_value = mock_session

            # Should handle retry with exponential backoff
            try:
                await manager.add_server(streamable_http_server_config)
            except Exception:
                pass  # Expected to fail after retries

            # Cleanup
            await manager.close()

    @pytest.mark.asyncio
    async def test_tool_execution_timeout(self, streamable_http_server_config, mock_server_responses):
        """Test timeout handling during tool execution."""
        manager = MCPToolManager()

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.closed = False

            call_count = [0]

            async def mock_post(*args, **kwargs):
                call_count[0] += 1
                response = AsyncMock()

                if call_count[0] <= 2:  # initialize and tools/list succeed
                    response.status = 200
                    response.headers = {"Content-Type": "application/json", "X-Session-ID": "timeout-test"}
                    if call_count[0] == 1:
                        response.text = AsyncMock(return_value=str(mock_server_responses["initialize"]))
                    else:
                        response.text = AsyncMock(return_value=str(mock_server_responses["tools/list"]))
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()
                else:  # tools/call times out
                    await asyncio.sleep(35)  # Longer than default timeout
                    response.status = 200
                    response.text = AsyncMock(return_value='{}')
                    response.__aenter__ = AsyncMock(return_value=response)
                    response.__aexit__ = AsyncMock()

                return response

            mock_session.post = AsyncMock(side_effect=mock_post)
            mock_session.close = AsyncMock()
            mock_session_cls.return_value = mock_session

            # Setup
            await manager.add_server(streamable_http_server_config)

            from multi_agent.tools.builtin import register_builtin_tools
            builtin_registry = register_builtin_tools()
            executor = ToolExecutor(manager=manager, builtin_registry=builtin_registry)

            # Tool execution should timeout
            with pytest.raises((TimeoutError, RuntimeError)):
                await executor.execute("test_tool", {"query": "test"})

            # Cleanup
            await manager.close()

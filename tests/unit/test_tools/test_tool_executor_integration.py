"""Tests for ToolExecutor integration with builtin and MCP tools."""

import pytest

from multi_agent.tools import ToolExecutor
from multi_agent.tools.builtin import register_builtin_tools
from multi_agent.tools.mcp_manager import MCPToolManager


class TestToolExecutorIntegration:
    """Test suite for ToolExecutor integration."""

    @pytest.fixture
    def executor(self):
        """Create a ToolExecutor with builtin tools only."""
        builtin_registry = register_builtin_tools()
        return ToolExecutor(manager=None, builtin_registry=builtin_registry)

    @pytest.mark.asyncio
    async def test_execute_builtin_tool(self, executor):
        """Test executing a builtin tool."""
        result = await executor.execute("calculate", {"expression": "2 + 2"})
        assert "content" in result
        assert "4" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_execute_builtin_tool_not_found(self, executor):
        """Test executing non-existent tool."""
        result = await executor.execute("nonexistent_tool", {})
        assert "content" in result
        assert "not found" in result["content"][0]["text"].lower()

    @pytest.mark.asyncio
    async def test_execute_batch_single_builtin(self, executor):
        """Test execute_batch() with single builtin tool."""
        tool_calls = [
            {
                "id": "call_1",
                "function": {
                    "name": "calculate",
                    "arguments": '{"expression": "2 + 2"}'
                }
            }
        ]
        results = await executor.execute_batch(tool_calls)
        assert len(results) == 1
        assert results[0]["tool_call_id"] == "call_1"
        assert "4" in results[0]["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_execute_batch_multiple_builtin(self, executor):
        """Test execute_batch() with multiple builtin tools in parallel."""
        tool_calls = [
            {
                "id": "call_1",
                "function": {
                    "name": "calculate",
                    "arguments": '{"expression": "2 + 2"}'
                }
            },
            {
                "id": "call_2",
                "function": {
                    "name": "calculate",
                    "arguments": '{"expression": "3 * 3"}'
                }
            },
            {
                "id": "call_3",
                "function": {
                    "name": "system_get_time",
                    "arguments": '{}'
                }
            }
        ]
        results = await executor.execute_batch(tool_calls)
        assert len(results) == 3
        assert results[0]["tool_call_id"] == "call_1"
        assert results[1]["tool_call_id"] == "call_2"
        assert results[2]["tool_call_id"] == "call_3"
        # Verify results
        assert "4" in results[0]["content"][0]["text"]
        assert "9" in results[1]["content"][0]["text"]
        assert len(results[2]["content"][0]["text"]) > 0

    @pytest.mark.asyncio
    async def test_execute_batch_mixed_success_failure(self, executor):
        """Test execute_batch() with some tools failing."""
        tool_calls = [
            {
                "id": "call_1",
                "function": {
                    "name": "calculate",
                    "arguments": '{"expression": "2 + 2"}'
                }
            },
            {
                "id": "call_2",
                "function": {
                    "name": "nonexistent_tool",
                    "arguments": '{}'
                }
            }
        ]
        results = await executor.execute_batch(tool_calls)
        assert len(results) == 2
        # First should succeed
        assert "4" in results[0]["content"][0]["text"]
        # Second should fail gracefully
        assert "not found" in results[1]["content"][0]["text"].lower()

    @pytest.mark.asyncio
    async def test_execute_batch_preserves_order(self, executor):
        """Test execute_batch() preserves result order."""
        tool_calls = [
            {
                "id": "call_1",
                "function": {
                    "name": "system_get_time",
                    "arguments": '{}'
                }
            },
            {
                "id": "call_2",
                "function": {
                    "name": "calculate",
                    "arguments": '{"expression": "1"}'
                }
            },
            {
                "id": "call_3",
                "function": {
                    "name": "calculate",
                    "arguments": '{"expression": "2"}'
                }
            }
        ]
        results = await executor.execute_batch(tool_calls)
        assert len(results) == 3
        assert results[0]["tool_call_id"] == "call_1"
        assert results[1]["tool_call_id"] == "call_2"
        assert results[2]["tool_call_id"] == "call_3"

    @pytest.mark.asyncio
    async def test_execute_batch_with_dict_arguments(self, executor):
        """Test execute_batch() handles dict arguments."""
        tool_calls = [
            {
                "id": "call_1",
                "function": {
                    "name": "calculate",
                    "arguments": {"expression": "5 + 5"}
                }
            }
        ]
        results = await executor.execute_batch(tool_calls)
        assert len(results) == 1
        assert "10" in results[0]["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_find_server_for_tool_without_manager(self, executor):
        """Test _find_server_for_tool() returns None without MCP manager."""
        server = await executor._find_server_for_tool("some_tool")
        assert server is None

    def test_executor_initialization_with_defaults(self):
        """Test ToolExecutor initializes with default builtin registry."""
        executor = ToolExecutor(manager=None)
        assert executor.builtin_registry is not None
        assert executor.manager is None

    def test_executor_initialization_with_custom_registry(self):
        """Test ToolExecutor accepts custom builtin registry."""
        from multi_agent.tools.builtin import BuiltinRegistry
        custom_registry = BuiltinRegistry()
        executor = ToolExecutor(manager=None, builtin_registry=custom_registry)
        assert executor.builtin_registry is custom_registry

    def test_executor_initialization_with_mcp_manager(self):
        """Test ToolExecutor accepts MCP manager."""
        manager = MCPToolManager()
        executor = ToolExecutor(manager=manager)
        assert executor.manager is manager
        assert executor.builtin_registry is not None

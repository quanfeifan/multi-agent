"""Tests for BuiltinRegistry class."""

import pytest

from multi_agent.tools.builtin import (
    BuiltinRegistry,
    register_builtin_tools,
    register_file_tools,
    register_programming_tools,
    register_network_tools,
    register_system_tools,
)
from multi_agent.tools.builtin.file import FileReadTool
from multi_agent.tools.builtin.result import ToolResult


class TestBuiltinRegistry:
    """Test suite for BuiltinRegistry."""

    def test_registry_initialization(self):
        """Test registry starts empty."""
        registry = BuiltinRegistry()
        assert len(registry.list_all()) == 0

    def test_register_single_tool(self):
        """Test registering a single tool."""
        registry = BuiltinRegistry()
        tool = FileReadTool()
        registry.register(tool)
        assert registry.has("file_read")
        assert registry.get("file_read") is tool

    def test_register_duplicate_tool_raises_error(self):
        """Test registering duplicate tool raises ValueError."""
        registry = BuiltinRegistry()
        tool = FileReadTool()
        registry.register(tool)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(tool)

    def test_get_nonexistent_tool_returns_none(self):
        """Test getting non-existent tool returns None."""
        registry = BuiltinRegistry()
        assert registry.get("nonexistent") is None

    def test_has_tool(self):
        """Test has() method."""
        registry = BuiltinRegistry()
        assert not registry.has("file_read")
        registry.register(FileReadTool())
        assert registry.has("file_read")

    def test_list_all_tools(self):
        """Test listing all tools."""
        registry = BuiltinRegistry()
        tool1 = FileReadTool()
        registry.register(tool1)
        tools = registry.list_all()
        assert len(tools) == 1
        assert tool1 in tools

    def test_to_llm_list_format(self):
        """Test to_llm_list() returns OpenAI-compatible format."""
        registry = BuiltinRegistry()
        registry.register(FileReadTool())
        llm_list = registry.to_llm_list()
        assert len(llm_list) == 1
        assert llm_list[0]["type"] == "function"
        assert "function" in llm_list[0]
        func_def = llm_list[0]["function"]
        assert "name" in func_def
        assert "description" in func_def
        assert "parameters" in func_def
        assert func_def["name"] == "file_read"

    def test_to_llm_list_all_tools(self):
        """Test to_llm_list() includes all registered tools."""
        registry = register_builtin_tools()
        llm_list = registry.to_llm_list()
        tool_names = {t["function"]["name"] for t in llm_list}
        # Expected tools
        expected_tools = {
            "file_read",
            "file_write",
            "file_list",
            "file_info",
            "calculate",
            "execute",
            "network_fetch",
            "system_get_time",
            "system_get_env",
            "system_list_processes",
        }
        assert tool_names == expected_tools

    def test_json_schema_validation(self):
        """Test all tool parameters are valid JSON Schema."""
        registry = register_builtin_tools()
        llm_list = registry.to_llm_list()
        for tool_def in llm_list:
            params = tool_def["function"]["parameters"]
            # Must have type: object
            assert params.get("type") == "object", f"{tool_def['function']['name']} parameters must have type=object"
            # Must have properties
            assert "properties" in params, f"{tool_def['function']['name']} parameters must have properties"
            # Must have required array
            assert isinstance(params.get("required"), list), f"{tool_def['function']['name']} parameters must have required list"

    @pytest.mark.asyncio
    async def test_execute_batch_empty(self):
        """Test execute_batch() with empty list."""
        registry = BuiltinRegistry()
        results = await registry.execute_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_execute_batch_single_tool(self):
        """Test execute_batch() with single tool."""
        registry = register_builtin_tools()
        results = await registry.execute_batch([("file_read", {"path": "README.md"})])
        assert len(results) == 1
        # Result could be success or failure depending on if README.md exists
        assert isinstance(results[0], ToolResult)

    @pytest.mark.asyncio
    async def test_execute_batch_multiple_tools(self):
        """Test execute_batch() with multiple tools in parallel."""
        registry = register_builtin_tools()
        calls = [
            ("calculate", {"expression": "2 + 2"}),
            ("calculate", {"expression": "3 * 3"}),
            ("system_get_time", {}),
        ]
        results = await registry.execute_batch(calls)
        assert len(results) == 3
        assert all(isinstance(r, ToolResult) for r in results)
        # Check specific results
        assert results[0].success is True
        assert "4" in results[0].data
        assert results[1].success is True
        assert "9" in results[1].data

    @pytest.mark.asyncio
    async def test_execute_batch_tool_not_found(self):
        """Test execute_batch() with non-existent tool."""
        registry = BuiltinRegistry()
        results = await registry.execute_batch([("nonexistent_tool", {})])
        assert len(results) == 1
        assert results[0].success is False
        assert "not found" in results[0].error.lower()

    def test_register_file_tools(self):
        """Test register_file_tools() returns file tools."""
        tools = register_file_tools()
        assert len(tools) == 4
        tool_names = {t.name for t in tools}
        assert tool_names == {"file_read", "file_write", "file_list", "file_info"}

    def test_register_programming_tools(self):
        """Test register_programming_tools() returns programming tools."""
        tools = register_programming_tools()
        assert len(tools) == 2
        tool_names = {t.name for t in tools}
        assert tool_names == {"calculate", "execute"}

    def test_register_network_tools(self):
        """Test register_network_tools() returns network tools."""
        tools = register_network_tools()
        assert len(tools) == 1
        assert tools[0].name == "network_fetch"

    def test_register_system_tools(self):
        """Test register_system_tools() returns system tools."""
        tools = register_system_tools()
        assert len(tools) == 3
        tool_names = {t.name for t in tools}
        assert tool_names == {"system_get_time", "system_get_env", "system_list_processes"}

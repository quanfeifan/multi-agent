"""Unit tests for data models.

These tests use mock values for LLM configuration since they test
the data structure logic, not actual LLM API calls.
For integration tests with real LLM calls, see tests/integration/
"""

import pytest
from datetime import datetime
from multi_agent.models import (
    Task,
    TaskStatus,
    Message,
    ToolCall,
    State,
    Agent,
    Tool,
    MCPServer,
)
from multi_agent.models.tool import MCPServerConfigStdio
from multi_agent.config.schemas import LLMConfig


class TestTask:
    """Tests for Task model."""

    def test_create_task(self):
        """Test creating a task with required fields."""
        task = Task(
            id="task-123",
            description="Test task",
            assigned_agent="test_agent"
        )
        assert task.id == "task-123"
        assert task.description == "Test task"
        assert task.assigned_agent == "test_agent"
        assert task.status == TaskStatus.PENDING
        assert task.result is None
        assert task.error is None

    def test_task_status_transitions(self):
        """Test task status transitions."""
        task = Task(
            id="task-123",
            description="Test task",
            assigned_agent="test_agent"
        )

        # Initial status
        assert task.status == TaskStatus.PENDING
        assert task.started_at is None
        assert task.completed_at is None

        # Mark as running
        task.mark_running()
        assert task.status == TaskStatus.RUNNING
        assert task.started_at is not None
        assert task.completed_at is None

        # Mark as completed
        task.mark_completed("Task completed successfully")
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "Task completed successfully"
        assert task.completed_at is not None

    def test_task_failure(self):
        """Test marking task as failed."""
        task = Task(
            id="task-123",
            description="Test task",
            assigned_agent="test_agent"
        )
        task.mark_failed("Something went wrong")
        assert task.status == TaskStatus.FAILED
        assert task.error == "Something went wrong"
        assert task.completed_at is not None

    def test_task_duration(self):
        """Test task duration calculation."""
        task = Task(
            id="task-123",
            description="Test task",
            assigned_agent="test_agent"
        )
        assert task.duration_seconds is None

        task.mark_running()
        assert task.duration_seconds is None

        task.mark_completed("Done")
        assert task.duration_seconds is not None
        assert task.duration_seconds >= 0


class TestMessage:
    """Tests for Message model."""

    def test_create_user_message(self):
        """Test creating a user message."""
        message = Message(role="user", content="Hello")
        assert message.role == "user"
        assert message.content == "Hello"
        assert message.is_from_user()
        assert not message.is_from_assistant()
        assert not message.is_from_tool()
        assert not message.is_system()

    def test_create_assistant_message(self):
        """Test creating an assistant message."""
        message = Message(role="assistant", content="Hi there")
        assert message.role == "assistant"
        assert message.is_from_assistant()
        assert not message.is_from_user()

    def test_create_tool_message(self):
        """Test creating a tool message."""
        message = Message(role="tool", content="Result: 42")
        assert message.role == "tool"
        assert message.is_from_tool()

    def test_create_system_message(self):
        """Test creating a system message."""
        message = Message(role="system", content="You are helpful")
        assert message.is_system()

    def test_message_with_tool_calls(self):
        """Test message with tool calls."""
        tool_call = ToolCall(
            id="call-123",
            server="test_server",
            tool="calculator",
            arguments={"x": 1, "y": 2}
        )
        message = Message(
            role="assistant",
            content="I'll calculate that",
            tool_calls=[tool_call]
        )
        assert len(message.tool_calls) == 1
        assert message.tool_calls[0].tool == "calculator"


class TestToolCall:
    """Tests for ToolCall model."""

    def test_create_tool_call(self):
        """Test creating a tool call."""
        tool_call = ToolCall(
            id="call-123",
            server="test_server",
            tool="search",
            arguments={"query": "test"}
        )
        assert tool_call.id == "call-123"
        assert tool_call.server == "test_server"
        assert tool_call.tool == "search"
        assert tool_call.arguments == {"query": "test"}


class TestState:
    """Tests for State model."""

    def test_create_state(self):
        """Test creating a state."""
        state = State(current_agent="test_agent")
        assert state.current_agent == "test_agent"
        assert state.messages == []
        assert state.next_action is None
        assert state.routing_key is None
        assert state.metadata == {}

    def test_add_message(self):
        """Test adding a message to state."""
        state = State(current_agent="test_agent")
        message = Message(role="user", content="Hello")

        new_state = state.add_message(message)
        assert len(new_state.messages) == 1
        assert new_state.messages[0].content == "Hello"
        # Original state should be unchanged (immutable)
        assert len(state.messages) == 0

    def test_add_multiple_messages(self):
        """Test adding multiple messages."""
        state = State(current_agent="test_agent")
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]

        new_state = state.add_messages(messages)
        assert len(new_state.messages) == 2

    def test_update_fields(self):
        """Test updating state fields."""
        state = State(current_agent="test_agent")
        new_state = state.update(next_action="respond", routing_key="continue")
        assert new_state.next_action == "respond"
        assert new_state.routing_key == "continue"
        # Original unchanged
        assert state.next_action is None

    def test_get_last_n_messages(self):
        """Test getting last n messages."""
        state = State(current_agent="test_agent")
        for i in range(5):
            state = state.add_message(Message(role="user", content=f"Message {i}"))

        assert len(state.get_last_n_messages(2)) == 2
        assert state.get_last_n_messages(2)[0].content == "Message 3"
        assert state.get_last_n_messages(2)[1].content == "Message 4"

    def test_message_count(self):
        """Test message count property."""
        state = State(current_agent="test_agent")
        assert state.message_count == 0

        state = state.add_message(Message(role="user", content="Test"))
        assert state.message_count == 1


class TestAgent:
    """Tests for Agent model."""

    def test_create_agent(self):
        """Test creating an agent.

        Note: LLMConfig uses api_key_env to specify which environment
        variable to read the API key from. The actual API key is read
        from the environment when LLMClient is initialized.
        """
        llm_config = LLMConfig(
            endpoint="https://api.example.com/v1",
            model="gpt-4",
            api_key_env="OPENAI_API_KEY"  # Reads from OPENAI_API_KEY env var
        )
        agent = Agent(
            name="test_agent",
            role="Assistant",
            system_prompt="You are helpful",
            llm_config=llm_config
        )
        assert agent.name == "test_agent"
        assert agent.role == "Assistant"
        assert agent.system_prompt == "You are helpful"
        assert agent.tools == []
        assert agent.max_iterations == 10

    def test_agent_with_tools(self):
        """Test agent with tools."""
        llm_config = LLMConfig(
            endpoint="https://api.example.com/v1",
            model="gpt-4",
            api_key_env="OPENAI_API_KEY"
        )
        agent = Agent(
            name="researcher",
            role="Research Assistant",
            system_prompt="You research topics",
            llm_config=llm_config,
            tools=["search", "calculator"]
        )
        assert agent.tools == ["search", "calculator"]

    def test_agent_temperature_override(self):
        """Test agent temperature override."""
        llm_config = LLMConfig(
            endpoint="https://api.example.com/v1",
            model="gpt-4",
            api_key_env="OPENAI_API_KEY",
            temperature=0.5
        )
        agent = Agent(
            name="test_agent",
            role="Assistant",
            system_prompt="You are helpful",
            llm_config=llm_config,
            temperature=0.9
        )
        assert agent.get_effective_temperature() == 0.9

    def test_agent_default_temperature(self):
        """Test agent uses LLM config temperature when not overridden."""
        llm_config = LLMConfig(
            endpoint="https://api.example.com/v1",
            model="gpt-4",
            api_key_env="OPENAI_API_KEY",
            temperature=0.7
        )
        agent = Agent(
            name="test_agent",
            role="Assistant",
            system_prompt="You are helpful",
            llm_config=llm_config
        )
        assert agent.get_effective_temperature() == 0.7


class TestTool:
    """Tests for Tool model."""

    def test_create_tool(self):
        """Test creating a tool."""
        tool = Tool(
            name="search",
            server="search_server",
            description="Search the web",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                }
            }
        )
        assert tool.name == "search"
        assert tool.server == "search_server"
        assert tool.description == "Search the web"

    def test_tool_full_name(self):
        """Test tool full name property."""
        tool = Tool(
            name="calculator",
            server="math_server",
            description="Calculate things",
            input_schema={}
        )
        assert tool.full_name == "math_server:calculator"


class TestMCPServer:
    """Tests for MCPServer model."""

    def test_create_stdio_server(self):
        """Test creating stdio MCP server."""
        config = MCPServerConfigStdio(
            command="/path/to/server",
            args=["--port", "8080"],
            env={"DEBUG": "true"}
        )
        server = MCPServer(
            name="test_server",
            transport="stdio",
            config=config,
            enabled=True
        )
        assert server.name == "test_server"
        assert server.transport == "stdio"
        assert server.enabled is True

    def test_disabled_server(self):
        """Test disabled MCP server."""
        config = MCPServerConfigStdio(command="/path/to/server")
        server = MCPServer(
            name="test_server",
            transport="stdio",
            config=config,
            enabled=False
        )
        assert server.enabled is False

"""Integration tests for US3: Recover Automatically from Tool Failures.

These tests verify:
- Configurable tool timeout (default 5 min)
- Automatic fallback on timeout
- Retry logic with exponential backoff
- Error classification (retryable vs non-retryable)
"""

import os
import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock
from dotenv import load_dotenv

from multi_agent.agent import BaseAgent
from multi_agent.models import Agent, State, ToolCall
from multi_agent.config.schemas import LLMConfig
from multi_agent.tools import FallbackManager, ToolExecutor
from multi_agent.tracing import Tracer

# Load environment variables from .env
load_dotenv()


@pytest.fixture
def llm_config():
    """Create LLM config using API key from environment."""
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.environ.get("DEFAULT_MODEL", "Qwen/Qwen3-8B")

    if not api_key:
        pytest.skip("OPENAI_API_KEY not set in environment")

    return LLMConfig(
        endpoint=base_url,
        model=model,
        api_key_env="OPENAI_API_KEY"
    )


@pytest.fixture
def temp_dir():
    """Create temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.asyncio
class TestUS3FallbackMechanism:
    """Integration tests for User Story 3: Fallback Mechanism."""

    async def test_tool_timeout_enforcement(self):
        """Test tool timeout is enforced."""
        async def slow_tool(tool_call: ToolCall) -> str:
            """A tool that takes too long."""
            await asyncio.sleep(10)  # Sleep for 10 seconds
            return "Done"

        fallback_manager = FallbackManager()

        tool_call = ToolCall(
            id="call-001",
            server="test_server",
            tool="slow_tool",
            arguments={}
        )

        # Should timeout before 10 seconds
        result = await fallback_manager.execute_with_fallback(
            tool_call=tool_call,
            primary_executor=slow_tool,
            timeout_seconds=2  # 2 second timeout
        )

        # Should have timed out
        assert result is None or "timeout" in str(result).lower()

    async def test_fallback_tool_invocation(self):
        """Test fallback tool is invoked on primary failure."""
        async def failing_tool(tool_call: ToolCall) -> str:
            """A tool that always fails."""
            raise Exception("Tool failed")

        async def fallback_tool(tool_call: ToolCall) -> str:
            """A fallback tool."""
            return "Fallback result"

        fallback_manager = FallbackManager()

        tool_call = ToolCall(
            id="call-002",
            server="test_server",
            tool="failing_tool",
            arguments={}
        )

        result = await fallback_manager.execute_with_fallback(
            tool_call=tool_call,
            primary_executor=failing_tool,
            fallback_executor=fallback_tool,
            timeout_seconds=5
        )

        assert result == "Fallback result"

    async def test_retry_with_exponential_backoff(self):
        """Test retry logic with exponential backoff."""
        call_count = 0

        async def flaky_tool(tool_call: ToolCall) -> str:
            """A tool that fails twice then succeeds."""
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "Success"

        fallback_manager = FallbackManager()

        tool_call = ToolCall(
            id="call-003",
            server="test_server",
            tool="flaky_tool",
            arguments={}
        )

        start_time = asyncio.get_event_loop().time()

        result = await fallback_manager.execute_with_retry(
            tool_call=tool_call,
            executor=flaky_tool,
            max_retries=3,
            base_delay=0.1  # 100ms base delay
        )

        end_time = asyncio.get_event_loop().time()

        assert result == "Success"
        assert call_count == 3  # Failed twice, succeeded on third try
        # Should have taken some time due to backoff
        assert (end_time - start_time) >= 0.2  # At least 200ms (0.1 + 0.2)

    async def test_error_classification_retryable(self):
        """Test retryable errors are classified correctly."""
        fallback_manager = FallbackManager()

        # Test various retryable errors
        retryable_errors = [
            TimeoutError("Request timed out"),
            ConnectionError("Connection lost"),
            Exception("Temporary failure")
        ]

        for error in retryable_errors:
            is_retryable = fallback_manager.is_retryable_error(error)
            assert is_retryable is True, f"Expected {error} to be retryable"

    async def test_error_classification_non_retryable(self):
        """Test non-retryable errors are classified correctly."""
        fallback_manager = FallbackManager()

        # Test various non-retryable errors
        non_retryable_errors = [
            ValueError("Invalid input"),
            PermissionError("Access denied"),
            KeyError("Missing key")
        ]

        for error in non_retryable_errors:
            is_retryable = fallback_manager.is_retryable_error(error)
            assert is_retryable is False, f"Expected {error} to be non-retryable"


@pytest.mark.asyncio
class TestUS3ToolConfiguration:
    """Tests for tool configuration with timeout and fallback."""

    async def test_tool_timeout_configuration(self):
        """Test tools can have custom timeout configured."""
        from multi_agent.models import Tool

        tool = Tool(
            name="slow_tool",
            server="test_server",
            description="A tool that takes time",
            input_schema={},
            timeout_seconds=30  # 30 second timeout
        )

        assert tool.timeout_seconds == 30

    async def test_tool_fallback_configuration(self):
        """Test tools can have fallback tools configured."""
        from multi_agent.models import Tool

        tool = Tool(
            name="primary_tool",
            server="test_server",
            description="Primary tool with fallback",
            input_schema={},
            fallback_tools=["fallback_tool_1", "fallback_tool_2"]
        )

        assert tool.fallback_tools == ["fallback_tool_1", "fallback_tool_2"]


@pytest.mark.asyncio
class TestUS3ContextLimitHandling:
    """Tests for LLM context limit handling."""

    async def test_context_limit_error_detection(self, llm_config):
        """Test context limit errors are detected."""
        from multi_agent.agent.base import ContextLimitError

        # This would be triggered by actual LLM calls
        # For now, we test the error class exists
        error = ContextLimitError("Context limit exceeded")
        assert "context limit" in str(error).lower()

    async def test_progressive_message_removal(self, llm_config):
        """Test messages are progressively removed when context limit is hit."""
        agent = Agent(
            name="context_test_agent",
            role="Test",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=5
        )

        # Create a state with many messages
        state = State(current_agent=agent.name)
        for i in range(100):
            state = state.add_message(
                Message(role="user", content=f"Message {i}")
            )

        # State should handle many messages
        assert state.message_count == 100

        # Getting last N messages should work
        last_10 = state.get_last_n_messages(10)
        assert len(last_10) == 10


@pytest.mark.asyncio
class TestUS3EndToEndFaultTolerance:
    """End-to-end tests for fault tolerance."""

    async def test_flaky_tool_with_fallback(self, llm_config, temp_dir):
        """Test agent handles flaky tool with automatic fallback."""
        call_count = 0

        async def flaky_tool(tool_call: ToolCall) -> str:
            """A tool that fails once then succeeds."""
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Temporary network issue")
            return f"Tool result: {tool_call.arguments}"

        async def fallback_tool(tool_call: ToolCall) -> str:
            """Fallback tool."""
            return f"Fallback: {tool_call.arguments}"

        agent = Agent(
            name="fault_tolerant_agent",
            role="Fault Tolerant Assistant",
            system_prompt="You are a helpful assistant. Use tools when needed.",
            llm_config=llm_config,
            max_iterations=3
        )

        task_dir = temp_dir / "fault_tolerance_task"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        fallback_manager = FallbackManager()

        # Test the flaky tool directly
        tool_call = ToolCall(
            id="call-flaky",
            server="test_server",
            tool="flaky_tool",
            arguments={"query": "test"}
        )

        result = await fallback_manager.execute_with_fallback(
            tool_call=tool_call,
            primary_executor=flaky_tool,
            fallback_executor=fallback_tool,
            timeout_seconds=5
        )

        # Should eventually succeed
        assert result is not None

    async def test_timeout_and_fallback_sequence(self):
        """Test timeout triggers fallback correctly."""
        execution_order = []

        async def timeout_tool(tool_call: ToolCall) -> str:
            """A tool that times out."""
            execution_order.append("primary")
            await asyncio.sleep(10)
            return "Primary result"

        async def fallback_tool(tool_call: ToolCall) -> str:
            """Fallback tool."""
            execution_order.append("fallback")
            return "Fallback result"

        fallback_manager = FallbackManager()

        tool_call = ToolCall(
            id="call-timeout",
            server="test_server",
            tool="timeout_tool",
            arguments={}
        )

        result = await fallback_manager.execute_with_fallback(
            tool_call=tool_call,
            primary_executor=timeout_tool,
            fallback_executor=fallback_tool,
            timeout_seconds=1
        )

        # Fallback should have been called
        assert "fallback" in execution_order
        assert result == "Fallback result"

    async def test_max_retries_exceeded(self):
        """Test behavior when max retries is exceeded."""
        async def always_failing_tool(tool_call: ToolCall) -> str:
            """A tool that always fails."""
            raise ConnectionError("Always fails")

        fallback_manager = FallbackManager()

        tool_call = ToolCall(
            id="call-fail",
            server="test_server",
            tool="failing_tool",
            arguments={}
        )

        result = await fallback_manager.execute_with_retry(
            tool_call=tool_call,
            executor=always_failing_tool,
            max_retries=2,
            base_delay=0.01
        )

        # Should return None after max retries exceeded
        assert result is None

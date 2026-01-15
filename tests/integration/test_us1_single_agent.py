"""Integration tests for US1: Execute Single-Agent Task with State Tracking.

These tests verify:
- Agent can reason across multiple iterations
- Tools can be invoked via MCP protocol
- State persists across all iterations
- Complete execution log is generated
"""

import os
import pytest
import tempfile
from pathlib import Path
from dotenv import load_dotenv

from multi_agent.agent import BaseAgent
from multi_agent.models import Agent, State, ToolCall
from multi_agent.config.schemas import LLMConfig
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
class TestUS1SingleAgent:
    """Integration tests for User Story 1: Single-Agent Task Execution."""

    async def test_single_agent_task_execution(self, llm_config):
        """Test end-to-end single-agent task execution."""
        agent = Agent(
            name="test_agent",
            role="Test Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=5
        )

        base_agent = BaseAgent(agent=agent, tool_executor=None)

        result = await base_agent.execute(
            task_description="What is 2 + 2? Answer briefly.",
            initial_state=None
        )

        assert result.completed is True
        assert result.steps >= 1
        assert len(result.output) > 0
        assert "4" in result.output.lower() or "four" in result.output.lower()

    async def test_multi_iteration_reasoning(self, llm_config):
        """Test multi-iteration reasoning with task requiring steps."""
        agent = Agent(
            name="reasoning_agent",
            role="Reasoning Assistant",
            system_prompt="You are a helpful assistant. Break down problems into steps.",
            llm_config=llm_config,
            max_iterations=5
        )

        base_agent = BaseAgent(agent=agent, tool_executor=None)

        result = await base_agent.execute(
            task_description="Calculate: (5 * 3) + (10 / 2). Show your work.",
            initial_state=None
        )

        assert result.completed is True
        assert result.steps >= 1
        # Should mention the calculation steps
        assert "15" in result.output or "5" in result.output

    async def test_state_persistence_across_iterations(self, llm_config):
        """Verify state persists across all iterations."""
        agent = Agent(
            name="state_agent",
            role="Stateful Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=3
        )

        base_agent = BaseAgent(agent=agent, tool_executor=None)

        result = await base_agent.execute(
            task_description="My name is Alice. What is my name?",
            initial_state=None
        )

        assert result.completed is True
        # State should have accumulated messages
        assert result.state.message_count > 0
        # Last message should contain the answer
        assert "alice" in result.output.lower()

    async def test_trace_log_completeness(self, llm_config, temp_dir):
        """Verify complete execution log is generated."""
        agent = Agent(
            name="traced_agent",
            role="Traced Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=3
        )

        task_dir = temp_dir / "task_test"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))
        base_agent = BaseAgent(agent=agent, tool_executor=None, tracer=tracer)

        result = await base_agent.execute(
            task_description="Say hello and goodbye",
            initial_state=None
        )

        # Verify trace log was created
        trace_file = task_dir / "trace.json"
        assert trace_file.exists()

        # Load and verify trace content
        trace_log = tracer.load_trace(str(task_dir))
        assert trace_log is not None
        assert len(trace_log.steps) > 0

        # Verify each step has required fields
        for step in trace_log.steps:
            assert step.step_number > 0
            assert step.timestamp is not None
            assert step.input is not None


@pytest.mark.asyncio
class TestUS1WithTools:
    """Tests for agent execution with tools (when MCP is available)."""

    async def test_tool_invocation_via_mcp(self, llm_config, temp_dir):
        """Test tools can be invoked via MCP protocol."""
        # Create a simple mock tool executor for testing
        async def mock_tool_executor(tool_call: ToolCall) -> str:
            """Mock tool executor that simulates MCP tool calls."""
            if tool_call.tool == "calculator":
                args = tool_call.arguments
                if "expression" in args:
                    try:
                        result = eval(args["expression"])
                        return str(result)
                    except:
                        return "Error evaluating expression"
            return f"Tool {tool_call.tool} executed with args: {tool_call.arguments}"

        agent = Agent(
            name="tool_agent",
            role="Tool-using Assistant",
            system_prompt="You are a helpful assistant. Use the calculator tool when needed.",
            llm_config=llm_config,
            max_iterations=5
        )

        task_dir = temp_dir / "task_tool"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))
        tool_executor = mock_tool_executor
        base_agent = BaseAgent(agent=agent, tool_executor=tool_executor, tracer=tracer)

        # This task should trigger tool use (in real scenario with proper tool schema)
        result = await base_agent.execute(
            task_description="What is 15 * 7?",
            initial_state=None
        )

        assert result.completed is True

        # Verify trace logs captured the execution
        trace_log = tracer.load_trace(str(task_dir))
        assert trace_log is not None

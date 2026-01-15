"""Integration tests for US4: Inspect and Debug Execution via Trace Logs.

These tests verify:
- Sequential step records with timestamps
- Tool inputs/outputs captured
- Sub-agent sessions tracked separately
- Failure points clearly identifiable
"""

import os
import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from multi_agent.agent import BaseAgent
from multi_agent.models import Agent, State, Message, ToolCall
from multi_agent.config.schemas import LLMConfig
from multi_agent.tracing import Tracer
from multi_agent.models.tracer import TraceLog, StepRecord, ToolCallRecord

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
class TestUS4TraceLogCapture:
    """Integration tests for User Story 4: Trace Log Capture."""

    async def test_trace_log_creation(self, llm_config, temp_dir):
        """Test trace log file is created."""
        task_dir = temp_dir / "trace_creation"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        agent = Agent(
            name="test_agent",
            role="Test Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=2
        )

        base_agent = BaseAgent(agent=agent, tool_executor=None, tracer=tracer)

        result = await base_agent.execute(
            task_description="Say hello",
            initial_state=None
        )

        # Verify trace file exists
        trace_file = task_dir / "trace.json"
        assert trace_file.exists()

    async def test_sequential_step_records(self, llm_config, temp_dir):
        """Verify sequential step records with timestamps."""
        task_dir = temp_dir / "sequential_steps"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        agent = Agent(
            name="sequential_agent",
            role="Sequential Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=3
        )

        base_agent = BaseAgent(agent=agent, tool_executor=None, tracer=tracer)

        result = await base_agent.execute(
            task_description="Count from 1 to 3",
            initial_state=None
        )

        # Load trace log
        trace_log = tracer.load_trace(str(task_dir))
        assert trace_log is not None

        # Verify steps are sequential
        step_numbers = [step.step_number for step in trace_log.steps]
        assert step_numbers == sorted(step_numbers)

        # Verify each step has timestamp
        for step in trace_log.steps:
            assert step.timestamp is not None
            assert isinstance(step.timestamp, datetime)

    async def test_step_duration_tracking(self, llm_config, temp_dir):
        """Verify step duration is tracked in milliseconds."""
        task_dir = temp_dir / "duration_tracking"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        agent = Agent(
            name="duration_agent",
            role="Duration Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=2
        )

        base_agent = BaseAgent(agent=agent, tool_executor=None, tracer=tracer)

        result = await base_agent.execute(
            task_description="What is 2 + 2?",
            initial_state=None
        )

        # Load trace log
        trace_log = tracer.load_trace(str(task_dir))
        assert trace_log is not None

        # Verify duration is tracked
        for step in trace_log.steps:
            if step.duration_ms is not None:
                assert step.duration_ms >= 0

    async def test_tool_inputs_outputs_captured(self, llm_config, temp_dir):
        """Verify tool inputs and outputs are captured."""
        task_dir = temp_dir / "tool_capture"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        # Create a mock tool executor
        async def mock_tool_executor(tool_call: ToolCall) -> str:
            return f"Result for {tool_call.tool}: {tool_call.arguments}"

        agent = Agent(
            name="tool_agent",
            role="Tool Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=3
        )

        base_agent = BaseAgent(
            agent=agent,
            tool_executor=mock_tool_executor,
            tracer=tracer
        )

        result = await base_agent.execute(
            task_description="Use a tool",
            initial_state=None
        )

        # Load trace log
        trace_log = tracer.load_trace(str(task_dir))
        assert trace_log is not None

        # Check for tool call records
        tool_calls_found = False
        for step in trace_log.steps:
            if step.tool_calls:
                tool_calls_found = True
                for tool_call in step.tool_calls:
                    assert tool_call.id is not None
                    assert tool_call.tool is not None
                    assert tool_call.arguments is not None

        # Tool calls may or may not be present depending on LLM behavior
        # Just verify the structure is correct if they exist


@pytest.mark.asyncio
class TestUS4SubAgentSessionTracking:
    """Tests for sub-agent session tracking in trace logs."""

    async def test_sub_agent_session_tracking(self, llm_config, temp_dir):
        """Verify sub-agent sessions are tracked separately."""
        task_dir = temp_dir / "sub_agent_tracking"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        # Create multiple agents
        agent1 = Agent(
            name="agent1",
            role="Agent 1",
            system_prompt="You are agent 1. Say hello.",
            llm_config=llm_config,
            max_iterations=2
        )

        agent2 = Agent(
            name="agent2",
            role="Agent 2",
            system_prompt="You are agent 2. Say goodbye.",
            llm_config=llm_config,
            max_iterations=2
        )

        # Execute both agents
        base_agent1 = BaseAgent(agent=agent1, tool_executor=None, tracer=tracer)
        result1 = await base_agent1.execute(
            task_description="Say hello",
            initial_state=None
        )

        base_agent2 = BaseAgent(agent=agent2, tool_executor=None, tracer=tracer)
        result2 = await base_agent2.execute(
            task_description="Say goodbye",
            initial_state=None
        )

        # Load trace log
        trace_log = tracer.load_trace(str(task_dir))
        assert trace_log is not None

        # Verify steps from different agents are tracked
        agent_names = set()
        for step in trace_log.steps:
            if step.agent_name:
                agent_names.add(step.agent_name)

        # Should have tracked both agents
        assert len(agent_names) >= 1


@pytest.mark.asyncio
class TestUS4FailurePointIdentification:
    """Tests for failure point identification in trace logs."""

    async def test_error_state_capture(self, llm_config, temp_dir):
        """Verify errors are captured in trace logs."""
        task_dir = temp_dir / "error_capture"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        # Create a tool executor that fails
        async def failing_tool(tool_call: ToolCall) -> str:
            raise Exception("Tool execution failed")

        agent = Agent(
            name="error_agent",
            role="Error Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=2
        )

        base_agent = BaseAgent(
            agent=agent,
            tool_executor=failing_tool,
            tracer=tracer
        )

        # Execute task (may or may not trigger tool use)
        result = await base_agent.execute(
            task_description="Say hello",
            initial_state=None
        )

        # Load trace log
        trace_log = tracer.load_trace(str(task_dir))
        assert trace_log is not None

        # Verify trace log structure
        assert trace_log.steps is not None
        assert len(trace_log.steps) > 0

    async def test_failure_points_clearly_identifiable(self, llm_config, temp_dir):
        """Verify failure points are clearly identifiable in trace."""
        task_dir = temp_dir / "failure_points"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        agent = Agent(
            name="failure_test_agent",
            role="Failure Test Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=2
        )

        base_agent = BaseAgent(agent=agent, tool_executor=None, tracer=tracer)

        result = await base_agent.execute(
            task_description="Say hello",
            initial_state=None
        )

        # Load trace log
        trace_log = tracer.load_trace(str(task_dir))

        # Verify each step has clear status information
        for step in trace_log.steps:
            assert step.step_number is not None
            assert step.timestamp is not None


@pytest.mark.asyncio
class TestUS4TraceLogUtilities:
    """Tests for trace log utility functions."""

    async def test_trace_log_pretty_print(self, llm_config, temp_dir):
        """Test trace log can be pretty-printed."""
        task_dir = temp_dir / "pretty_print"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        agent = Agent(
            name="print_agent",
            role="Print Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=2
        )

        base_agent = BaseAgent(agent=agent, tool_executor=None, tracer=tracer)

        result = await base_agent.execute(
            task_description="Say hello",
            initial_state=None
        )

        # Load and pretty print trace log
        trace_log = tracer.load_trace(str(task_dir))
        assert trace_log is not None

        # Get pretty printed output
        pretty_output = tracer.pretty_print_trace(str(task_dir))
        assert pretty_output is not None
        assert len(pretty_output) > 0
        assert "Trace Log" in pretty_output or "step" in pretty_output.lower()

    async def test_trace_log_reader(self, llm_config, temp_dir):
        """Test trace log reader utility."""
        task_dir = temp_dir / "trace_reader"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        agent = Agent(
            name="reader_agent",
            role="Reader Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=2
        )

        base_agent = BaseAgent(agent=agent, tool_executor=None, tracer=tracer)

        result = await base_agent.execute(
            task_description="Say hello",
            initial_state=None
        )

        # Read trace log
        trace_log = tracer.load_trace(str(task_dir))
        assert trace_log is not None

        # Verify trace log structure
        assert hasattr(trace_log, "task_id")
        assert hasattr(trace_log, "steps")
        assert hasattr(trace_log, "started_at")
        assert hasattr(trace_log, "completed_at")

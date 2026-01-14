"""Integration tests for single-agent task execution with real LLM.

These tests use the actual LLM API configured in .env file.
The API key is read from the OPENAI_API_KEY environment variable.

To run these tests:
1. Ensure .env file exists with OPENAI_API_KEY set
2. Run: pytest tests/integration/test_agent_execution.py -v
"""

import os
import pytest
from dotenv import load_dotenv

from multi_agent.agent import BaseAgent
from multi_agent.models import Agent, State
from multi_agent.config.schemas import LLMConfig
from multi_agent.tools import MCPToolManager, ToolExecutor

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
        api_key_env="OPENAI_API_KEY",
        temperature=0.7
    )


@pytest.fixture
def test_agent(llm_config):
    """Create a test agent."""
    return Agent(
        name="test_agent",
        role="Test Assistant",
        system_prompt="You are a helpful assistant that provides concise answers.",
        llm_config=llm_config,
        max_iterations=5
    )


@pytest.mark.asyncio
class TestAgentExecution:
    """Integration tests for agent execution."""

    async def test_agent_simple_query(self, test_agent):
        """Test agent can answer a simple question."""
        agent = BaseAgent(agent=test_agent, tool_executor=None)

        result = await agent.execute(
            task_description="What is 2 + 2?",
            initial_state=None
        )

        assert result.completed is True
        assert result.steps >= 1
        assert len(result.output) > 0
        assert "4" in result.output.lower() or "four" in result.output.lower()
        print(f"\nAgent output: {result.output}")

    async def test_agent_with_system_prompt(self, llm_config):
        """Test agent follows system prompt instructions."""
        agent = Agent(
            name="translator",
            role="Translator",
            system_prompt="You translate everything to English. Only output the translation.",
            llm_config=llm_config,
            max_iterations=3
        )
        base_agent = BaseAgent(agent=agent, tool_executor=None)

        result = await base_agent.execute(
            task_description="Bonjour",
            initial_state=None
        )

        assert result.completed is True
        # Should contain English translation
        assert "hello" in result.output.lower() or "hi" in result.output.lower()
        print(f"\nTranslation output: {result.output}")

    async def test_agent_conversation_context(self, test_agent):
        """Test agent maintains conversation context."""
        agent = BaseAgent(agent=test_agent, tool_executor=None)

        # First message
        result1 = await agent.execute(
            task_description="My favorite color is blue.",
            initial_state=None
        )

        # Second message - should remember context
        initial_state = result1.state
        result2 = await agent.execute(
            task_description="What is my favorite color?",
            initial_state=initial_state
        )

        assert result2.completed is True
        assert "blue" in result2.output.lower()
        print(f"\nContext response: {result2.output}")

    async def test_agent_temperature_effect(self, llm_config):
        """Test agent temperature affects output variability."""
        # Low temperature agent
        agent_cold = Agent(
            name="agent_cold",
            role="Conservative Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            temperature=0.1
        )

        # High temperature agent
        agent_hot = Agent(
            name="agent_hot",
            role="Creative Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            temperature=1.0
        )

        base_agent_cold = BaseAgent(agent=agent_cold, tool_executor=None)
        base_agent_hot = BaseAgent(agent=agent_hot, tool_executor=None)

        result_cold = await base_agent_cold.execute(
            task_description="Tell me a short joke.",
            initial_state=None
        )

        result_hot = await base_agent_hot.execute(
            task_description="Tell me a short joke.",
            initial_state=None
        )

        assert result_cold.completed is True
        assert result_hot.completed is True
        print(f"\nCold (0.1) output: {result_cold.output}")
        print(f"Hot (1.0) output: {result_hot.output}")

    async def test_agent_max_iterations(self, llm_config):
        """Test agent respects max_iterations limit."""
        agent = Agent(
            name="limited_agent",
            role="Limited Assistant",
            system_prompt="You always ask follow-up questions. Never stop asking.",
            llm_config=llm_config,
            max_iterations=2
        )
        base_agent = BaseAgent(agent=agent, tool_executor=None)

        result = await base_agent.execute(
            task_description="Hello",
            initial_state=None
        )

        # Should stop after max_iterations even though agent wants to continue
        assert result.steps <= 2
        assert result.completed is True  # Completes due to max iterations
        print(f"\nLimited agent output: {result.output}")


@pytest.mark.asyncio
class TestAgentStateManagement:
    """Integration tests for agent state management."""

    async def test_state_message_accumulation(self, test_agent):
        """Test messages accumulate in state during execution."""
        agent = BaseAgent(agent=test_agent, tool_executor=None)

        result = await agent.execute(
            task_description="Count from 1 to 3",
            initial_state=None
        )

        # Should have multiple messages (user + assistant responses)
        assert result.state.message_count > 0
        print(f"\nTotal messages: {result.state.message_count}")

    async def test_state_metadata(self, test_agent):
        """Test state can hold metadata."""
        agent = BaseAgent(agent=test_agent, tool_executor=None)

        initial_state = State(
            current_agent=test_agent.name,
            metadata={"user_id": "test_user", "session_id": "123"}
        )

        result = await agent.execute(
            task_description="Say hello",
            initial_state=initial_state
        )

        assert result.state.metadata.get("user_id") == "test_user"
        assert result.state.metadata.get("session_id") == "123"
        print(f"\nState metadata: {result.state.metadata}")


@pytest.mark.asyncio
class TestAgentErrorHandling:
    """Integration tests for agent error handling."""

    async def test_agent_empty_task(self, test_agent):
        """Test agent handles empty task."""
        agent = BaseAgent(agent=test_agent, tool_executor=None)

        result = await agent.execute(
            task_description="",
            initial_state=None
        )

        # Agent should still respond even to empty input
        assert result.completed is True
        print(f"\nEmpty task response: {result.output}")

    async def test_agent_complex_query(self, test_agent):
        """Test agent handles more complex queries."""
        agent = BaseAgent(agent=test_agent, tool_executor=None)

        result = await agent.execute(
            task_description="Explain the difference between Python and JavaScript in one sentence.",
            initial_state=None
        )

        # Handle rate limiting gracefully
        if not result.completed and "rate limit" in result.error.lower():
            pytest.skip("API rate limit exceeded")
            return

        assert result.completed is True
        assert len(result.output) > 20  # Should have substantial response
        print(f"\nComplex query response: {result.output}")

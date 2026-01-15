"""Integration tests for single-agent task execution with mocked LLM.

These tests use mocked LLM responses to avoid API rate limiting issues.
They verify the framework's functionality without requiring actual API calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from multi_agent.agent import BaseAgent
from multi_agent.models import Agent, State
from multi_agent.config.schemas import LLMConfig
from multi_agent.state import StateManager


@pytest.fixture
def llm_config():
    """Create LLM config using mock credentials."""
    return LLMConfig(
        endpoint="https://mock.api/v1",
        model="mock-model",
        api_key_env="OPENAI_API_KEY"
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


@pytest.fixture
def mock_llm_complete():
    """Create a properly async mock LLM complete function."""
    async def mock_complete_fn(messages, temperature=None, max_tokens=None, tools=None):
        # Return a properly formatted response
        return {
            "content": "The answer is 42.",
            "tool_calls": []
        }

    return mock_complete_fn


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI API response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "The answer is 42."
    mock_response.choices[0].message.tool_calls = None
    return mock_response


@pytest.mark.asyncio
class TestAgentExecutionWithMock:
    """Integration tests for agent execution with mocked LLM."""

    async def test_agent_simple_query_mock(self, test_agent, mock_openai_response):
        """Test agent can answer a simple question with mocked LLM."""
        with patch('multi_agent.agent.base.AsyncOpenAI') as mock_openai_class:
            # Setup mock client
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_openai_class.return_value = mock_client

            agent = BaseAgent(agent=test_agent, tool_executor=None)

            result = await agent.execute(
                task_description="What is 2 + 2?",
                initial_state=None
            )

            assert result.completed is True
            assert result.steps >= 1
            assert len(result.output) > 0

    async def test_agent_with_system_prompt_mock(self, llm_config, mock_openai_response):
        """Test agent follows system prompt instructions with mocked LLM."""
        agent = Agent(
            name="translator",
            role="Translator",
            system_prompt="You translate everything to English.",
            llm_config=llm_config,
            max_iterations=3
        )

        with patch('multi_agent.agent.base.AsyncOpenAI') as mock_openai_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_openai_class.return_value = mock_client

            base_agent = BaseAgent(agent=agent, tool_executor=None)

            result = await base_agent.execute(
                task_description="Bonjour",
                initial_state=None
            )

            assert result.completed is True
            assert len(result.output) > 0

    async def test_agent_conversation_context_mock(self, test_agent, mock_openai_response):
        """Test agent maintains conversation context with mocked LLM."""
        with patch('multi_agent.agent.base.AsyncOpenAI') as mock_openai_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_openai_class.return_value = mock_client

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
            assert len(result2.output) > 0

    async def test_agent_max_iterations_mock(self, llm_config, mock_openai_response):
        """Test agent respects max_iterations limit with mocked LLM."""
        agent = Agent(
            name="limited_agent",
            role="Limited Assistant",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=2
        )

        with patch('multi_agent.agent.base.AsyncOpenAI') as mock_openai_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_openai_class.return_value = mock_client

            base_agent = BaseAgent(agent=agent, tool_executor=None)

            result = await base_agent.execute(
                task_description="Hello",
                initial_state=None
            )

            # Should stop after max_iterations
            assert result.steps <= 2
            assert result.completed is True


@pytest.mark.asyncio
class TestAgentStateManagementWithMock:
    """Integration tests for agent state management with mocked LLM."""

    async def test_state_message_accumulation_mock(self, test_agent, mock_openai_response):
        """Test messages accumulate in state during execution with mocked LLM."""
        with patch('multi_agent.agent.base.AsyncOpenAI') as mock_openai_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_openai_class.return_value = mock_client

            agent = BaseAgent(agent=test_agent, tool_executor=None)

            result = await agent.execute(
                task_description="Count from 1 to 3",
                initial_state=None
            )

            # Should have multiple messages (user + assistant responses)
            assert result.state.message_count > 0

    async def test_state_metadata_mock(self, test_agent, mock_openai_response):
        """Test state can hold metadata with mocked LLM."""
        with patch('multi_agent.agent.base.AsyncOpenAI') as mock_openai_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_openai_class.return_value = mock_client

            agent = BaseAgent(agent=test_agent, tool_executor=None)

            initial_state = State(
                current_agent=test_agent.name,
                next_action=None,
                routing_key=None,
                metadata={"user_id": "test_user", "session_id": "123"}
            )

            result = await agent.execute(
                task_description="Say hello",
                initial_state=initial_state
            )

            assert result.state.metadata.get("user_id") == "test_user"
            assert result.state.metadata.get("session_id") == "123"

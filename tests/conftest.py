"""Test configuration and fixtures for multi-agent framework tests.

This module provides shared fixtures and configuration for all tests.
"""

import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Check if we should use mock LLM (for CI/CD or when API is unavailable)
USE_MOCK_LLM = os.environ.get("USE_MOCK_LLM", "false").lower() == "true" or \
              os.environ.get("CI", "false") == "true"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def mock_llm_response():
    """Mock LLM response for testing."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Test response: 2 + 2 equals 4."
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 10,
            "total_tokens": 20
        }
    }


@pytest.fixture(scope="session")
def mock_llm_client_class(mock_llm_response):
    """Create a mock LLM client class."""
    class MockLLMClient:
        """Mock LLM client for testing."""

        def __init__(self, base_url, api_key, model, timeout=30, **kwargs):
            self.base_url = base_url
            self.api_key = api_key
            self.model = model
            self.timeout = timeout
            self.call_count = 0

        async def chat(self, messages, **kwargs):
            """Mock chat completion."""
            self.call_count += 1
            # Simulate API delay
            await asyncio.sleep(0.01)

            # Return mock response
            return MagicMock(
                choices=[MagicMock(
                    message=MagicMock(
                        role="assistant",
                        content=f"Mock response #{self.call_count}: The answer is 42."
                    )
                )],
                usage=MagicMock(
                    prompt_tokens=10,
                    completion_tokens=10,
                    total_tokens=20
                )
            )

        async def close(self):
            """Mock close."""
            pass

    return MockLLMClient


@pytest.fixture(scope="function")
def mock_openai_client(monkeypatch, mock_llm_client_class):
    """Mock the OpenAI client for tests."""
    mock_client = mock_llm_client_class(
        base_url="https://mock.api/v1",
        api_key="mock-key",
        model="mock-model"
    )

    # Patch the OpenAI client
    with patch('openai.AsyncOpenAI') as mock_openai:
        mock_openai.return_value = mock_client
        yield mock_client


@pytest.fixture(scope="function")
def llm_config_with_fallback():
    """Create LLM config that works even when API is unavailable."""
    api_key = os.environ.get("OPENAI_API_KEY", "mock-key-for-testing")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.environ.get("DEFAULT_MODEL", "Qwen/Qwen3-8B")

    from multi_agent.config.schemas import LLMConfig

    return LLMConfig(
        endpoint=base_url,
        model=model,
        api_key_env="OPENAI_API_KEY"
    )


@pytest.fixture(scope="function")
def skip_if_no_api_key():
    """Skip test if API key is not available or using mock."""
    if USE_MOCK_LLM:
        pytest.skip("Using mock LLM - skipping real API test")

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("sk-xxxxx"):
        pytest.skip("OPENAI_API_KEY not configured - set a real API key to run this test")


@pytest.fixture(scope="function")
def temp_output_dir(tmp_path):
    """Create a temporary directory for test outputs."""
    output_dir = tmp_path / "test_output"
    output_dir.mkdir(exist_ok=True)
    return output_dir


@pytest.fixture(scope="function")
def mock_tool_executor():
    """Create a mock tool executor."""
    async def mock_executor(tool_call):
        """Mock tool execution."""
        from multi_agent.models import ToolCall

        tool_name = getattr(tool_call, 'tool', 'unknown_tool')
        arguments = getattr(tool_call, 'arguments', {})

        return f"Mock result from {tool_name}: {arguments}"

    return mock_executor


@pytest.fixture(scope="function")
def sample_agent_config():
    """Create a sample agent configuration."""
    from multi_agent.config.schemas import LLMConfig, AgentConfig

    return AgentConfig(
        name="test_agent",
        role="Test Assistant",
        system_prompt="You are a helpful test assistant.",
        llm=LLMConfig(
            endpoint="https://api.example.com/v1",
            model="test-model",
            api_key_env="OPENAI_API_KEY"
        ),
        tools=["test_tool"],
        max_iterations=5
    )


@pytest.fixture(scope="function")
def sample_state():
    """Create a sample state."""
    from multi_agent.models import State, Message

    return State(
        current_agent="test_agent",
        messages=[
            Message(role="user", content="Hello, test agent!")
        ]
    )


@pytest.fixture(scope="function")
def sample_task():
    """Create a sample task."""
    from multi_agent.models import Task

    return Task(
        id="test-task-001",
        description="Test task description",
        assigned_agent="test_agent"
    )


@pytest.fixture(scope="function")
def sample_workflow():
    """Create a sample workflow."""
    from multi_agent.models import Workflow, NodeDef, EdgeDef

    return Workflow(
        name="test_workflow",
        entry_point="start",
        nodes={
            "start": NodeDef(type="agent", agent="test_agent"),
            "end": NodeDef(type="agent", agent="test_agent")
        },
        edges=[
            EdgeDef(from_node="start", to="end")
        ]
    )


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may require API keys)"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (skip with --skip-slow)"
    )
    config.addinivalue_line(
        "markers", "requires_api: marks tests that require real API access"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Mark unit tests
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Mark tests that require API
        if "test_agent_execution" in str(item.fspath):
            item.add_marker(pytest.mark.requires_api)

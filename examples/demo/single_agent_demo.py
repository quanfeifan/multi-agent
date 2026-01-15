#!/usr/bin/env python3
"""
Single Agent Demo - Multi-Agent Framework

This demo shows how to use the multi-agent framework with a single agent.
The agent can have conversations, answer questions, and maintain context.

Run this demo:
    python examples/demo/single_agent_demo.py

Or with custom settings:
    OPENAI_BASE_URL=https://api.siliconflow.cn/v1 \
    OPENAI_API_KEY=your-key \
    DEFAULT_MODEL=Qwen/Qwen3-8B \
    python examples/demo/single_agent_demo.py

Features demonstrated:
    - Single agent creation and configuration
    - Task execution with reasoning loop
    - State management with conversation history
    - Multi-turn conversation with context preservation
    - Error handling and status tracking
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from multi_agent.agent import BaseAgent
from multi_agent.models import Agent
from multi_agent.config.schemas import LLMConfig


# ============================================================================
# Demo Functions
# ============================================================================

async def run_basic_demo():
    """Run basic demo with example tasks."""

    print("=" * 70)
    print("Multi-Agent Framework - Single Agent Demo")
    print("=" * 70)
    print()

    # Check API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxxxx") or api_key.startswith("sk-mock"):
        print("⚠️  OPENAI_API_KEY not set or using placeholder value.")
        print("Please set OPENAI_API_KEY in your .env file.")
        print()
        return

    print(f"✓ API Key configured")
    print(f"✓ Base URL: {os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')}")
    print(f"✓ Model: {os.environ.get('DEFAULT_MODEL', 'gpt-4')}")
    print()

    # Create LLM config
    llm_config = LLMConfig(
        endpoint=os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
        model=os.environ.get("DEFAULT_MODEL", "Qwen/Qwen3-8B"),
        api_key_env="OPENAI_API_KEY"
    )

    # Create agent
    agent = Agent(
        name="demo_agent",
        role="Demo Assistant",
        system_prompt="""You are a helpful demo assistant for the multi-agent framework.
You can help users with:
- Answering questions
- Performing calculations
- Providing information
- Having conversations

Be concise and helpful. Provide clear and accurate answers.""",
        llm_config=llm_config,
        max_iterations=3
    )

    # Create base agent
    base_agent = BaseAgent(agent=agent, tool_executor=None)

    # Example tasks
    tasks = [
        "What is 15 * 27?",
        "What is the capital of France?",
        "Explain what Python is in one sentence.",
    ]

    print("-" * 70)
    print("Running Example Tasks:")
    print("-" * 70)
    print()

    for task in tasks:
        print(f"📝 Task: {task}")

        try:
            result = await base_agent.execute(
                task_description=task,
                initial_state=None
            )

            if result.completed:
                print(f"✓ Steps: {result.steps}")
                print(f"✓ Output: {result.output}")
            else:
                print(f"✗ Failed: {result.error}")
        except Exception as e:
            print(f"✗ Error: {e}")

        print()

    print("=" * 70)
    print("✓ Demo Complete!")
    print("=" * 70)
    print()


async def run_conversation_demo():
    """Demonstrate multi-turn conversation with context preservation."""

    print("=" * 70)
    print("Conversation Demo - Multi-turn with Context")
    print("=" * 70)
    print()

    # Create LLM config
    llm_config = LLMConfig(
        endpoint=os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
        model=os.environ.get("DEFAULT_MODEL", "Qwen/Qwen3-8B"),
        api_key_env="OPENAI_API_KEY"
    )

    # Create agent with memory focus
    agent = Agent(
        name="conversation_agent",
        role="Conversation Assistant",
        system_prompt="""You are a helpful assistant with good memory.
Remember details from our conversation and reference them when relevant.""",
        llm_config=llm_config,
        max_iterations=2
    )

    base_agent = BaseAgent(agent=agent, tool_executor=None)

    # Multi-turn conversation
    turns = [
        "My name is Alice.",
        "What is my name?",
        "What is 10 + 5?",
        "What was my name again?",
    ]

    state = None

    for user_message in turns:
        print(f"👤 User: {user_message}")

        result = await base_agent.execute(
            task_description=user_message,
            initial_state=state
        )

        if result.completed:
            print(f"🤖 Assistant: {result.output}")
            # Preserve state for next turn
            state = result.state
        else:
            print(f"✗ Error: {result.error}")

        print()

    print("=" * 70)
    print("✓ Conversation Demo Complete!")
    print("=" * 70)
    print()


async def run_interactive_mode():
    """Interactive chat mode."""

    print("=" * 70)
    print("Interactive Mode")
    print("=" * 70)
    print("Type your message (or 'quit' to exit)")
    print()

    # Create LLM config
    llm_config = LLMConfig(
        endpoint=os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
        model=os.environ.get("DEFAULT_MODEL", "Qwen/Qwen3-8B"),
        api_key_env="OPENAI_API_KEY"
    )

    # Create agent
    agent = Agent(
        name="interactive_agent",
        role="Assistant",
        system_prompt="You are a helpful assistant. Be concise and friendly.",
        llm_config=llm_config,
        max_iterations=2
    )

    base_agent = BaseAgent(agent=agent, tool_executor=None)
    state = None

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break

            result = await base_agent.execute(
                task_description=user_input,
                initial_state=state
            )

            if result.completed:
                print(f"Assistant: {result.output}")
                state = result.state  # Preserve conversation
            else:
                print(f"Error: {result.error}")

            print()

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            print()


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Single-Agent Demo for Multi-Agent Framework"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--conversation", "-c",
        action="store_true",
        help="Run conversation demo"
    )

    args = parser.parse_args()

    if args.interactive:
        asyncio.run(run_interactive_mode())
    elif args.conversation:
        asyncio.run(run_conversation_demo())
    else:
        asyncio.run(run_basic_demo())

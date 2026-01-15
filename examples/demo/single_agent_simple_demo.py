#!/usr/bin/env python3
"""
Simple Single-Agent Demo (Simplified)

This demo shows how to use the multi-agent framework with a single agent.
The demo focuses on basic conversation and state management features.

Run this demo:
    python examples/demo/single_agent_simple_demo.py

Or with custom settings:
    OPENAI_BASE_URL=https://api.siliconflow.cn/v1 \
    OPENAI_API_KEY=your-key \
    DEFAULT_MODEL=Qwen/Qwen3-8B \
    python examples/demo/single_agent_simple_demo.py
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from multi_agent.agent import BaseAgent
from multi_agent.models import Agent, State
from multi_agent.config.schemas import LLMConfig


# ============================================================================
# Main Demo
# ============================================================================

async def run_demo():
    """Run the single-agent demo."""

    print("=" * 70)
    print("Multi-Agent Framework - Single Agent Demo (Simplified)")
    print("=" * 70)
    print()

    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxxxx") or api_key.startswith("sk-mock"):
        print("⚠️  WARNING: OPENAI_API_KEY not set or using placeholder value.")
        print("Please set OPENAI_API_KEY in your .env file or environment.")
        print()
        print("Example:")
        print("  export OPENAI_API_KEY=your-actual-api-key")
        print("  export OPENAI_BASE_URL=https://api.siliconflow.cn/v1")
        print("  export DEFAULT_MODEL=Qwen/Qwen3-8B")
        print()
        return

    print(f"✓ API Key found")
    print(f"✓ Base URL: {os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')}")
    print(f"✓ Model: {os.environ.get('DEFAULT_MODEL', 'gpt-4')}")
    print()

    # Create LLM config
    llm_config = LLMConfig(
        endpoint=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
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

Be concise and helpful in your responses. Provide clear and accurate answers.""",
        llm_config=llm_config,
        max_iterations=3
    )

    # Create base agent
    base_agent = BaseAgent(agent=agent, tool_executor=None)

    # Example tasks
    example_tasks = [
        "What is 15 * 27? Please calculate and show the result.",
        "What is the capital of France?",
        "Explain what Python programming is in one sentence.",
        "What are 3 tips for writing good code?",
    ]

    print("-" * 70)
    print("Example Tasks:")
    for i, task in enumerate(example_tasks, 1):
        print(f"  {i}. {task}")
    print("-" * 70)
    print()

    print("=" * 70)
    print("Running Agent Tasks:")
    print("=" * 70)
    print()

    for task in example_tasks:
        print(f"📝 Task: {task}")
        print("-" * 70)

        try:
            result = await base_agent.execute(
                task_description=task,
                initial_state=None
            )

            if result.completed:
                print(f"✓ Completed in {result.steps} step(s)")
                print(f"📤 Output: {result.output}")
                print(f"📊 Messages: {result.state.message_count}")
            else:
                print(f"✗ Failed: {result.error}")
        except Exception as e:
            print(f"✗ Error: {e}")

        print()

    print("=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print()
    print("Key Features Demonstrated:")
    print("  ✓ Single agent creation and configuration")
    print("  ✓ Task execution with reasoning loop")
    print("  ✓ State management with message history")
    print("  ✓ Error handling and status tracking")
    print()


# ============================================================================
# Interactive Mode
# ============================================================================

async def run_interactive_mode():
    """Run interactive mode where user can input their own tasks."""

    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxxxx") or api_key.startswith("sk-mock"):
        print("⚠️  OPENAI_API_KEY not set. Please set it to run interactive mode.")
        print()
        print("To use interactive mode, set your API key:")
        print("  export OPENAI_API_KEY=your-actual-api-key")
        return

    # Create LLM config
    llm_config = LLMConfig(
        endpoint=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        model=os.environ.get("DEFAULT_MODEL", "Qwen/Qwen3-8B"),
        api_key_env="OPENAI_API_KEY"
    )

    # Create agent
    agent = Agent(
        name="interactive_agent",
        role="Interactive Assistant",
        system_prompt="""You are a helpful interactive assistant.
You can answer questions, provide information, and have conversations.
Be concise and helpful.""",
        llm_config=llm_config,
        max_iterations=3
    )

    base_agent = BaseAgent(agent=agent, tool_executor=None)

    print("=" * 70)
    print("Interactive Mode")
    print("=" * 70)
    print("Type your questions or tasks (or 'quit' to exit)")
    print()

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break

            print(f"🤖 Processing: {user_input}")

            result = await base_agent.execute(
                task_description=user_input,
                initial_state=None
            )

            if result.completed:
                print(f"🤖 Assistant: {result.output}")
            else:
                print(f"✗ Error: {result.error}")

            print()

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            print()


# ============================================================================
# Conversation Demo (Multi-turn)
# ============================================================================

async def run_conversation_demo():
    """Demonstrate conversation with context preservation."""

    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxxxx") or api_key.startswith("sk-mock"):
        print("⚠️  OPENAI_API_KEY not set. Please set it to run conversation demo.")
        return

    print("=" * 70)
    print("Conversation Demo - Multi-turn with Context")
    print("=" * 70)
    print()

    # Create LLM config
    llm_config = LLMConfig(
        endpoint=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
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

    # Simulated conversation
    conversation = [
        "My name is Alice and I love Python programming.",
        "What is my name?",
        "What programming language do I like?",
        "What is 2 + 2?",
    ]

    state = None

    for user_message in conversation:
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
    print("Conversation Demo Complete!")
    print("=" * 70)


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Single-Agent Demo for Multi-Agent Framework (Simplified)"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--conversation", "-c",
        action="store_true",
        help="Run conversation demo with context"
    )

    args = parser.parse_args()

    if args.interactive:
        asyncio.run(run_interactive_mode())
    elif args.conversation:
        asyncio.run(run_conversation_demo())
    else:
        asyncio.run(run_demo())

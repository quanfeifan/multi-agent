#!/usr/bin/env python3
"""
Single Agent Demo with Tool Calling

This demo shows how to use the multi-agent framework with a single agent
that can call tools through MCP (Model Context Protocol).

Usage:
    # Terminal 1: Start the tool server
    PYTHONPATH=src python3 examples/demo/tools_server.py

    # Terminal 2: Run the demo
    PYTHONPATH=src python3 examples/demo/single_agent_tools_demo.py
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from multi_agent.agent import BaseAgent
from multi_agent.models import Agent, MCPServer
from multi_agent.models.tool import MCPServerConfigStdio
from multi_agent.config.schemas import LLMConfig, AgentConfig
from multi_agent.tools import MCPToolManager, ToolExecutor


async def main():
    print("=" * 70)
    print("Multi-Agent Framework - Tool Calling Demo")
    print("=" * 70)
    print()

    # Check API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxxxx"):
        print("⚠️  Set OPENAI_API_KEY in .env file")
        return

    # Create LLM config
    llm_config = LLMConfig(
        endpoint=os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
        model=os.environ.get("DEFAULT_MODEL", "Qwen/Qwen3-8B"),
        api_key_env="OPENAI_API_KEY"
    )

    # Create agent config
    agent_config = AgentConfig(
        name="demo_agent",
        role="Assistant",
        system_prompt="""You are a helpful assistant with access to tools.
Available tools:
- calculator: Perform math calculations
- read_file: Read file contents
- list_files: List files in directory
- get_time: Get current time

When you need to use a tool, call it with appropriate arguments.""",
        llm_config=llm_config,
        tools=["calculator", "read_file", "list_files", "get_time"],
        max_iterations=5
    )

    # Create tool manager
    tool_manager = MCPToolManager()

    # Add demo tool server (stdio)
    demo_server = MCPServer(
        name="demo_tools",
        transport="stdio",
        config=MCPServerConfigStdio(
            command=sys.executable,
            args=["examples/demo/tools_server.py"]
        ),
        description="Demo tools server",
        enabled=True
    )

    try:
        await tool_manager.add_server(demo_server)

        # List available tools
        tools = tool_manager.list_tools()
        print(f"✓ Connected to {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")
        print()

        # Create agent
        agent = Agent(
            name=agent_config.name,
            role=agent_config.role,
            system_prompt=agent_config.system_prompt,
            llm_config=agent_config.llm_config,
            tools=agent_config.tools,
            max_iterations=agent_config.max_iterations
        )

        tool_executor = ToolExecutor(tool_manager)
        base_agent = BaseAgent(agent=agent, tool_executor=tool_executor)

        # Test tasks
        tasks = [
            "What is 25 * 34?",
            "What is the current time?",
        ]

        for task in tasks:
            print(f"📝 Task: {task}")
            result = await base_agent.execute(task, initial_state=None)

            if result.completed:
                print(f"✓ Output: {result.output}")
            else:
                print(f"✗ Failed: {result.error}")
            print()

    finally:
        await tool_manager.close()


if __name__ == "__main__":
    asyncio.run(main())

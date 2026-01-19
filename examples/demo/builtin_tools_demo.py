#!/usr/bin/env python3
"""Demo of built-in tools for multi-agent framework.

This demo shows how to use the built-in tool library with the new dual-track
architecture that supports both builtin tools (direct Python execution) and
MCP tools (external services via JSON-RPC).

For a complete LLM integration demo showing how an LLM receives user input,
decides which tools to call, executes them, and synthesizes results, see:
    examples/demo/llm_with_builtin_tools_demo.py
"""

import asyncio
from pathlib import Path

from multi_agent.tools import ToolExecutor
from multi_agent.tools.builtin import (
    BuiltinRegistry,
    register_builtin_tools,
    register_file_tools,
    register_programming_tools,
    register_system_tools,
)


async def demo_basic_usage():
    """Demonstrate basic tool registry usage."""
    print("=" * 60)
    print("Built-in Tools Demo (Dual-Track Architecture)")
    print("=" * 60)

    # Register all builtin tools
    registry = register_builtin_tools()

    # List all tools
    tools = registry.list_all()
    print(f"\nTotal tools registered: {len(tools)}")
    print("\nAvailable tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")

    return registry


async def demo_file_tools(registry: BuiltinRegistry):
    """Demonstrate file tools."""
    print("\n" + "=" * 60)
    print("File Tools Demo")
    print("=" * 60)

    # Create a test file
    write_tool = registry.get("file_write")
    result = await write_tool.execute(path="demo_test.txt", content="Hello from built-in tools!")
    print(f"\n✓ {result.data}")

    # Read the file
    read_tool = registry.get("file_read")
    result = await read_tool.execute(path="demo_test.txt")
    print(f"\n✓ File content: {result.data}")

    # List directory
    list_tool = registry.get("file_list")
    result = await list_tool.execute(path=".")
    print(f"\n✓ Directory listing (first 5 lines):")
    for line in result.data.split("\n")[:5]:
        print(f"  {line}")


async def demo_programming_tools(registry: BuiltinRegistry):
    """Demonstrate programming tools."""
    print("\n" + "=" * 60)
    print("Programming Tools Demo")
    print("=" * 60)

    # Calculate tool
    calc_tool = registry.get("calculate")

    expressions = [
        "2 + 2",
        "2 ** 10",
        "math.sqrt(144)",
        "math.pi * 2",
    ]

    for expr in expressions:
        result = await calc_tool.execute(expression=expr)
        print(f"\n✓ {expr} = {result.data}")


async def demo_system_tools(registry: BuiltinRegistry):
    """Demonstrate system tools."""
    print("\n" + "=" * 60)
    print("System Tools Demo")
    print("=" * 60)

    # Get time
    time_tool = registry.get("system_get_time")
    result = await time_tool.execute()
    print(f"\n✓ Current time: {result.data}")

    # Get environment variable
    env_tool = registry.get("system_get_env")
    result = await env_tool.execute(name="PATH")
    print(f"\n✓ PATH length: {len(result.data)} characters")


async def demo_llm_format(registry: BuiltinRegistry):
    """Demonstrate LLM function calling format."""
    print("\n" + "=" * 60)
    print("LLM Function Calling Format Demo")
    print("=" * 60)

    # Export tools in LLM format (OpenAI compatible)
    llm_list = registry.to_llm_list()
    print(f"\n✓ Exported {len(llm_list)} tools in LLM format")
    print("\nExample tool definition:")
    if llm_list:
        first_tool = llm_list[0]
        print(f"  Name: {first_tool['function']['name']}")
        print(f"  Type: {first_tool['type']}")
        print(f"  Description: {first_tool['function']['description']}")


async def demo_parallel_execution():
    """Demonstrate parallel tool execution."""
    print("\n" + "=" * 60)
    print("Parallel Execution Demo")
    print("=" * 60)

    # Create executor with builtin tools
    builtin_registry = register_builtin_tools()
    executor = ToolExecutor(manager=None, builtin_registry=builtin_registry)

    # Simulate LLM tool calls (parallel execution)
    tool_calls = [
        {
            "id": "call_1",
            "function": {
                "name": "calculate",
                "arguments": '{"expression": "2 ** 8"}'
            }
        },
        {
            "id": "call_2",
            "function": {
                "name": "calculate",
                "arguments": '{"expression": "math.sqrt(1024)"}'
            }
        },
        {
            "id": "call_3",
            "function": {
                "name": "system_get_time",
                "arguments": '{}'
            }
        }
    ]

    print("\n✓ Executing 3 tools in parallel...")
    results = await executor.execute_batch(tool_calls)

    print("\n✓ Results:")
    for result in results:
        content = result["content"][0]["text"]
        print(f"  [{result['tool_call_id']}]: {content[:50]}...")


async def demo_tool_executor():
    """Demonstrate unified ToolExecutor with builtin and MCP tools."""
    print("\n" + "=" * 60)
    print("ToolExecutor Demo (Unified Builtin + MCP)")
    print("=" * 60)

    # Create executor with builtin tools only (MCP manager is optional)
    builtin_registry = register_builtin_tools()
    executor = ToolExecutor(manager=None, builtin_registry=builtin_registry)

    # Execute single builtin tool
    print("\n✓ Single execution: calculate(2 * 21)")
    result = await executor.execute("calculate", {"expression": "2 * 21"})
    print(f"  Result: {result['content'][0]['text']}")

    # Execute another builtin tool
    print("\n✓ Single execution: system_get_time()")
    result = await executor.execute("system_get_time", {})
    print(f"  Result: {result['content'][0]['text']}")


async def demo_category_registration():
    """Demonstrate category-based tool registration."""
    print("\n" + "=" * 60)
    print("Category Registration Demo")
    print("=" * 60)

    # Register tools by category
    from multi_agent.tools.builtin import BuiltinRegistry

    registry = BuiltinRegistry()

    # Register file tools only
    file_tools = register_file_tools()
    for tool in file_tools:
        registry.register(tool)

    print(f"\n✓ Registered {len(file_tools)} file tools:")
    for tool in file_tools:
        print(f"  - {tool.name}")

    # Register programming tools
    prog_tools = register_programming_tools()
    for tool in prog_tools:
        registry.register(tool)

    print(f"\n✓ Registered {len(prog_tools)} programming tools:")
    for tool in prog_tools:
        print(f"  - {tool.name}")

    # Register system tools
    sys_tools = register_system_tools()
    for tool in sys_tools:
        registry.register(tool)

    print(f"\n✓ Registered {len(sys_tools)} system tools:")
    for tool in sys_tools:
        print(f"  - {tool.name}")

    print(f"\n✓ Total tools in registry: {registry.list_all()}")


async def main():
    """Run all demos."""
    try:
        # Basic usage
        registry = await demo_basic_usage()

        # Tool categories
        await demo_file_tools(registry)
        await demo_programming_tools(registry)
        await demo_system_tools(registry)

        # Search and format
        await demo_llm_format(registry)

        # Parallel execution
        await demo_parallel_execution()

        # ToolExecutor
        await demo_tool_executor()

        # Category registration
        await demo_category_registration()

        print("\n" + "=" * 60)
        print("Demo Complete!")
        print("=" * 60)

    finally:
        # Cleanup
        demo_file = Path("demo_test.txt")
        if demo_file.exists():
            demo_file.unlink()


if __name__ == "__main__":
    asyncio.run(main())

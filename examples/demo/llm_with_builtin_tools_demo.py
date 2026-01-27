#!/usr/bin/env python3
"""
LLM with Builtin Tools Demo

This demo shows how an LLM can use builtin tools directly:
1. LLM receives user input
2. LLM decides which tools to call
3. Tools are executed in parallel
4. LLM synthesizes results to answer

Usage:
    PYTHONPATH=src python3 examples/demo/llm_with_builtin_tools_demo.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

# Disable proxy to avoid unsupported protocol error (socks://)
# httpx only supports http://, https://, and socks5://
proxy_keys = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]
for key in proxy_keys:
    if key in os.environ:
        del os.environ[key]

from multi_agent.agent.base import LLMClient
from multi_agent.config.schemas import LLMConfig
from multi_agent.tools import ToolExecutor
from multi_agent.tools.builtin import register_builtin_tools


async def main():
    print("=" * 70)
    print("LLM with Builtin Tools Demo")
    print("=" * 70)
    print()

    # Check API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxxxx"):
        print("⚠️  Set OPENAI_API_KEY in .env file")
        return

    # Create LLM config (same as single_agent_tools_demo.py)
    llm_config = LLMConfig(
        endpoint=os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
        model=os.environ.get("DEFAULT_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
        api_key_env="OPENAI_API_KEY"
    )

    print(f"✓ Using model: {llm_config.model}")
    print(f"✓ Endpoint: {llm_config.endpoint}")
    print()

    # Initialize LLM client
    llm_client = LLMClient(llm_config)

    # Initialize tool executor with builtin tools
    builtin_registry = register_builtin_tools()
    tool_executor = ToolExecutor(manager=None, builtin_registry=builtin_registry)

    # Get tools in LLM format
    tools = builtin_registry.to_llm_list()
    print(f"✓ Available tools: {[t['function']['name'] for t in tools]}")
    print()

    # Conversation history
    messages = [
        {
            "role": "system",
            "content": """You are a helpful assistant with access to various tools.
When the user asks questions that require calculations, file operations, or system information, use the appropriate tools.
After receiving tool results, synthesize them into a clear and helpful answer.

IMPORTANT: When the user asks multiple questions or requests multiple operations that are independent of each other, you should call ALL relevant tools in a SINGLE response. This allows parallel execution for better efficiency.
For example:
- "Calculate X and also tell me the time" → Call BOTH calculate AND system_get_time tools
- "List files and calculate 2+2" → Call BOTH file_list AND calculate tools

Only call tools one at a time when there's a clear dependency (e.g., "read the file and then tell me its size")."""
        }
    ]

    # Example questions that will trigger tool calls
    questions = [
        "Calculate 2 raised to the power of 10.",

        "Calculate 15 * 27 and also tell me the current time.",
    ]

    for question in questions:
        print("=" * 70)
        print(f"👤 User: {question}")
        print("-" * 70)

        # Add user message to conversation
        messages.append({"role": "user", "content": question})

        # Get LLM response with tools
        print("🤖 LLM thinking...")
        response = await llm_client.complete(messages, tools=tools)

        # Check if LLM wants to call tools
        if response["tool_calls"]:
            print(f"✓ LLM decided to call {len(response['tool_calls'])} tool(s):")

            # Build tool_calls list for executor
            tool_calls = []
            for tc in response["tool_calls"]:
                print(f"  - {tc['tool']}({tc['arguments']})")
                tool_calls.append({
                    "id": tc["id"],
                    "function": {
                        "name": tc["tool"],
                        "arguments": str(tc["arguments"]) if not isinstance(tc["arguments"], dict) 
                            else tc["arguments"]
                    }
                })

            # Add assistant message with tool calls to conversation
            assistant_message = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["tool"],
                            "arguments": json.dumps(tc["arguments"]) if isinstance(tc["arguments"], dict)
                                else str(tc["arguments"])
                        }
                    }
                    for tc in response["tool_calls"]
                ]
            }
            # Only include content if it's not None or empty string
            if response.get("content"):
                assistant_message["content"] = response["content"]
            messages.append(assistant_message)

            # Execute tools in parallel
            print("\n🔧 Executing tools...")
            results = await tool_executor.execute_batch(tool_calls)

            # Send tool results back to LLM
            print("\n📊 Tool results:")
            for result in results:
                call_id = result["tool_call_id"]
                content = result["content"][0]["text"]
                # Truncate long content for display
                display_content = content[:100] + "..." if len(content) > 100 else content
                print(f"  [{call_id}]: {display_content}")

                # Add tool result message to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": content
                })

            # Get final answer from LLM
            # Note: Don't pass tools parameter on follow-up calls after tool execution
            print("\n🤖 LLM synthesizing answer...")
            final_response = await llm_client.complete(messages)

            # Add assistant response to conversation
            messages.append({
                "role": "assistant",
                "content": final_response["content"] or ""
            })

            print(f"\n✅ Assistant: {final_response['content']}")

        else:
            # LLM answered directly without tools
            print(f"✅ Assistant: {response['content']}")
            messages.append({
                "role": "assistant",
                "content": response["content"]
            })

        print()

    print("=" * 70)
    print("Demo Complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

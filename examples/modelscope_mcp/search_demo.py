#!/usr/bin/env python3
"""智谱搜索MCP示例 - 展示LLM如何调用智谱搜索MCP工具.

This example demonstrates:
1. Loading Zhipu Web Search MCP server from configuration
2. Using Web Search tools for intelligent search and retrieval
3. Direct tool execution without LLM wrapper
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Load .env file
from dotenv import load_dotenv
load_dotenv()

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from multi_agent.models.tool import MCPServer, MCPServerConfigSSE, MCPServerConfigStdio
from multi_agent.tools import ToolExecutor
from multi_agent.tools.builtin import register_builtin_tools
from multi_agent.tools.mcp_manager import MCPToolManager


def config_to_server(name: str, config):
    """Convert MCPServerConfig to MCPServer model."""
    if config.transport == "stdio":
        server_config = MCPServerConfigStdio(
            command=config.config.command,
            args=config.config.args,
            env=config.config.env,
        )
    elif config.transport == "sse":
        server_config = MCPServerConfigSSE(
            url=config.config.url,
            headers=config.config.headers,
        )
    else:
        raise ValueError(f"Unsupported transport: {config.transport}")

    return MCPServer(
        name=name,
        transport=config.transport,
        config=server_config,
        description=config.description,
        enabled=config.enabled,
    )


async def verify_connection(manager: MCPToolManager) -> bool:
    """验证MCP服务器连接并显示可用工具.

    Args:
        manager: MCPToolManager实例

    Returns:
        True if Web Search tools available
    """
    print("🔍 验证MCP服务器连接...\n")

    tools = manager.list_tools()

    if not tools:
        print("❌ 未发现MCP工具")
        print("\n请检查:")
        print("1. ~/.multi-agent/config/mcp_servers.yaml 文件是否存在")
        print("2. 配置文件中是否启用了智谱搜索MCP服务器")
        print("3. 智谱API密钥是否已配置")
        return False

    print(f"✅ 发现 {len(tools)} 个MCP工具:\n")
    for tool in tools:
        print(f"  • {tool.name}: {tool.description[:80]}...")

    # 检查是否有搜索工具
    search_tools = [t for t in tools if "search" in t.name.lower() or "web" in t.name.lower()]
    if search_tools:
        print(f"\n✅ 搜索工具已配置: {', '.join([t.name for t in search_tools])}")
        return True
    else:
        print("\n⚠️  未发现搜索工具，请检查Web Search服务器配置")
        return False


async def demo_basic_search(executor: ToolExecutor) -> None:
    """演示基本搜索."""
    print("\n" + "=" * 60)
    print("🔍 基本搜索演示")
    print("=" * 60)
    print()

    # Get the manager to access transports directly
    manager = executor.manager
    if manager is None:
        print("❌ MCP manager not available")
        return

    # Check if web-search transport is available
    if "web-search" not in manager.transports:
        print("❌ web-search transport not available")
        return

    transport = manager.transports["web-search"]

    try:
        # Direct tool call using transport
        from multi_agent.tools.mcp_client import MCPMessage

        message = MCPMessage(
            method="tools/call",
            params={
                "name": "webSearchPro",  # Use actual tool name from web-search server
                "arguments": {"search_query": "人工智能最新进展 2025"}  # Correct parameter name
            }
        )

        response = await transport.send_message(message)

        print("-" * 60)
        print("📝 搜索结果:")
        print()

        if response.result:
            if isinstance(response.result, dict):
                if "content" in response.result:
                    for content_item in response.result["content"]:
                        if content_item.get("type") == "text":
                            text = content_item.get("text", "")
                            print(text)
                else:
                    print(response.result)
            else:
                print(response.result)
        else:
            print(f"Response: {response.model_dump()}")
        print()

    except TimeoutError as e:
        print(f"❌ 搜索超时: {e}")
        print("提示: 检查网络连接或增加超时时间")
    except RuntimeError as e:
        if "API key" in str(e).lower() or "authorization" in str(e).lower():
            print(f"❌ API密钥错误: {e}")
            print("提示: 请检查智谱API密钥是否正确设置")
        else:
            print(f"❌ 搜索失败: {e}")
    except Exception as e:
        print(f"❌ 搜索失败: {e}")
        print("提示: 确保智谱API密钥已正确配置")


async def demo_tech_search(executor: ToolExecutor) -> None:
    """演示技术搜索."""
    print("\n" + "=" * 60)
    print("💻 技术搜索演示")
    print("=" * 60)
    print()

    manager = executor.manager
    if manager is None or "web-search" not in manager.transports:
        print("❌ web-search transport not available")
        return

    transport = manager.transports["web-search"]

    try:
        from multi_agent.tools.mcp_client import MCPMessage

        message = MCPMessage(
            method="tools/call",
            params={
                "name": "webSearchPro",  # Use actual tool name from web-search server
                "arguments": {"search_query": "Python asyncio 异步编程最佳实践"}  # Correct parameter name
            }
        )

        response = await transport.send_message(message)

        print("-" * 60)
        print("📝 技术搜索结果:")
        print()

        if response.result:
            if isinstance(response.result, dict) and "content" in response.result:
                for content_item in response.result["content"]:
                    if content_item.get("type") == "text":
                        text = content_item.get("text", "")
                        print(text[:500])  # Limit output
                        if len(text) > 500:
                            print("...")
            else:
                print(response.result)
        print()

    except Exception as e:
        print(f"⚠️  技术搜索演示跳过: {e}")


async def demo_news_search(executor: ToolExecutor) -> None:
    """演示新闻搜索."""
    print("\n" + "=" * 60)
    print("📰 新闻搜索演示")
    print("=" * 60)
    print()

    manager = executor.manager
    if manager is None or "web-search" not in manager.transports:
        print("❌ web-search transport not available")
        return

    transport = manager.transports["web-search"]

    try:
        from multi_agent.tools.mcp_client import MCPMessage

        message = MCPMessage(
            method="tools/call",
            params={
                "name": "webSearchPro",  # Use actual tool name from web-search server
                "arguments": {"search_query": "最新科技新闻 AI"}  # Correct parameter name
            }
        )

        response = await transport.send_message(message)

        print("-" * 60)
        print("📝 新闻搜索结果:")
        print()

        if response.result:
            if isinstance(response.result, dict) and "content" in response.result:
                for content_item in response.result["content"]:
                    if content_item.get("type") == "text":
                        text = content_item.get("text", "")
                        print(text[:500])
                        if len(text) > 500:
                            print("...")
            else:
                print(response.result)
        print()

    except Exception as e:
        print(f"⚠️  新闻搜索演示跳过: {e}")


async def demo_academic_search(executor: ToolExecutor) -> None:
    """演示学术搜索."""
    print("\n" + "=" * 60)
    print("🎓 学术搜索演示")
    print("=" * 60)
    print()

    manager = executor.manager
    if manager is None or "web-search" not in manager.transports:
        print("❌ web-search transport not available")
        return

    transport = manager.transports["web-search"]

    try:
        from multi_agent.tools.mcp_client import MCPMessage

        message = MCPMessage(
            method="tools/call",
            params={
                "name": "webSearchPro",  # Use actual tool name from web-search server
                "arguments": {"search_query": "transformer architecture deep learning"}  # Correct parameter name
            }
        )

        response = await transport.send_message(message)

        print("-" * 60)
        print("📝 学术搜索结果:")
        print()

        if response.result:
            if isinstance(response.result, dict) and "content" in response.result:
                for content_item in response.result["content"]:
                    if content_item.get("type") == "text":
                        text = content_item.get("text", "")
                        print(text[:500])
                        if len(text) > 500:
                            print("...")
            else:
                print(response.result)
        print()

    except Exception as e:
        print(f"⚠️  学术搜索演示跳过: {e}")


async def main() -> int:
    """主函数.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(description="智谱搜索MCP示例")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="验证MCP服务器连接而不运行完整示例",
    )
    parser.add_argument(
        "--demo",
        choices=["basic", "tech", "news", "academic", "all"],
        default="all",
        help="选择要运行的演示 (默认: all)",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="自定义搜索查询",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("ModelScope MCP示例: 智谱搜索服务")
    print("=" * 60)
    print()

    # 初始化ToolExecutor
    print("📦 初始化ToolExecutor...")
    from multi_agent.config.loader import load_mcp_servers_config

    manager = MCPToolManager()
    servers_file = Path('/home/yzq/package/multi-agent/examples/config/mcp_servers_modelscope.yaml')

    # Load MCP servers from config
    if servers_file.exists():
        try:
            servers_config = load_mcp_servers_config(servers_file)
            for name, config in servers_config.items():
                if config.enabled:
                    try:
                        server = config_to_server(name, config)
                        await manager.add_server(server)
                    except Exception as e:
                        print(f"  ⚠️  Failed to load {name}: {e}")
        except Exception as e:
            print(f"  ⚠️  Failed to load config: {e}")

    builtin_registry = register_builtin_tools()
    executor = ToolExecutor(manager=manager, builtin_registry=builtin_registry)

    # 验证模式
    if args.verify:
        success = await verify_connection(manager)
        await manager.close()
        return 0 if success else 1

    # 列出可用工具
    mcp_tools = manager.list_tools()
    builtin_tools = builtin_registry.list_all()
    print(f"✅ 已加载 {len(mcp_tools) + len(builtin_tools)} 个工具 (builtin + MCP)\n")

    # 运行演示
    try:
        # 自定义查询
        if args.query:
            print("\n" + "=" * 60)
            print(f"🔍 自定义搜索: {args.query}")
            print("=" * 60)
            print()
            result = await executor.execute("web-search", {"query": args.query, "num_results": 5})

            print("-" * 60)
            print("📝 搜索结果:")
            print()
            if "content" in result:
                for content_item in result["content"]:
                    if content_item.get("type") == "text":
                        text = content_item.get("text", "")
                        print(text)
            print()

        # 预设演示
        elif args.demo == "all" or args.demo == "basic":
            await demo_basic_search(executor)

        if args.demo == "all" or args.demo == "tech":
            await demo_tech_search(executor)

        if args.demo == "all" or args.demo == "news":
            await demo_news_search(executor)

        if args.demo == "all" or args.demo == "academic":
            await demo_academic_search(executor)

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        await manager.close()



    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

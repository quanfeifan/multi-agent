#!/usr/bin/env python3
"""高德地图MCP示例 - 展示LLM如何调用高德地图MCP工具.

This example demonstrates:
1. Loading Amap MCP server from configuration
2. Using Amap tools for geocoding, weather, and route planning
3. Direct tool execution without LLM wrapper
"""

import argparse
import asyncio
import sys
from pathlib import Path

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
        True if Amap tools available
    """
    print("🔍 验证MCP服务器连接...\n")

    tools = manager.list_tools()

    if not tools:
        print("❌ 未发现MCP工具")
        print("\n请检查:")
        print("1. ~/.multi-agent/config/mcp_servers.yaml 文件是否存在")
        print("2. 配置文件中是否启用了高德MCP服务器")
        print("3. Node.js和npx是否已安装")
        print("4. 高德API密钥是否已配置")
        return False

    print(f"✅ 发现 {len(tools)} 个MCP工具:\n")
    for tool in tools:
        print(f"  • {tool.name}: {tool.description[:60]}...")

    # 检查是否有高德工具
    amap_tools = [t for t in tools if "map" in t.name.lower() or "geo" in t.name.lower() or "weather" in t.name.lower()]
    if amap_tools:
        print(f"\n✅ 高德地图工具已配置: {', '.join([t.name for t in amap_tools])}")
        return True
    else:
        print("\n⚠️  未发现高德地图工具，请检查Amap服务器配置")
        return False


async def demo_geocoding(executor: ToolExecutor) -> None:
    """演示地理编码 - 地址转坐标."""
    print("\n" + "=" * 60)
    print("📍 地理编码演示: 地址 → 经纬度")
    print("=" * 60)
    print()

    try:
        result = await executor.execute(
            "maps_geo",
            {"address": "北京市朝阳区望京", "city": "北京"}
        )

        print("-" * 60)
        print("📝 地理编码结果:")
        print()

        if "content" in result:
            for content_item in result["content"]:
                if content_item.get("type") == "text":
                    text = content_item.get("text", "")
                    print(text)
        print()

    except TimeoutError as e:
        print(f"❌ 地理编码超时: {e}")
        print("提示: 检查网络连接或增加超时时间")
    except RuntimeError as e:
        if "API key" in str(e).lower() or "invalid" in str(e).lower():
            print(f"❌ API密钥错误: {e}")
            print("提示: 请检查 AMAP_MAPS_API_KEY 环境变量是否正确设置")
        else:
            print(f"❌ 地理编码失败: {e}")
    except Exception as e:
        print(f"❌ 地理编码失败: {e}")
        print("提示: 确保高德API密钥已正确配置")


async def demo_weather(executor: ToolExecutor) -> None:
    """演示天气查询."""
    print("\n" + "=" * 60)
    print("🌤️  天气查询演示")
    print("=" * 60)
    print()

    try:
        result = await executor.execute(
            "maps_weather",
            {"city": "北京", "extensions": "all"}
        )

        print("-" * 60)
        print("📝 天气查询结果:")
        print()

        if "content" in result:
            for content_item in result["content"]:
                if content_item.get("type") == "text":
                    text = content_item.get("text", "")
                    print(text)
        print()

    except TimeoutError as e:
        print(f"❌ 天气查询超时: {e}")
        print("提示: 检查网络连接或增加超时时间")
    except RuntimeError as e:
        if "API key" in str(e).lower() or "invalid" in str(e).lower():
            print(f"❌ API密钥错误: {e}")
            print("提示: 请检查 AMAP_MAPS_API_KEY 环境变量是否正确设置")
        else:
            print(f"❌ 天气查询失败: {e}")
    except Exception as e:
        print(f"❌ 天气查询失败: {e}")


async def demo_regeocode(executor: ToolExecutor) -> None:
    """演示逆地理编码 - 坐标转地址."""
    print("\n" + "=" * 60)
    print("📍 逆地理编码演示: 经纬度 → 地址")
    print("=" * 60)
    print()

    try:
        # 使用天安门坐标
        result = await executor.execute(
            "maps_regeocode",
            {"location": "116.397428,39.90923", "extensions": "base"}
        )

        print("-" * 60)
        print("📝 逆地理编码结果:")
        print()

        if "content" in result:
            for content_item in result["content"]:
                if content_item.get("type") == "text":
                    text = content_item.get("text", "")
                    print(text)
        print()

    except TimeoutError as e:
        print(f"❌ 逆地理编码超时: {e}")
        print("提示: 检查网络连接或增加超时时间")
    except RuntimeError as e:
        if "API key" in str(e).lower() or "invalid" in str(e).lower():
            print(f"❌ API密钥错误: {e}")
            print("提示: 请检查 AMAP_MAPS_API_KEY 环境变量是否正确设置")
        else:
            print(f"❌ 逆地理编码失败: {e}")
    except Exception as e:
        print(f"❌ 逆地理编码失败: {e}")


async def demo_route_planning(executor: ToolExecutor) -> None:
    """演示路径规划."""
    print("\n" + "=" * 60)
    print("🛣️  路径规划演示")
    print("=" * 60)
    print()

    try:
        result = await executor.execute(
            "maps_direction_{{mode}}",  # 可能需要根据实际工具名调整
            {
                "origin": "116.481028,39.989643",  # 北京西站附近
                "destination": "116.397428,39.90923",  # 天安门
                "strategy": "10"  # 速度优先
            }
        )

        print("-" * 60)
        print("📝 路径规划结果:")
        print()

        if "content" in result:
            for content_item in result["content"]:
                if content_item.get("type") == "text":
                    text = content_item.get("text", "")
                    print(text[:500])
                    if len(text) > 500:
                        print("...")
        print()

    except Exception as e:
        print(f"⚠️  路径规划演示跳过: {e}")
        print("提示: 路径规划工具名称可能需要根据实际MCP服务器调整")


async def main() -> None:
    """主函数."""
    parser = argparse.ArgumentParser(description="高德地图MCP示例")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="验证MCP服务器连接而不运行完整示例",
    )
    parser.add_argument(
        "--demo",
        choices=["geo", "weather", "regeocode", "route", "all"],
        default="all",
        help="选择要运行的演示 (默认: all)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("ModelScope MCP示例: 高德地图服务")
    print("=" * 60)
    print()

    # 初始化ToolExecutor
    print("📦 初始化ToolExecutor...")
    from multi_agent.config.loader import load_mcp_servers_config
    from multi_agent.config.paths import get_default_config_dir

    manager = MCPToolManager()
    config_dir = get_default_config_dir()
    # servers_file = config_dir / "config" / "mcp_servers.yaml"
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
        if args.demo in ["geo", "all"]:
            await demo_geocoding(executor)

        if args.demo in ["weather", "all"]:
            await demo_weather(executor)

        if args.demo in ["regeocode", "all"]:
            await demo_regeocode(executor)

        if args.demo in ["route", "all"]:
            await demo_route_planning(executor)

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        await manager.close()

    print()
    print("=" * 60)
    print("✅ 示例完成")
    print("=" * 60)
    print()
    print("💡 高德地图API密钥获取:")
    print("   访问: https://console.amap.com/")
    print("   注册并创建应用获取 API Key")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

#!/usr/bin/env python3
"""智能搜索演示 - 结合 LLM 和 MCP 工具实现智能搜索.

This example demonstrates:
1. Using LLM to decide when to use MCP search tools
2. LLM analyzing user queries and choosing appropriate search strategies
3. Automatically invoking MCP tools and formatting results for the user
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Load .env file
from dotenv import load_dotenv
load_dotenv()

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from openai import OpenAI

from multi_agent.config.loader import load_mcp_servers_config
from multi_agent.models.tool import MCPServer, MCPServerConfigSSE
from multi_agent.tools.mcp_manager import MCPToolManager
from multi_agent.tools.builtin import register_builtin_tools


def config_to_server(name: str, config):
    """Convert MCPServerConfig to MCPServer model."""
    if config.transport == "sse":
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


class IntelligentSearchAgent:
    """智能搜索代理 - 结合 LLM 和 MCP 工具."""

    def __init__(self, mcp_manager: MCPToolManager, api_key: str, base_url: str):
        """Initialize the intelligent search agent.

        Args:
            mcp_manager: MCPToolManager instance
            api_key: SiliconFlow API key
            base_url: API base URL
        """
        self.mcp_manager = mcp_manager
        self.client = OpenAI(api_key=api_key, base_url=base_url)

        # 获取可用的搜索工具
        self.available_tools = self._get_available_tools()

    def _get_available_tools(self):
        """获取可用的搜索工具列表."""
        tools = self.mcp_manager.list_tools()
        search_tools = {}

        for tool in tools:
            if "search" in tool.name.lower() or "web" in tool.name.lower():
                search_tools[tool.name] = {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }

        return search_tools

    def _build_system_prompt(self):
        """构建系统提示词."""
        tools_desc = "\n".join([
            f"- {name}: {desc['description']}"
            for name, desc in self.available_tools.items()
        ])

        return f"""你是一个智能搜索助手，可以帮助用户搜索网络信息。

## 可用工具

{tools_desc}

## 工作流程

1. 分析用户的问题
2. 判断是否需要使用搜索工具：
   - 如果问题涉及实时信息、时事新闻、技术问题等，应该使用搜索
   - 如果是简单的闲聊或常识性问题，可以直接回答
3. 如果需要搜索：
   - 选择最合适的搜索工具
   - 使用搜索查询参数：search_query
   - 从搜索结果中提取关键信息，用简洁友好的方式呈现给用户

## 输出格式

### 不需要搜索时：
直接回答用户的问题，格式简洁友好。

### 需要搜索时：
首先输出一段简短的说明，然后按以下JSON格式调用工具：

```json
{{
    "tool": "工具名称",
    "search_query": "搜索关键词"
}}
```

搜索完成后，你需要整理搜索结果，用简洁友好的方式呈现给用户。

## 注意事项

- 搜索关键词应该简洁明了，直击要点
- 从搜索结果中提取最相关的信息
- 回答要用中文，格式清晰，使用emoji增强可读性
- 如果搜索结果不满意，可以尝试不同的关键词再次搜索
"""

    async def _call_search_tool(self, tool_name: str, search_query: str):
        """调用 MCP 搜索工具.

        Args:
            tool_name: 工具名称
            search_query: 搜索关键词

        Returns:
            搜索结果
        """
        # 获取对应的 transport
        transport_name = None
        for name in self.mcp_manager.transports:
            if "search" in name.lower() or "web" in name.lower():
                transport_name = name
                break

        if not transport_name:
            return {"error": "未找到搜索工具"}

        transport = self.mcp_manager.transports[transport_name]

        try:
            from multi_agent.tools.mcp_client import MCPMessage

            message = MCPMessage(
                method="tools/call",
                params={
                    "name": tool_name,
                    "arguments": {"search_query": search_query}
                }
            )

            response = await transport.send_message(message)

            if response.result:
                if isinstance(response.result, dict) and "content" in response.result:
                    for content_item in response.result["content"]:
                        if content_item.get("type") == "text":
                            return {"result": content_item.get("text", "")}

            return response.result if response.result else {"error": "无搜索结果"}

        except Exception as e:
            return {"error": f"搜索失败: {str(e)}"}

    def _parse_tool_call(self, response: str):
        """解析 LLM 返回的工具调用.

        Args:
            response: LLM 响应文本

        Returns:
            (tool_name, search_query) 或 None
        """
        import json
        import re

        # 查找 JSON 格式的工具调用
        json_match = re.search(r'\{[^{}]*"tool"[^{}]*"search_query"[^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                tool_call = json.loads(json_match.group())
                return tool_call.get("tool"), tool_call.get("search_query")
            except json.JSONDecodeError:
                pass

        return None, None

    async def search(self, user_query: str, max_iterations: int = 3):
        """智能搜索主流程.

        Args:
            user_query: 用户查询
            max_iterations: 最大迭代次数（防止无限循环）

        Returns:
            搜索结果
        """
        print(f"\n🤔 用户问题: {user_query}\n")

        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": user_query}
        ]

        for iteration in range(max_iterations):
            try:
                # 调用 LLM
                response = self.client.chat.completions.create(
                    model="Qwen/Qwen3-8B",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2000
                )

                assistant_message = response.choices[0].message.content
                messages.append({"role": "assistant", "content": assistant_message})

                # 检查是否需要调用工具
                tool_name, search_query = self._parse_tool_call(assistant_message)

                if tool_name and search_query:
                    print(f"🔍 正在搜索: {search_query}")
                    print(f"   使用工具: {tool_name}\n")

                    # 调用 MCP 搜索工具
                    search_result = await self._call_search_tool(tool_name, search_query)

                    # 格式化搜索结果
                    if "error" in search_result:
                        tool_response = f"搜索遇到问题: {search_result['error']}"
                    else:
                        raw_result = search_result.get("result", "")
                        # 截取前2000字符避免token过多
                        tool_response = f"搜索结果如下：\n\n{raw_result[:2000]}"

                    print(f"📊 搜索完成!\n")

                    # 将工具调用结果添加到对话历史
                    messages.append({
                        "role": "user",
                        "content": f"工具 {tool_name} 返回的结果：\n{tool_response}\n\n请整理并总结搜索结果，用简洁友好的方式回答用户的问题。"
                    })

                    # 再次调用 LLM 整理结果
                    final_response = self.client.chat.completions.create(
                        model="Qwen/Qwen3-8B",
                        messages=messages,
                        temperature=0.7,
                        max_tokens=2000
                    )

                    final_answer = final_response.choices[0].message.content
                    return final_answer
                else:
                    # 不需要搜索，直接返回 LLM 回答
                    return assistant_message

            except Exception as e:
                error_msg = f"处理过程出错: {str(e)}"
                print(f"❌ {error_msg}\n")
                return error_msg

        return "抱歉，搜索过程中遇到了问题。"


async def main():
    """主函数."""
    parser = argparse.ArgumentParser(description="智能搜索演示 - 结合 LLM 和 MCP 工具")
    parser.add_argument(
        "query",
        nargs="?",
        help="搜索问题（如果不提供，将进入交互模式）"
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="SiliconFlow API key (从环境变量 SILICONFLOW_API_KEY 读取)"
    )
    parser.add_argument(
        "--base-url",
        default="https://api.siliconflow.cn/v1",
        help="API base URL"
    )
    parser.add_argument(
        "--config",
        default="examples/config/mcp_servers_modelscope.yaml",
        help="MCP 服务器配置文件路径"
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="交互模式（可以持续提问）"
    )
    args = parser.parse_args()

    # 从环境变量读取 API key（优先级：命令行参数 > 环境变量）
    api_key = args.api_key or os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        print("❌ 错误: 请设置 SiliconFlow API key")
        print()
        print("使用方式:")
        print("  export SILICONFLOW_API_KEY='your_api_key_here'")
        print("  或")
        print("  python ai_search_demo.py --api-key 'your_api_key_here'")
        print()
        print("获取 API Key: https://siliconflow.cn/")
        sys.exit(1)

    print("=" * 60)
    print("🤖 智能搜索演示")
    print("=" * 60)
    print()

    # 初始化 MCP 管理器
    print("📦 初始化 MCP 工具...")
    manager = MCPToolManager()
    servers_file = Path(args.config)

    # 加载 MCP 服务器配置
    if servers_file.exists():
        try:
            servers_config = load_mcp_servers_config(servers_file)
            for name, config in servers_config.items():
                if config.enabled and config.transport == "sse":
                    try:
                        server = config_to_server(name, config)
                        await manager.add_server(server)
                    except Exception as e:
                        print(f"  ⚠️  Failed to load {name}: {e}")
        except Exception as e:
            print(f"  ⚠️  Failed to load config: {e}")

    # 检查可用工具
    mcp_tools = manager.list_tools()
    print(f"✅ 已加载 {len(mcp_tools)} 个 MCP 工具\n")

    # 初始化智能搜索代理
    agent = IntelligentSearchAgent(
        mcp_manager=manager,
        api_key=api_key,
        base_url=args.base_url
    )

    async def process_query(query: str):
        """处理单个查询."""
        result = await agent.search(query)
        print("=" * 60)
        print("💡 智能回答")
        print("=" * 60)
        print()
        print(result)
        print()
        print("=" * 60)

    # 处理查询
    if args.query:
        # 单次查询模式
        await process_query(args.query)
    else:
        # 交互模式
        print("📝 交互模式已启动（输入 'quit' 或 'exit' 退出）")
        print()

        while True:
            try:
                query = input("🤔 请输入您的问题: ").strip()
                if not query:
                    continue

                if query.lower() in ["quit", "exit", "退出", "q"]:
                    print("👋 再见！")
                    break

                await process_query(query)

            except KeyboardInterrupt:
                print("\n👋 再见！")
                break
            except EOFError:
                break

    # 清理
    await manager.close()


if __name__ == "__main__":
    asyncio.run(main())

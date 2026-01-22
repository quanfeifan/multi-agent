# MCP Examples

本目录包含展示如何使用 MCP 服务器的示例脚本。

## 前置条件

1. **配置 MCP 服务器**：复制配置模板到 `~/.multi-agent/config/mcp_servers.yaml`
   ```bash
   cp examples/config/mcp_servers_modelscope.yaml ~/.multi-agent/config/mcp_servers.yaml
   ```

2. **安装 Node.js 和 npx**：用于启动 stdio 传输的 MCP 服务器
   ```bash
   # 检查是否已安装
   npx --version
   ```

3. **设置 API 密钥**：根据使用的 MCP 服务器设置相应的 API 密钥
   ```bash
   # 高德地图 API Key（可选）: https://console.amap.com/
   export AMAP_MAPS_API_KEY="your_api_key_here"

   # 智谱 API Key（用于 web-search 和 wiki 服务器）: https://open.bigmodel.cn/
   # 在配置文件中设置 Authorization header
   ```

## 快速开始

### 1. 验证连接

首先验证 MCP 服务器是否正确配置：

```bash
# 验证高德地图服务器
python examples/modelscope_mcp/amap_demo.py --verify

# 验证 Web 搜索服务器
python examples/modelscope_mcp/search_demo.py
```

成功输出示例：
```
✅ 发现 5 个MCP工具:
  • maps_geo: 地理编码，将地址转换为经纬度坐标...
  • maps_regeo: 逆地理编码...
  • maps_weather: 查询指定城市的天气信息...
```

### 2. 运行演示

#### 高德地图示例 (`amap_demo.py`)

```bash
# 地理编码演示（地址 → 经纬度）
python examples/modelscope_mcp/amap_demo.py --demo geo

# 天气查询演示
python examples/modelscope_mcp/amap_demo.py --demo weather

# 逆地理编码演示（经纬度 → 地址）
python examples/modelscope_mcp/amap_demo.py --demo regeocode

# 运行所有演示
python examples/modelscope_mcp/amap_demo.py
```

#### Web 搜索示例 (`search_demo.py`)

```bash
# 运行所有搜索演示（基本搜索、技术搜索、新闻搜索、学术搜索）
python examples/modelscope_mcp/search_demo.py
```

#### AI 智能搜索示例 (`ai_search_demo.py`)

```bash
# 单次查询模式
python examples/modelscope_mcp/ai_search_demo.py "2025年人工智能有什么重要进展"

# 交互模式（持续对话）
python examples/modelscope_mcp/ai_search_demo.py -i
```

**AI 智能搜索特性**：
- LLM 自动判断是否需要使用搜索工具
- 智能选择最合适的搜索工具和关键词
- 自动整理搜索结果，提供简洁友好的回答
- 支持简单闲聊和复杂搜索查询

#### 股票查询示例 (`stock_demo.py`)

```bash
# 验证股票服务器
python examples/modelscope_mcp/stock_demo.py --verify

# 查询股票价格
python examples/modelscope_mcp/stock_demo.py --demo query

# 查询公司信息
python examples/modelscope_mcp/stock_demo.py --demo company
```

## 示例说明

### 高德地图示例 - `amap_demo.py`

展示如何直接调用高德地图 MCP 工具（stdio 传输）：

| 功能 | 工具名称 | 说明 |
|------|----------|------|
| 地理编码 | `maps_geo` | 将地址转换为经纬度坐标 |
| 逆地理编码 | `maps_regeo` | 将经纬度转换为地址 |
| 天气查询 | `maps_weather` | 查询指定城市的天气信息 |
| 距离计算 | `maps_distance` | 计算两点之间的距离 |
| POI 搜索 | `maps_text_search` | 关键词搜索周边地点 |

### Web 搜索示例 - `search_demo.py`

展示如何使用智谱 Web 搜索 MCP 服务（SSE 传输）：

| 功能 | 工具名称 | 说明 |
|------|----------|------|
| Web 搜索 | `webSearchPro` | 搜索网络信息 |
| 搜狗搜索 | `webSearchSogou` | 搜狗搜索引擎 |
| 夸克搜索 | `webSearchQuark` | 夸克搜索引擎 |
| 标准搜索 | `webSearchStd` | 标准搜索引擎 |

**SSE 传输特性**：
- 自动保持 SSE 连接活跃
- 连接断开时自动重连
- 响应通过 SSE 流返回，而非 HTTP 响应体

### 股票查询示例 - `stock_demo.py`

展示如何使用 Pozansky 股票 MCP 服务（stdio 传输）：

| 功能 | 工具名称 | 说明 |
|------|----------|------|
| 股票价格 | `get_stock_price` | 查询实时股价 |
| 公司信息 | `get_company_info` | 查询公司基本信息 |

### AI 智能搜索示例 - `ai_search_demo.py`

展示如何结合 LLM 和 MCP 工具实现智能搜索：

| 功能 | 说明 |
|------|------|
| 智能判断 | LLM 自动分析用户问题，判断是否需要搜索 |
| 工具选择 | 智能选择最合适的搜索工具和关键词 |
| 结果整理 | 自动整理搜索结果，提供简洁友好的回答 |
| 交互模式 | 支持持续对话，可以多次提问 |

**工作流程**：
1. 用户提出问题
2. LLM 分析问题，判断是否需要搜索
3. 如果需要搜索，调用 MCP 工具获取实时信息
4. LLM 整理搜索结果，生成友好的回答

### 代码示例

#### 基础 MCP 工具调用

```python
import asyncio
from multi_agent.tools import ToolExecutor, MCPToolManager
from multi_agent.tools.builtin import register_builtin_tools

async def main():
    # 初始化 MCP 管理器
    manager = MCPToolManager()

    # 加载配置
    from pathlib import Path
    from multi_agent.config.loader import load_mcp_servers_config

    servers_file = Path('examples/config/mcp_servers_modelscope.yaml')

    if servers_file.exists():
        servers_config = load_mcp_servers_config(servers_file)
        for name, config in servers_config.items():
            if config.enabled:
                await manager.add_server(name, config)

    # 创建统一执行器（MCP + builtin 工具）
    executor = ToolExecutor(
        manager=manager,
        builtin_registry=register_builtin_tools()
    )

    # 调用 MCP 工具
    result = await executor.execute(
        "maps_geo",
        {"address": "北京市朝阳区", "city": "北京"}
    )

    print(result)
    # {'content': [{'type': 'text', 'text': '经度: 116.4, 纬度: 39.9'}]}

    await manager.close()

asyncio.run(main())
```

#### AI 智能搜索（LLM + MCP）

```python
import asyncio
from openai import OpenAI
from multi_agent.tools import MCPToolManager
from multi_agent.tools.mcp_client import MCPMessage

class IntelligentSearchAgent:
    def __init__(self, mcp_manager, api_key, base_url):
        self.mcp_manager = mcp_manager
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    async def search(self, query: str):
        # 1. LLM 判断是否需要搜索
        response = self.client.chat.completions.create(
            model="Qwen/Qwen3-8B",
            messages=[
                {"role": "system", "content": "你是智能搜索助手..."},
                {"role": "user", "content": query}
            ]
        )

        # 2. 如果需要搜索，调用 MCP 工具
        if self._needs_search(response.choices[0].message.content):
            search_result = await self._call_mcp_tool("webSearchPro", query)

            # 3. LLM 整理搜索结果
            final_response = self.client.chat.completions.create(
                model="Qwen/Qwen3-8B",
                messages=[
                    {"role": "system", "content": "整理搜索结果..."},
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": search_result}
                ]
            )
            return final_response.choices[0].message.content

        return response.choices[0].message.content

    async def _call_mcp_tool(self, tool_name: str, query: str):
        transport = self.mcp_manager.transports["web-search"]
        message = MCPMessage(
            method="tools/call",
            params={"name": tool_name, "arguments": {"search_query": query}}
        )
        response = await transport.send_message(message)
        return response.result["content"][0]["text"]

# 使用示例
async def main():
    manager = MCPToolManager()
    # ... 加载配置 ...

    agent = IntelligentSearchAgent(manager, "your_api_key", "https://api.siliconflow.cn/v1")
    result = await agent.search("2025年人工智能有什么重要进展")
    print(result)

    await manager.close()

asyncio.run(main())
```

## MCP 传输类型

框架支持三种 MCP 传输方式：

| 传输类型 | 说明 | 适用场景 | 示例 |
|----------|------|----------|------|
| **stdio** | 通过标准输入/输出通信 | 本地 MCP 服务器 | 高德地图、股票查询 |
| **SSE** | 通过 Server-Sent Events 通信 | 远程 MCP 服务器 | 智谱搜索、Wiki |
| **streamable-http** | 统一的 HTTP 端点 | 现代 MCP 服务器 | ModelScope 托管服务器 |

### SSE 传输特性

SSE 传输实现以下高级特性：

- **持久连接**：保持 SSE 连接打开以接收响应
- **自动重连**：检测到连接断开时自动重新建立连接
- **响应匹配**：通过请求 ID 匹配异步响应
- **后台读取**：独立的异步任务持续读取 SSE 流

## 错误处理

示例包含完善的错误处理机制：

| 错误类型 | 处理方式 |
|----------|----------|
| 连接错误 | 检查服务器配置、网络连接、API 密钥 |
| 超时错误 | 默认 30 秒超时，SSE 连接超时自动重连 |
| 工具未找到 | 使用 `--verify` 列出可用工具 |
| SSE 连接断开 | 自动检测并重新建立连接 |

## 故障排查

### 问题：未发现 MCP 工具

```bash
# 检查配置文件
cat examples/config/mcp_servers_modelscope.yaml

# 检查服务器是否启用
# 确保 enabled: true

# 验证 API 密钥
```

### 问题：SSE 连接超时

```bash
# SSE 连接会自动重连
# 如果持续超时，检查：
# 1. 网络连接
# 2. API 密钥是否有效
# 3. MCP 服务器是否在线
```

### 问题：stdio 服务器启动失败

```bash
# 检查 npx 是否安装
npx --version

# 手动测试服务器包
npx -y @amap/amap-maps-mcp-server --help

# 检查 uvx（用于股票服务器）
uvx --version
pip install uv
```

## 更多资源

- **完整文档**：[docs/modelscope_mcp_integration.md](../../docs/modelscope_mcp_integration.md)
- **配置模板**：[examples/config/mcp_servers_modelscope.yaml](../config/mcp_servers_modelscope.yaml)
- **智谱 API**：[https://open.bigmodel.cn/](https://open.bigmodel.cn/)

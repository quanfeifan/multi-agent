# ModelScope MCP 服务器集成文档

本文档说明如何在 multi-agent 框架中集成和使用 ModelScope 平台的 MCP 服务器。

## 目录

- [架构说明](#架构说明)
- [快速开始](#快速开始)
- [ModelScope MCP 服务器列表](#modelscope-mcp-服务器列表)
- [API 密钥获取指南](#api-密钥获取指南)
- [常见问题排查](#常见问题排查)
- [LLM 调用 MCP 工具流程](#llm-调用-mcp-工具流程)

---

## 架构说明

### 统一工具调用接口

multi-agent 框架采用统一的工具调用接口，MCP 工具和 builtin（内置）工具对 LLM 来说是完全相同的：

```
ToolExecutor (统一工具调用接口)
├── BuiltinRegistry (本地工具: file_read, calculate等)
└── MCPToolManager (MCP服务器工具: 高德地图、搜索等)
    └── 通过 mcp_servers.yaml 配置外部服务器
```

**核心原则**：
- 所有 MCP 工具都和 builtin 工具一样，只是 LLM 可以调用的工具
- LLM 不需要知道工具来源（本地或远程 MCP 服务器）
- 通过统一的 `ToolExecutor.execute()` 接口调用
- 支持混合并行调用：`ToolExecutor.execute_batch()` 可以同时执行 builtin 和 MCP 工具

### 配置驱动

添加新的 MCP 服务器无需修改代码，只需在 YAML 配置文件中添加配置：

```yaml
# ~/.multi-agent/config/mcp_servers.yaml
server_name:
  transport: stdio  # 或 sse
  config:
    command: "npx"
    args: ["-y", "@package/package-name"]
    env:
      API_KEY: "${API_KEY}"
  enabled: true
```

---

## 快速开始

### 前置条件

1. **Python 3.10+** 已安装
2. **Node.js 和 npx** 已安装（用于 stdio 传输的 MCP 服务器）
3. **API 密钥**（如需要，如高德地图）

### 5 分钟配置第一个 MCP 服务器

#### 步骤 1: 复制配置模板

```bash
# 创建配置目录（如果不存在）
mkdir -p ~/.multi-agent/config

# 复制配置模板
cp examples/config/mcp_servers_modelscope.yaml ~/.multi-agent/config/mcp_servers.yaml
```

#### 步骤 2: 设置 API 密钥（如需要）

以高德地图为例：

```bash
# 设置环境变量（推荐添加到 ~/.bashrc 或 ~/.zshrc）
export AMAP_MAPS_API_KEY="your_api_key_here"
```

#### 步骤 3: 验证连接

```bash
# 验证 MCP 服务器连接并列出可用工具
python examples/modelscope_mcp/amap_demo.py --verify
```

成功输出示例：

```
🔍 验证MCP服务器连接...

✅ 发现 5 个MCP工具:

  • maps_geo: 地理编码，将地址转换为经纬度坐标...
  • maps_regeo: 逆地理编码，将经纬度转换为地址...
  • maps_weather: 查询指定城市的天气信息...
  • maps_distance: 计算两点之间的距离...
  • maps_text_search: 关键词搜索POI...

✅ 高德地图工具已配置: maps_geo, maps_regeo, maps_weather, maps_distance, maps_text_search
```

#### 步骤 4: 运行示例

```bash
# 查询北京市朝阳区的经纬度
python examples/modelscope_mcp/amap_demo.py --demo geo
```

---

## ModelScope MCP 服务器列表

### 高德地图 (@amap/amap-maps-mcp-server)

**功能**：地理编码、逆地理编码、天气查询、路线规划、POI 搜索

**传输方式**：stdio

**认证**：需要 API Key

**配置**：

```yaml
amap:
  transport: stdio
  config:
    command: "npx"
    args: ["-y", "@amap/amap-maps-mcp-server"]
    env:
      AMAP_MAPS_API_KEY: "${AMAP_MAPS_API_KEY}"
  enabled: true
```

**可用工具**：
- `maps_geo`: 地理编码（地址 → 经纬度）
- `maps_regeo`: 逆地理编码（经纬度 → 地址）
- `maps_weather`: 天气查询
- `maps_distance`: 距离计算
- `maps_text_search`: POI 搜索

**API 密钥获取**：参见 [API 密钥获取指南](#api-密钥获取指南)

---

## API 密钥获取指南

### 高德地图 API Key

1. 访问 [高德开放平台](https://console.amap.com/)
2. 注册/登录账号
3. 进入「应用管理」→「我的应用」→「创建新应用」
4. 选择「Web端」或「服务器端」应用类型
5. 添加 Key，选择「Web服务」类型
6. 复制获取到的 Key

**设置环境变量**：

```bash
# 临时设置（当前会话）
export AMAP_MAPS_API_KEY="your_key_here"

# 永久设置（添加到 ~/.bashrc 或 ~/.zshrc）
echo 'export AMAP_MAPS_API_KEY="your_key_here"' >> ~/.bashrc
source ~/.bashrc
```

---

## 常见问题排查

### 问题 1: MCP 服务器连接失败

**症状**：`✗ 未发现MCP工具`

**可能原因**：
1. `mcp_servers.yaml` 配置文件路径错误
2. Node.js 或 npx 未安装
3. 服务器包名错误

**解决方案**：

```bash
# 检查配置文件是否存在
ls -la ~/.multi-agent/config/mcp_servers.yaml

# 检查 Node.js 和 npx
node --version
npx --version

# 手动测试 npx 包是否可用
npx -y @amap/amap-maps-mcp-server --help
```

### 问题 2: API 密钥错误

**症状**：`Tool execution failed: Invalid API key`

**解决方案**：

```bash
# 检查环境变量是否设置
echo $AMAP_MAPS_API_KEY

# 重新设置环境变量
export AMAP_MAPS_API_KEY="your_correct_key"
```

### 问题 3: 工具执行超时

**症状**：`Timeout executing tool_name`

**可能原因**：
1. 网络连接问题
2. MCP 服务器响应慢
3. 默认超时时间太短

**解决方案**：

```python
# 在代码中增加超时时间
await executor.execute("tool_name", arguments, timeout=60)
```

### 问题 4: 找不到工具

**症状**：`Tool not found: tool_name`

**可能原因**：
1. MCP 服务器未正确连接
2. 工具名称拼写错误
3. 服务器未提供该工具

**解决方案**：

```bash
# 列出所有可用工具
python examples/modelscope_mcp/amap_demo.py --verify
```

---

## LLM 调用 MCP 工具流程

### 完整调用链路

```
用户输入
  ↓
LLM (function calling)
  ↓
ToolExecutor (统一接口)
  ↓
  ├─→ BuiltinRegistry → 本地 Python 工具
  └─→ MCPToolManager → MCP 服务器 (npx 进程或 HTTP SSE)
       ↓
    JSON-RPC 协议通信
       ↓
    MCP 服务器执行工具
       ↓
    返回结果 (MCP 格式)
       ↓
    ToolExecutor 转换为统一格式
       ↓
    LLM 接收结果并生成回复
       ↓
    用户收到最终回复
```

### 代码示例

```python
import asyncio
from multi_agent.tools import ToolExecutor, MCPToolManager
from multi_agent.tools.builtin import register_builtin_tools
from multi_agent.config.paths import get_default_config_dir
from multi_agent.config.loader import load_mcp_servers_config

async def main():
    # 1. 初始化 MCP 管理器并加载配置
    manager = MCPToolManager()
    config_dir = get_default_config_dir()
    servers_file = config_dir / "config" / "mcp_servers.yaml"

    if servers_file.exists():
        servers_config = load_mcp_servers_config(servers_file)
        for name, config in servers_config.items():
            if config.enabled:
                await manager.add_server(config)

    # 2. 注册 builtin 工具
    builtin_registry = register_builtin_tools()

    # 3. 创建统一执行器
    executor = ToolExecutor(
        manager=manager,
        builtin_registry=builtin_registry
    )

    # 4. 执行 MCP 工具（与 builtin 工具完全相同的接口）
    result = await executor.execute(
        "maps_geo",  # MCP 工具名称
        {"address": "北京市朝阳区", "city": "北京"}
    )

    print(result)
    # 输出: {"content": [{"type": "text", "text": "经度: 116.4, 纬度: 39.9"}]}

    # 5. 清理
    await manager.close()

asyncio.run(main())
```

### 批量并行执行

```python
# 同时执行多个工具（builtin + MCP）
tool_calls = [
    {"id": "1", "function": {"name": "maps_geo", "arguments": "{\"address\": \"天安门\"}"}},
    {"id": "2", "function": {"name": "file_read", "arguments": "{\"path\": \"test.txt\"}"}},
    {"id": "3", "function": {"name": "maps_weather", "arguments": "{\"city\": \"北京\"}"}},
]

results = await executor.execute_batch(tool_calls)
# 所有工具并行执行，混合 builtin 和 MCP 工具
```

---

## 更多资源

- **示例代码**：`examples/modelscope_mcp/amap_demo.py`
- **配置模板**：`examples/config/mcp_servers_modelscope.yaml`
- **快速开始**：`docs/quickstart_modelscope_mcp.md`

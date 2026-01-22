# ModelScope MCP 快速开始指南

5 分钟内完成第一个 ModelScope MCP 服务器的配置和使用。

## 前置条件检查

```bash
# 检查 Python 版本（需要 3.10+）
python --version

# 检查 Node.js 和 npx
npx --version
```

如果缺少 Node.js，请访问 [nodejs.org](https://nodejs.org/) 下载安装。

---

## 步骤 1: 配置 MCP 服务器（1 分钟）

### 1.1 创建配置目录

```bash
mkdir -p ~/.multi-agent/config
```

### 1.2 创建配置文件

```bash
# 创建 ~/.multi-agent/config/mcp_servers.yaml
cat > ~/.multi-agent/config/mcp_servers.yaml << 'EOF'
amap:
  transport: stdio
  config:
    command: "npx"
    args: ["-y", "@amap/amap-maps-mcp-server"]
    env:
      AMAP_MAPS_API_KEY: "${AMAP_MAPS_API_KEY}"
  enabled: true
EOF
```

### 1.3 设置 API 密钥

```bash
# 获取高德地图 API Key: https://console.amap.com/
export AMAP_MAPS_API_KEY="your_api_key_here"
```

---

## 步骤 2: 验证连接（1 分钟）

```bash
# 验证 MCP 服务器连接
python examples/modelscope_mcp/amap_demo.py --verify
```

**成功输出**：

```
🔍 验证MCP服务器连接...

✅ 发现 5 个MCP工具:

  • maps_geo: 地理编码，将地址转换为经纬度坐标...
  • maps_regeo: 逆地理编码，将经纬度转换为地址...
  • maps_weather: 查询指定城市的天气信息...

✅ 高德地图工具已配置
```

**如果失败**：

- 检查 `~/.multi-agent/config/mcp_servers.yaml` 文件是否存在
- 检查 Node.js 和 npx 是否已安装
- 检查 API 密钥是否正确设置

---

## 步骤 3: 运行示例（3 分钟）

### 示例 1: 地理编码

```bash
python examples/modelscope_mcp/amap_demo.py --demo geo
```

**输出**：

```
============================================================
📍 地理编码演示: 地址 → 经纬度
================================================------------

📝 地理编码结果:
经度: 116.481, 纬度: 39.990
地址: 北京市朝阳区望京
```

### 示例 2: 天气查询

```bash
python examples/modelscope_mcp/amap_demo.py --demo weather
```

### 示例 3: 运行所有演示

```bash
python examples/modelscope_mcp/amap_demo.py
```

---

## 在代码中使用 MCP 工具

### 直接工具调用

```python
import asyncio
from multi_agent.tools import ToolExecutor, MCPToolManager
from multi_agent.tools.builtin import register_builtin_tools

async def main():
    # 初始化
    manager = MCPToolManager()
    # ... 加载配置 ...

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

asyncio.run(main())
```

### LLM Function Calling

MCP 工具会自动转换为 LLM function calling 格式：

```python
from multi_agent.agent import Agent
from multi_agent.tools import ToolExecutor

# ToolExecutor 会自动加载 MCP 工具
executor = ToolExecutor()

# Agent 可以调用所有 MCP 工具
agent = Agent(
    name="assistant",
    tools=executor.list_tools()
)

# LLM 自动选择并调用 MCP 工具
response = await agent.chat("北京市朝阳区的经纬度是多少？")
```

---

## 常用命令

```bash
# 验证连接
python examples/modelscope_mcp/amap_demo.py --verify

# 地理编码演示
python examples/modelscope_mcp/amap_demo.py --demo geo

# 天气查询演示
python examples/modelscope_mcp/amap_demo.py --demo weather

# 逆地理编码演示
python examples/modelscope_mcp/amap_demo.py --demo regeocode

# 运行所有演示
python examples/modelscope_mcp/amap_demo.py
```

---

## 配置文件参考

完整配置模板：`examples/config/mcp_servers_modelscope.yaml`

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

---

## 下一步

- 阅读完整文档：[docs/modelscope_mcp_integration.md](./modelscope_mcp_integration.md)
- 查看更多示例：`examples/modelscope_mcp/`
- 了解 builtin 工具：`src/multi_agent/tools/builtin/`

---

## 故障排查

### 问题：连接失败

```bash
# 检查配置文件
cat ~/.multi-agent/config/mcp_servers.yaml

# 检查 npx
npx -y @amap/amap-maps-mcp-server --help
```

### 问题：API 密钥错误

```bash
# 检查环境变量
echo $AMAP_MAPS_API_KEY

# 重新设置
export AMAP_MAPS_API_KEY="correct_key"
```

### 问题：工具未找到

```bash
# 列出可用工具
python examples/modelscope_mcp/amap_demo.py --verify
```

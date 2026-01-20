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

3. **设置 API 密钥**：高德地图需要 API Key
   ```bash
   # 获取 API Key: https://console.amap.com/
   export AMAP_MAPS_API_KEY="your_api_key_here"
   ```

## 快速开始

### 1. 验证连接

首先验证 MCP 服务器是否正确配置：

```bash
python examples/modelscope_mcp/amap_demo.py --verify
```

成功输出示例：
```
✅ 发现 5 个MCP工具:
  • maps_geo: 地理编码，将地址转换为经纬度坐标...
  • maps_regeo: 逆地理编码...
  • maps_weather: 查询指定城市的天气信息...
```

### 2. 运行演示

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

## 示例说明

### 高德地图示例 - `amap_demo.py`

展示如何直接调用高德地图 MCP 工具：

| 功能 | 工具名称 | 说明 |
|------|----------|------|
| 地理编码 | `maps_geo` | 将地址转换为经纬度坐标 |
| 逆地理编码 | `maps_regeo` | 将经纬度转换为地址 |
| 天气查询 | `maps_weather` | 查询指定城市的天气信息 |
| 距离计算 | `maps_distance` | 计算两点之间的距离 |
| POI 搜索 | `maps_text_search` | 关键词搜索周边地点 |

### 代码示例

```python
import asyncio
from multi_agent.tools import ToolExecutor, MCPToolManager
from multi_agent.tools.builtin import register_builtin_tools

async def main():
    # 初始化 MCP 管理器
    manager = MCPToolManager()

    # 加载配置（从 ~/.multi-agent/config/mcp_servers.yaml）
    from multi_agent.config.paths import get_default_config_dir
    from multi_agent.config.loader import load_mcp_servers_config

    config_dir = get_default_config_dir()
    servers_file = config_dir / "config" / "mcp_servers.yaml"

    if servers_file.exists():
        servers_config = load_mcp_servers_config(servers_file)
        for name, config in servers_config.items():
            if config.enabled:
                await manager.add_server(config)

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

## 错误处理

示例包含完善的错误处理机制：

| 错误类型 | 处理方式 |
|----------|----------|
| 连接错误 | 检查 npx 是否安装，服务器包名是否正确 |
| API 密钥错误 | 检查 `AMAP_MAPS_API_KEY` 环境变量 |
| 超时错误 | 默认 30 秒超时，可在代码中调整 |
| 工具未找到 | 使用 `--verify` 列出可用工具 |

## 故障排查

### 问题：未发现 MCP 工具

```bash
# 检查配置文件
cat ~/.multi-agent/config/mcp_servers.yaml

# 检查 npx
npx --version

# 手动测试服务器包
npx -y @amap/amap-maps-mcp-server --help
```

### 问题：API 密钥错误

```bash
# 检查环境变量
echo $AMAP_MAPS_API_KEY

# 重新设置
export AMAP_MAPS_API_KEY="your_correct_key"
```

## 更多资源

- **完整文档**：[docs/modelscope_mcp_integration.md](../../docs/modelscope_mcp_integration.md)
- **快速开始**：[docs/quickstart_modelscope_mcp.md](../../docs/quickstart_modelscope_mcp.md)
- **配置模板**：[examples/config/mcp_servers_modelscope.yaml](../config/mcp_servers_modelscope.yaml)

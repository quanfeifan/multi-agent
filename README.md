# Multi-Agent Framework

A Python framework for orchestrating AI agents with tool integration, state machine-based execution, and fault tolerance.

## Features

- **Single-Agent Execution**: Execute tasks with AI agents that can reason across multiple iterations
- **Multi-Agent Coordination**: Supervisor pattern for coordinating specialized sub-agents
- **MCP Protocol Integration**: Unified tool access via Model Context Protocol (stdio + SSE)
- **Fault Tolerance**: Automatic retries, fallback tools, and error recovery
- **State Machine Workflows**: Graph-based execution with composable patterns (ReAct, Reflection)
- **Human-in-the-Loop**: Checkpoint/resume capabilities for workflows requiring human approval
- **Observability**: Structured trace logs for debugging and inspection
- **Parallel Execution**: Automatic dependency detection for optimized task execution

## Installation

### Development Installation

```bash
cd multi-agent
pip install -e ".[dev]"
```

## Quick Start

### 1. Set up environment variables

```bash
export OPENAI_API_KEY="sk-xxxxxxxxxxxxx"
# or use DeepSeek, GLM, Ollama, etc.
```

### 2. Run the demo
```bash
python examples/demo/llm_with_builtin_tools_demo.py
```

## ModelScope MCP Server Integration

This framework supports integrating MCP (Model Context Protocol) servers for extended capabilities like maps, search, and more.

**Key Principle**: All MCP tools work through the same unified `ToolExecutor` interface as builtin tools. LLMs can call MCP tools seamlessly without knowing the tool source.

**Documentation**:
- [Integration Guide](docs/modelscope_mcp_integration.md) - Complete documentation with architecture explanation
- [Quick Start](docs/quickstart_modelscope_mcp.md) - 5-minute setup guide

**Quick Setup**:
```bash
# 1. Copy configuration template
cp examples/config/mcp_servers_modelscope.yaml ~/.multi-agent/config/mcp_servers.yaml

# 2. Set API key (for services like Amap)
export AMAP_MAPS_API_KEY="your_api_key_here"

# 3. Verify connection
python examples/modelscope_mcp/amap_demo.py --verify
```

**Examples**:
- [Amap Demo](examples/modelscope_mcp/amap_demo.py) - High德地图 (Geocoding, weather, routing)
- [Configuration Template](examples/config/mcp_servers_modelscope.yaml) - YAML config reference



## Requirements

- Python 3.10 or higher
- An OpenAI-compatible LLM API key (or compatible service like DeepSeek, GLM, Ollama)

## License

MIT License - see LICENSE file for details.



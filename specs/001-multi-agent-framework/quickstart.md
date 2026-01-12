# Quick Start Guide: Multi-Agent Framework

**Feature**: 001-multi-agent-framework
**Date**: 2026-01-12
**Python**: 3.10+

---

## Overview

This guide will help you get started with the Multi-Agent Framework in under 30 minutes. You'll learn how to:

1. Install and configure the framework
2. Create your first AI agent with tools
3. Run multi-agent workflows
4. Add custom MCP servers

---

## Installation

### Prerequisites

- Python 3.10 or higher
- pip or poetry for package management

### Install via pip

```bash
pip install multi-agent-framework
```

### Install from source

```bash
git clone https://github.com/your-org/multi-agent.git
cd multi-agent
pip install -e .
```

### Development setup

```bash
# Clone repository
git clone https://github.com/your-org/multi-agent.git
cd multi-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/
```

---

## Configuration

### 1. Set up environment variables

Create a `.env` file in your project root:

```bash
# OpenAI API (or compatible)
OPENAI_API_KEY=sk-xxxxxxxxxxxxx

# Or use DeepSeek (国产大模型)
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx

# Or use GLM (智谱)
GLM_API_KEY=xxxxxxxxxxxxxxxxxxxxx

# Or use Ollama (本地模型)
OLLAMA_BASE_URL=http://localhost:11434
```

### 2. Create configuration directory

```bash
mkdir -p ~/.multi-agent/{agents,workflows,mcp_servers}
```

### 3. Configure MCP servers

Create `~/.multi-agent/mcp_servers/search.yaml`:

```yaml
brave_search:
  description: "Web search using Brave Search API"
  transport: sse
  config:
    url: "https://api.search.brave.com/res/v1/mcp/sse"
  enabled: true
```

---

## Your First Agent

### Create an agent configuration

Create `~/.multi-agent/agents/researcher.yaml`:

```yaml
name: web_researcher
role: "Searches the web and summarizes findings"
system_prompt: |
  You are a research assistant. Your job is to:
  1. Search for information using the web_search tool
  2. Synthesize findings into a clear summary
  Always cite your sources.
tools: [web_search]
max_iterations: 10
llm_config:
  endpoint: "https://api.openai.com/v1"
  model: "gpt-4"
  api_key_env: "OPENAI_API_KEY"
  api_type: openai
temperature: 0.7
```

### Run your first task

```python
from multi_agent import Agent, Task

# Load agent
agent = Agent.from_config("~/.multi-agent/agents/researcher.yaml")

# Create and execute task
task = Task(
    description="What are the latest developments in quantum computing?",
    agent=agent
)

result = task.run()
print(result.output)
```

### Output

```
[TRACE] Starting task: task_abc123
[TRACE] Agent: web_researcher
[TRACE] Step 1: Thinking about search query...
[TRACE] Step 2: Calling tool web_search...
[TRACE] Step 3: Processing search results...
[TRACE] Step 4: Synthesizing summary...
[TRACE] Task completed in 45 seconds

Recent developments in quantum computing (2024):
1. IBM's 1000-qubit Condor processor achieved breakthrough...
2. Google's quantum error correction improved by 50%...
3. Chinese researchers demonstrated quantum advantage in chemistry simulations...

Sources: nature.com, ibm.com, science.org
```

---

## Multi-Agent Supervisor Pattern

### Create supervisor with sub-agents

Create `~/.multi-agent/workflows/research_pipeline.yaml`:

```yaml
name: research_pipeline
description: "Research and write article"
patterns: [react]
entry_point: supervisor
nodes:
  supervisor:
    type: agent
    agent: supervisor
    allow_human_input: true
  researcher:
    type: agent
    agent: web_researcher
    max_iterations: 5
  writer:
    type: agent
    agent: content_writer
    max_iterations: 5
edges:
  - from: supervisor
    to:
      delegate_research: researcher
      delegate_write: writer
      complete: __end__
  - from: researcher
    to: supervisor
  - from: writer
    to: supervisor
checkpoints: [supervisor]
```

### Run the workflow

```python
from multi_agent import Workflow

workflow = Workflow.from_config("~/.multi-agent/workflows/research_pipeline.yaml")

result = workflow.run(
    task="Research AI trends in 2024 and write a 500-word blog post"
)

print(result.final_output)
```

---

## Using Chinese LLMs (国产大模型)

### DeepSeek (深度求索)

```yaml
# ~/.multi-agent/agents/deepseek_researcher.yaml
name: deepseek_researcher
role: "使用 DeepSeek 进行研究"
system_prompt: |
  你是一个研究助手。使用搜索工具查找信息并提供准确的总结。
tools: [web_search]
llm_config:
  endpoint: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
  api_key_env: "DEEPSEEK_API_KEY"
  api_type: deepseek
temperature: 0.7
```

### GLM (智谱)

```yaml
# ~/.multi-agent/agents/glm_analyst.yaml
name: glm_analyst
role: "数据分析助手"
system_prompt: |
  你是一个数据分析助手。使用可用工具分析数据并提供洞察。
tools: [csv_reader, data_visualize]
llm_config:
  endpoint: "https://open.bigmodel.cn/api/paas/v4"
  model: "glm-4-flash"
  api_key_env: "GLM_API_KEY"
  api_type: glm
temperature: 0.5
```

### Ollama (本地模型)

```yaml
# ~/.multi-agent/agents/ollama_chat.yaml
name: local_chat
role: "本地聊天助手"
system_prompt: |
  你是一个有用的助手，运行在本地模型上。提供简洁准确的回答。
tools: []
llm_config:
  endpoint: "http://localhost:11434/v1"
  model: "llama2"
  api_key_env: "OLLAMA_API_KEY"  # Ollama 通常不需要
  api_type: ollama
temperature: 0.7
```

---

## Adding Custom MCP Servers

### Method 1: Python stdio Server

Create `my_mcp_server.py`:

```python
#!/usr/bin/env python3
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("my-custom-server")

@server.tool()
async def my_tool(param1: str) -> str:
    """我的自定义工具"""
    return f"收到参数: {param1}"

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream,
                        server.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

Configure in `~/.multi-agent/mcp_servers/custom.yaml`:

```yaml
my_custom_server:
  description: "我的自定义 MCP 服务器"
  transport: stdio
  config:
    command: "python"
    args: ["/path/to/my_mcp_server.py"]
  enabled: true
```

### Method 2: SSE Server

Create `my_sse_server.py`:

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from mcp.server import Server

app = FastAPI()
server = Server("my-sse-server")

@server.tool()
async def process_data(data: str) -> str:
    """处理数据"""
    return f"已处理: {data}"

@app.get("/sse")
async def sse_endpoint():
    # SSE endpoint implementation
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Configure in `~/.multi-agent/mcp_servers/sse_custom.yaml`:

```yaml
my_sse_server:
  description: "自定义 SSE 服务器"
  transport: sse
  config:
    url: "http://localhost:8000/sse"
  enabled: true
```

---

## Common Patterns

### 1. ReAct Pattern (推理-行动-观察)

```python
from multi_agent.patterns import ReActPattern

workflow = Workflow(
    name="react_workflow",
    patterns=[ReActPattern()],
    agent=agent
)
```

### 2. Reflection Pattern (反思改进)

```python
from multi_agent.patterns import ReflectionPattern

workflow = Workflow(
    name="reflection_workflow",
    patterns=[ReflectionPattern()],
    agent=agent
)
```

### 3. Parallel Execution (并行执行)

```yaml
nodes:
  parallel_tasks:
    type: parallel
    parallel_tasks: [task_a, task_b, task_c]
  aggregator:
    type: agent
    agent: result_aggregator
edges:
  - from: dispatcher
    to: parallel_tasks
  - from: parallel_tasks
    to: aggregator
```

---

## Error Handling & Retry

### Automatic fallback configuration

```yaml
# ~/.multi-agent/mcp_servers/tools.yaml
tool_overrides:
  web_search:brave_search:
    timeout_seconds: 30
    fallback_tools:
      - web_search:tavily_search
      - puppeteer:navigate_to
    retry_on_errors: ["timeout", "rate_limit"]
```

### Manual error handling

```python
try:
    result = task.run()
except ToolTimeoutError:
    print("Tool timed out, using fallback...")
except ToolExecutionError as e:
    print(f"Tool failed: {e}")
    # Retry with different approach
```

---

## Observability & Debugging

### View trace logs

```bash
# View trace for a specific task
multi-agent trace show <task_id>

# List recent tasks
multi-agent task list --limit 10

# View checkpoint history
multi-agent checkpoint list <task_id>
```

### Time-travel debugging

```python
# Load checkpoint at specific sequence
task = Task.load(task_id="task_abc123")
checkpoint = task.get_checkpoint(sequence=3)

# Inspect state at that point
print(checkpoint.state)

# Resume from checkpoint
task.resume_from(checkpoint)
```

---

## Advanced Topics

### Human-in-the-Loop (HITL)

```yaml
nodes:
  approval_step:
    type: agent
    agent: supervisor
    allow_human_input: true
```

When execution reaches `approval_step`, it pauses and waits for human input:

```python
# Resume after human approval
task.resume(human_feedback={"action": "approve"})
```

### Dependency-Aware Parallel Execution

The framework automatically detects data dependencies and executes independent tasks in parallel:

```python
from multi_agent import TaskGroup

tasks = TaskGroup([
    Task("Research topic A"),
    Task("Research topic B"),
    Task("Research topic C")
])

# Tasks A and B will run in parallel if no dependencies
results = tasks.run_parallel()
```

---

## Next Steps

- **API Reference**: See `/docs/api.md` for complete API documentation
- **Examples**: Check `/examples/` directory for more examples
- **Contributing**: See `/CONTRIBUTING.md` for development guidelines

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Install with `pip install -e .` |
| `Connection refused` | Check MCP server is running |
| `API key error` | Verify environment variables are set |
| `Timeout` | Increase timeout in agent config |

### Getting Help

- GitHub Issues: https://github.com/your-org/multi-agent/issues
- Documentation: https://docs.multi-agent.dev
- Discord: https://discord.gg/multi-agent

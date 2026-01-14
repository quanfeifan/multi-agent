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

### From PyPI (when published)

```bash
pip install multi-agent-framework
```

### From Source

```bash
git clone https://github.com/your-org/multi-agent.git
cd multi-agent
pip install -e .
```

### Development Installation

```bash
git clone https://github.com/your-org/multi-agent.git
cd multi-agent
pip install -e ".[dev]"
```

## Quick Start

### 1. Set up environment variables

```bash
export OPENAI_API_KEY="sk-xxxxxxxxxxxxx"
# or use DeepSeek, GLM, Ollama, etc.
```

### 2. Create an agent configuration

```yaml
# ~/.multi-agent/agents/researcher.yaml
name: web_researcher
role: "Searches the web and summarizes findings"
system_prompt: |
  You are a research assistant. Use web_search to find information
  and synthesize findings into a clear summary.
tools: [web_search]
max_iterations: 10
llm_config:
  endpoint: "https://api.openai.com/v1"
  model: "gpt-4"
  api_key_env: "OPENAI_API_KEY"
  api_type: openai
  temperature: 0.7
```

### 3. Run your first task

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


## Requirements

- Python 3.10 or higher
- An OpenAI-compatible LLM API key (or compatible service like DeepSeek, GLM, Ollama)

## License

MIT License - see LICENSE file for details.



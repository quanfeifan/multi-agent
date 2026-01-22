# Single Agent Demo

This demo shows how to use the multi-agent framework with a single agent. The agent can have conversations, answer questions, perform calculations, call tools, and maintain context across multiple turns.

## Features Demonstrated

### Basic Demo
1. **Single Agent Creation** - Create and configure an AI agent
2. **Task Execution** - Execute tasks with reasoning loop
3. **State Management** - Conversation history and context preservation
4. **Multi-turn Conversations** - Maintain context across conversation turns
5. **Error Handling** - Graceful error handling and status tracking

### Tools Demo
1. **Tool Calling** - Execute tools through the agent
2. **MCP Protocol** - Standard Model Context Protocol for tool integration
3. **Custom Tools** - Easy to add new tools via stdio or SSE
4. **LLM Decision** - LLM decides which tool to call based on task

## Quick Start

### 1. Set up your environment

Create a `.env` file in the project root:

```bash
# Using SiliconFlow (recommended for this demo)
# 获取 API Key: https://siliconflow.cn/
OPENAI_API_KEY=your_siliconflow_api_key_here
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
DEFAULT_MODEL=Qwen/Qwen3-8B

# Or use OpenAI
# OPENAI_API_KEY=sk-your-openai-key
# OPENAI_BASE_URL=https://api.openai.com/v1
# DEFAULT_MODEL=gpt-4
```

### 2. Run the demo

```bash
# Basic demo with example tasks
python examples/demo/single_agent_demo.py

# Conversation demo with context preservation
python examples/demo/single_agent_demo.py --conversation

# Interactive chat mode
python examples/demo/single_agent_demo.py --interactive
```

## Demo Modes

### Basic Mode (Default)

Runs 3 example tasks:
- Mathematical calculation: "What is 15 * 27?"
- General knowledge: "What is the capital of France?"
- Concept explanation: "Explain what Python is in one sentence."

```bash
python examples/demo/single_agent_demo.py
```

**Example Output:**
```
======================================================================
Multi-Agent Framework - Single Agent Demo
======================================================================

✓ API Key configured
✓ Base URL: https://api.siliconflow.cn/v1
✓ Model: Qwen/Qwen3-8B

----------------------------------------------------------------------
Running Example Tasks:
----------------------------------------------------------------------

📝 Task: What is 15 * 27?
✓ Steps: 2
✓ Output: 15 multiplied by 27 is 405.

📝 Task: What is the capital of France?
✓ Steps: 2
✓ Output: The capital of France is Paris.

📝 Task: Explain what Python is in one sentence.
✓ Steps: 2
✓ Output: Python is a high-level, interpreted programming language...
```

### Conversation Mode (--conversation)

Demonstrates multi-turn conversation with context preservation:

```bash
python examples/demo/single_agent_demo.py --conversation
```

**Example Output:**
```
======================================================================
Conversation Demo - Multi-turn with Context
======================================================================

👤 User: My name is Alice.
🤖 Assistant: Hello, Alice! It's nice to meet you.

👤 User: What is my name?
🤖 Assistant: Your name is Alice! How can I help you today?

👤 User: What is 10 + 5?
🤖 Assistant: 10 + 5 equals 15. Is there anything else I can help you with, Alice?
```

## Tools Demo

The `single_agent_tools_demo.py` demonstrates tool calling with MCP (Model Context Protocol).

**Important Note**: Tool calling requires an LLM that supports OpenAI function calling format. The SiliconFlow Qwen model does not support this feature. For tool calling to work, use a model like GPT-4.

```bash
# Terminal 1: Start the tool server
PYTHONPATH=src python3 examples/demo/tools_server.py

# Terminal 2: Run the demo (with GPT-4 or other model supporting function calling)
OPENAI_API_KEY=your-gpt4-key \
OPENAI_BASE_URL=https://api.openai.com/v1 \
DEFAULT_MODEL=gpt-4 \
PYTHONPATH=src python3 examples/demo/single_agent_tools_demo.py
```

### Available Tools

| Tool | Description | Example Usage |
|------|-------------|---------------|
| `calculator` | Perform mathematical calculations | "What is 25 * 34?" |
| `read_file` | Read file contents | "Read the file README.md" |
| `list_files` | List files in directory | "List files in current directory" |
| `get_time` | Get current date/time | "What is the current time?" |

### Interactive Mode (--interactive)

Chat with the agent directly:

```bash
python examples/demo/single_agent_demo.py --interactive
```

```
======================================================================
Interactive Mode
======================================================================
Type your message (or 'quit' to exit)

You: What is the capital of Japan?
Assistant: The capital of Japan is Tokyo.

You: And what's the population there?
Assistant: Tokyo has a population of approximately 14 million people...

You: quit
Goodbye!
```

## Code Structure

```python
from multi_agent.agent import BaseAgent
from multi_agent.models import Agent
from multi_agent.config.schemas import LLMConfig

# 1. Create LLM configuration
llm_config = LLMConfig(
    endpoint="https://api.siliconflow.cn/v1",
    model="Qwen/Qwen3-8B",
    api_key_env="OPENAI_API_KEY"
)

# 2. Create agent
agent = Agent(
    name="demo_agent",
    role="Demo Assistant",
    system_prompt="You are a helpful assistant.",
    llm_config=llm_config,
    max_iterations=3
)

# 3. Create base agent
base_agent = BaseAgent(agent=agent, tool_executor=None)

# 4. Execute task
result = await base_agent.execute(
    task_description="What is 2 + 2?",
    initial_state=None
)

# 5. Check result
if result.completed:
    print(f"Output: {result.output}")
    print(f"Steps: {result.steps}")
```

## Framework Features Demonstrated

### 1. Agent Configuration

```python
agent = Agent(
    name="my_agent",              # Agent identifier
    role="Assistant",             # Agent role
    system_prompt="...",          # System instructions
    llm_config=llm_config,        # LLM settings
    max_iterations=5               # Max reasoning steps
)
```

### 2. Task Execution

```python
result = await base_agent.execute(
    task_description="Your task here",
    initial_state=None  # Or pass previous state for context
)
```

### 3. State Management

```python
# Get execution result
output = result.output
steps = result.steps
state = result.state

# Use state for next turn
next_result = await base_agent.execute(
    task_description="Follow-up question",
    initial_state=state
)
```

### 4. Status Checking

```python
if result.completed:
    print(f"Success: {result.output}")
else:
    print(f"Failed: {result.error}")
```

## API Configuration

### SiliconFlow (Recommended for this demo)

```bash
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
DEFAULT_MODEL=Qwen/Qwen3-8B
```

### OpenAI

```bash
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.openai.com/v1
DEFAULT_MODEL=gpt-4
```

### Ollama (Local)

```bash
OPENAI_API_KEY=not-needed
OPENAI_BASE_URL=http://localhost:11434/v1
DEFAULT_MODEL=llama2
```

## Troubleshooting

### API Key Not Set

```
⚠️  OPENAI_API_KEY not set or using placeholder value.
```

**Solution**: Set your API key in `.env` file or environment:
```bash
export OPENAI_API_KEY=your-actual-api-key
```

### Import Errors

```
ModuleNotFoundError: No module named 'multi_agent'
```

**Solution**: Run from project root with PYTHONPATH:
```bash
cd /path/to/multi-agent
PYTHONPATH=src python examples/demo/single_agent_demo.py
```

### API Errors

```
Error code: 401 - Api key is invalid
Error code: 403 - RPM limit exceeded
```

**Solution**:
- Verify API key is correct
- Check API rate limits
- Try a different endpoint/model
- Wait and retry

## Next Steps

- **Try the tools demo**: Requires a model with function calling support (e.g., GPT-4)
- **Modify the agent**: Change `system_prompt` to customize behavior
- **Create custom tools**: See `tools_server.py` for an example MCP server
- **Explore MCP servers**: See tool examples in `examples/mcp-servers/`
- **Try workflows**: Check workflow examples in `examples/workflows/`
- **Explore supervisor pattern**: See agent configurations in `examples/agents/`

## More Examples

- `examples/agents/` - Agent configuration examples (YAML)
- `examples/workflows/` - Workflow definitions (YAML)
- `examples/mcp-servers/` - MCP server configurations

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Multi-Agent Framework                      │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐    ┌──────────┐    ┌─────────────┐              │
│  │ Agent   │ -> │  State   │ -> │   LLM       │              │
│  │         │    │ Manager  │    │   Client    │              │
│  └─────────┘    └──────────┘    └─────────────┘              │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                   Tool Executor                      │  │
│  │  (Optional - for tool/function calling)              │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    Tracer                            │  │
│  │  (Optional - for execution tracking and debugging)    │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Support

For issues or questions:
- Check the main README in the project root
- See test examples in `tests/` directory
- Review the source code in `src/multi_agent/`

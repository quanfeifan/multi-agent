# Multi-Agent Framework API Reference

This document provides a comprehensive reference for the Multi-Agent Framework API.

## Table of Contents

- [Core Models](#core-models)
- [Configuration](#configuration)
- [Agent API](#agent-api)
- [Execution API](#execution-api)
- [State Management](#state-management)
- [Tools API](#tools-api)
- [Tracing & Metrics](#tracing--metrics)
- [Workflow Patterns](#workflow-patterns)

---

## Core Models

### Task

```python
from multi_agent import Task, TaskStatus

task = Task(
    task_id="task_abc123",
    description="Search for information about Python",
    agent_name="researcher",
    status=TaskStatus.PENDING,
)
```

**Attributes:**
- `task_id`: Unique task identifier
- `description`: Task description
- `agent_name`: Assigned agent
- `status`: One of `pending`, `running`, `completed`, `failed`
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

### State

```python
from multi_agent import State, Message

state = State(
    messages=[],
    current_agent="agent_name",
    next_action="execute",
)

# Add a message
new_state = state.add_message(Message(
    role="user",
    content="Hello, world!"
))
```

**Attributes:**
- `messages`: List of conversation messages
- `current_agent`: Currently executing agent
- `next_action`: Next action to take
- `routing_key`: Routing key for conditional edges
- `metadata`: Additional metadata

### Agent

```python
from multi_agent import Agent, LLMConfig

agent = Agent(
    name="researcher",
    role="Researches information using web search",
    system_prompt="You are a research assistant...",
    tools=["web_search", "read_file"],
    max_iterations=10,
    llm_config=LLMConfig(
        endpoint="https://api.openai.com/v1",
        model="gpt-4",
        api_key_env="OPENAI_API_KEY",
        api_type="openai",
    ),
)
```

---

## Configuration

### Loading Agent Configurations

```python
from multi_agent import load_agent_config

config = load_agent_config("path/to/agent.yaml")
print(config.name)
print(config.llm_config.model)
```

### Loading MCP Servers

```python
from multi_agent import load_mcp_servers_config

servers = load_mcp_servers_config("path/to/mcp-servers.yaml")
for name, config in servers.items():
    print(f"{name}: {config.transport}")
```

### Loading Workflows

```python
from multi_agent import load_workflow_config

workflow = load_workflow_config("path/to/workflow.yaml")
print(f"Workflow: {workflow.name}")
print(f"Patterns: {workflow.patterns}")
```

---

## Agent API

### BaseAgent

```python
from multi_agent import BaseAgent, Agent, ToolExecutor

agent = BaseAgent(agent=agent_model, tool_executor=tool_executor)

# Execute a task
result = await agent.execute(
    task_description="What is the latest version of Python?",
)

print(result.output)
print(result.steps)
print(result.completed)
```

**Methods:**
- `execute(task_description, initial_state)`: Execute a task
- `from_config(config, tool_executor)`: Create agent from configuration

### SupervisorAgent

```python
from multi_agent import SupervisorAgent

supervisor = SupervisorAgent(
    agent=supervisor_agent_model,
    sub_agents={
        "researcher": researcher_agent,
        "writer": writer_agent,
    },
    tool_executor=tool_executor,
)

result = await supervisor.execute(task_description)
```

---

## Execution API

### Orchestrator

```python
from multi_agent import Orchestrator, OrchestratorConfig

config = OrchestratorConfig(
    max_concurrent_tasks=100,
    task_timeout=3600,
)

orchestrator = Orchestrator(
    agents={"agent1": agent1, "agent2": agent2},
    tool_executor=tool_executor,
    config=config,
)

# Submit a task
task_id = await orchestrator.submit_task(
    description="Research AI trends",
    agent_name="researcher",
)

# Get result
result = await orchestrator.get_task_result(task_id, timeout=300)
```

### ExecutableTask

```python
from multi_agent import ExecutableTask

task = ExecutableTask(
    task_id="task_abc",
    description="Do something",
    agent_name="agent1",
)

result = await task.run(tool_executor)
```

### Parallel Execution

```python
from multi_agent.execution import analyze_and_execute_parallel

tasks = [task1, task2, task3]
results = await analyze_and_execute_parallel(
    tasks=tasks,
    agents={"agent1": agent1, "agent2": agent2},
    tool_executor=tool_executor,
    max_concurrent=50,
)
```

---

## State Management

### StateManager

```python
from multi_agent import StateManager

manager = StateManager(task_id="task_abc")

# Save state
manager.save_state(state)

# Load state
state = manager.load_state()

# Save checkpoint
manager.save_checkpoint(checkpoint)

# Save task
manager.save_task(task)
```

### StateMachine

```python
from multi_agent import StateMachine

sm = StateMachine()

# Add nodes
def my_handler(state: State) -> State:
    return state.add_message(Message(role="assistant", content="Done"))

sm.add_node("process", my_handler)
sm.add_node("finalize", finalize_handler, interrupt_before=True)

# Add edges
sm.add_edge("process", "finalize")
sm.add_conditional_edges(
    "finalize",
    routing={"continue": "process", "end": "__end__"},
)

# Compile
graph = sm.compile()
```

---

## Tools API

### MCPToolManager

```python
from multi_agent import MCPToolManager, MCPServerConfig

manager = MCPToolManager()

# Add servers
config = MCPServerConfig(
    transport="stdio",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/path"],
)

await manager.add_server("filesystem", config)

# List tools
tools = manager.list_tools()

# Execute tool
result = await manager.execute_tool(
    server="filesystem",
    tool_name="read_file",
    arguments={"path": "/path/to/file"},
)
```

### ToolExecutor

```python
from multi_agent import ToolExecutor

executor = ToolExecutor(manager=tool_manager)

# Execute with fallback
result = await executor.execute_with_fallback(
    server="filesystem",
    tool_name="read_file",
    arguments={"path": "/path/to/file"},
    agent_name="agent1",
)
```

---

## Tracing & Metrics

### Tracer

```python
from multi_agent import Tracer, StateManager

state_manager = StateManager(task_id="task_abc")
tracer = Tracer(task_id="task_abc", state_manager=state_manager)

# Log a step
step = tracer.log_step(
    step_name="tool_call",
    message="Calling web search tool",
    agent="researcher",
    status="info",
    tool_calls=[...],
)

# Log tool call
tool_call = tracer.log_tool_call(
    server="web",
    tool="search",
    arguments={"query": "python"},
    result={"pages": [...]},
)

# Get trace
trace = tracer.get_trace()
print(trace.pretty_print())
```

### Metrics

```python
from multi_agent.tracing import get_metrics_tracker

tracker = get_metrics_tracker()

# Track an operation
with tracker.track_operation("agent_execution"):
    # ... do work ...
    pass

# Get statistics
avg_duration = tracker.get_average_duration("agent_execution")
success_rate = tracker.get_success_rate("agent_execution")
p95 = tracker.get_percentile("agent_execution", 95)

# Get summary
summary = tracker.get_summary()
```

---

## Workflow Patterns

### ReAct Pattern

```python
from multi_agent import create_react_pattern, BaseAgent

pattern = create_react_pattern(
    agent=agent,
    max_iterations=10,
)

# Build into state machine
sm = pattern.build("my_react_workflow", StateMachine())
```

### Reflection Pattern

```python
from multi_agent import create_reflection_pattern

pattern = create_reflection_pattern(
    agent=generator_agent,
    critique_agent=critic_agent,
    max_refinements=3,
)
```

### Chain-of-Thought

```python
from multi_agent import create_cot_pattern

pattern = create_cot_pattern(agent=agent)
```

### Pattern Composer

```python
from multi_agent import PatternComposer, create_react_pattern, create_reflection_pattern

composer = PatternComposer("complex_workflow")
composer.add_pattern(create_react_pattern(agent1))
composer.add_pattern(create_reflection_pattern(agent2))

sm = composer.build()
```

### WorkflowExecutor

```python
from multi_agent.execution import WorkflowExecutor, load_workflow_from_file

workflow = load_workflow_from_file("path/to/workflow.yaml")

executor = WorkflowExecutor(
    workflow=workflow,
    agents={"agent1": agent1, "agent2": agent2},
    tool_executor=tool_executor,
)

# Execute
final_state = await executor.execute(
    task_description="Complete the workflow",
)
```

---

## Human-in-the-Loop

### HITLManager

```python
from multi_agent.execution import HITLManager

hitl = HITLManager(task_id="task_abc", state_manager=state_manager)

# Create checkpoint
checkpoint = hitl.create_checkpoint(
    state=current_state,
    node_name="critical_step",
    human_feedback=None,
)

# List checkpoints
checkpoints = hitl.list_checkpoints()

# Resume
resumed_state = hitl.resume_from_checkpoint(
    checkpoint_id=checkpoint.checkpoint_id,
    feedback="Proceed with the operation",
)
```

### InterruptibleWorkflow

```python
from multi_agent.execution import InterruptibleWorkflow

workflow = InterruptibleWorkflow(
    task_id="task_abc",
    state_manager=state_manager,
    interrupt_before={"delete_files", "send_email"},
)

if workflow.should_interrupt("delete_files"):
    # Create checkpoint and wait
    checkpoint = workflow.create_interrupt_checkpoint(state, "delete_files")

# Resume
state = workflow.resume_with_feedback(checkpoint_id, "Confirmed")
```

---

## CLI Usage

```bash
# List tasks
multi-agent task list --status completed

# Show task details
multi-agent task show task_abc123

# View trace logs
multi-agent trace show task_abc123

# Search traces
multi-agent trace search --agent researcher --errors

# List checkpoints
multi-agent checkpoint list task_abc123

# Resume from checkpoint
multi-agent checkpoint resume task_abc123 <checkpoint_id> --feedback "Proceed"

# List agents
multi-agent agents

# List workflows
multi-agent workflows

# Validate workflow
multi-agent workflows my_workflow --format json

# Clean up old tasks
multi-agent cleanup --seconds 86400
```

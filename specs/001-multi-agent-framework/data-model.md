# Data Model: Multi-Agent Framework

**Feature**: 001-multi-agent-framework
**Date**: 2026-01-12
**Status**: Complete

## Overview

This document defines the core entities, their attributes, relationships, and state transitions for the multi-agent framework. All entities use Pydantic for validation and JSON serialization.

---

## Entity Definitions

### 1. Task

Represents a unit of work to be executed.

**Fields**:
| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `id` | str | Unique identifier (UUID v4) | Required |
| `description` | str | Human-readable task description | Required, min_length=1 |
| `status` | TaskStatus | Current execution status | Required |
| `assigned_agent` | str | Name of assigned agent | Required |
| `result` | str | Output result | Optional |
| `error` | str | Error message if failed | Optional |
| `created_at` | datetime | Task creation timestamp | Default=now |
| `started_at` | datetime | Execution start timestamp | Optional |
| `completed_at` | datetime | Execution completion timestamp | Optional |
| `retention_days` | int | Days to keep logs/trace | Optional (default=7) |
| `parent_task_id` | str | Parent task for sub-tasks | Optional |

**State Transitions**:
```
pending → running → completed
                    ↘ failed
```

**Relationships**:
- `TraceLog`: One-to-one (trace contains task execution history)
- `SubAgentSession`: One-to-many (may spawn sub-agent sessions)

---

### 2. Agent

Represents an AI entity with access to specific tools.

**Fields**:
| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `name` | str | Unique agent identifier | Required, pattern=^[a-z][a-z0-9_]*$ |
| `role` | str | Agent's role/purpose | Required |
| `system_prompt` | str | System instruction for LLM | Required |
| `tools` | list[str] | Available tool names | Required, unique items |
| `max_iterations` | int | Maximum reasoning iterations | Default=10 |
| `llm_config` | LLMConfig | LLM endpoint and model | Required |
| `temperature` | float | LLM sampling temperature | Default=0.7, ge=0, le=2 |

**LLMConfig**:
| Field | Type | Description |
|-------|------|-------------|
| `endpoint` | str | API base URL |
| `model` | str | Model identifier |
| `api_key` | str | API key (from environment) |

**Relationships**:
- `Tool`: Many-to-many (agent has many tools, tools can be shared)

---

### 3. State

Represents the shared execution context for an agent run.

**Fields**:
| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `messages` | list[Message] | Conversation history | Required |
| `next_action` | str | Next planned action | Optional |
| `current_agent` | str | Currently executing agent | Required |
| `routing_key` | str | Key for conditional routing | Optional |
| `metadata` | dict | Additional context | Optional |

**Message**:
| Field | Type | Description |
|-------|------|-------------|
| `role` | str | "user", "assistant", "tool", "system" |
| `content` | str | Message content |
| `tool_calls` | list[ToolCall] | Tool invocations (assistant only) |
| `timestamp` | datetime | Message timestamp |

**ToolCall**:
| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Unique call ID (UUID v4) |
| `server` | str | MCP server name |
| `tool` | str | Tool name |
| `arguments` | dict | Tool parameters |

**State Update Behavior**:
- `messages`: Append-only (reducer pattern)
- Other fields: Replace on update

---

### 4. Tool

Represents an invocable capability via MCP.

**Fields**:
| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `name` | str | Tool name | Required |
| `server` | str | MCP server providing tool | Required |
| `description` | str | Tool description | Required |
| `input_schema` | dict | JSON Schema for arguments | Required |
| `output_schema` | dict | JSON Schema for results | Optional |
| `timeout_seconds` | int | Execution timeout | Default=300 (5 min) |
| `fallback_tools` | list[str] | Alternative tools on failure | Optional |

**Relationships**:
- `MCPServer`: Many-to-one (belongs to one server)

---

### 5. MCPServer

Represents an MCP server connection.

**Fields**:
| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `name` | str | Server identifier | Required, unique |
| `transport` | TransportType | "stdio" or "sse" | Required |
| `config` | ServerConfig | Connection parameters | Required |

**ServerConfig (stdio)**:
| Field | Type | Description |
|-------|------|-------------|
| `command` | str | Executable path |
| `args` | list[str] | Command arguments |
| `env` | dict | Environment variables |

**ServerConfig (sse)**:
| Field | Type | Description |
|-------|------|-------------|
| `url` | str | SSE endpoint URL |

---

### 6. TraceLog

Represents the execution history for debugging.

**Fields**:
| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `task_id` | str | Associated task ID | Required |
| `steps` | list[StepRecord] | Execution steps | Required |
| `sub_agent_sessions` | dict[str, SubAgentSessionInfo] | Sub-agent tracking | Required |
| `created_at` | datetime | Log creation timestamp | Default=now |
| `updated_at` | datetime | Last update timestamp | Auto-update |

**StepRecord**:
| Field | Type | Description |
|-------|------|-------------|
| `step_name` | str | Step identifier |
| `message` | str | Description |
| `timestamp` | datetime | When step occurred |
| `status` | str | "info", "warning", "error" |
| `agent` | str | Executing agent |
| `tool_calls` | list[ToolCallRecord] | Tools invoked |
| `duration_ms` | int | Step duration |

**ToolCallRecord**:
| Field | Type | Description |
|-------|------|-------------|
| `server` | str | MCP server |
| `tool` | str | Tool name |
| `arguments` | dict | Input arguments |
| `result` | dict | Output result |
| `error` | str | Error if failed |
| `duration_ms` | int | Call duration |

**SubAgentSessionInfo**:
| Field | Type | Description |
|-------|------|-------------|
| `session_id` | str | Sub-agent session ID |
| `agent` | str | Sub-agent name |
| `message_count` | int | Messages in session |
| `status` | str | Session status |

---

### 7. SubAgentSession

Represents an isolated sub-agent conversation.

**Fields**:
| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `session_id` | str | Unique session ID (UUID v4) | Required |
| `parent_task_id` | str | Parent task ID | Required |
| `agent_name` | str | Sub-agent name | Required |
| `task_description` | str | Sub-task description | Required |
| `message_history` | list[Message] | Isolated conversation | Required |
| `summary` | str | Result summary for parent | Optional |
| `status` | str | "running", "completed", "failed" | Required |
| `created_at` | datetime | Session creation timestamp | Default=now |

**Isolation Guarantee**: Each session maintains separate message history from parent agent.

---

### 8. Workflow

Represents a composed execution pattern.

**Fields**:
| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `name` | str | Workflow identifier | Required |
| `patterns` | list[str] | Pattern sequence (e.g., ["react", "reflection"]) | Required |
| `nodes` | dict[str, NodeDef] | Named workflow nodes | Required |
| `edges` | list[EdgeDef] | Connections between nodes | Required |
| `entry_point` | str | Starting node | Required |
| `checkpoints` | list[str] | Nodes that support HITL | Optional |
| `max_iterations` | int | Global iteration limit | Default=50 |

**NodeDef**:
| Field | Type | Description |
|-------|------|-------------|
| `type` | str | "agent", "tool", "condition", "human" |
| `agent` | str | Agent name (if type=agent) |
| `tool` | str | Tool name (if type=tool) |

**EdgeDef**:
| Field | Type | Description |
|-------|------|-------------|
| `from` | str | Source node |
| `to` | str | Destination node (or condition mapping) |
| `condition` | str | Optional condition expression |

---

### 9. Checkpoint

Represents a saved execution state for HITL.

**Fields**:
| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `checkpoint_id` | str | Unique ID (UUID v4) | Required |
| `task_id` | str | Associated task | Required |
| `state` | State | Full execution state | Required |
| `position` | str | Current node in workflow | Required |
| `sequence` | int | Checkpoint sequence number | Required |
| `created_at` | datetime | Checkpoint timestamp | Default=now |
| `awaiting_human` | bool | Waiting for human input | Default=false |

**Human Feedback** (when resuming):
| Field | Type | Description |
|-------|------|-------------|
| `action` | str | "approve", "reject", "modify" |
| `message` | str | Human feedback message |
| `state_updates` | dict | Manual state modifications |

---

## Entity Relationships

```
Task (1) ──── (1) TraceLog
  │
  ├─── (0..*) SubAgentSession
  │
  └─── (0..*) Checkpoint

Agent (*) ──── (*) Tool
  │
  └─── (1) MCPServer

Workflow (1) ──── (*) NodeDef
           │
           └─── (*) EdgeDef
```

---

## State Transition Diagrams

### Task Lifecycle
```
     ┌─────────┐
     │ pending │
     └────┬────┘
          │ submit
          ▼
     ┌─────────┐     error
     │ running │─────────▶ failed
     └────┬────┘
          │ complete
          ▼
    ┌──────────┐
    │ completed │
    └──────────┘
```

### SubAgentSession Lifecycle
```
     ┌─────────┐
     │ running │
     └────┬────┘
          │
     ┌────┴────┐
     ▼         ▼
┌───────┐ ┌──────┐
│completed││failed│
└───────┘ └──────┘
```

### Checkpoint States
```
┌─────────────┐
│   created   │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ awaiting_human  │ ◀─── HITL pause point
└────────┬────────┘
         │ human response
         ▼
┌─────────────────┐
│    resumed      │
└─────────────────┘
```

---

## Validation Rules

1. **Task ID uniqueness**: UUID v4, globally unique
2. **Agent names**: Snake case, must match `^[a-z][a-z0-9_]*$`
3. **Tool timeout**: Must be positive integer, default 300 seconds
4. **State updates**: `messages` field uses reducer (append), others replace
5. **Workflow DAG**: Must not contain cycles (validated at workflow load)
6. **Checkpoint sequence**: Monotonically increasing per task

---

## Storage Schema

### File Layout
```
~/.multi-agent/
├── tasks/
│   ├── {task_id}/
│   │   ├── task.json           # Task state
│   │   ├── checkpoint_000.json # Historical checkpoints
│   │   ├── checkpoint_001.json
│   │   └── trace.json          # Execution trace
│   └── ...
├── agents/
│   └── {agent_name}.json
├── workflows/
│   └── {workflow_name}.json
└── config/
    ├── mcp_servers.yaml        # MCP server configs
    └── retention_policy.yaml    # Data retention rules
```

### Retention Policy
```yaml
default_days: 7
by_task:
  critical: 30
  debug: 3
by_status:
  completed: 7
  failed: 14
```

---

## Next Steps

Proceed to configuration schema generation in `contracts/` directory.

# Research: Multi-Agent Framework

**Feature**: 001-multi-agent-framework
**Date**: 2026-01-12
**Status**: Complete

## Overview

This document captures research findings and technology decisions for the multi-agent framework implementation. Each research area addresses specific unknowns from the Technical Context.

---

## 1. State Machine Implementation

### Question
How should we implement the graph-based state machine for agent execution flows?

### Decision: Custom Graph Implementation with LangGraph-Inspired Design

**Rationale**:
- **Typed State Support**: Using Python `typing.TypedDict` with `Annotated` for reducer functions provides compile-time type safety and IDE auto-completion
- **Conditional Routing**: Explicit edge definitions (conditional and direct) make flow control declarative and debuggable
- **Visualization**: Graph structure naturally renders to Mermaid/dot for debugging
- **Independence**: Building from scratch avoids external dependency lock-in while learning from proven patterns

**Alternatives Considered**:
| Alternative | Pros | Cons | Verdict |
|------------|------|------|---------|
| LangGraph | Proven, battle-tested | Heavy dependency, opinionated patterns | Rejected for MVP |
| NetworkX | Mature graph library | Not designed for state machines, no reducer support | Rejected |
| Custom (chosen) | Full control, minimal deps | More initial implementation | **Selected** |

**Implementation Pattern**:
```python
from typing import TypedDict, Annotated

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    next_action: str | None
    current_agent: str

def add_messages(left: list, right: list) -> list:
    """Reducer: append messages rather than replace"""
    return left + right

# Graph construction
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_edge("agent", END)
workflow.add_conditional_edges("agent", route_function, {
    "continue": "agent",
    "end": END
})
```

---

## 2. MCP Python SDK

### Question
What is the maturity of MCP Python SDK for stdio and SSE transport?

### Decision: Use `mcp` Python SDK with Direct Protocol Implementation

**Rationale**:
- The official MCP Python SDK (`mcp` package) supports both stdio and SSE transports
- For stdio: Uses `subprocess.Popen` with process management
- For SSE: Uses `aiohttp` for async HTTP connections
- Tool discovery via `list_tools()` and execution via `call_tool()` are well-defined

**Alternatives Considered**:
| Alternative | Pros | Cons | Verdict |
|------------|------|------|---------|
| mcp package | Official support, both transports | Still evolving API | **Selected** |
| Custom stdio only | Full control | No SSE support, more maintenance | Rejected |
| httpx-based SSE | Modern async client | Reinventing protocol layer | Rejected |

**Implementation Pattern**:
```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client

# stdio transport
async def connect_stdio(server_params: StdioServerParameters):
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()

# SSE transport
async def connect_sse(url: str):
    async with sse_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
```

---

## 3. Async Task Orchestration

### Question
How should we implement the 100 concurrent task limit with FIFO queue?

### Decision: asyncio.Semaphore with asyncio.Queue

**Rationale**:
- `asyncio.Semaphore(100)` provides hard limit on concurrent tasks
- `asyncio.Queue` for FIFO pending tasks
- Native Python asyncio - no external dependencies
- Clean integration with existing async ecosystem

**Alternatives Considered**:
| Alternative | Pros | Cons | Verdict |
|------------|------|------|---------|
| asyncio.Semaphore + Queue | Built-in, simple | Manual queue management | **Selected** |
| Celery | Production-ready | Heavy, requires Redis/RabbitMQ | Rejected (overkill) |
| asyncio.create_task limit | Simple | No queue, tasks rejected at limit | Rejected |

**Implementation Pattern**:
```python
import asyncio

class TaskQueue:
    def __init__(self, max_concurrent: int = 100):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.pending = asyncio.Queue()

    async def submit(self, task, coro):
        await self.pending.put((task, coro))
        return await self._process_next()

    async def _process_next(self):
        async with self.semaphore:
            task, coro = await self.pending.get()
            return await coro
```

---

## 4. Checkpoint/Resume Patterns

### Question
How should we implement state serialization for checkpoint/resume?

### Decision: Pydantic Model with JSON Serialization

**Rationale**:
- Pydantic provides automatic serialization/deserialization
- Type validation ensures data integrity on resume
- JSON is human-readable for debugging
- Incremental writes prevent data loss on crashes

**Alternatives Considered**:
| Alternative | Pros | Cons | Verdict |
|------------|------|------|---------|
| Pydantic + JSON | Type-safe, readable | Manual model definition | **Selected** |
| pickle | Automatic for any Python object | Security risk, not human-readable | Rejected |
| shelve | Built-in persistence | Schema evolution difficult | Rejected |

**Implementation Pattern**:
```python
from pydantic import BaseModel
from datetime import datetime

class Checkpoint(BaseModel):
    task_id: str
    state: AgentState
    timestamp: datetime
    position: str  # Current node in workflow

    def save(self, path: str):
        with open(path, "w") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: str) -> "Checkpoint":
        with open(path) as f:
            return cls.model_validate_json(f.read())
```

**Time-Travel Debugging**:
- Store each checkpoint with sequence number
- `checkpoint_000.json`, `checkpoint_001.json`, etc.
- Load any historical checkpoint by ID

---

## 5. Dependency Detection

### Question
How should we implement automatic data dependency detection for parallel execution?

### Decision: LLM-Based Output Analysis with Topological Sort

**Rationale**:
- LLM can parse natural language agent outputs to identify "produces" and "consumes"
- Build DAG from producer-consumer relationships
- `networkx` for topological sort and parallel level detection
- Fallback to sequential execution if analysis fails

**Alternatives Considered**:
| Alternative | Pros | Cons | Verdict |
|------------|------|------|---------|
| LLM analysis | Flexible, no annotations | Requires LLM call, not 100% accurate | **Selected** |
| Manual annotation | Explicit, reliable | Developer burden, not automatic | Rejected |
| Static code analysis | Fast, no LLM needed | Cannot analyze dynamic outputs | Rejected |

**Implementation Pattern**:
```python
import networkx as nx

class DependencyAnalyzer:
    async def analyze(self, tasks: list[Task]) -> nx.DiGraph:
        """Analyze task dependencies via LLM"""
        graph = nx.DiGraph()

        # LLM call to detect produces/consumes
        for task in tasks:
            produces = await self._extract_produces(task)
            consumes = await self._extract_consumes(task)

            graph.add_node(task.id, produces=produces, consumes=consumes)

        # Add edges based on data flow
        for consumer in graph.nodes():
            for producer in graph.nodes():
                if consumer == producer:
                    continue
                if graph.nodes[consumer]["consumes"] & graph.nodes[producer]["produces"]:
                    graph.add_edge(producer.id, consumer.id)

        return graph

    def get_parallel_batches(self, graph: nx.DiGraph) -> list[list[str]]:
        """Return tasks grouped by parallel execution level"""
        return [list(level) for level in nx.topological_generations(graph)]
```

---

## Summary of Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.10+ |
| State Machine | Custom (LangGraph-inspired) | - |
| MCP Protocol | `mcp` package | latest |
| Data Validation | Pydantic | 2.0+ |
| Async Runtime | asyncio (stdlib) | - |
| Concurrency Control | asyncio.Semaphore + Queue | - |
| Graph Analysis | networkx | 3.0+ |
| Serialization | JSON (stdlib) | - |
| Testing | pytest | 7.0+ |
| LLM Client | OpenAI-compatible | - |

---

## Next Steps

Proceed to **Phase 1: Design Artifacts**
- Generate `data-model.md` with entity definitions
- Create configuration schemas in `contracts/`
- Write `quickstart.md` developer guide

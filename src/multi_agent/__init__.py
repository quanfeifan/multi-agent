"""Multi-Agent Framework.

A Python framework for orchestrating AI agents with tool integration,
state machine-based execution, and fault tolerance.
"""

from .agent import BaseAgent
from .config import (
    AgentConfig,
    LLMConfig,
    MCPServerConfig,
    WorkflowConfig,
    load_agent_config,
    load_mcp_servers_config,
    load_workflow_config,
)
from .execution import ExecutableTask, Orchestrator
from .models import (
    Agent,
    Checkpoint,
    Message,
    State,
    SubAgentSession,
    Task,
    TaskStatus,
    Tool,
    ToolCall,
    TraceLog,
    Workflow,
)
from .state import StateMachine, StateManager, create_initial_state
from .tools import MCPToolManager, ToolExecutor
from .tracing import Tracer

__version__ = "0.1.0"

__all__ = [
    # Version
    "__version__",
    # Core entities
    "Task",
    "TaskStatus",
    "Agent",
    "State",
    "Message",
    "Tool",
    "ToolCall",
    "TraceLog",
    "Workflow",
    "Checkpoint",
    "SubAgentSession",
    # Configuration
    "AgentConfig",
    "LLMConfig",
    "WorkflowConfig",
    "MCPServerConfig",
    "load_agent_config",
    "load_workflow_config",
    "load_mcp_servers_config",
    # Agent
    "BaseAgent",
    # Execution
    "ExecutableTask",
    "Orchestrator",
    # State management
    "StateManager",
    "StateMachine",
    "create_initial_state",
    # Tools
    "MCPToolManager",
    "ToolExecutor",
    # Tracing
    "Tracer",
]

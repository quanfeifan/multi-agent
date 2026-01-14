"""Agent module for multi-agent framework."""

from .base import AgentExecutionResult, BaseAgent, ContextLimitError, LLMClient
from .patterns import (
    ChainOfThoughtPattern,
    Pattern,
    PatternComposer,
    ReActPattern,
    ReflectionPattern,
    create_cot_pattern,
    create_reflection_pattern,
    create_react_pattern,
)
from .session import SubAgentSessionManager, create_summary_message
from .supervisor import SubAgentTool, SupervisorAgent

__all__ = [
    "BaseAgent",
    "LLMClient",
    "AgentExecutionResult",
    "ContextLimitError",
    "SubAgentSessionManager",
    "create_summary_message",
    "SupervisorAgent",
    "SubAgentTool",
    "Pattern",
    "ReActPattern",
    "ReflectionPattern",
    "ChainOfThoughtPattern",
    "PatternComposer",
    "create_react_pattern",
    "create_reflection_pattern",
    "create_cot_pattern",
]

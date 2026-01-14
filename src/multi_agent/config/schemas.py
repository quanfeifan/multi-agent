"""Configuration schemas for multi-agent framework.

This module defines Pydantic models for validating configuration data.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class LLMConfig(BaseModel):
    """Configuration for LLM endpoint."""

    endpoint: str = Field(..., description="API base URL")
    model: str = Field(..., description="Model identifier")
    api_key_env: str = Field(..., description="Environment variable name containing API key")
    api_type: Literal["openai", "deepseek", "glm", "ollama", "custom"] = Field(
        default="openai", description="API type"
    )
    temperature: float = Field(default=0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: int | None = Field(default=None, ge=1, description="Maximum tokens to generate")


class AgentConfig(BaseModel):
    """Configuration for an AI agent."""

    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$", description="Unique agent identifier")
    role: str = Field(..., description="Agent's role/purpose")
    system_prompt: str = Field(..., description="System instruction for LLM")
    tools: list[str] = Field(default_factory=list, description="Available tool names")
    max_iterations: int = Field(default=10, ge=1, le=1000, description="Maximum reasoning iterations")
    llm_config: LLMConfig = Field(..., description="LLM endpoint configuration")
    temperature: float | None = Field(default=None, ge=0, le=2, description="Override LLM temperature")


class MCPServerConfigStdio(BaseModel):
    """Configuration for stdio transport."""

    command: str = Field(..., description="Executable path")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")


class MCPServerConfigSSE(BaseModel):
    """Configuration for SSE transport."""

    url: str = Field(..., description="SSE endpoint URL")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP headers")


class MCPServerConfigCustom(BaseModel):
    """Configuration for custom transport."""

    class_path: str = Field(..., description="Python class path (module.submodule:ClassName)")
    init_params: dict[str, Any] = Field(default_factory=dict, description="Initialization parameters")


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server connection."""

    description: str | None = Field(None, description="Server description")
    transport: Literal["stdio", "sse", "custom"] = Field(..., description="Transport type")
    config: MCPServerConfigStdio | MCPServerConfigSSE | MCPServerConfigCustom = Field(
        ..., description="Transport-specific configuration"
    )
    enabled: bool = Field(default=True, description="Whether this server is enabled")

    @field_validator("config")
    @classmethod
    def validate_config_matches_transport(
        cls, v: MCPServerConfigStdio | MCPServerConfigSSE | MCPServerConfigCustom, info
    ) -> MCPServerConfigStdio | MCPServerConfigSSE | MCPServerConfigCustom:
        """Validate that config type matches transport type."""
        transport = info.data.get("transport")
        if transport == "stdio" and not isinstance(v, MCPServerConfigStdio):
            raise ValueError("stdio transport requires MCPServerConfigStdio config")
        if transport == "sse" and not isinstance(v, MCPServerConfigSSE):
            raise ValueError("sse transport requires MCPServerConfigSSE config")
        if transport == "custom" and not isinstance(v, MCPServerConfigCustom):
            raise ValueError("custom transport requires MCPServerConfigCustom config")
        return v


class RetentionPolicyConfig(BaseModel):
    """Configuration for data retention policies."""

    default_days: int = Field(default=7, ge=0, description="Default retention days")
    by_task: dict[str, int] = Field(default_factory=dict, description="Retention by task type")
    by_status: dict[str, int] = Field(
        default_factory=lambda: {"completed": 7, "failed": 14}, description="Retention by status"
    )


class NodeDef(BaseModel):
    """Definition of a workflow node."""

    type: Literal["agent", "tool", "condition", "human", "parallel"] = Field(
        ..., description="Node type"
    )
    agent: str | None = Field(None, description="Agent name (for type=agent)")
    tool: str | None = Field(None, description="Tool name (for type=tool)")
    condition: str | None = Field(None, description="Condition expression (for type=condition)")
    parallel_tasks: list[str] | None = Field(None, description="Parallel task names (for type=parallel)")
    allow_human_input: bool = Field(default=False, description="Enable human-in-the-loop")
    max_iterations: int = Field(default=10, ge=1, description="Maximum iterations for this node")


class EdgeDef(BaseModel):
    """Definition of a workflow edge."""

    from_node: str = Field(..., alias="from", description="Source node name")
    to: str | dict[str, str] = Field(..., description="Target node or conditional routing")
    condition: str | None = Field(None, description="Optional condition expression")

    class Config:
        populate_by_name = True


class WorkflowConfig(BaseModel):
    """Configuration for a workflow."""

    name: str = Field(..., description="Workflow identifier")
    description: str | None = Field(None, description="Workflow description")
    patterns: list[Literal["react", "reflection", "cot", "debate", "tot"]] = Field(
        default_factory=list, description="Composable pattern sequence"
    )
    entry_point: str = Field(..., description="Starting node name")
    nodes: dict[str, NodeDef] = Field(..., description="Named workflow nodes")
    edges: list[EdgeDef] = Field(..., description="Connections between nodes")
    max_iterations: int = Field(default=50, ge=1, description="Global iteration limit")
    checkpoints: list[str] = Field(default_factory=list, description="Nodes that support HITL")


# Validation functions


def validate_agent_config(data: dict[str, Any]) -> AgentConfig:
    """Validate agent configuration data.

    Args:
        data: Raw configuration dictionary

    Returns:
        Validated AgentConfig object

    Raises:
        ValidationError: If the configuration is invalid
    """
    return AgentConfig(**data)


def validate_mcp_server_config(data: dict[str, Any]) -> dict[str, MCPServerConfig]:
    """Validate MCP server configuration data.

    Args:
        data: Raw configuration dictionary

    Returns:
        Dictionary of validated MCPServerConfig objects

    Raises:
        ValidationError: If the configuration is invalid
    """
    return {name: MCPServerConfig(**config) for name, config in data.items()}


def validate_workflow_config(data: dict[str, Any]) -> WorkflowConfig:
    """Validate workflow configuration data.

    Args:
        data: Raw configuration dictionary

    Returns:
        Validated WorkflowConfig object

    Raises:
        ValidationError: If the configuration is invalid
    """
    return WorkflowConfig(**data)


def validate_retention_policy(data: dict[str, Any]) -> RetentionPolicyConfig:
    """Validate retention policy configuration data.

    Args:
        data: Raw configuration dictionary

    Returns:
        Validated RetentionPolicyConfig object

    Raises:
        ValidationError: If the configuration is invalid
    """
    return RetentionPolicyConfig(**data)

"""Tool entity for multi-agent framework.

This module defines Tool and MCPServer entities for MCP protocol integration.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class MCPServerConfigStdio(BaseModel):
    """Configuration for stdio transport.

    Attributes:
        command: Executable path
        args: Command arguments
        env: Environment variables
    """

    command: str = Field(..., description="Executable path")
    args: list[str] = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")


class MCPServerConfigSSE(BaseModel):
    """Configuration for SSE transport.

    Attributes:
        url: SSE endpoint URL
        headers: HTTP headers
    """

    url: str = Field(..., description="SSE endpoint URL")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP headers")


class MCPServerConfigCustom(BaseModel):
    """Configuration for custom transport.

    Attributes:
        class_path: Python class path
        init_params: Initialization parameters
    """

    class_path: str = Field(..., description="Python class path (module.submodule:ClassName)")
    init_params: dict[str, Any] = Field(default_factory=dict, description="Initialization parameters")


class MCPServer(BaseModel):
    """Represents an MCP server connection.

    Attributes:
        name: Server identifier
        transport: Transport type ("stdio" or "sse" or "custom")
        config: Connection parameters
        description: Server description
        enabled: Whether this server is enabled
    """

    name: str = Field(..., description="Server identifier")
    transport: Literal["stdio", "sse", "custom"] = Field(..., description="Transport type")
    config: MCPServerConfigStdio | MCPServerConfigSSE | MCPServerConfigCustom = Field(
        ..., description="Connection parameters"
    )
    description: Optional[str] = Field(None, description="Server description")
    enabled: bool = Field(default=True, description="Whether this server is enabled")

    @property
    def is_stdio(self) -> bool:
        """Check if this is a stdio transport server.

        Returns:
            True if transport is "stdio"
        """
        return self.transport == "stdio"

    @property
    def is_sse(self) -> bool:
        """Check if this is an SSE transport server.

        Returns:
            True if transport is "sse"
        """
        return self.transport == "sse"

    @property
    def is_custom(self) -> bool:
        """Check if this is a custom transport server.

        Returns:
            True if transport is "custom"
        """
        return self.transport == "custom"


class Tool(BaseModel):
    """Represents an invocable capability via MCP.

    Attributes:
        name: Tool name
        server: MCP server providing tool
        description: Tool description
        input_schema: JSON Schema for arguments
        output_schema: JSON Schema for results
        timeout_seconds: Execution timeout
        fallback_tools: Alternative tools on failure
    """

    name: str = Field(..., description="Tool name")
    server: str = Field(..., description="MCP server providing tool")
    description: str = Field(..., description="Tool description")
    input_schema: dict[str, Any] = Field(..., description="JSON Schema for arguments")
    output_schema: Optional[dict[str, Any]] = Field(None, description="JSON Schema for results")
    timeout_seconds: int = Field(default=300, ge=1, description="Execution timeout (seconds)")
    fallback_tools: list[str] = Field(default_factory=list, description="Alternative tools on failure")

    @property
    def full_name(self) -> str:
        """Get the full tool name including server.

        Returns:
            Tool name in "server:tool" format
        """
        return f"{self.server}:{self.name}"

    def has_fallback(self) -> bool:
        """Check if this tool has fallback options.

        Returns:
            True if fallback_tools is not empty
        """
        return len(self.fallback_tools) > 0

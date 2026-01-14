"""Agent entity for multi-agent framework.

This module defines the Agent entity representing an AI entity with tool access.
"""

from typing import Optional

from pydantic import BaseModel, Field

from ..config.schemas import LLMConfig


class Agent(BaseModel):
    """Represents an AI entity with access to specific tools.

    Attributes:
        name: Unique agent identifier (snake case)
        role: Agent's role/purpose
        system_prompt: System instruction for LLM
        tools: Available tool names
        max_iterations: Maximum reasoning iterations
        llm_config: LLM endpoint and model configuration
        temperature: Override LLM sampling temperature
    """

    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$", description="Unique agent identifier")
    role: str = Field(..., description="Agent's role/purpose")
    system_prompt: str = Field(..., description="System instruction for LLM")
    tools: list[str] = Field(default_factory=list, description="Available tool names")
    max_iterations: int = Field(default=10, ge=1, le=1000, description="Maximum reasoning iterations")
    llm_config: LLMConfig = Field(..., description="LLM endpoint configuration")
    temperature: Optional[float] = Field(None, ge=0, le=2, description="Override LLM temperature")

    def get_effective_temperature(self) -> float:
        """Get the effective temperature for this agent.

        Returns the override temperature if set, otherwise the LLM config temperature.

        Returns:
            The temperature value to use
        """
        return self.temperature if self.temperature is not None else self.llm_config.temperature

    def has_tool(self, tool_name: str) -> bool:
        """Check if the agent has access to a specific tool.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if the agent has access to the tool
        """
        return tool_name in self.tools

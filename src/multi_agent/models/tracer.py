"""Tracer entity for multi-agent framework.

This module defines TraceLog entity for execution history tracking.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ToolCallRecord(BaseModel):
    """Represents a tool call in the trace log.

    Attributes:
        server: MCP server
        tool: Tool name
        arguments: Input arguments
        result: Output result
        error: Error if failed
        duration_ms: Call duration
    """

    server: str = Field(..., description="MCP server")
    tool: str = Field(..., description="Tool name")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Input arguments")
    result: Optional[dict[str, Any]] = Field(None, description="Output result")
    error: Optional[str] = Field(None, description="Error if failed")
    duration_ms: int = Field(default=0, ge=0, description="Call duration in milliseconds")


class StepRecord(BaseModel):
    """Represents a single step in the execution trace.

    Attributes:
        step_name: Step identifier
        message: Description
        timestamp: When step occurred
        status: Step status
        agent: Executing agent
        tool_calls: Tools invoked
        duration_ms: Step duration
    """

    step_name: str = Field(..., description="Step identifier")
    message: str = Field(..., description="Description")
    timestamp: datetime = Field(default_factory=datetime.now, description="When step occurred")
    status: str = Field(default="info", description="Step status (info/warning/error)")
    agent: str = Field(..., description="Executing agent")
    tool_calls: list[ToolCallRecord] = Field(default_factory=list, description="Tools invoked")
    duration_ms: int = Field(default=0, ge=0, description="Step duration in milliseconds")


class SubAgentSessionInfo(BaseModel):
    """Information about a sub-agent session in the trace.

    Attributes:
        session_id: Sub-agent session ID
        agent: Sub-agent name
        message_count: Messages in session
        status: Session status
    """

    session_id: str = Field(..., description="Sub-agent session ID")
    agent: str = Field(..., description="Sub-agent name")
    message_count: int = Field(default=0, ge=0, description="Messages in session")
    status: str = Field(..., description="Session status")


class TraceLog(BaseModel):
    """Represents the execution history for debugging.

    Attributes:
        task_id: Associated task ID
        steps: Execution steps
        sub_agent_sessions: Sub-agent tracking
        created_at: Log creation timestamp
        updated_at: Last update timestamp
    """

    task_id: str = Field(..., description="Associated task ID")
    steps: list[StepRecord] = Field(default_factory=list, description="Execution steps")
    sub_agent_sessions: dict[str, SubAgentSessionInfo] = Field(
        default_factory=dict, description="Sub-agent tracking"
    )
    created_at: datetime = Field(default_factory=datetime.now, description="Log creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")

    def add_step(self, step: StepRecord) -> None:
        """Add a step to the trace log.

        Args:
            step: The step to add
        """
        self.steps.append(step)
        self.updated_at = datetime.now()

    def add_sub_agent_session(self, session_id: str, info: SubAgentSessionInfo) -> None:
        """Add or update a sub-agent session.

        Args:
            session_id: The session ID
            info: Session information
        """
        self.sub_agent_sessions[session_id] = info
        self.updated_at = datetime.now()

    @property
    def step_count(self) -> int:
        """Get the number of steps in the trace.

        Returns:
            Number of steps
        """
        return len(self.steps)

    @property
    def total_duration_ms(self) -> int:
        """Calculate total duration of all steps.

        Returns:
            Total duration in milliseconds
        """
        return sum(step.duration_ms for step in self.steps)

    def get_steps_by_agent(self, agent_name: str) -> list[StepRecord]:
        """Get all steps executed by a specific agent.

        Args:
            agent_name: Name of the agent

        Returns:
            List of steps executed by the agent
        """
        return [step for step in self.steps if step.agent == agent_name]

    def get_error_steps(self) -> list[StepRecord]:
        """Get all steps with error status.

        Returns:
            List of error steps
        """
        return [step for step in self.steps if step.status == "error"]

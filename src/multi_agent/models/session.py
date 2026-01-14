"""Sub-agent session entity for multi-agent framework.

This module defines the SubAgentSession entity for isolated sub-agent conversations.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .state import Message


class SubAgentSession(BaseModel):
    """Represents an isolated sub-agent conversation.

    Each session maintains separate message history from the parent agent,
    ensuring isolation between sub-agent executions.

    Attributes:
        session_id: Unique session ID (UUID v4)
        parent_task_id: Parent task ID
        agent_name: Sub-agent name
        task_description: Sub-task description
        message_history: Isolated conversation
        summary: Result summary for parent
        status: Session status
        created_at: Session creation timestamp
    """

    session_id: str = Field(..., description="Unique session ID (UUID v4)")
    parent_task_id: str = Field(..., description="Parent task ID")
    agent_name: str = Field(..., description="Sub-agent name")
    task_description: str = Field(..., description="Sub-task description")
    message_history: list[Message] = Field(
        default_factory=list, description="Isolated conversation"
    )
    summary: Optional[str] = Field(None, description="Result summary for parent")
    status: str = Field(default="running", description="Session status (running/completed/failed)")
    created_at: datetime = Field(default_factory=datetime.now, description="Session creation timestamp")

    def add_message(self, message: Message) -> None:
        """Add a message to the session history.

        Args:
            message: The message to add
        """
        self.message_history.append(message)

    def complete(self, summary: str) -> None:
        """Mark the session as completed with a summary.

        Args:
            summary: Result summary
        """
        self.status = "completed"
        self.summary = summary

    def fail(self, error: str) -> None:
        """Mark the session as failed.

        Args:
            error: Error message
        """
        self.status = "failed"
        self.summary = f"Failed: {error}"

    @property
    def message_count(self) -> int:
        """Get the number of messages in the session.

        Returns:
            Number of messages
        """
        return len(self.message_history)

    @property
    def is_running(self) -> bool:
        """Check if the session is still running.

        Returns:
            True if status is "running"
        """
        return self.status == "running"

    @property
    def is_completed(self) -> bool:
        """Check if the session completed successfully.

        Returns:
            True if status is "completed"
        """
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if the session failed.

        Returns:
            True if status is "failed"
        """
        return self.status == "failed"

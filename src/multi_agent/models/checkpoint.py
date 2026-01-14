"""Checkpoint entity for multi-agent framework.

This module defines the Checkpoint entity for HITL (Human-in-the-Loop) support.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .state import State


class HumanFeedback(BaseModel):
    """Human feedback when resuming from a checkpoint.

    Attributes:
        action: Feedback action
        message: Feedback message
        state_updates: Manual state modifications
    """

    action: str = Field(..., description="Feedback action (approve/reject/modify)")
    message: Optional[str] = Field(None, description="Feedback message")
    state_updates: dict[str, Any] = Field(default_factory=dict, description="Manual state modifications")


class Checkpoint(BaseModel):
    """Represents a saved execution state for HITL.

    Checkpoints allow pausing long-running tasks for human review,
    then resuming from the exact state where it paused.

    Attributes:
        checkpoint_id: Unique ID (UUID v4)
        task_id: Associated task
        state: Full execution state
        position: Current node in workflow
        sequence: Checkpoint sequence number
        created_at: Checkpoint timestamp
        awaiting_human: Waiting for human input
    """

    checkpoint_id: str = Field(..., description="Unique ID (UUID v4)")
    task_id: str = Field(..., description="Associated task")
    state: State = Field(..., description="Full execution state")
    position: str = Field(..., description="Current node in workflow")
    sequence: int = Field(..., ge=0, description="Checkpoint sequence number")
    created_at: datetime = Field(default_factory=datetime.now, description="Checkpoint timestamp")
    awaiting_human: bool = Field(default=False, description="Waiting for human input")

    def await_human_input(self) -> None:
        """Mark this checkpoint as awaiting human input."""
        self.awaiting_human = True

    def apply_feedback(self, feedback: HumanFeedback) -> State:
        """Apply human feedback to create a new state.

        Args:
            feedback: The human feedback to apply

        Returns:
            Updated state
        """
        updated_state = self.state

        # Apply state updates if provided
        if feedback.state_updates:
            updated_state = updated_state.update(**feedback.state_updates)

        # Add feedback as a system message
        from .state import Message

        feedback_message = (
            f"Human feedback: {feedback.action}"
            + (f" - {feedback.message}" if feedback.message else "")
        )
        feedback_msg = Message(role="system", content=feedback_message)
        updated_state = updated_state.add_message(feedback_msg)

        return updated_state

    @property
    def is_awaiting_human(self) -> bool:
        """Check if this checkpoint is awaiting human input.

        Returns:
            True if awaiting human input
        """
        return self.awaiting_human

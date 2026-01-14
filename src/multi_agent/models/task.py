"""Task entity for multi-agent framework.

This module defines the Task entity representing a unit of work to be executed.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Status of a task during execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    """Represents a unit of work to be executed.

    Attributes:
        id: Unique identifier (UUID v4)
        description: Human-readable task description
        status: Current execution status
        assigned_agent: Name of assigned agent
        result: Output result (populated after completion)
        error: Error message if failed
        created_at: Task creation timestamp
        started_at: Execution start timestamp
        completed_at: Execution completion timestamp
        retention_days: Days to keep logs/trace
        parent_task_id: Parent task for sub-tasks
    """

    id: str = Field(..., description="Unique identifier (UUID v4)")
    description: str = Field(..., min_length=1, description="Human-readable task description")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current execution status")
    assigned_agent: str = Field(..., description="Name of assigned agent")
    result: Optional[str] = Field(None, description="Output result")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(default_factory=datetime.now, description="Task creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Execution start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Execution completion timestamp")
    retention_days: int = Field(default=7, ge=0, description="Days to keep logs/trace")
    parent_task_id: Optional[str] = Field(None, description="Parent task for sub-tasks")

    def mark_running(self) -> None:
        """Mark the task as running."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

    def mark_completed(self, result: str) -> None:
        """Mark the task as completed with a result.

        Args:
            result: The output result
        """
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now()

    def mark_failed(self, error: str) -> None:
        """Mark the task as failed with an error.

        Args:
            error: The error message
        """
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate the duration of the task execution in seconds.

        Returns:
            Duration in seconds, or None if the task hasn't completed
        """
        if self.started_at is None or self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

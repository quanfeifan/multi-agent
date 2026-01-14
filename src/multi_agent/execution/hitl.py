"""Human-in-the-Loop (HITL) module for multi-agent framework.

This module provides checkpoint-based pause/resume functionality for long-running tasks.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel

from ..config.paths import get_default_config_dir
from ..models import Agent, Checkpoint, State
from ..state import StateManager
from ..utils import get_logger, generate_uuid

logger = get_logger(__name__)


class CheckpointMetadata(BaseModel):
    """Metadata about a checkpoint.

    Attributes:
        checkpoint_id: Unique checkpoint identifier
        task_id: Associated task ID
        sequence_number: Checkpoint sequence number
        node_name: Node where checkpoint was created
        state: Checkpoint state
        created_at: Creation timestamp
        human_feedback: Human feedback if provided
    """

    checkpoint_id: str
    task_id: str
    sequence_number: int
    node_name: str
    state: State
    created_at: datetime
    human_feedback: Optional[str] = None


class HITLManager:
    """Manages human-in-the-loop checkpoints and pause/resume functionality.

    Provides checkpoint creation, listing, loading, and resume capabilities.
    """

    def __init__(self, task_id: str, state_manager: StateManager) -> None:
        """Initialize the HITL manager.

        Args:
            task_id: Task ID
            state_manager: State manager for persistence
        """
        self.task_id = task_id
        self.state_manager = state_manager
        self._checkpoints_dir = state_manager.task_dir / "checkpoints"
        self._checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self._sequence_counter = self._load_sequence_counter()

    def _load_sequence_counter(self) -> int:
        """Load the current sequence counter.

        Returns:
            Current sequence number
        """
        counter_file = self._checkpoints_dir / ".sequence"
        if counter_file.exists():
            try:
                return int(counter_file.read_text(encoding="utf-8").strip())
            except Exception:
                pass
        return 0

    def _save_sequence_counter(self) -> None:
        """Save the current sequence counter."""
        counter_file = self._checkpoints_dir / ".sequence"
        counter_file.write_text(str(self._sequence_counter), encoding="utf-8")

    def create_checkpoint(
        self,
        state: State,
        node_name: str,
        human_feedback: Optional[str] = None,
    ) -> Checkpoint:
        """Create a checkpoint at the current execution state.

        Args:
            state: Current execution state
            node_name: Name of the node where checkpoint is created
            human_feedback: Optional human feedback

        Returns:
            Created checkpoint
        """
        self._sequence_counter += 1
        self._save_sequence_counter()

        checkpoint_id = generate_uuid()

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            task_id=self.task_id,
            sequence_number=self._sequence_counter,
            state=state,
            human_feedback=human_feedback,
            created_at=datetime.now(),
        )

        # Save checkpoint metadata
        metadata = CheckpointMetadata(
            checkpoint_id=checkpoint_id,
            task_id=self.task_id,
            sequence_number=self._sequence_counter,
            node_name=node_name,
            state=state,
            created_at=checkpoint.created_at,
            human_feedback=human_feedback,
        )

        checkpoint_file = self._checkpoints_dir / f"{checkpoint_id}.json"
        checkpoint_file.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")

        # Save state for quick resume
        self.state_manager.save_state(state)

        logger.info(f"Created checkpoint {checkpoint_id} at node {node_name} (sequence {self._sequence_counter})")

        return checkpoint

    def list_checkpoints(self) -> list[CheckpointMetadata]:
        """List all checkpoints for this task.

        Returns:
            List of checkpoint metadata, sorted by sequence number
        """
        checkpoints: list[CheckpointMetadata] = []

        for checkpoint_file in sorted(self._checkpoints_dir.glob("*.json")):
            if checkpoint_file.name.startswith("."):
                continue

            try:
                data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
                # Convert state dict back to State model
                if "state" in data and isinstance(data["state"], dict):
                    from ..state.serializer import StateSerializer
                    data["state"] = State.model_validate(data["state"])
                checkpoints.append(CheckpointMetadata(**data))
            except Exception as e:
                logger.warning(f"Failed to load checkpoint {checkpoint_file.name}: {e}")

        return sorted(checkpoints, key=lambda c: c.sequence_number)

    def load_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointMetadata]:
        """Load a specific checkpoint.

        Args:
            checkpoint_id: Checkpoint ID to load

        Returns:
            Checkpoint metadata or None if not found
        """
        checkpoint_file = self._checkpoints_dir / f"{checkpoint_id}.json"

        if not checkpoint_file.exists():
            return None

        try:
            data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            # Convert state dict back to State model
            if "state" in data and isinstance(data["state"], dict):
                data["state"] = State.model_validate(data["state"])
            return CheckpointMetadata(**data)
        except Exception as e:
            logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None

    def load_checkpoint_by_sequence(self, sequence_number: int) -> Optional[CheckpointMetadata]:
        """Load a checkpoint by sequence number.

        Args:
            sequence_number: Sequence number to load

        Returns:
            Checkpoint metadata or None if not found
        """
        for checkpoint in self.list_checkpoints():
            if checkpoint.sequence_number == sequence_number:
                return checkpoint
        return None

    def load_latest_checkpoint(self) -> Optional[CheckpointMetadata]:
        """Load the most recent checkpoint.

        Returns:
            Latest checkpoint metadata or None if no checkpoints exist
        """
        checkpoints = self.list_checkpoints()
        return checkpoints[-1] if checkpoints else None

    def resume_from_checkpoint(
        self,
        checkpoint_id: str,
        feedback: Optional[str] = None,
    ) -> Optional[State]:
        """Resume execution from a checkpoint.

        Args:
            checkpoint_id: Checkpoint ID to resume from
            feedback: Optional human feedback to add

        Returns:
            Resumed state or None if checkpoint not found
        """
        checkpoint = self.load_checkpoint(checkpoint_id)

        if checkpoint is None:
            logger.error(f"Checkpoint not found: {checkpoint_id}")
            return None

        # Add feedback if provided
        if feedback:
            from ..models import Message

            feedback_message = Message(
                role="human",
                content=feedback,
            )

            updated_state = checkpoint.state.add_message(feedback_message)

            # Update checkpoint with feedback
            checkpoint.human_feedback = feedback
            checkpoint_file = self._checkpoints_dir / f"{checkpoint_id}.json"
            checkpoint_file.write_text(checkpoint.model_dump_json(indent=2), encoding="utf-8")

            logger.info(f"Resumed from checkpoint {checkpoint_id} with feedback")
            return updated_state

        logger.info(f"Resumed from checkpoint {checkpoint_id}")
        return checkpoint.state

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            checkpoint_id: Checkpoint ID to delete

        Returns:
            True if deleted, False if not found
        """
        checkpoint_file = self._checkpoints_dir / f"{checkpoint_id}.json"

        if not checkpoint_file.exists():
            return False

        try:
            checkpoint_file.unlink()
            logger.info(f"Deleted checkpoint {checkpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
            return False


class InterruptibleWorkflow:
    """Workflow with human-in-the-loop interrupt capabilities.

    Allows pausing execution at designated nodes for human review.
    """

    def __init__(
        self,
        task_id: str,
        state_manager: StateManager,
        interrupt_before: Optional[set[str]] = None,
    ) -> None:
        """Initialize the interruptible workflow.

        Args:
            task_id: Task ID
            state_manager: State manager for persistence
            interrupt_before: Set of node names to interrupt before executing
        """
        self.task_id = task_id
        self.state_manager = state_manager
        self.hitl_manager = HITLManager(task_id, state_manager)
        self.interrupt_before = interrupt_before or set()
        self._awaiting_human = False

    def should_interrupt(self, node_name: str) -> bool:
        """Check if execution should interrupt before a node.

        Args:
            node_name: Node name to check

        Returns:
            True if should interrupt
        """
        return node_name in self.interrupt_before

    def create_interrupt_checkpoint(
        self,
        state: State,
        node_name: str,
        reason: Optional[str] = None,
    ) -> Checkpoint:
        """Create a checkpoint when interrupting.

        Args:
            state: Current execution state
            node_name: Node being interrupted
            reason: Optional reason for interruption

        Returns:
            Created checkpoint
        """
        self._awaiting_human = True

        feedback = reason if reason else f"Interrupted before node: {node_name}"

        return self.hitl_manager.create_checkpoint(state, node_name, feedback)

    def resume_with_feedback(
        self,
        checkpoint_id: str,
        feedback: str,
    ) -> Optional[State]:
        """Resume execution with human feedback.

        Args:
            checkpoint_id: Checkpoint to resume from
            feedback: Human feedback

        Returns:
            Resumed state
        """
        self._awaiting_human = False
        return self.hitl_manager.resume_from_checkpoint(checkpoint_id, feedback)

    def is_awaiting_human(self) -> bool:
        """Check if workflow is waiting for human input.

        Returns:
            True if awaiting human input
        """
        return self._awaiting_human


def load_checkpoint_global(task_id: str, checkpoint_id: str) -> Optional[CheckpointMetadata]:
    """Load a checkpoint from any task.

    Args:
        task_id: Task ID
        checkpoint_id: Checkpoint ID

    Returns:
        Checkpoint metadata or None if not found
    """
    config_dir = get_default_config_dir()
    checkpoint_file = config_dir / "tasks" / task_id / "checkpoints" / f"{checkpoint_id}.json"

    if not checkpoint_file.exists():
        return None

    try:
        data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        if "state" in data and isinstance(data["state"], dict):
            data["state"] = State.model_validate(data["state"])
        return CheckpointMetadata(**data)
    except Exception as e:
        logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
        return None


def list_all_checkpoints(task_id: str) -> list[CheckpointMetadata]:
    """List all checkpoints for a task using global path.

    Args:
        task_id: Task ID

    Returns:
        List of checkpoint metadata
    """
    config_dir = get_default_config_dir()
    checkpoints_dir = config_dir / "tasks" / task_id / "checkpoints"

    if not checkpoints_dir.exists():
        return []

    checkpoints: list[CheckpointMetadata] = []

    for checkpoint_file in sorted(checkpoints_dir.glob("*.json")):
        if checkpoint_file.name.startswith("."):
            continue

        try:
            data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            if "state" in data and isinstance(data["state"], dict):
                data["state"] = State.model_validate(data["state"])
            checkpoints.append(CheckpointMetadata(**data))
        except Exception as e:
            logger.warning(f"Failed to load checkpoint {checkpoint_file.name}: {e}")

    return sorted(checkpoints, key=lambda c: c.sequence_number)

"""State persistence manager for multi-agent framework.

This module provides state persistence with file-based storage and incremental saving.
"""

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from ..config.paths import get_task_dir
from ..models import Checkpoint, Message, State, SubAgentSession, Task
from .serializer import FileStateSerializer, StateSerializer


class StateManager:
    """Manages state persistence with file-based storage.

    Provides thread-safe state persistence with incremental saving
    after each operation to enable crash recovery.
    """

    def __init__(
        self,
        task_id: str,
        config_dir: Optional[Path] = None,
        create_backups: bool = True,
    ) -> None:
        """Initialize the state manager.

        Args:
            task_id: Unique task identifier
            config_dir: Configuration directory
            create_backups: Whether to create backup files
        """
        self.task_id = task_id
        self.task_dir = get_task_dir(task_id, config_dir)
        self.serializer = FileStateSerializer(create_backups=create_backups)
        self._lock = threading.RLock()

    @property
    def state_file(self) -> Path:
        """Get the path to the state file.

        Returns:
            Path to state.json
        """
        return self.task_dir / "state.json"

    @property
    def checkpoint_file(self, checkpoint_num: int) -> Path:
        """Get the path to a checkpoint file.

        Args:
            checkpoint_num: Checkpoint sequence number

        Returns:
            Path to checkpoint_NNN.json
        """
        return self.task_dir / f"checkpoint_{checkpoint_num:03d}.json"

    @property
    def messages_file(self) -> Path:
        """Get the path to the messages file.

        Returns:
            Path to messages.json
        """
        return self.task_dir / "messages.json"

    def save_state(self, state: State) -> None:
        """Save state to disk (incremental save).

        Args:
            state: State to save
        """
        with self._lock:
            self.serializer.save(state, self.state_file)

    def load_state(self) -> Optional[State]:
        """Load state from disk.

        Returns:
            Loaded state or None if file doesn't exist
        """
        with self._lock:
            try:
                return self.serializer.load(self.state_file, State)
            except FileNotFoundError:
                return None

    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint to disk.

        Args:
            checkpoint: Checkpoint to save
        """
        with self._lock:
            path = self.checkpoint_file.format(checkpoint_num=checkpoint.sequence)
            self.serializer.save(checkpoint, path)

    def load_checkpoint(self, sequence: int) -> Optional[Checkpoint]:
        """Load a checkpoint from disk.

        Args:
            sequence: Checkpoint sequence number

        Returns:
            Loaded checkpoint or None if file doesn't exist
        """
        with self._lock:
            try:
                path = self.checkpoint_file.format(checkpoint_num=sequence)
                return self.serializer.load(path, Checkpoint)
            except FileNotFoundError:
                return None

    def list_checkpoints(self) -> list[int]:
        """List all checkpoint sequence numbers.

        Returns:
            List of checkpoint sequences sorted by number
        """
        with self._lock:
            checkpoints: list[int] = []
            for file_path in self.task_dir.glob("checkpoint_*.json"):
                # Extract sequence number from filename
                stem = file_path.stem  # e.g., "checkpoint_001"
                try:
                    num = int(stem.split("_")[1])
                    checkpoints.append(num)
                except (IndexError, ValueError):
                    continue
            return sorted(checkpoints)

    def save_task(self, task: Task) -> None:
        """Save task to disk.

        Args:
            task: Task to save
        """
        with self._lock:
            self.serializer.save(task, self.task_dir / "task.json")

    def load_task(self) -> Optional[Task]:
        """Load task from disk.

        Returns:
            Loaded task or None if file doesn't exist
        """
        with self._lock:
            try:
                return self.serializer.load(self.task_dir / "task.json", Task)
            except FileNotFoundError:
                return None

    def save_session(self, session: SubAgentSession) -> None:
        """Save a sub-agent session to disk.

        Args:
            session: Session to save
        """
        with self._lock:
            session_dir = self.task_dir / "sessions"
            session_dir.mkdir(exist_ok=True)
            path = session_dir / f"{session.session_id}.json"
            self.serializer.save(session, path)

    def load_session(self, session_id: str) -> Optional[SubAgentSession]:
        """Load a sub-agent session from disk.

        Args:
            session_id: Session identifier

        Returns:
            Loaded session or None if file doesn't exist
        """
        with self._lock:
            try:
                path = self.task_dir / "sessions" / f"{session_id}.json"
                return self.serializer.load(path, SubAgentSession)
            except FileNotFoundError:
                return None

    def save_messages_incremental(self, messages: list[Message]) -> None:
        """Save messages incrementally (append-only).

        Args:
            messages: Messages to save
        """
        with self._lock:
            # For incremental saving, we serialize messages and append to file
            data = [m.model_dump() for m in messages]
            self.serializer.save_json({"messages": data}, self.messages_file)

    def load_messages(self) -> list[Message]:
        """Load messages from disk.

        Returns:
            List of loaded messages
        """
        with self._lock:
            try:
                data = self.serializer.load_json(self.messages_file)
                return [Message(**m) for m in data.get("messages", [])]
            except FileNotFoundError:
                return []

    @contextmanager
    def atomic_update(self):
        """Context manager for atomic state updates.

        Acquires lock for the duration of the update.

        Yields:
            None
        """
        self._lock.acquire()
        try:
            yield
        finally:
            self._lock.release()

    def cleanup(self, keep_checkpoints: int = 10) -> None:
        """Clean up old checkpoint files.

        Args:
            keep_checkpoints: Number of most recent checkpoints to keep
        """
        with self._lock:
            checkpoints = self.list_checkpoints()
            if len(checkpoints) > keep_checkpoints:
                # Remove old checkpoints
                for seq in checkpoints[:-keep_checkpoints]:
                    path = self.checkpoint_file.format(checkpoint_num=seq)
                    path.unlink(missing_ok=True)

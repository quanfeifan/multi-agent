"""State serialization for multi-agent framework.

This module provides serialization and deserialization of state objects.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from ..models import (
    Checkpoint,
    Message,
    State,
    SubAgentSession,
    Task,
    TaskStatus,
    ToolCall,
)

T = TypeVar("T", bound=BaseModel)


class StateSerializer:
    """Serializer for state objects.

    Handles JSON serialization with datetime support and Pydantic model validation.
    """

    @staticmethod
    def _datetime_converter(obj: Any) -> Any:
        """Convert datetime objects to ISO format strings.

        Args:
            obj: Object to convert

        Returns:
            JSON-serializable value
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @staticmethod
    def serialize(state: State | Task | Checkpoint | SubAgentSession) -> str:
        """Serialize a state object to JSON string.

        Args:
            state: State object to serialize

        Returns:
            JSON string
        """
        return json.dumps(
            state.model_dump(),
            default=StateSerializer._datetime_converter,
            indent=2,
            ensure_ascii=False,
        )

    @staticmethod
    def deserialize(
        data: str | dict[str, Any],
        model_class: type[T],
    ) -> T:
        """Deserialize JSON to a state object.

        Args:
            data: JSON string or dictionary
            model_class: Pydantic model class

        Returns:
            Deserialized model instance

        Raises:
            ValueError: If deserialization fails
        """
        if isinstance(data, str):
            data = json.loads(data)

        try:
            return model_class(**data)
        except Exception as e:
            raise ValueError(f"Failed to deserialize to {model_class.__name__}: {e}")

    @staticmethod
    def serialize_message(message: Message) -> str:
        """Serialize a single message.

        Args:
            message: Message to serialize

        Returns:
            JSON string
        """
        return json.dumps(
            message.model_dump(),
            default=StateSerializer._datetime_converter,
        )

    @staticmethod
    def deserialize_message(data: str | dict[str, Any]) -> Message:
        """Deserialize JSON to a message.

        Args:
            data: JSON string or dictionary

        Returns:
            Message instance
        """
        return StateSerializer.deserialize(data, Message)

    @staticmethod
    def serialize_messages(messages: list[Message]) -> str:
        """Serialize a list of messages.

        Args:
            messages: Messages to serialize

        Returns:
            JSON string
        """
        return json.dumps(
            [m.model_dump() for m in messages],
            default=StateSerializer._datetime_converter,
        )

    @staticmethod
    def deserialize_messages(data: str | list[dict[str, Any]]) -> list[Message]:
        """Deserialize JSON to a list of messages.

        Args:
            data: JSON string or list of dictionaries

        Returns:
            List of Message instances
        """
        if isinstance(data, str):
            data = json.loads(data)
        return [Message(**m) for m in data]

    @staticmethod
    def serialize_tool_call(tool_call: ToolCall) -> str:
        """Serialize a tool call.

        Args:
            tool_call: ToolCall to serialize

        Returns:
            JSON string
        """
        return json.dumps(tool_call.model_dump())

    @staticmethod
    def deserialize_tool_call(data: str | dict[str, Any]) -> ToolCall:
        """Deserialize JSON to a tool call.

        Args:
            data: JSON string or dictionary

        Returns:
            ToolCall instance
        """
        return StateSerializer.deserialize(data, ToolCall)


class FileStateSerializer:
    """File-based state serializer with automatic backup.

    Provides safe file writing with atomic operations and backup support.
    """

    def __init__(self, create_backups: bool = True) -> None:
        """Initialize the file serializer.

        Args:
            create_backups: Whether to create backup files
        """
        self.create_backups = create_backups

    def save(
        self,
        state: State | Task | Checkpoint | SubAgentSession,
        file_path: Path | str,
    ) -> None:
        """Save state to a file.

        Args:
            state: State object to save
            file_path: Path to save the file
        """
        path = Path(file_path)

        # Create backup if file exists and backups are enabled
        if self.create_backups and path.exists():
            backup_path = path.with_suffix(f"{path.suffix}.bak")
            path.replace(backup_path)

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temporary file first, then rename (atomic operation)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(StateSerializer.serialize(state), encoding="utf-8")
        temp_path.replace(path)

    def load(
        self,
        file_path: Path | str,
        model_class: type[T],
    ) -> T:
        """Load state from a file.

        Args:
            file_path: Path to the file
            model_class: Pydantic model class

        Returns:
            Loaded state object

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If deserialization fails
        """
        path = Path(file_path)

        if not path.exists():
            # Try backup file
            backup_path = path.with_suffix(f"{path.suffix}.bak")
            if backup_path.exists():
                path = backup_path
            else:
                raise FileNotFoundError(f"State file not found: {file_path}")

        try:
            data = path.read_text(encoding="utf-8")
            return StateSerializer.deserialize(data, model_class)
        except Exception as e:
            raise ValueError(f"Failed to load state from {file_path}: {e}")

    def save_json(self, data: dict[str, Any], file_path: Path | str) -> None:
        """Save arbitrary JSON data to a file.

        Args:
            data: Data to save
            file_path: Path to save the file
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        temp_path.replace(path)

    def load_json(self, file_path: Path | str) -> dict[str, Any]:
        """Load arbitrary JSON data from a file.

        Args:
            file_path: Path to the file

        Returns:
            Loaded JSON data

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {file_path}")

        return json.loads(path.read_text(encoding="utf-8"))

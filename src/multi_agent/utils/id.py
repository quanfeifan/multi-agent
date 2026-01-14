"""ID generation utilities for multi-agent framework.

This module provides UUID v4 generation for unique identifiers.
"""

import uuid
from typing import Optional


def generate_uuid() -> str:
    """Generate a UUID v4 as a string.

    Returns:
        UUID v4 string (without dashes)
    """
    return uuid.uuid4().hex


def generate_uuid_with_dashes() -> str:
    """Generate a UUID v4 with dashes.

    Returns:
        UUID v4 string with standard format (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
    """
    return str(uuid.uuid4())


def generate_task_id() -> str:
    """Generate a unique task identifier.

    Returns:
        Task ID prefixed with "task_"
    """
    return f"task_{generate_uuid()}"


def generate_session_id() -> str:
    """Generate a unique session identifier.

    Returns:
        Session ID prefixed with "session_"
    """
    return f"session_{generate_uuid()}"


def generate_checkpoint_id() -> str:
    """Generate a unique checkpoint identifier.

    Returns:
        Checkpoint ID prefixed with "checkpoint_"
    """
    return f"checkpoint_{generate_uuid()}"


def is_valid_uuid(uuid_string: str) -> bool:
    """Check if a string is a valid UUID v4.

    Args:
        uuid_string: String to validate

    Returns:
        True if valid UUID v4
    """
    try:
        # Try with dashes first
        uuid_obj = uuid.UUID(uuid_string)
        return uuid_obj.version == 4
    except ValueError:
        # Try without dashes
        try:
            uuid_obj = uuid.UUID(hex=uuid_string)
            return uuid_obj.version == 4
        except ValueError:
            return False


def extract_task_id(task_id: str) -> Optional[str]:
    """Extract the UUID portion from a task ID.

    Args:
        task_id: Task ID (with or without prefix)

    Returns:
        UUID portion or None if invalid format
    """
    if task_id.startswith("task_"):
        return task_id[5:]
    return task_id if is_valid_uuid(task_id) else None

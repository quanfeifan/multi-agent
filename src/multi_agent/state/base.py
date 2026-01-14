"""Base state management for multi-agent framework.

This module provides the typed state structure with reducer support.
"""

from typing import Any, Callable, TypeVar

from pydantic import BaseModel

from ..models import Message, State

# Reducer type for state updates
StateReducer = Callable[[State, dict[str, Any]], State]

T = TypeVar("T", bound=State)


def create_initial_state(agent_name: str, task_description: str) -> State:
    """Create an initial state for a task.

    Args:
        agent_name: Name of the executing agent
        task_description: Description of the task

    Returns:
        Initial state with user message
    """
    user_message = Message(role="user", content=task_description)
    return State(
        messages=[user_message],
        current_agent=agent_name,
        next_action=None,
    )


def apply_messages_reducer(current: State, update: dict[str, Any]) -> State:
    """Reducer that appends messages instead of replacing.

    Args:
        current: Current state
        update: Update data

    Returns:
        Updated state with messages appended
    """
    if "messages" in update:
        # Extract new messages and merge with existing
        new_messages = update.pop("messages")
        merged_messages = list(current.messages)
        if isinstance(new_messages, list):
            merged_messages.extend(new_messages)
        else:
            merged_messages.append(new_messages)
        update["messages"] = merged_messages

    return current.model_copy(update=update)


def create_state_reducer(
    merge_messages: bool = True,
) -> Callable[[State, dict[str, Any]], State]:
    """Create a state reducer with configurable merge behavior.

    Args:
        merge_messages: If True, merge messages; otherwise replace all fields

    Returns:
        State reducer function
    """
    if merge_messages:
        return apply_messages_reducer

    # Default reducer: replace all fields
    return lambda current, update: current.model_copy(update=update)


def reduce_state(state: State, updates: dict[str, Any], merge_messages: bool = True) -> State:
    """Apply updates to state using reducer pattern.

    Args:
        state: Current state
        updates: Updates to apply
        merge_messages: Whether to merge messages (default: True)

    Returns:
        Updated state
    """
    reducer = create_state_reducer(merge_messages=merge_messages)
    return reducer(state, updates)


class StateReducerBuilder:
    """Builder for creating custom state reducers.

    Allows fine-grained control over how different fields are merged.
    """

    def __init__(self) -> None:
        """Initialize the builder."""
        self._merge_fields: set[str] = {"messages"}  # Default: merge messages
        self._replace_fields: set[str] = set()

    def merge_field(self, field_name: str) -> "StateReducerBuilder":
        """Mark a field to be merged (appended).

        Args:
            field_name: Name of the field

        Returns:
            Self for chaining
        """
        self._merge_fields.add(field_name)
        self._replace_fields.discard(field_name)
        return self

    def replace_field(self, field_name: str) -> "StateReducerBuilder":
        """Mark a field to be replaced.

        Args:
            field_name: Name of the field

        Returns:
            Self for chaining
        """
        self._replace_fields.add(field_name)
        self._merge_fields.discard(field_name)
        return self

    def build(self) -> Callable[[State, dict[str, Any]], State]:
        """Build the reducer function.

        Returns:
            Reducer function
        """
        def reducer(current: State, update: dict[str, Any]) -> State:
            result = current
            merge_data: dict[str, Any] = {}
            replace_data: dict[str, Any] = {}

            for key, value in update.items():
                if key in self._merge_fields and isinstance(value, list):
                    # Merge list fields
                    current_value = getattr(result, key, [])
                    if isinstance(current_value, list):
                        merge_data[key] = list(current_value) + list(value)
                    else:
                        replace_data[key] = value
                else:
                    # Replace other fields
                    replace_data[key] = value

            # Apply merges and replacements
            if merge_data:
                result = result.model_copy(update=merge_data)
            if replace_data:
                result = result.model_copy(update=replace_data)

            return result

        return reducer

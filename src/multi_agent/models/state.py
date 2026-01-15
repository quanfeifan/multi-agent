"""State entity for multi-agent framework.

This module defines the State entity representing the shared execution context.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Represents a tool invocation within a message.

    Attributes:
        id: Unique call ID (UUID v4)
        server: MCP server name (optional, filled during execution)
        tool: Tool name
        arguments: Tool parameters
    """

    id: str = Field(..., description="Unique call ID (UUID v4)")
    server: Optional[str] = Field(None, description="MCP server name")
    tool: str = Field(..., description="Tool name")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")


class Message(BaseModel):
    """Represents a message in the conversation history.

    Attributes:
        role: Message role ("user", "assistant", "tool", "system")
        content: Message content
        tool_calls: Tool invocations (assistant only)
        timestamp: Message timestamp
    """

    role: str = Field(..., description="Message role (user/assistant/tool/system)")
    content: str = Field(..., description="Message content")
    tool_calls: list[ToolCall] = Field(default_factory=list, description="Tool invocations")
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")

    def is_from_assistant(self) -> bool:
        """Check if this message is from the assistant.

        Returns:
            True if role is "assistant"
        """
        return self.role == "assistant"

    def is_from_user(self) -> bool:
        """Check if this message is from the user.

        Returns:
            True if role is "user"
        """
        return self.role == "user"

    def is_from_tool(self) -> bool:
        """Check if this message is from a tool.

        Returns:
            True if role is "tool"
        """
        return self.role == "tool"

    def is_system(self) -> bool:
        """Check if this is a system message.

        Returns:
            True if role is "system"
        """
        return self.role == "system"


class State(BaseModel):
    """Represents the shared execution context for an agent run.

    The state uses a reducer pattern where messages are appended and
    other fields are replaced on update.

    Attributes:
        messages: Conversation history
        next_action: Next planned action
        current_agent: Currently executing agent
        routing_key: Key for conditional routing
        metadata: Additional context
    """

    messages: list[Message] = Field(default_factory=list, description="Conversation history")
    next_action: Optional[str] = Field(None, description="Next planned action")
    current_agent: str = Field(..., description="Currently executing agent")
    routing_key: Optional[str] = Field(None, description="Key for conditional routing")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    def add_message(self, message: Message) -> "State":
        """Add a message to the state.

        Args:
            message: The message to add

        Returns:
            Updated state (immutable pattern)
        """
        updated_messages = list(self.messages)
        updated_messages.append(message)
        return self.model_copy(update={"messages": updated_messages})

    def add_messages(self, messages: list[Message]) -> "State":
        """Add multiple messages to the state.

        Args:
            messages: The messages to add

        Returns:
            Updated state (immutable pattern)
        """
        updated_messages = list(self.messages)
        updated_messages.extend(messages)
        return self.model_copy(update={"messages": updated_messages})

    def update(self, **kwargs: Any) -> "State":
        """Update state fields (except messages, which are appended).

        Args:
            **kwargs: Fields to update

        Returns:
            Updated state (immutable pattern)
        """
        return self.model_copy(update=kwargs)

    def get_last_n_messages(self, n: int) -> list[Message]:
        """Get the last n messages.

        Args:
            n: Number of messages to retrieve

        Returns:
            List of the last n messages
        """
        return self.messages[-n:] if n > 0 else []

    @property
    def message_count(self) -> int:
        """Get the number of messages in the state.

        Returns:
            Number of messages
        """
        return len(self.messages)

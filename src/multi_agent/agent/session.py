"""Sub-agent session management for multi-agent framework.

This module provides session management for isolated sub-agent executions.
"""

from typing import Optional

from pydantic import BaseModel

from ..agent.base import BaseAgent
from ..models import Message, State, SubAgentSession
from ..state import StateManager
from ..tools import ToolExecutor
from ..tracing import Tracer
from ..utils import generate_session_id, get_logger

logger = get_logger(__name__)


class SubAgentSessionManager:
    """Manages sub-agent sessions with isolation guarantees.

    Each session maintains separate message history and state from the parent agent.
    """

    def __init__(
        self,
        parent_task_id: str,
        state_manager: StateManager,
        tracer: Tracer,
    ) -> None:
        """Initialize the session manager.

        Args:
            parent_task_id: Parent task ID
            state_manager: State manager for persistence
            tracer: Trace logger
        """
        self.parent_task_id = parent_task_id
        self.state_manager = state_manager
        self.tracer = tracer
        self.sessions: dict[str, SubAgentSession] = {}

    async def create_session(
        self,
        agent: BaseAgent,
        task_description: str,
    ) -> SubAgentSession:
        """Create a new sub-agent session.

        Args:
            agent: Sub-agent to execute
            task_description: Sub-task description

        Returns:
            Created session
        """
        session_id = generate_session_id()

        # Create initial state with isolated message history
        from ..state.base import create_initial_state

        initial_state = create_initial_state(agent.agent.name, task_description)

        session = SubAgentSession(
            session_id=session_id,
            parent_task_id=self.parent_task_id,
            agent_name=agent.agent.name,
            task_description=task_description,
            message_history=[],
            status="running",
        )

        self.sessions[session_id] = session

        # Log session creation
        self.tracer.log_sub_agent_session(
            session_id=session_id,
            agent=agent.agent.name,
            message_count=0,
            status="running",
        )

        logger.info(f"Created sub-agent session: {session_id} for agent {agent.agent.name}")

        return session

    async def execute_session(
        self,
        session: SubAgentSession,
        agent: BaseAgent,
    ) -> str:
        """Execute a sub-agent session.

        Args:
            session: Session to execute
            agent: Sub-agent instance

        Returns:
            Session summary
        """
        logger.info(f"Executing sub-agent session: {session.session_id}")

        try:
            # Execute agent
            result = await agent.execute(
                task_description=session.task_description,
            )

            # Update session with results
            session.message_history = result.state.messages
            session.complete(result.output)

            # Log completion
            self.tracer.log_sub_agent_session(
                session_id=session.session_id,
                agent=session.agent_name,
                message_count=len(result.state.messages),
                status="completed",
            )

            # Save session
            self.state_manager.save_session(session)

            logger.info(f"Completed sub-agent session: {session.session_id}")

            return result.output

        except Exception as e:
            logger.error(f"Sub-agent session failed: {session.session_id} - {e}")
            session.fail(str(e))

            # Log failure
            self.tracer.log_sub_agent_session(
                session_id=session.session_id,
                agent=session.agent_name,
                message_count=len(session.message_history),
                status="failed",
            )

            # Save session
            self.state_manager.save_session(session)

            raise

    def get_session(self, session_id: str) -> Optional[SubAgentSession]:
        """Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session or None if not found
        """
        return self.sessions.get(session_id)

    def generate_summary(self, session: SubAgentSession) -> str:
        """Generate a summary of the session for the parent agent.

        Args:
            session: Session to summarize

        Returns:
            Session summary
        """
        if session.is_completed:
            return session.summary or f"Task completed: {session.task_description}"
        elif session.is_failed:
            return session.summary or f"Task failed: {session.task_description}"
        else:
            return f"Task in progress: {session.task_description} ({session.message_count} messages)"

    def get_session_messages(self, session: SubAgentSession) -> list[Message]:
        """Get messages from a session.

        Args:
            session: Session to get messages from

        Returns:
            List of messages
        """
        return session.message_history

    def create_summary_message(
        self,
        session: SubAgentSession,
        include_details: bool = False,
    ) -> Message:
        """Create a message summarizing the session for the parent.

        Args:
            session: Session to summarize
            include_details: Whether to include detailed message history

        Returns:
            Summary message
        """
        summary = self.generate_summary(session)

        if include_details and session.message_history:
            # Add key details from the conversation
            details = []
            for msg in session.message_history[-5:]:  # Last 5 messages
                role = msg.role.upper()
                content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                details.append(f"{role}: {content_preview}")

            summary += "\n\nRecent messages:\n" + "\n".join(details)

        return Message(
            role="assistant",
            content=summary,
        )


def create_summary_message(
    session: SubAgentSession,
    include_details: bool = False,
) -> Message:
    """Create a summary message for a sub-agent session.

    Standalone helper function for creating summary messages.

    Args:
        session: Session to summarize
        include_details: Whether to include detailed message history

    Returns:
        Summary message
    """
    if session.is_completed:
        summary = session.summary or f"Task completed: {session.task_description}"
    elif session.is_failed:
        summary = session.summary or f"Task failed: {session.task_description}"
    else:
        summary = f"Task in progress: {session.task_description} ({session.message_count} messages)"

    if include_details and session.message_history:
        # Add key details from the conversation
        details = []
        for msg in session.message_history[-5:]:  # Last 5 messages
            role = msg.role.upper()
            content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            details.append(f"{role}: {content_preview}")

        summary += "\n\nRecent messages:\n" + "\n".join(details)

    return Message(
        role="assistant",
        content=summary,
    )

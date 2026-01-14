"""Supervisor agent for multi-agent framework.

This module provides the Supervisor agent for coordinating sub-agents.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from ..agent.base import AgentExecutionResult, BaseAgent
from ..agent.session import SubAgentSessionManager, create_summary_message
from ..models import Agent, Message, State, ToolCall
from ..state import StateManager
from ..tools import ToolExecutor
from ..tracing import Tracer
from ..utils import get_logger

logger = get_logger(__name__)


class SubAgentTool(BaseModel):
    """Tool wrapper for sub-agent invocation.

    Attributes:
        name: Tool name (e.g., "delegate_research")
        agent: Sub-agent to invoke
        description: Tool description
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    agent: BaseAgent
    description: str


class SupervisorAgent(BaseAgent):
    """Supervisor agent for coordinating specialized sub-agents.

    The supervisor can delegate tasks to sub-agents, aggregate their results,
    and make decisions about which sub-agent to invoke next.
    """

    def __init__(
        self,
        agent: Agent,
        sub_agents: dict[str, BaseAgent],
        tool_executor: Optional[ToolExecutor] = None,
    ) -> None:
        """Initialize the supervisor agent.

        Args:
            agent: Supervisor agent model
            sub_agents: Dictionary of sub-agents by name
            tool_executor: Tool executor
        """
        super().__init__(agent, tool_executor)
        self.sub_agents = sub_agents
        self.sub_agent_tools: list[SubAgentTool] = []

        # Register sub-agents as tools
        for name, sub_agent in sub_agents.items():
            self.sub_agent_tools.append(
                SubAgentTool(
                    name=f"delegate_{name}",
                    agent=sub_agent,
                    description=f"Delegate task to {name} agent",
                )
            )

        # Session manager
        self.session_manager: Optional[SubAgentSessionManager] = None

    async def execute_with_session_manager(
        self,
        task_description: str,
        session_manager: SubAgentSessionManager,
        initial_state: Optional[State] = None,
    ) -> AgentExecutionResult:
        """Execute with session manager for sub-agent tracking.

        Args:
            task_description: Task to execute
            session_manager: Session manager for sub-agents
            initial_state: Optional initial state

        Returns:
            Execution result
        """
        self.session_manager = session_manager
        return await super().execute(task_description, initial_state)

    async def _reasoning_step(self, state: State) -> State:
        """Execute reasoning step with sub-agent delegation.

        Args:
            state: Current state

        Returns:
            Updated state
        """
        # Prepare tools including sub-agents
        tools = self._prepare_tools() + self._prepare_sub_agent_tools()

        # Prepare messages
        messages = self._prepare_messages(state)

        # Call LLM
        response = await self.llm_client.complete(
            messages=messages,
            temperature=self.agent.get_effective_temperature(),
            tools=tools,
        )

        # Add assistant message
        assistant_message = Message(
            role="assistant",
            content=response["content"],
            tool_calls=[
                Message.ToolCall(
                    id=tc["id"],
                    server="sub_agent",
                    tool=tc["tool"],
                    arguments=tc["arguments"],
                )
                for tc in response["tool_calls"]
            ],
        )
        state = state.add_message(assistant_message)

        # Execute tool calls (including sub-agent delegation)
        if response["tool_calls"]:
            state = await self._execute_tool_calls_with_delegation(state, response["tool_calls"])

        return state

    def _prepare_sub_agent_tools(self) -> list[dict[str, Any]]:
        """Prepare sub-agent tools for LLM.

        Returns:
            List of sub-agent tool definitions
        """
        tools: list[dict[str, Any]] = []

        for sub_tool in self.sub_agent_tools:
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": sub_tool.name,
                        "description": sub_tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "task": {
                                    "type": "string",
                                    "description": "Task description for the sub-agent",
                                }
                            },
                            "required": ["task"],
                        },
                    },
                }
            )

        return tools

    async def _execute_tool_calls_with_delegation(
        self,
        state: State,
        tool_calls: list[dict[str, Any]],
    ) -> State:
        """Execute tool calls with sub-agent delegation support.

        Args:
            state: Current state
            tool_calls: Tool calls from LLM

        Returns:
            Updated state
        """
        from ..models import ToolCall

        for tool_call_dict in tool_calls:
            tool_call = ToolCall(**tool_call_dict)

            # Check if this is a sub-agent delegation
            if tool_call.tool.startswith("delegate_"):
                await self._handle_sub_agent_delegation(state, tool_call)
            else:
                # Handle regular tool calls
                await self._handle_regular_tool_call(state, tool_call)

        return state

    async def _handle_sub_agent_delegation(
        self,
        state: State,
        tool_call: ToolCall,
    ) -> None:
        """Handle sub-agent delegation.

        Args:
            state: Current state
            tool_call: Tool call to handle
        """
        # Find sub-agent
        agent_name = tool_call.tool.replace("delegate_", "")
        sub_agent = self.sub_agents.get(agent_name)

        if not sub_agent:
            error_msg = f"Sub-agent not found: {agent_name}"
            logger.warning(error_msg)
            error_message = Message(
                role="tool",
                content=f"Error: {error_msg}",
            )
            state.add_message(error_message)
            return

        if not self.session_manager:
            logger.warning("No session manager available for sub-agent delegation")
            return

        try:
            # Create and execute session
            task_description = tool_call.arguments.get("task", "")
            session = await self.session_manager.create_session(sub_agent, task_description)

            result = await self.session_manager.execute_session(session, sub_agent)

            # Add result as tool message
            result_message = Message(
                role="tool",
                content=result,
                tool_calls=[tool_call],
            )
            state.add_message(result_message)

        except Exception as e:
            logger.error(f"Sub-agent delegation failed: {e}")
            error_message = Message(
                role="tool",
                content=f"Sub-agent execution failed: {str(e)}",
                tool_calls=[tool_call],
            )
            state.add_message(error_message)

    async def _handle_regular_tool_call(
        self,
        state: State,
        tool_call: ToolCall,
    ) -> None:
        """Handle regular (non-sub-agent) tool calls.

        Args:
            state: Current state
            tool_call: Tool call to handle
        """
        if not self.tool_executor:
            error_msg = f"Tool executor not available for: {tool_call.tool}"
            logger.warning(error_msg)
            error_message = Message(
                role="tool",
                content=f"Error: {error_msg}",
                tool_calls=[tool_call],
            )
            state.add_message(error_message)
            return

        # Use parent class method for regular tools
        await super()._execute_tool_calls(state, [tool_call.model_dump()])

    def aggregate_results(self, sessions: list) -> str:
        """Aggregate results from multiple sub-agent sessions.

        Args:
            sessions: List of completed sessions

        Returns:
            Aggregated results summary
        """
        summaries: list[str] = []

        for session in sessions:
            if self.session_manager:
                summary = self.session_manager.generate_summary(session)
                summaries.append(f"- {session.agent_name}: {summary}")

        return "\n\nAggregated Results:\n" + "\n".join(summaries)

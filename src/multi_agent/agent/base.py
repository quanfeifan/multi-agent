"""Base agent implementation for multi-agent framework.

This module provides the base Agent class for LLM-based agent execution.
"""

import json
import os
from typing import Any, Optional

from openai import AsyncOpenAI
from pydantic import BaseModel

from ..config.schemas import AgentConfig, LLMConfig
from ..models import Agent, Message, State, ToolCall
from ..tools import ToolExecutor
from ..utils import get_logger, generate_uuid
from ..utils.timeout import TimeoutError

logger = get_logger(__name__)


class ContextLimitError(Exception):
    """Exception raised when LLM context limit is exceeded."""

    pass


class LLMClient:
    """LLM client wrapper for OpenAI-compatible APIs.

    Supports OpenAI, DeepSeek, GLM, Ollama, and custom endpoints.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize the LLM client.

        Args:
            config: LLM configuration
        """
        self.config = config

        # Get API key from environment
        api_key = os.environ.get(config.api_key_env, "")
        if not api_key and config.api_type not in ["ollama", "custom"]:
            logger.warning(f"API key not found for {config.api_key_env}")

        # Create client
        self.client = AsyncOpenAI(
            base_url=config.endpoint,
            api_key=api_key if api_key else "not-needed",  # Ollama doesn't need API key
        )

    async def complete(
        self,
        messages: list[dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Complete a chat conversation.

        Args:
            messages: Conversation history
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: Available tools for function calling

        Returns:
            Completion response

        Raises:
            ContextLimitError: If context limit is exceeded
        """
        params: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
        }

        if temperature is not None:
            params["temperature"] = temperature
        elif self.config.temperature:
            params["temperature"] = self.config.temperature

        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        elif self.config.max_tokens:
            params["max_tokens"] = self.config.max_tokens

        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        try:
            response = await self.client.chat.completions.create(**params)
            return {
                "content": response.choices[0].message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "server": None,  # Will be filled by agent
                        "tool": tc.function.name,
                        "arguments": self._parse_function_args(tc.function.arguments),
                    }
                    for tc in (response.choices[0].message.tool_calls or [])
                ],
            }
        except Exception as e:
            error_str = str(e).lower()
            # Check for context limit errors
            if "context" in error_str and "limit" in error_str:
                raise ContextLimitError(f"LLM context limit exceeded: {e}")
            logger.error(f"LLM completion error: {e}")
            raise

    def _parse_function_args(self, args_str: str) -> dict[str, Any]:
        """Parse function arguments from JSON string.

        Args:
            args_str: JSON string of arguments

        Returns:
            Parsed arguments dictionary
        """
        try:
            return json.loads(args_str)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse function arguments: {args_str}")
            return {}


class AgentExecutionResult(BaseModel):
    """Result of agent execution.

    Attributes:
        output: Final output text
        state: Final execution state
        steps: Number of iterations
        completed: Whether execution completed
        error: Error message if failed
    """

    output: str
    state: State
    steps: int
    completed: bool
    error: Optional[str] = None


class BaseAgent:
    """Base AI agent with tool calling capabilities.

    Executes reasoning loops with tool invocation and state management.
    Supports context limit handling through progressive message history removal.
    """

    def __init__(
        self,
        agent: Agent,
        tool_executor: Optional[ToolExecutor] = None,
    ) -> None:
        """Initialize the base agent.

        Args:
            agent: Agent configuration
            tool_executor: Tool executor for MCP tools
        """
        self.agent = agent
        self.tool_executor = tool_executor
        self.llm_client = LLMClient(agent.llm_config)
        self._context_limit_retries = 0
        self._max_context_limit_retries = 3

    @classmethod
    def from_config(cls, config: AgentConfig, tool_executor: Optional[ToolExecutor] = None) -> "BaseAgent":
        """Create agent from configuration.

        Args:
            config: Agent configuration
            tool_executor: Tool executor

        Returns:
            BaseAgent instance
        """
        agent = Agent(
            name=config.name,
            role=config.role,
            system_prompt=config.system_prompt,
            tools=config.tools,
            max_iterations=config.max_iterations,
            llm_config=config.llm_config,
            temperature=config.temperature,
        )
        return cls(agent, tool_executor)

    async def execute(
        self,
        task_description: str,
        initial_state: Optional[State] = None,
    ) -> AgentExecutionResult:
        """Execute a task with reasoning loop.

        Args:
            task_description: Task to execute
            initial_state: Optional initial state

        Returns:
            Execution result
        """
        # Create or use initial state
        if initial_state is None:
            from ..state.base import create_initial_state

            state = create_initial_state(self.agent.name, task_description)
        else:
            # Add the new task as a user message to the existing state
            from ..models import Message

            user_message = Message(role="user", content=task_description)
            state = initial_state.add_message(user_message)

        steps = 0
        max_iterations = self.agent.max_iterations

        try:
            while steps < max_iterations:
                steps += 1
                logger.debug(f"Agent {self.agent.name} iteration {steps}/{max_iterations}")

                # Check for completion
                if self._should_complete(state):
                    break

                # Execute reasoning step
                state = await self._reasoning_step(state)

            # Extract final output
            output = self._extract_output(state)

            return AgentExecutionResult(
                output=output,
                state=state,
                steps=steps,
                completed=True,
            )

        except Exception as e:
            logger.error(f"Agent {self.agent.name} execution failed: {e}")
            return AgentExecutionResult(
                output=state.messages[-1].content if state.messages else "",
                state=state,
                steps=steps,
                completed=False,
                error=str(e),
            )

    async def _reasoning_step(self, state: State) -> State:
        """Execute a single reasoning step.

        Args:
            state: Current state

        Returns:
            Updated state
        """
        # Prepare messages for LLM
        messages = self._prepare_messages(state)

        # Prepare tools for LLM
        tools = self._prepare_tools() if self.tool_executor else None

        # Call LLM with context limit handling
        try:
            response = await self.llm_client.complete(
                messages=messages,
                temperature=self.agent.get_effective_temperature(),
                tools=tools,
            )
            # Reset context limit retry counter on success
            self._context_limit_retries = 0
        except ContextLimitError as e:
            logger.warning(f"Context limit exceeded: {e}")
            # Try with reduced context
            state = await self._handle_context_limit(state)
            return state
        except TimeoutError as e:
            logger.error(f"LLM timeout: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM error: {e}")
            raise

        # Add assistant message
        assistant_message = Message(
            role="assistant",
            content=response["content"],
            tool_calls=[
                ToolCall(
                    id=tc["id"] or generate_uuid(),
                    server="",  # Will be filled during tool execution
                    tool=tc["tool"],
                    arguments=tc["arguments"],
                )
                for tc in response["tool_calls"]
            ],
        )
        state = state.add_message(assistant_message)

        # Execute tool calls
        if response["tool_calls"] and self.tool_executor:
            state = await self._execute_tool_calls(state, response["tool_calls"])

        return state

    async def _handle_context_limit(self, state: State) -> State:
        """Handle context limit by removing old messages.

        Args:
            state: Current state

        Returns:
            Updated state with reduced context
        """
        self._context_limit_retries += 1

        if self._context_limit_retries > self._max_context_limit_retries:
            raise RuntimeError("Max context limit retries exceeded")

        # Remove oldest non-system messages (keep at least system prompt + last 10 messages)
        messages = state.messages
        if len(messages) > 15:
            # Keep system messages and recent messages
            system_messages = [m for m in messages if m.is_system()]
            recent_messages = messages[-10:] if len(messages) > 10 else messages

            # Create new state with reduced message history
            from ..state.base import create_initial_state

            reduced_state = State(
                messages=system_messages + recent_messages,
                current_agent=state.current_agent,
                next_action=state.next_action,
                routing_key=state.routing_key,
                metadata=state.metadata,
            )

            logger.info(f"Reduced context from {len(messages)} to {len(reduced_state.messages)} messages")
            return reduced_state

        # Can't reduce further
        raise RuntimeError("Cannot reduce context further")

    def _prepare_messages(self, state: State) -> list[dict[str, Any]]:
        """Prepare messages for LLM.

        Args:
            state: Current state

        Returns:
            List of message dictionaries
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.agent.system_prompt}
        ]

        for msg in state.messages:
            message_dict: dict[str, Any] = {"role": msg.role, "content": msg.content}

            # Add tool calls
            if msg.tool_calls:
                message_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.tool,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]

            messages.append(message_dict)

        return messages

    def _prepare_tools(self) -> list[dict[str, Any]]:
        """Prepare tool definitions for LLM.

        Returns:
            List of tool definitions
        """
        if not self.tool_executor:
            return []

        tools: list[dict[str, Any]] = []

        for tool_name in self.agent.tools:
            # Find tool (could be on any server)
            for tool in self.tool_executor.manager.list_tools():
                if tool.name == tool_name:
                    tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.input_schema,
                            },
                        }
                    )
                    break

        return tools

    async def _execute_tool_calls(
        self,
        state: State,
        tool_calls: list[dict[str, Any]],
    ) -> State:
        """Execute tool calls and update state.

        Args:
            state: Current state
            tool_calls: Tool calls from LLM

        Returns:
            Updated state
        """
        for tool_call_dict in tool_calls:
            tool_call = ToolCall(**tool_call_dict)

            # Find tool
            tool = None
            for available_tool in self.tool_executor.manager.list_tools():
                if available_tool.name == tool_call.tool:
                    tool = available_tool
                    tool_call.server = tool.server
                    break

            if not tool:
                error_msg = f"Tool not found: {tool_call.tool}"
                logger.warning(error_msg)
                # Add error as tool result message
                error_message = Message(
                    role="tool",
                    content=f"Error: {error_msg}",
                    tool_calls=[tool_call],
                )
                state = state.add_message(error_message)
                continue

            try:
                # Execute tool
                result = await self.tool_executor.execute(
                    server=tool.server,
                    tool_name=tool.name,
                    arguments=tool_call.arguments,
                )

                # Add result as tool message
                result_content = str(result)
                result_message = Message(
                    role="tool",
                    content=result_content,
                    tool_calls=[tool_call],
                )
                state = state.add_message(result_message)

            except TimeoutError as e:
                logger.error(f"Tool execution timeout: {tool.full_name}")
                error_message = Message(
                    role="tool",
                    content=f"Tool execution timed out: {str(e)}",
                    tool_calls=[tool_call],
                )
                state = state.add_message(error_message)

            except Exception as e:
                logger.error(f"Tool execution error: {tool.full_name} - {e}")
                error_message = Message(
                    role="tool",
                    content=f"Tool execution failed: {str(e)}",
                    tool_calls=[tool_call],
                )
                state = state.add_message(error_message)

        return state

    def _should_complete(self, state: State) -> bool:
        """Check if execution should complete.

        Args:
            state: Current state

        Returns:
            True if should complete
        """
        # Complete if last message is from assistant with no tool calls
        if not state.messages:
            return False

        last_message = state.messages[-1]
        if last_message.is_from_assistant() and not last_message.tool_calls:
            return True

        return False

    def _extract_output(self, state: State) -> str:
        """Extract final output from state.

        Args:
            state: Final state

        Returns:
            Output text
        """
        if not state.messages:
            return ""

        # Get last assistant message content
        for msg in reversed(state.messages):
            if msg.is_from_assistant():
                return msg.content

        return ""

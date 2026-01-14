"""Agent execution patterns for multi-agent framework.

This module provides reusable execution patterns like ReAct, Reflection, and Chain-of-Thought.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from ..agent import BaseAgent
from ..config.schemas import AgentConfig
from ..models import Agent as AgentModel, Message, State
from ..state import StateMachine
from ..tools import ToolExecutor
from ..utils import get_logger

logger = get_logger(__name__)


class Pattern(ABC):
    """Base class for agent execution patterns.

    Patterns define structured execution flows that can be composed
    into workflows.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Get pattern name."""
        pass

    @abstractmethod
    def build(self, workflow_name: str, state_machine: StateMachine) -> StateMachine:
        """Build the pattern into a state machine.

        Args:
            workflow_name: Name for the workflow
            state_machine: State machine to build into

        Returns:
            Built state machine
        """
        pass


class ReActPattern(Pattern):
    """ReAct (Reason + Act) pattern.

    Implements the think-act-observe loop where the agent:
    1. Thinks about the current state
    2. Acts by calling tools or generating output
    3. Observes the results and updates state
    """

    def __init__(
        self,
        agent: BaseAgent,
        max_iterations: int = 10,
    ) -> None:
        """Initialize the ReAct pattern.

        Args:
            agent: Agent to execute with
            max_iterations: Maximum think-act cycles
        """
        self.agent = agent
        self.max_iterations = max_iterations

    @property
    def name(self) -> str:
        return "react"

    def build(self, workflow_name: str, state_machine: StateMachine) -> StateMachine:
        """Build ReAct pattern into state machine.

        Args:
            workflow_name: Name for the workflow
            state_machine: State machine to build into

        Returns:
            Built state machine
        """

        def think(state: State) -> State:
            """Think step - analyze current state and plan next action."""
            logger.debug(f"[ReAct] Thinking step for agent {self.agent.agent.name}")
            # Add thought prompt to state
            thought_msg = Message(
                role="system",
                content="Think about what to do next based on the current state. "
                        "You can call tools or provide a final answer.",
            )
            return state.add_message(thought_msg)

        def act(state: State) -> State:
            """Act step - execute reasoning and tool calls."""
            logger.debug(f"[ReAct] Acting step for agent {self.agent.agent.name}")
            # This would trigger agent execution with tool calls
            # For now, we'll mark that action should be taken
            updated_state = state.model_copy(update={"next_action": "execute"})
            return updated_state

        def observe(state: State) -> State:
            """Observe step - process results and update understanding."""
            logger.debug(f"[ReAct] Observing step for agent {self.agent.agent.name}")
            # Process tool results and update state
            observation_msg = Message(
                role="system",
                content="Observe the results of your actions and decide what to do next.",
            )
            return state.add_message(observation_msg)

        def should_continue(state: State) -> str:
            """Check if we should continue looping."""
            # Check if we've reached max iterations or have a final answer
            if len(state.messages) >= self.max_iterations * 3:
                return "end"

            # Check if last message has a final answer (no tool calls)
            if state.messages and state.messages[-1].is_from_assistant():
                if not state.messages[-1].tool_calls:
                    return "end"

            return "continue"

        # Add nodes
        state_machine.add_node("think", think)
        state_machine.add_node("act", act)
        state_machine.add_node("observe", observe)

        # Add edges for the loop
        state_machine.add_conditional_edges(
            "observe",
            routing={"continue": "think", "end": "__end__"},
            condition=lambda s: should_continue(s),
        )
        state_machine.add_edge("think", "act")
        state_machine.add_edge("act", "observe")

        state_machine.entry_point = "think"

        return state_machine


class ReflectionPattern(Pattern):
    """Reflection pattern.

    Implements generate -> critique -> refine loop where:
    1. Generate initial output
    2. Critique the output
    3. Refine based on critique
    """

    def __init__(
        self,
        agent: BaseAgent,
        critique_agent: Optional[BaseAgent] = None,
        max_refinements: int = 3,
    ) -> None:
        """Initialize the Reflection pattern.

        Args:
            agent: Primary agent for generation
            critique_agent: Optional separate agent for critique
            max_refinements: Maximum refinement iterations
        """
        self.agent = agent
        self.critique_agent = critique_agent or agent
        self.max_refinements = max_refinements

    @property
    def name(self) -> str:
        return "reflection"

    def build(self, workflow_name: str, state_machine: StateMachine) -> StateMachine:
        """Build Reflection pattern into state machine.

        Args:
            workflow_name: Name for the workflow
            state_machine: State machine to build into

        Returns:
            Built state machine
        """

        def generate(state: State) -> State:
            """Generate initial output."""
            logger.debug(f"[Reflection] Generating with agent {self.agent.agent.name}")
            prompt_msg = Message(
                role="user",
                content="Generate your response to the task.",
            )
            return state.add_message(prompt_msg)

        def critique(state: State) -> State:
            """Critique the current output."""
            logger.debug(f"[Reflection] Critiquing with agent {self.critique_agent.agent.name}")
            critique_prompt = Message(
                role="user",
                content="Critique the previous response. Identify strengths, weaknesses, and areas for improvement.",
            )
            return state.add_message(critique_prompt)

        def refine(state: State) -> State:
            """Refine based on critique."""
            logger.debug(f"[Reflection] Refining with agent {self.agent.agent.name}")
            refine_prompt = Message(
                role="user",
                content="Refine your previous response based on the critique provided.",
            )
            return state.add_message(refine_prompt)

        def should_refine(state: State) -> str:
            """Check if we should continue refining."""
            # Count refinement cycles
            refinement_count = sum(1 for m in state.messages if "refine" in m.content.lower())
            if refinement_count >= self.max_refinements:
                return "end"
            return "continue"

        # Add nodes
        state_machine.add_node("generate", generate)
        state_machine.add_node("critique", critique)
        state_machine.add_node("refine", refine)

        # Add edges for the loop
        state_machine.add_edge("generate", "critique")
        state_machine.add_edge("critique", "refine")
        state_machine.add_conditional_edges(
            "refine",
            routing={"continue": "critique", "end": "__end__"},
            condition=lambda s: should_refine(s),
        )

        state_machine.entry_point = "generate"

        return state_machine


class ChainOfThoughtPattern(Pattern):
    """Chain-of-Thought pattern.

    Guides the agent to think through problems step-by-step,
    making reasoning explicit before final output.
    """

    def __init__(
        self,
        agent: BaseAgent,
    ) -> None:
        """Initialize the Chain-of-Thought pattern.

        Args:
            agent: Agent to execute with
        """
        self.agent = agent

    @property
    def name(self) -> str:
        return "cot"

    def build(self, workflow_name: str, state_machine: StateMachine) -> StateMachine:
        """Build Chain-of-Thought pattern into state machine.

        Args:
            workflow_name: Name for the workflow
            state_machine: State machine to build into

        Returns:
            Built state machine
        """

        def setup_thinking(state: State) -> State:
            """Setup the thinking process."""
            logger.debug(f"[CoT] Setting up thinking for agent {self.agent.agent.name}")
            setup_msg = Message(
                role="system",
                content="Think through this problem step-by-step. "
                        "1. Understand the problem\n"
                        "2. Break it down into sub-problems\n"
                        "3. Solve each sub-problem\n"
                        "4. Combine into final answer",
            )
            return state.add_message(setup_msg)

        def think_step(state: State) -> State:
            """Execute a thinking step."""
            logger.debug(f"[CoT] Thinking step for agent {self.agent.agent.name}")
            return state.model_copy(update={"next_action": "think"})

        def final_answer(state: State) -> State:
            """Generate final answer."""
            logger.debug(f"[CoT] Generating final answer for agent {self.agent.agent.name}")
            final_msg = Message(
                role="user",
                content="Based on your step-by-step thinking, provide the final answer.",
            )
            return state.add_message(final_msg)

        # Add nodes
        state_machine.add_node("setup", setup_thinking)
        state_machine.add_node("think", think_step)
        state_machine.add_node("answer", final_answer)

        # Add edges
        state_machine.add_edge("setup", "think")
        state_machine.add_edge("think", "answer")
        state_machine.add_edge("answer", "__end__")

        state_machine.entry_point = "setup"

        return state_machine


class PatternComposer:
    """Composer for combining multiple patterns.

    Allows building complex workflows by composing simpler patterns.
    """

    def __init__(self, workflow_name: str) -> None:
        """Initialize the pattern composer.

        Args:
            workflow_name: Name for the composed workflow
        """
        self.workflow_name = workflow_name
        self.patterns: list[Pattern] = []

    def add_pattern(self, pattern: Pattern) -> "PatternComposer":
        """Add a pattern to the composition.

        Args:
            pattern: Pattern to add

        Returns:
            Self for chaining
        """
        self.patterns.append(pattern)
        return self

    def build(self) -> StateMachine:
        """Build the composed workflow.

        Returns:
            Built state machine
        """
        state_machine = StateMachine()

        # Build each pattern in sequence
        for i, pattern in enumerate(self.patterns):
            pattern_name = f"{pattern.name}_{i}"
            state_machine = pattern.build(pattern_name, state_machine)

        return state_machine


def create_react_pattern(
    agent: BaseAgent,
    max_iterations: int = 10,
) -> ReActPattern:
    """Create a ReAct pattern.

    Args:
        agent: Agent to execute with
        max_iterations: Maximum think-act cycles

    Returns:
        ReAct pattern instance
    """
    return ReActPattern(agent, max_iterations)


def create_reflection_pattern(
    agent: BaseAgent,
    critique_agent: Optional[BaseAgent] = None,
    max_refinements: int = 3,
) -> ReflectionPattern:
    """Create a Reflection pattern.

    Args:
        agent: Primary agent for generation
        critique_agent: Optional separate agent for critique
        max_refinements: Maximum refinement iterations

    Returns:
        Reflection pattern instance
    """
    return ReflectionPattern(agent, critique_agent, max_refinements)


def create_cot_pattern(
    agent: BaseAgent,
) -> ChainOfThoughtPattern:
    """Create a Chain-of-Thought pattern.

    Args:
        agent: Agent to execute with

    Returns:
        Chain-of-Thought pattern instance
    """
    return ChainOfThoughtPattern(agent)

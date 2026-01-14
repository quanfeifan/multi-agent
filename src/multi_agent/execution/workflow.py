"""Workflow execution engine for multi-agent framework.

This module provides workflow loading, validation, and execution.
"""

import asyncio
from pathlib import Path
from typing import Any, Optional

import yaml

from ..agent import BaseAgent
from ..agent.patterns import ChainOfThoughtPattern, Pattern, ReActPattern, ReflectionPattern
from ..config.paths import get_default_config_dir
from ..config.schemas import WorkflowConfig
from ..models import State, Workflow
from ..state import StateMachine
from ..tools import ToolExecutor
from ..utils import get_logger

logger = get_logger(__name__)


class WorkflowExecutor:
    """Executes workflows defined as graphs of nodes and edges.

    Supports pattern-based workflows (ReAct, Reflection, CoT) and
    custom workflows from YAML configuration.
    """

    def __init__(
        self,
        workflow: Workflow,
        agents: dict[str, BaseAgent],
        tool_executor: Optional[ToolExecutor] = None,
    ) -> None:
        """Initialize the workflow executor.

        Args:
            workflow: Workflow definition
            agents: Available agents by name
            tool_executor: Tool executor for tool nodes
        """
        self.workflow = workflow
        self.agents = agents
        self.tool_executor = tool_executor
        self.state_machine = StateMachine(workflow)
        self._compile_workflow()

    def _compile_workflow(self) -> None:
        """Compile the workflow into a state machine."""
        # Add all nodes to the state machine
        for node_name, node_def in self.workflow.nodes.items():
            handler = self._create_node_handler(node_def)
            interrupt = node_def.allow_human_input or self.workflow.is_checkpoint_node(node_name)
            self.state_machine.add_node(node_name, handler, interrupt_before=interrupt)

        # Compile and validate
        try:
            self.state_machine.compile()
        except ValueError as e:
            logger.error(f"Workflow compilation failed: {e}")
            raise

    def _create_node_handler(self, node_def: Any) -> Any:
        """Create a handler function for a node.

        Args:
            node_def: Node definition

        Returns:
            Handler function
        """

        async def handler(state: State) -> State:
            """Default node handler."""
            node_type = node_def.type if hasattr(node_def, "type") else "agent"

            if node_type == "agent" and node_def.agent:
                agent = self.agents.get(node_def.agent)
                if agent:
                    # Execute agent with current state
                    result = await agent.execute(
                        task_description=state.messages[-1].content if state.messages else "",
                        initial_state=state,
                    )
                    # Update state with result
                    from ..models import Message
                    result_msg = Message(
                        role="assistant",
                        content=result.output,
                    )
                    return state.add_message(result_msg)

            elif node_type == "tool" and node_def.tool and self.tool_executor:
                # Execute tool
                # Parse tool calls from state or execute directly
                pass

            elif node_type == "human":
                # Wait for human input
                state = state.model_copy(update={"next_action": "await_human"})
                return state

            elif node_type == "parallel" and node_def.parallel_tasks:
                # Execute parallel tasks
                pass

            return state

        return handler

    async def execute(
        self,
        initial_state: Optional[State] = None,
        task_description: str = "",
    ) -> State:
        """Execute the workflow.

        Args:
            initial_state: Optional initial state
            task_description: Task description to execute

        Returns:
            Final state after execution
        """
        if initial_state is None:
            from ..state.base import create_initial_state
            initial_state = create_initial_state(
                self.workflow.name,
                task_description,
            )

        state = initial_state
        current_node = self.workflow.entry_point
        iterations = 0
        max_iterations = self.workflow.max_iterations

        while current_node and current_node != "__end__" and iterations < max_iterations:
            iterations += 1
            logger.debug(f"Workflow executing node: {current_node} (iteration {iterations})")

            # Check for interrupt
            if self.state_machine.should_interrupt(current_node):
                logger.info(f"Workflow interrupted before node: {current_node}")
                state = state.model_copy(update={"next_action": "interrupted"})
                break

            # Get handler for node
            handler_info = self.state_machine.handlers.get(current_node)
            if not handler_info:
                logger.warning(f"No handler for node: {current_node}")
                break

            # Execute node handler
            try:
                state = await handler_info.handler(state)
            except Exception as e:
                logger.error(f"Node handler failed for {current_node}: {e}")
                from ..models import Message
                error_msg = Message(
                    role="system",
                    content=f"Error in node {current_node}: {str(e)}",
                )
                state = state.add_message(error_msg)
                break

            # Get next node
            current_node = self.state_machine.get_next_node(current_node, state)

        logger.info(f"Workflow execution completed after {iterations} iterations")
        return state

    def get_execution_graph(self) -> StateMachine:
        """Get the compiled execution graph.

        Returns:
            State machine graph
        """
        return self.state_machine


def load_workflow_from_file(file_path: Path) -> Workflow:
    """Load workflow from YAML file.

    Args:
        file_path: Path to workflow YAML file

    Returns:
        Loaded workflow

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If workflow is invalid
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Workflow file not found: {file_path}")

    try:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        config = WorkflowConfig(**data)
        return config.to_workflow()
    except Exception as e:
        raise ValueError(f"Failed to load workflow from {file_path}: {e}")


def load_workflow_from_config(config: WorkflowConfig) -> Workflow:
    """Load workflow from configuration.

    Args:
        config: Workflow configuration

    Returns:
        Loaded workflow
    """
    return config.to_workflow()


def find_workflow_files() -> list[Path]:
    """Find all workflow YAML files in config directory.

    Returns:
        List of workflow file paths
    """
    config_dir = get_default_config_dir()
    workflows_dir = config_dir / "workflows"

    if not workflows_dir.exists():
        return []

    return list(workflows_dir.glob("*.yaml")) + list(workflows_dir.glob("*.yml"))


def validate_workflow(workflow: Workflow) -> list[str]:
    """Validate a workflow for correctness.

    Args:
        workflow: Workflow to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors: list[str] = []

    # Check entry point exists
    if workflow.entry_point not in workflow.nodes:
        errors.append(f"Entry point '{workflow.entry_point}' not found in nodes")

    # Check all edge targets exist
    for edge in workflow.edges:
        if edge.from_node not in workflow.nodes:
            errors.append(f"Edge source '{edge.from_node}' not found in nodes")

        if isinstance(edge.to, str):
            if edge.to not in workflow.nodes and edge.to != "__end__":
                errors.append(f"Edge target '{edge.to}' not found in nodes")
        elif isinstance(edge.to, dict):
            for target in edge.to.values():
                if target not in workflow.nodes and target != "__end__":
                    errors.append(f"Edge target '{target}' not found in nodes")

    # Check for cycles using state machine compilation
    try:
        sm = StateMachine(workflow)
        sm.compile()
    except ValueError as e:
        errors.append(str(e))

    # Check checkpoint nodes exist
    for checkpoint in workflow.checkpoints:
        if checkpoint not in workflow.nodes:
            errors.append(f"Checkpoint node '{checkpoint}' not found in nodes")

    return errors


def create_workflow_from_pattern(
    name: str,
    pattern: Pattern,
    entry_point: str = "start",
) -> Workflow:
    """Create a workflow from a pattern.

    Args:
        name: Workflow name
        pattern: Pattern to build from
        entry_point: Entry point node name

    Returns:
        Created workflow
    """
    state_machine = pattern.build(name, StateMachine())

    # Convert state machine to workflow
    from ..models import NodeDef, EdgeDef

    nodes: dict[str, NodeDef] = {}
    edges: list[EdgeDef] = []

    for node_name in state_machine.graph.nodes():
        if node_name == "__end__":
            continue

        handler_info = state_machine.handlers.get(node_name)
        node_type = "agent" if handler_info else "condition"

        nodes[node_name] = NodeDef(
            type=node_type,
            agent=handler_info.name if handler_info else None,
        )

    for from_node, to_node in state_machine.graph.edges():
        edges.append(EdgeDef(from_=from_node, to=to_node))

    return Workflow(
        name=name,
        patterns=[pattern.name],
        nodes=nodes,
        edges=edges,
        entry_point=entry_point,
    )

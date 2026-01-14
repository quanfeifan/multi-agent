"""Graph-based state machine for multi-agent framework.

This module provides a state machine implementation for workflow execution.
"""

import networkx as nx
from typing import Any, Callable, Optional

from pydantic import BaseModel

from ..models import State, Workflow, NodeDef, EdgeDef


class NodeHandler(BaseModel):
    """Handler for a node in the state machine.

    Attributes:
        name: Node name
        handler: Execution function
        interrupt_before: Whether to interrupt before execution
    """

    name: str
    handler: Callable[[State], State]
    interrupt_before: bool = False


class ConditionalEdge(BaseModel):
    """Conditional routing edge.

    Attributes:
        from_node: Source node
        condition: Condition expression or callable
        routing: Mapping of condition values to target nodes
        default: Default target node
    """

    from_node: str
    condition: str | object | None = None
    routing: dict[str, str] = {}
    default: str | None = None


class StateMachine:
    """Graph-based state machine for workflow execution.

    Supports node registration, conditional edges, and execution flow.
    Uses networkx for graph operations and visualization.

    Attributes:
        workflow: Associated workflow definition
        graph: Directed graph representation
        handlers: Node execution handlers
        conditional_edges: Conditional routing rules
        entry_point: Starting node name
    """

    def __init__(self, workflow: Optional[Workflow] = None) -> None:
        """Initialize the state machine.

        Args:
            workflow: Optional workflow definition
        """
        self.workflow = workflow
        self.graph: nx.DiGraph = nx.DiGraph()
        self.handlers: dict[str, NodeHandler] = {}
        self.conditional_edges: dict[str, ConditionalEdge] = {}
        self.entry_point: str | None = None

        if workflow:
            self._load_workflow(workflow)

    def _load_workflow(self, workflow: Workflow) -> None:
        """Load workflow definition into the state machine.

        Args:
            workflow: Workflow to load
        """
        self.workflow = workflow
        self.entry_point = workflow.entry_point
        self.graph.clear()
        self.handlers.clear()
        self.conditional_edges.clear()

        # Add all nodes
        for node_name, node_def in workflow.nodes.items():
            self.graph.add_node(node_name, **node_def.model_dump())

        # Add all edges
        for edge_def in workflow.edges:
            if isinstance(edge_def.to, dict):
                # Conditional edge
                self.conditional_edges[edge_def.from_node] = ConditionalEdge(
                    from_node=edge_def.from_node,
                    condition=edge_def.condition,
                    routing=edge_def.to,
                    default=None,
                )
                # Add edges to all possible targets
                for target in edge_def.to.values():
                    self.graph.add_edge(edge_def.from_node, target)
            else:
                # Simple edge
                self.graph.add_edge(edge_def.from_node, edge_def.to)

    def add_node(
        self,
        name: str,
        handler: Callable[[State], State],
        interrupt_before: bool = False,
        **node_attrs: Any,
    ) -> None:
        """Add a node to the state machine.

        Args:
            name: Node name
            handler: Execution function
            interrupt_before: Whether to interrupt before execution
            **node_attrs: Additional node attributes
        """
        self.graph.add_node(name, **node_attrs)
        self.handlers[name] = NodeHandler(name=name, handler=handler, interrupt_before=interrupt_before)

        if self.entry_point is None:
            self.entry_point = name

    def add_edge(self, from_node: str, to_node: str, **edge_attrs: Any) -> None:
        """Add an edge between nodes.

        Args:
            from_node: Source node name
            to_node: Target node name
            **edge_attrs: Additional edge attributes
        """
        self.graph.add_edge(from_node, to_node, **edge_attrs)

    def add_conditional_edges(
        self,
        from_node: str,
        routing: dict[str, str],
        condition: Optional[str] = None,
        default: Optional[str] = None,
    ) -> None:
        """Add conditional routing edges.

        Args:
            from_node: Source node name
            routing: Mapping of condition values to target nodes
            condition: Optional condition expression
            default: Default target node
        """
        self.conditional_edges[from_node] = ConditionalEdge(
            from_node=from_node,
            condition=condition,
            routing=routing,
            default=default,
        )

        # Add edges to all possible targets
        for target in set(routing.values()) | ({default} if default else set()):
            if target:
                self.graph.add_edge(from_node, target)

    def compile(self) -> nx.DiGraph:
        """Compile the state machine graph.

        Validates the graph and returns it for execution.

        Returns:
            Compiled directed graph

        Raises:
            ValueError: If graph has cycles or entry point is missing
        """
        if self.entry_point is None:
            raise ValueError("State machine has no entry point")

        # Check for cycles (excluding __end__ which is a terminal node)
        graph_without_end = self.graph.copy()
        graph_without_end.remove_node("__end__") if "__end__" in graph_without_end else None

        if not nx.is_directed_acyclic_graph(graph_without_end):
            cycles = list(nx.simple_cycles(graph_without_end))
            raise ValueError(f"State machine contains cycles: {cycles}")

        return self.graph

    def get_next_node(self, current_node: str, state: State) -> Optional[str]:
        """Get the next node to execute based on current state.

        Args:
            current_node: Current node name
            state: Current execution state

        Returns:
            Next node name or None if execution should end
        """
        # Check for conditional edge
        if current_node in self.conditional_edges:
            cond_edge = self.conditional_edges[current_node]

            # Evaluate condition if provided
            if cond_edge.condition:
                try:
                    result = eval(cond_edge.condition, {"state": state})
                    next_node = cond_edge.routing.get(result)
                    if next_node:
                        return next_node
                except Exception:
                    pass

            # Check routing_key in state
            if state.routing_key in cond_edge.routing:
                return cond_edge.routing[state.routing_key]

            # Return default if set
            if cond_edge.default:
                return cond_edge.default

        # Get simple edge
        successors = list(self.graph.successors(current_node))
        if not successors:
            return None
        if len(successors) == 1:
            return successors[0]

        # Multiple successors without conditional edge - use first
        return successors[0]

    def should_interrupt(self, node_name: str) -> bool:
        """Check if execution should interrupt before a node.

        Args:
            node_name: Node name to check

        Returns:
            True if should interrupt
        """
        handler = self.handlers.get(node_name)
        if handler:
            return handler.interrupt_before

        # Check workflow checkpoint configuration
        if self.workflow and self.workflow.is_checkpoint_node(node_name):
            return True

        return False

    def visualize(self, format: str = "mermaid") -> str:
        """Generate a visualization of the state machine.

        Args:
            format: Visualization format ("mermaid" or "dot")

        Returns:
            Visualization string
        """
        if format == "mermaid":
            return self._to_mermaid()
        elif format == "dot":
            return self._to_dot()
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _to_mermaid(self) -> str:
        """Convert to Mermaid diagram format.

        Returns:
            Mermaid diagram string
        """
        lines = ["graph TD"]

        # Add nodes
        for node in self.graph.nodes():
            lines.append(f"  {node}[{node}]")

        # Add edges
        for from_node, to_node in self.graph.edges():
            lines.append(f"  {from_node} --> {to_node}")

        # Add entry point marker
        if self.entry_point:
            lines.append(f"  START(({self.entry_point}))")
            lines.append(f"  START --> {self.entry_point}")

        return "\n".join(lines)

    def _to_dot(self) -> str:
        """Convert to Graphviz DOT format.

        Returns:
            DOT format string
        """
        lines = ["digraph state_machine {"]
        lines.append("  rankdir=LR;")
        lines.append("  node [shape=box];")

        # Add nodes
        for node in self.graph.nodes():
            label = node
            if node == self.entry_point:
                lines.append(f'  "{node}" [style="bold",label="{label}"];')
            else:
                lines.append(f'  "{node}" [label="{label}"];')

        # Add edges
        for from_node, to_node in self.graph.edges():
            lines.append(f'  "{from_node}" -> "{to_node}";')

        lines.append("}")
        return "\n".join(lines)

    def get_node_info(self, node_name: str) -> Optional[dict[str, Any]]:
        """Get information about a node.

        Args:
            node_name: Node name

        Returns:
            Node attributes or None if not found
        """
        return self.graph.nodes.get(node_name)

    def get_execution_path(self, start_node: Optional[str] = None) -> list[str]:
        """Get a possible execution path through the graph.

        Args:
            start_node: Starting node (default: entry point)

        Returns:
            List of node names in execution order
        """
        if start_node is None:
            start_node = self.entry_point

        if start_node is None:
            return []

        # Simple path following
        path: list[str] = []
        current = start_node
        visited: set[str] = set()

        while current and current not in visited and current != "__end__":
            path.append(current)
            visited.add(current)
            successors = list(self.graph.successors(current))
            current = successors[0] if successors else None

        return path

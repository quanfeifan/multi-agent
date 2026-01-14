"""Workflow entity for multi-agent framework.

This module defines the Workflow entity for graph-based execution patterns.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class NodeDef(BaseModel):
    """Definition of a workflow node.

    Attributes:
        type: Node type
        agent: Agent name (for type=agent)
        tool: Tool name (for type=tool)
        condition: Condition expression (for type=condition)
        parallel_tasks: Parallel task names (for type=parallel)
        allow_human_input: Enable human-in-the-loop
        max_iterations: Maximum iterations for this node
    """

    type: Literal["agent", "tool", "condition", "human", "parallel"] = Field(
        ..., description="Node type"
    )
    agent: Optional[str] = Field(None, description="Agent name (for type=agent)")
    tool: Optional[str] = Field(None, description="Tool name (for type=tool)")
    condition: Optional[str] = Field(None, description="Condition expression (for type=condition)")
    parallel_tasks: Optional[list[str]] = Field(None, description="Parallel tasks (for type=parallel)")
    allow_human_input: bool = Field(default=False, description="Enable human-in-the-loop")
    max_iterations: int = Field(default=10, ge=1, description="Maximum iterations")


class EdgeDef(BaseModel):
    """Definition of a workflow edge.

    Attributes:
        from_node: Source node name
        to: Target node or conditional routing
        condition: Optional condition expression
    """

    from_node: str = Field(..., alias="from", description="Source node name")
    to: str | dict[str, str] = Field(..., description="Target node or conditional routing")
    condition: Optional[str] = Field(None, description="Optional condition expression")

    class Config:
        populate_by_name = True


class Workflow(BaseModel):
    """Represents a composed execution pattern.

    Workflows define execution flow as a graph of nodes and edges,
    supporting composable patterns like ReAct and Reflection.

    Attributes:
        name: Workflow identifier
        patterns: Pattern sequence
        nodes: Named workflow nodes
        edges: Connections between nodes
        entry_point: Starting node
        checkpoints: Nodes that support HITL
        max_iterations: Global iteration limit
    """

    name: str = Field(..., description="Workflow identifier")
    patterns: list[Literal["react", "reflection", "cot", "debate", "tot"]] = Field(
        default_factory=list, description="Pattern sequence"
    )
    nodes: dict[str, NodeDef] = Field(..., description="Named workflow nodes")
    edges: list[EdgeDef] = Field(..., description="Connections between nodes")
    entry_point: str = Field(..., description="Starting node")
    checkpoints: list[str] = Field(default_factory=list, description="Nodes that support HITL")
    max_iterations: int = Field(default=50, ge=1, description="Global iteration limit")

    def has_pattern(self, pattern: str) -> bool:
        """Check if workflow contains a specific pattern.

        Args:
            pattern: Pattern name to check

        Returns:
            True if pattern is in the workflow
        """
        return pattern in self.patterns

    def is_checkpoint_node(self, node_name: str) -> bool:
        """Check if a node is a checkpoint node.

        Args:
            node_name: Name of the node

        Returns:
            True if the node supports checkpoints
        """
        return node_name in self.checkpoints

    def get_node(self, node_name: str) -> Optional[NodeDef]:
        """Get a node definition by name.

        Args:
            node_name: Name of the node

        Returns:
            Node definition or None if not found
        """
        return self.nodes.get(node_name)

    def get_outgoing_edges(self, node_name: str) -> list[EdgeDef]:
        """Get all outgoing edges from a node.

        Args:
            node_name: Source node name

        Returns:
            List of edges from this node
        """
        return [edge for edge in self.edges if edge.from_node == node_name]

    @property
    def node_count(self) -> int:
        """Get the number of nodes in the workflow.

        Returns:
            Number of nodes
        """
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Get the number of edges in the workflow.

        Returns:
            Number of edges
        """
        return len(self.edges)

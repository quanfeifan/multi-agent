"""Unit tests for state machine."""

import pytest
from multi_agent.state.machine import StateMachine, NodeHandler, ConditionalEdge
from multi_agent.models import Workflow, NodeDef, EdgeDef, State


class TestNodeHandler:
    """Tests for NodeHandler model."""

    def test_create_node_handler(self):
        """Test creating a node handler."""
        def dummy_handler(state: State) -> State:
            return state

        handler = NodeHandler(
            name="test_node",
            handler=dummy_handler,
            interrupt_before=False
        )
        assert handler.name == "test_node"
        assert handler.interrupt_before is False


class TestConditionalEdge:
    """Tests for ConditionalEdge model."""

    def test_create_conditional_edge(self):
        """Test creating a conditional edge."""
        edge = ConditionalEdge(
            from_node="node1",
            condition="state.status == 'done'",
            routing={"done": "end", "continue": "next"},
            default="next"
        )
        assert edge.from_node == "node1"
        assert edge.condition == "state.status == 'done'"
        assert edge.routing == {"done": "end", "continue": "next"}
        assert edge.default == "next"


class TestStateMachine:
    """Tests for StateMachine class."""

    def test_create_empty_state_machine(self):
        """Test creating an empty state machine."""
        sm = StateMachine()
        assert sm.workflow is None
        assert sm.entry_point is None
        assert len(sm.handlers) == 0

    def test_create_state_machine_from_workflow(self):
        """Test creating state machine from workflow definition."""
        workflow = Workflow(
            name="test_workflow",
            entry_point="start",
            nodes={
                "start": NodeDef(type="agent", agent="agent1"),
                "end": NodeDef(type="agent", agent="agent2")
            },
            edges=[
                EdgeDef(from_node="start", to="end")
            ]
        )

        sm = StateMachine(workflow)
        assert sm.workflow.name == "test_workflow"
        assert sm.entry_point == "start"

    def test_add_node(self):
        """Test adding a node to the state machine."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("test_node", handler)
        assert "test_node" in sm.graph.nodes()
        assert "test_node" in sm.handlers
        assert sm.entry_point == "test_node"

    def test_add_node_with_interrupt(self):
        """Test adding a node with interrupt_before flag."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("checkpoint", handler, interrupt_before=True)
        assert sm.should_interrupt("checkpoint") is True

    def test_add_edge(self):
        """Test adding an edge between nodes."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("node1", handler)
        sm.add_node("node2", handler)
        sm.add_edge("node1", "node2")

        assert sm.graph.has_edge("node1", "node2")

    def test_add_conditional_edges(self):
        """Test adding conditional routing edges."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("node1", handler)
        sm.add_node("success", handler)
        sm.add_node("failure", handler)

        sm.add_conditional_edges(
            "node1",
            routing={"success": "success", "fail": "failure"},
            default="failure"
        )

        assert "node1" in sm.conditional_edges
        assert sm.graph.has_edge("node1", "success")
        assert sm.graph.has_edge("node1", "failure")

    def test_compile_valid_dag(self):
        """Test compiling a valid DAG."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("start", handler)
        sm.add_node("middle", handler)
        sm.add_node("end", handler)
        sm.add_edge("start", "middle")
        sm.add_edge("middle", "end")

        graph = sm.compile()
        assert graph is not None
        assert len(graph.nodes()) == 3

    def test_compile_with_cycle_fails(self):
        """Test that compiling a graph with cycles fails."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("node1", handler)
        sm.add_node("node2", handler)
        sm.add_edge("node1", "node2")
        sm.add_edge("node2", "node1")  # Creates a cycle

        with pytest.raises(ValueError, match="contains cycles"):
            sm.compile()

    def test_compile_without_entry_point_fails(self):
        """Test that compiling without entry point fails."""
        sm = StateMachine()
        # No nodes added, so no entry point

        with pytest.raises(ValueError, match="no entry point"):
            sm.compile()

    def test_get_next_node_simple_edge(self):
        """Test getting next node with simple edge."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("start", handler)
        sm.add_node("next", handler)
        sm.add_edge("start", "next")

        state = State(current_agent="test")
        next_node = sm.get_next_node("start", state)
        assert next_node == "next"

    def test_get_next_node_conditional(self):
        """Test getting next node with conditional routing."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("decision", handler)
        sm.add_node("success", handler)
        sm.add_node("failure", handler)

        sm.add_conditional_edges(
            "decision",
            routing={"yes": "success", "no": "failure"},
            default="failure"
        )

        # Test with routing_key
        state_yes = State(current_agent="test", routing_key="yes")
        next_node = sm.get_next_node("decision", state_yes)
        assert next_node == "success"

        state_no = State(current_agent="test", routing_key="no")
        next_node = sm.get_next_node("decision", state_no)
        assert next_node == "failure"

    def test_get_next_node_terminal(self):
        """Test getting next node when at terminal."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("end", handler)

        state = State(current_agent="test")
        next_node = sm.get_next_node("end", state)
        assert next_node is None

    def test_should_interrupt(self):
        """Test interrupt detection."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("normal", handler, interrupt_before=False)
        sm.add_node("checkpoint", handler, interrupt_before=True)

        assert sm.should_interrupt("normal") is False
        assert sm.should_interrupt("checkpoint") is True

    def test_visualize_mermaid(self):
        """Test Mermaid visualization."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("start", handler)
        sm.add_node("end", handler)
        sm.add_edge("start", "end")

        mermaid = sm.visualize(format="mermaid")
        assert "graph TD" in mermaid
        assert "start" in mermaid
        assert "end" in mermaid
        assert "start --> end" in mermaid

    def test_visualize_dot(self):
        """Test Graphviz DOT visualization."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("start", handler)
        sm.add_node("end", handler)
        sm.add_edge("start", "end")

        dot = sm.visualize(format="dot")
        assert "digraph state_machine" in dot
        assert '"start"' in dot
        assert '"end"' in dot

    def test_invalid_visualization_format(self):
        """Test that invalid visualization format raises error."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("start", handler)

        with pytest.raises(ValueError, match="Unsupported format"):
            sm.visualize(format="invalid")

    def test_get_node_info(self):
        """Test getting node information."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("test", handler, custom_attr="value")
        info = sm.get_node_info("test")

        assert info is not None
        assert info.get("custom_attr") == "value"

    def test_get_execution_path(self):
        """Test getting execution path."""
        sm = StateMachine()

        def handler(state: State) -> State:
            return state

        sm.add_node("start", handler)
        sm.add_node("middle", handler)
        sm.add_node("end", handler)
        sm.add_edge("start", "middle")
        sm.add_edge("middle", "end")

        path = sm.get_execution_path()
        assert path == ["start", "middle", "end"]

    def test_load_workflow_with_conditional_edges(self):
        """Test loading workflow with conditional edges."""
        workflow = Workflow(
            name="conditional_workflow",
            entry_point="start",
            nodes={
                "start": NodeDef(type="agent", agent="agent1"),
                "branch_a": NodeDef(type="agent", agent="agent2"),
                "branch_b": NodeDef(type="agent", agent="agent3"),
            },
            edges=[
                EdgeDef(from_node="start", to={"a": "branch_a", "b": "branch_b"}, condition="state.choice")
            ]
        )

        sm = StateMachine(workflow)
        assert "start" in sm.conditional_edges
        assert sm.graph.has_edge("start", "branch_a")
        assert sm.graph.has_edge("start", "branch_b")

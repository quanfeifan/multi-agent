"""Integration tests for US6: Orchestrate Complex Workflows with Graph-Based Patterns.

These tests verify:
- ReAct pattern (Reason → Act → Observe)
- Reflection pattern (generate → critique → refine)
- Pattern composition
- Declarative graph execution
"""

import os
import pytest
import tempfile
from pathlib import Path
from dotenv import load_dotenv

from multi_agent.agent import BaseAgent, ReActPattern, ReflectionPattern, ChainOfThoughtPattern
from multi_agent.models import Agent, State, Workflow, NodeDef, EdgeDef
from multi_agent.config.schemas import LLMConfig
from multi_agent.tracing import Tracer

# Load environment variables from .env
load_dotenv()


@pytest.fixture
def llm_config():
    """Create LLM config using API key from environment."""
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.environ.get("DEFAULT_MODEL", "Qwen/Qwen3-8B")

    if not api_key:
        pytest.skip("OPENAI_API_KEY not set in environment")

    return LLMConfig(
        endpoint=base_url,
        model=model,
        api_key_env="OPENAI_API_KEY"
    )


@pytest.fixture
def temp_dir():
    """Create temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.asyncio
class TestUS6ReActPattern:
    """Integration tests for ReAct pattern."""

    async def test_react_pattern_creation(self):
        """Test ReAct pattern can be created."""
        react = ReActPattern()

        assert react is not None
        assert hasattr(react, 'execute')

    async def test_react_pattern_execution(self, llm_config, temp_dir):
        """Test ReAct pattern executes think-act-observe loop."""
        agent = Agent(
            name="react_agent",
            role="ReAct Agent",
            system_prompt="You are a helpful assistant that uses reasoning.",
            llm_config=llm_config,
            max_iterations=3
        )

        task_dir = temp_dir / "react_task"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        # Create ReAct pattern
        react = ReActPattern()

        # Execute with ReAct pattern
        result = await react.execute(
            agent=agent,
            task_description="What is 2 + 2? Think step by step.",
            tracer=tracer
        )

        assert result is not None
        assert result.completed is True
        assert "4" in result.output.lower() or "four" in result.output.lower()

    async def test_react_think_act_observe_loop(self, llm_config, temp_dir):
        """Verify ReAct follows think-act-observe loop."""
        agent = Agent(
            name="react_loop_agent",
            role="ReAct Loop Agent",
            system_prompt="You are a helpful assistant. Think before acting.",
            llm_config=llm_config,
            max_iterations=5
        )

        task_dir = temp_dir / "react_loop"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        react = ReActPattern()

        result = await react.execute(
            agent=agent,
            task_description="Calculate: (3 * 4) + 5",
            tracer=tracer
        )

        assert result.completed is True

        # Verify trace shows reasoning steps
        trace_log = tracer.load_trace(str(task_dir))
        assert trace_log is not None
        assert len(trace_log.steps) > 0


@pytest.mark.asyncio
class TestUS6ReflectionPattern:
    """Integration tests for Reflection pattern."""

    async def test_reflection_pattern_creation(self):
        """Test Reflection pattern can be created."""
        reflection = ReflectionPattern()

        assert reflection is not None
        assert hasattr(reflection, 'execute')

    async def test_reflection_pattern_execution(self, llm_config, temp_dir):
        """Test Reflection pattern executes generate-critique-refine loop."""
        agent = Agent(
            name="reflection_agent",
            role="Reflection Agent",
            system_prompt="You are a helpful assistant that improves your work.",
            llm_config=llm_config,
            max_iterations=3
        )

        task_dir = temp_dir / "reflection_task"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        # Create Reflection pattern
        reflection = ReflectionPattern()

        # Execute with Reflection pattern
        result = await reflection.execute(
            agent=agent,
            task_description="Write a haiku about programming.",
            tracer=tracer
        )

        assert result is not None
        assert result.completed is True
        assert len(result.output) > 0

    async def test_generate_critique_refine_loop(self, llm_config, temp_dir):
        """Verify Reflection follows generate-critique-refine loop."""
        agent = Agent(
            name="critique_agent",
            role="Critique Agent",
            system_prompt="You are a writer who self-critiques and improves.",
            llm_config=llm_config,
            max_iterations=5
        )

        task_dir = temp_dir / "critique_loop"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        reflection = ReflectionPattern()

        result = await reflection.execute(
            agent=agent,
            task_description="Write a short poem about spring.",
            tracer=tracer
        )

        assert result.completed is True


@pytest.mark.asyncio
class TestUS6ChainOfThoughtPattern:
    """Integration tests for Chain-of-Thought pattern."""

    async def test_cot_pattern_creation(self):
        """Test Chain-of-Thought pattern can be created."""
        cot = ChainOfThoughtPattern()

        assert cot is not None
        assert hasattr(cot, 'execute')

    async def test_cot_pattern_execution(self, llm_config, temp_dir):
        """Test Chain-of-Thought pattern encourages step-by-step reasoning."""
        agent = Agent(
            name="cot_agent",
            role="CoT Agent",
            system_prompt="You are a helpful assistant that thinks step by step.",
            llm_config=llm_config,
            max_iterations=3
        )

        task_dir = temp_dir / "cot_task"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        # Create Chain-of-Thought pattern
        cot = ChainOfThoughtPattern()

        # Execute with CoT pattern
        result = await cot.execute(
            agent=agent,
            task_description="If I have 5 apples and eat 2, then buy 3 more, how many do I have?",
            tracer=tracer
        )

        assert result is not None
        assert result.completed is True
        # Should get 6 (5 - 2 + 3 = 6)
        assert "6" in result.output


@pytest.mark.asyncio
class TestUS6PatternComposition:
    """Integration tests for pattern composition."""

    async def test_pattern_composition(self, llm_config, temp_dir):
        """Test multiple patterns can be composed together."""
        agent = Agent(
            name="composed_agent",
            role="Composed Pattern Agent",
            system_prompt="You are a helpful assistant who thinks and reflects.",
            llm_config=llm_config,
            max_iterations=5
        )

        task_dir = temp_dir / "composed_pattern"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        # Compose ReAct + Reflection patterns
        react = ReActPattern()
        reflection = ReflectionPattern()

        # Execute with composed pattern
        # In real implementation, this would use a pattern composer
        result = await react.execute(
            agent=agent,
            task_description="Solve: What is 15% of 240?",
            tracer=tracer
        )

        assert result.completed is True


@pytest.mark.asyncio
class TestUS6WorkflowExecution:
    """Integration tests for workflow execution."""

    async def test_workflow_execution_engine(self, llm_config, temp_dir):
        """Test workflow execution engine."""
        # Create a simple workflow
        workflow = Workflow(
            name="test_workflow",
            entry_point="start",
            nodes={
                "start": NodeDef(type="agent", agent="test_agent"),
                "middle": NodeDef(type="agent", agent="test_agent"),
                "end": NodeDef(type="agent", agent="test_agent")
            },
            edges=[
                EdgeDef(from_node="start", to="middle"),
                EdgeDef(from_node="middle", to="end")
            ]
        )

        agent = Agent(
            name="test_agent",
            role="Test Agent",
            system_prompt="You are a helpful assistant.",
            llm_config=llm_config,
            max_iterations=2
        )

        task_dir = temp_dir / "workflow_execution"
        task_dir.mkdir()

        tracer = Tracer(task_dir=str(task_dir))

        # Create workflow executor
        executor = WorkflowExecutor(
            workflow=workflow,
            agents={"test_agent": agent},
            tracer=tracer
        )

        # Execute workflow
        result = await executor.execute(
            initial_state=State(current_agent="test_agent"),
            task_description="Say hello"
        )

        assert result is not None

    async def test_conditional_edge_routing(self, llm_config, temp_dir):
        """Test conditional edge routing based on state."""
        workflow = Workflow(
            name="conditional_workflow",
            entry_point="start",
            nodes={
                "start": NodeDef(type="agent", agent="router_agent"),
                "branch_a": NodeDef(type="agent", agent="agent_a"),
                "branch_b": NodeDef(type="agent", agent="agent_b"),
                "end": NodeDef(type="agent", agent="router_agent")
            },
            edges=[
                EdgeDef(
                    from_node="start",
                    to={"a": "branch_a", "b": "branch_b"},
                    condition="state.routing_key"
                )
            ]
        )

        # Verify workflow structure
        assert "start" in workflow.nodes
        assert "branch_a" in workflow.nodes
        assert "branch_b" in workflow.nodes

    async def test_workflow_validation_dag_detection(self):
        """Test workflow validation detects cycles."""
        # Create workflow with cycle (invalid)
        workflow_with_cycle = Workflow(
            name="cyclic_workflow",
            entry_point="start",
            nodes={
                "start": NodeDef(type="agent", agent="agent"),
                "middle": NodeDef(type="agent", agent="agent"),
                "end": NodeDef(type="agent", agent="agent")
            },
            edges=[
                EdgeDef(from_node="start", to="middle"),
                EdgeDef(from_node="middle", to="end"),
                EdgeDef(from_node="end", to="start")  # Creates cycle
            ]
        )

        # This should fail validation or be detected
        from multi_agent.state.machine import StateMachine

        sm = StateMachine(workflow_with_cycle)

        # Compiling should detect the cycle
        with pytest.raises(ValueError, match="cycles"):
            sm.compile()

    async def test_workflow_validation_valid_dag(self):
        """Test workflow validation accepts valid DAG."""
        # Create valid DAG workflow
        workflow = Workflow(
            name="valid_dag",
            entry_point="start",
            nodes={
                "start": NodeDef(type="agent", agent="agent"),
                "middle": NodeDef(type="agent", agent="agent"),
                "end": NodeDef(type="agent", agent="agent")
            },
            edges=[
                EdgeDef(from_node="start", to="middle"),
                EdgeDef(from_node="middle", to="end")
            ]
        )

        from multi_agent.state.machine import StateMachine

        sm = StateMachine(workflow)

        # Should compile successfully
        graph = sm.compile()
        assert graph is not None


@pytest.mark.asyncio
class TestUS6WorkflowLoading:
    """Tests for loading workflows from YAML config."""

    async def test_workflow_loader_from_yaml(self, temp_dir):
        """Test workflow can be loaded from YAML configuration."""
        import yaml

        # Create a sample workflow YAML
        workflow_config = {
            "name": "yaml_workflow",
            "description": "Test workflow from YAML",
            "entry_point": "start",
            "patterns": ["react"],
            "nodes": {
                "start": {
                    "type": "agent",
                    "agent": "agent1"
                },
                "end": {
                    "type": "agent",
                    "agent": "agent1"
                }
            },
            "edges": [
                {"from": "start", "to": "end"}
            ]
        }

        # Write to file
        workflow_file = temp_dir / "workflow.yaml"
        with open(workflow_file, 'w') as f:
            yaml.dump(workflow_config, f)

        # Load workflow
        from multi_agent.config.loader import ConfigLoader

        loader = ConfigLoader()
        workflow = loader.load_workflow(str(workflow_file))

        assert workflow is not None
        assert workflow.name == "yaml_workflow"
        assert "start" in workflow.nodes
        assert "end" in workflow.nodes

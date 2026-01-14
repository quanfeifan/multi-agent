"""Parallel execution module for multi-agent framework.

This module provides automatic task dependency detection and parallel execution.
"""

import asyncio
from typing import Any, Optional

import networkx as nx

from ..agent import BaseAgent
from ..models import State, Task as TaskModel
from ..tools import ToolExecutor
from ..utils import get_logger

logger = get_logger(__name__)


class TaskDependency:
    """Represents a dependency between tasks.

    Attributes:
        task_id: Source task ID
        produces: Data this task produces
        consumes: Data this task consumes
    """

    def __init__(
        self,
        task_id: str,
        produces: list[str],
        consumes: list[str],
    ) -> None:
        """Initialize task dependency.

        Args:
            task_id: Task ID
            produces: Data this task produces
            consumes: Data this task consumes
        """
        self.task_id = task_id
        self.produces = produces
        self.consumes = consumes


class DependencyAnalyzer:
    """Analyzes task dependencies to enable parallel execution.

    Uses LLM-based analysis to determine what data each task
    produces and consumes, then builds a DAG for execution planning.
    """

    def __init__(self, llm_client: Any) -> None:
        """Initialize the dependency analyzer.

        Args:
            llm_client: LLM client for analysis
        """
        self.llm_client = llm_client

    async def analyze_task_dependencies(
        self,
        tasks: list[TaskModel],
    ) -> list[TaskDependency]:
        """Analyze dependencies between tasks.

        Args:
            tasks: List of tasks to analyze

        Returns:
            List of task dependencies
        """
        dependencies = []

        for task in tasks:
            # Use LLM to extract produces/consumes from task description
            produces = await self._extract_produces(task)
            consumes = await self._extract_consumes(task)

            dependencies.append(TaskDependency(
                task_id=task.id,
                produces=produces,
                consumes=consumes,
            ))

        return dependencies

    async def _extract_produces(self, task: TaskModel) -> list[str]:
        """Extract data produced by a task.

        Args:
            task: Task to analyze

        Returns:
            List of data keys this task produces
        """
        # Simple heuristic: extract words like "create", "generate", "produce"
        # In production, would use LLM for more accurate extraction
        description = task.description.lower()
        produces = []

        keywords = ["create", "generate", "produce", "write", "make"]
        for keyword in keywords:
            if f"{keyword} " in description:
                # Extract the object being created
                parts = description.split(f"{keyword} ")
                if len(parts) > 1:
                    obj = parts[1].split()[0].strip(".,;")
                    produces.append(obj)

        return produces

    async def _extract_consumes(self, task: TaskModel) -> list[str]:
        """Extract data consumed by a task.

        Args:
            task: Task to analyze

        Returns:
            List of data keys this task consumes
        """
        # Simple heuristic: extract words like "use", "read", "load"
        description = task.description.lower()
        consumes = []

        keywords = ["use", "read", "load", "process", "analyze"]
        for keyword in keywords:
            if f"{keyword} " in description:
                # Extract the object being used
                parts = description.split(f"{keyword} ")
                if len(parts) > 1:
                    obj = parts[1].split()[0].strip(".,;")
                    consumes.append(obj)

        return consumes

    def build_dependency_graph(
        self,
        dependencies: list[TaskDependency],
    ) -> nx.DiGraph:
        """Build a dependency graph from task dependencies.

        Args:
            dependencies: List of task dependencies

        Returns:
            Directed graph of task dependencies
        """
        graph = nx.DiGraph()

        # Add all tasks as nodes
        for dep in dependencies:
            graph.add_node(dep.task_id, produces=dep.produces, consumes=dep.consumes)

        # Add edges for dependencies
        for producer in dependencies:
            for consumer in dependencies:
                if producer.task_id == consumer.task_id:
                    continue

                # Check if consumer depends on producer
                for produced in producer.produces:
                    if produced in consumer.consumes:
                        graph.add_edge(producer.task_id, consumer.task_id)
                        break

        return graph

    def detect_circular_dependencies(self, graph: nx.DiGraph) -> list[list[str]]:
        """Detect circular dependencies in the graph.

        Args:
            graph: Dependency graph

        Returns:
            List of cycles (each cycle is a list of task IDs)
        """
        try:
            cycles = list(nx.simple_cycles(graph))
            return cycles
        except Exception:
            return []

    def get_execution_batches(
        self,
        graph: nx.DiGraph,
    ) -> list[list[str]]:
        """Generate parallel execution batches.

        Tasks in each batch can be executed in parallel.
        Later batches depend on earlier batches.

        Args:
            graph: Dependency graph

        Returns:
            List of batches, each batch is a list of task IDs
        """
        # Use topological sort to get execution order
        try:
            topo_order = list(nx.topological_sort(graph))
        except nx.NetworkXError:
            # Graph has cycles, return empty
            return []

        # Group into levels where each level can run in parallel
        batches: list[list[str]] = []
        completed: set[str] = set()
        remaining = set(topo_order)

        while remaining:
            # Find all tasks whose dependencies are satisfied
            batch = []
            for task_id in list(remaining):
                # Get predecessors
                predecessors = set(graph.predecessors(task_id))
                if predecessors.issubset(completed):
                    batch.append(task_id)

            if not batch:
                # Circular dependency detected
                logger.warning("Unable to resolve next batch, possible circular dependency")
                break

            batches.append(batch)
            completed.update(batch)
            remaining -= set(batch)

        return batches


class ParallelExecutor:
    """Executes tasks in parallel where possible.

    Uses dependency analysis to determine which tasks can run
    concurrently, with a configurable concurrency limit.
    """

    def __init__(
        self,
        agents: dict[str, BaseAgent],
        tool_executor: Optional[ToolExecutor] = None,
        max_concurrent: int = 100,
    ) -> None:
        """Initialize the parallel executor.

        Args:
            agents: Available agents by name
            tool_executor: Tool executor
            max_concurrent: Maximum concurrent tasks
        """
        self.agents = agents
        self.tool_executor = tool_executor
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def execute_tasks(
        self,
        tasks: list[TaskModel],
        initial_state: Optional[State] = None,
    ) -> dict[str, Any]:
        """Execute tasks with automatic parallelization.

        Args:
            tasks: List of tasks to execute
            initial_state: Optional initial state

        Returns:
            Dictionary of task results by task ID
        """
        # Analyze dependencies
        analyzer = DependencyAnalyzer(llm_client=None)
        dependencies = await analyzer.analyze_task_dependencies(tasks)

        # Build dependency graph
        graph = analyzer.build_dependency_graph(dependencies)

        # Check for circular dependencies
        cycles = analyzer.detect_circular_dependencies(graph)
        if cycles:
            logger.error(f"Circular dependencies detected: {cycles}")
            raise ValueError(f"Circular dependencies: {cycles}")

        # Get execution batches
        batches = analyzer.get_execution_batches(graph)

        logger.info(f"Executing {len(tasks)} tasks in {len(batches)} batches")

        results: dict[str, Any] = {}

        # Execute each batch
        for i, batch in enumerate(batches):
            logger.info(f"Executing batch {i + 1}/{len(batches)} with {len(batch)} tasks")

            # Execute batch in parallel
            batch_results = await self._execute_batch(tasks, batch, initial_state)
            results.update(batch_results)

        return results

    async def _execute_batch(
        self,
        all_tasks: list[TaskModel],
        task_ids: list[str],
        initial_state: Optional[State],
    ) -> dict[str, Any]:
        """Execute a batch of tasks in parallel.

        Args:
            all_tasks: All tasks (for lookup)
            task_ids: Task IDs in this batch
            initial_state: Initial state

        Returns:
            Results for tasks in this batch
        """
        tasks_map = {t.task_id: t for t in all_tasks}

        async def execute_single(task_id: str) -> tuple[str, Any]:
            """Execute a single task with semaphore."""
            async with self._semaphore:
                task = tasks_map[task_id]
                agent = self.agents.get(task.agent_name)

                if not agent:
                    logger.error(f"Agent not found: {task.agent_name}")
                    return task_id, {"error": f"Agent not found: {task.agent_name}"}

                try:
                    result = await agent.execute(
                        task_description=task.description,
                        initial_state=initial_state,
                    )
                    return task_id, result
                except Exception as e:
                    logger.error(f"Task execution failed: {task_id} - {e}")
                    return task_id, {"error": str(e)}

        # Execute all tasks in the batch concurrently
        results = await asyncio.gather(
            *[execute_single(tid) for tid in task_ids],
            return_exceptions=True,
        )

        return dict(results)


class FIFOQueue:
    """FIFO queue for pending tasks.

    Maintains order of tasks waiting to be executed.
    """

    def __init__(self) -> None:
        """Initialize the FIFO queue."""
        self._queue: list[str] = []
        self._set: set[str] = set()

    def put(self, task_id: str) -> None:
        """Add a task to the queue.

        Args:
            task_id: Task ID to add
        """
        if task_id not in self._set:
            self._queue.append(task_id)
            self._set.add(task_id)

    def get(self) -> Optional[str]:
        """Get the next task from the queue.

        Returns:
            Task ID or None if queue is empty
        """
        if not self._queue:
            return None

        task_id = self._queue.pop(0)
        self._set.remove(task_id)
        return task_id

    def peek(self) -> Optional[str]:
        """Peek at the next task without removing it.

        Returns:
            Next task ID or None if queue is empty
        """
        return self._queue[0] if self._queue else None

    def remove(self, task_id: str) -> bool:
        """Remove a task from the queue.

        Args:
            task_id: Task ID to remove

        Returns:
            True if removed, False if not in queue
        """
        if task_id not in self._set:
            return False

        self._queue.remove(task_id)
        self._set.remove(task_id)
        return True

    def __len__(self) -> int:
        """Get queue length."""
        return len(self._queue)

    def __contains__(self, task_id: str) -> bool:
        """Check if task is in queue."""
        return task_id in self._set


async def analyze_and_execute_parallel(
    tasks: list[TaskModel],
    agents: dict[str, BaseAgent],
    tool_executor: Optional[ToolExecutor] = None,
    max_concurrent: int = 100,
) -> dict[str, Any]:
    """Analyze dependencies and execute tasks in parallel.

    Convenience function for parallel execution.

    Args:
        tasks: List of tasks to execute
        agents: Available agents
        tool_executor: Tool executor
        max_concurrent: Maximum concurrent tasks

    Returns:
        Task results by task ID
    """
    executor = ParallelExecutor(agents, tool_executor, max_concurrent)
    return await executor.execute_tasks(tasks)

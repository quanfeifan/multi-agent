"""Orchestrator for multi-agent framework.

This module provides the main execution engine with FIFO queue management.
"""

import asyncio
from collections import deque
from typing import Any, Optional

from pydantic import BaseModel

from ..agent.base import BaseAgent
from ..config import AgentConfig, load_agent_config
from ..models import Agent, Task, TaskStatus
from ..tools import MCPToolManager, ToolExecutor
from ..utils import get_logger
from .task import ExecutableTask, TaskResult

logger = get_logger(__name__)


class OrchestratorConfig(BaseModel):
    """Orchestrator configuration.

    Attributes:
        max_concurrent: Maximum concurrent tasks
        queue_size: Maximum queue size
        enable_tracing: Enable trace logging
    """

    max_concurrent: int = 100
    queue_size: int = 1000
    enable_tracing: bool = True


class TaskQueue:
    """FIFO queue for pending tasks."""

    def __init__(self, max_size: int = 1000) -> None:
        """Initialize the task queue.

        Args:
            max_size: Maximum queue size
        """
        self.queue: deque[ExecutableTask] = deque(maxlen=max_size)
        self.max_size = max_size
        self._pending: set[str] = set()

    def put(self, task: ExecutableTask) -> bool:
        """Add a task to the queue.

        Args:
            task: Task to queue

        Returns:
            True if task was queued, False if queue is full
        """
        if len(self.queue) >= self.max_size:
            logger.warning(f"Task queue is full ({self.max_size}), rejecting task: {task.task_id}")
            return False

        if task.task_id in self._pending:
            logger.warning(f"Task already in queue: {task.task_id}")
            return False

        self.queue.append(task)
        self._pending.add(task.task_id)
        return True

    def get(self) -> Optional[ExecutableTask]:
        """Get next task from queue.

        Returns:
            Next task or None if queue is empty
        """
        if not self.queue:
            return None

        task = self.queue.popleft()
        self._pending.discard(task.task_id)
        return task

    def peek(self) -> Optional[ExecutableTask]:
        """Peek at next task without removing it.

        Returns:
            Next task or None if queue is empty
        """
        return self.queue[0] if self.queue else None

    def remove(self, task_id: str) -> bool:
        """Remove a task from the queue.

        Args:
            task_id: Task ID to remove

        Returns:
            True if task was removed
        """
        for i, task in enumerate(self.queue):
            if task.task_id == task_id:
                del self.queue[i]
                self._pending.discard(task_id)
                return True
        return False

    @property
    def size(self) -> int:
        """Get queue size.

        Returns:
            Number of tasks in queue
        """
        return len(self.queue)

    @property
    def empty(self) -> bool:
        """Check if queue is empty.

        Returns:
            True if queue is empty
        """
        return len(self.queue) == 0


class Orchestrator:
    """Main execution orchestrator for multi-agent framework.

    Manages concurrent task execution with FIFO queue and tool integration.
    """

    def __init__(
        self,
        config: Optional[OrchestratorConfig] = None,
        tool_manager: Optional[MCPToolManager] = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            config: Orchestrator configuration
            tool_manager: MCP tool manager
        """
        self.config = config or OrchestratorConfig()
        self.tool_manager = tool_manager or MCPToolManager()
        self.tool_executor = ToolExecutor(self.tool_manager)

        self.queue = TaskQueue(max_size=self.config.queue_size)
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._agents: dict[str, BaseAgent] = {}
        self._shutdown = False

    async def initialize(self) -> None:
        """Initialize the orchestrator.

        Starts background queue processor.
        """
        logger.info("Initializing orchestrator")

        # Start queue processor
        asyncio.create_task(self._process_queue())

    async def shutdown(self) -> None:
        """Shutdown the orchestrator.

        Waits for running tasks to complete.
        """
        logger.info("Shutting down orchestrator")
        self._shutdown = True

        # Wait for running tasks
        if self._running_tasks:
            logger.info(f"Waiting for {len(self._running_tasks)} running tasks...")
            await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)

        # Close tool manager
        await self.tool_manager.close()

    async def submit_task(
        self,
        description: str,
        agent_name: str,
        task_id: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Submit a task for execution.

        Args:
            description: Task description
            agent_name: Name of agent to execute task
            task_id: Optional task ID
            **kwargs: Additional task parameters

        Returns:
            Task ID
        """
        # Get or create agent
        agent = self._get_agent(agent_name)

        # Create executable task
        task = ExecutableTask(
            description=description,
            agent=agent,
            task_id=task_id,
            **kwargs,
        )

        # Add to queue or execute directly if under concurrent limit
        if len(self._running_tasks) >= self.config.max_concurrent:
            if not self.queue.put(task):
                raise RuntimeError("Task queue is full")
            logger.info(f"Task queued: {task.task_id}")
        else:
            # Execute immediately
            self._execute_task(task)

        return task.task_id

    async def get_task_result(self, task_id: str, timeout: float = 300.0) -> TaskResult:
        """Get task result, waiting if necessary.

        Args:
            task_id: Task ID
            timeout: Maximum time to wait in seconds

        Returns:
            Task result

        Raises:
            TimeoutError: If timeout is reached
            FileNotFoundError: If task not found
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            # Check if task is in running tasks
            if task_id in self._running_tasks:
                task = self._running_tasks[task_id]
                try:
                    result = await asyncio.wait_for(task, timeout=timeout)
                    return result
                except asyncio.TimeoutError:
                    raise TimeoutError(f"Timeout waiting for task: {task_id}")

            # Check if task is in queue
            queued = False
            for task in self.queue.queue:
                if task.task_id == task_id:
                    queued = True
                    break

            if queued:
                # Wait and check again
                await asyncio.sleep(0.1)
                continue

            # Task might be completed, try to load from storage
            try:
                task = ExecutableTask.load(task_id)
                # Task is completed
                return TaskResult(
                    task=task.task,
                    state=None,
                    trace=task.tracer.get_trace(),
                    completed=task.task.status == TaskStatus.COMPLETED,
                    output=task.task.result or "",
                    error=task.task.error,
                )
            except FileNotFoundError:
                pass

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f"Timeout waiting for task: {task_id}")

            await asyncio.sleep(0.1)

    async def _process_queue(self) -> None:
        """Background task to process queued tasks."""
        while not self._shutdown:
            # Clean up completed tasks
            self._cleanup_completed_tasks()

            # Execute queued tasks if under limit
            while not self.queue.empty and len(self._running_tasks) < self.config.max_concurrent:
                task = self.queue.get()
                if task:
                    self._execute_task(task)

            await asyncio.sleep(0.1)

    def _execute_task(self, task: ExecutableTask) -> None:
        """Execute a task asynchronously.

        Args:
            task: Task to execute
        """
        async def run_task() -> TaskResult:
            return await task.run(self.tool_executor)

        # Create background task
        asyncio_task = asyncio.create_task(run_task())
        self._running_tasks[task.task_id] = asyncio_task

        # Add cleanup callback
        asyncio_task.add_done_callback(lambda t: self._running_tasks.pop(task.task_id, None))

        logger.info(f"Executing task: {task.task_id}")

    def _cleanup_completed_tasks(self) -> None:
        """Clean up completed tasks."""
        completed = [
            task_id
            for task_id, task in self._running_tasks.items()
            if task.done()
        ]
        for task_id in completed:
            self._running_tasks.pop(task_id, None)

    def _get_agent(self, agent_name: str) -> BaseAgent:
        """Get or create an agent.

        Args:
            agent_name: Name of agent

        Returns:
            BaseAgent instance
        """
        if agent_name in self._agents:
            return self._agents[agent_name]

        # Load agent config
        from ..config.paths import resolve_config_path

        try:
            config_path = resolve_config_path(agent_name, config_type="agents")
            config = load_agent_config(config_path)
            agent = BaseAgent.from_config(config, self.tool_executor)
            self._agents[agent_name] = agent
            return agent
        except FileNotFoundError:
            raise ValueError(f"Agent not found: {agent_name}")

    @property
    def running_count(self) -> int:
        """Get number of running tasks.

        Returns:
            Number of running tasks
        """
        return len(self._running_tasks)

    @property
    def queued_count(self) -> int:
        """Get number of queued tasks.

        Returns:
            Number of queued tasks
        """
        return self.queue.size

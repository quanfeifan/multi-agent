"""Task execution for multi-agent framework.

This module provides the Task class for executing agent tasks.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..agent.base import BaseAgent
from ..config.paths import get_task_dir
from ..models import Agent, State, Task, TaskStatus, TraceLog
from ..state import StateManager
from ..tracing import Tracer
from ..utils import generate_task_id, get_logger

logger = get_logger(__name__)


class TaskExecutionContext(BaseModel):
    """Context for task execution.

    Attributes:
        task: Task being executed
        state_manager: State persistence manager
        tracer: Trace logger
        agent: Agent instance
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    task: Task
    state_manager: StateManager
    tracer: Tracer
    agent: BaseAgent


class ExecutableTask:
    """Executable task with agent binding.

    Wraps a Task model with execution context and methods.
    """

    def __init__(
        self,
        description: str,
        agent: Agent | BaseAgent,
        task_id: Optional[str] = None,
        retention_days: int = 7,
        parent_task_id: Optional[str] = None,
        config_dir: Optional[str] = None,
    ) -> None:
        """Initialize an executable task.

        Args:
            description: Task description
            agent: Agent model or BaseAgent instance
            task_id: Optional task ID (auto-generated if not provided)
            retention_days: Days to keep logs
            parent_task_id: Parent task ID for sub-tasks
            config_dir: Configuration directory
        """
        self.task_id = task_id or generate_task_id()
        self.description = description
        self.retention_days = retention_days
        self.parent_task_id = parent_task_id

        # Create task model
        self.task = Task(
            id=self.task_id,
            description=description,
            status=TaskStatus.PENDING,
            assigned_agent=agent.name if isinstance(agent, Agent) else agent.agent.name,
            retention_days=retention_days,
            parent_task_id=parent_task_id,
        )

        # Setup execution context
        self.state_manager = StateManager(self.task_id, config_dir)
        self.tracer = Tracer(self.task_id, self.state_manager)

        # Store agent
        if isinstance(agent, BaseAgent):
            self.agent = agent
        else:
            # BaseAgent needs ToolExecutor which we don't have yet
            # This will be handled by the orchestrator
            self.agent_model = agent
            self.agent = None

    async def run(self, tool_executor=None) -> "TaskResult":
        """Execute the task.

        Args:
            tool_executor: Optional tool executor

        Returns:
            Task result
        """
        try:
            # Mark as running
            self.task.mark_running()
            await self._save_task()

            self.tracer.log_step(
                step_name="task_start",
                message=f"Starting task: {self.description}",
                agent=self.task.assigned_agent,
            )

            # Initialize agent if needed
            if self.agent is None:
                from ..agent.base import BaseAgent

                from ..config import AgentConfig

                # Create agent from model
                llm_config = AgentConfig.LLMConfig(**self.agent_model.llm_config.model_dump())
                config = AgentConfig(
                    name=self.agent_model.name,
                    role=self.agent_model.role,
                    system_prompt=self.agent_model.system_prompt,
                    tools=self.agent_model.tools,
                    max_iterations=self.agent_model.max_iterations,
                    llm_config=llm_config,
                    temperature=self.agent_model.temperature,
                )
                self.agent = BaseAgent.from_config(config, tool_executor)

            # Execute agent
            result = await self.agent.execute(
                task_description=self.description,
            )

            # Update task with result
            if result.completed:
                self.task.mark_completed(result.output)
                self.tracer.log_step(
                    step_name="task_complete",
                    message=f"Task completed successfully",
                    agent=self.task.assigned_agent,
                )
            else:
                self.task.mark_failed(result.error or "Unknown error")
                self.tracer.log_step(
                    step_name="task_failed",
                    message=f"Task failed: {result.error}",
                    agent=self.task.assigned_agent,
                    status="error",
                )

            await self._save_task()

            return TaskResult(
                task=self.task,
                state=result.state,
                trace=self.tracer.get_trace(),
                completed=result.completed,
                output=result.output,
                error=result.error,
            )

        except Exception as e:
            logger.error(f"Task execution error: {e}")
            self.task.mark_failed(str(e))
            await self._save_task()

            return TaskResult(
                task=self.task,
                state=None,
                trace=self.tracer.get_trace(),
                completed=False,
                output="",
                error=str(e),
            )

    async def _save_task(self) -> None:
        """Save task state to disk."""
        self.state_manager.save_task(self.task)

    def get_status(self) -> TaskStatus:
        """Get current task status.

        Returns:
            Task status
        """
        return self.task.status

    @classmethod
    def load(cls, task_id: str, config_dir: Optional[str] = None) -> "ExecutableTask":
        """Load a task from storage.

        Args:
            task_id: Task ID to load
            config_dir: Configuration directory

        Returns:
            Loaded ExecutableTask
        """
        state_manager = StateManager(task_id, config_dir)
        task = state_manager.load_task()

        if task is None:
            raise FileNotFoundError(f"Task not found: {task_id}")

        # Create wrapper
        executable = cls.__new__(cls)
        executable.task_id = task_id
        executable.description = task.description
        executable.retention_days = task.retention_days
        executable.parent_task_id = task.parent_task_id
        executable.task = task
        executable.state_manager = state_manager
        executable.tracer = Tracer(task_id, state_manager)
        executable.agent = None
        executable.agent_model = None

        return executable

    async def resume(self, tool_executor=None) -> "TaskResult":
        """Resume a paused or failed task.

        Args:
            tool_executor: Optional tool executor

        Returns:
            Task result
        """
        logger.info(f"Resuming task: {self.task_id}")
        return await self.run(tool_executor)


class TaskResult(BaseModel):
    """Result of task execution.

    Attributes:
        task: Executed task
        state: Final execution state
        trace: Execution trace log
        completed: Whether task completed
        output: Task output
        error: Error message if failed
    """

    task: Task
    state: Optional[State]
    trace: TraceLog
    completed: bool
    output: str
    error: Optional[str] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get task execution duration.

        Returns:
            Duration in seconds or None
        """
        return self.task.duration_seconds

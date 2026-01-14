"""Tracing module for multi-agent framework.

This module provides structured trace logging for debugging and observability.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from ..models import StepRecord, SubAgentSessionInfo, ToolCallRecord, TraceLog
from ..state import StateManager
from ..utils import get_logger

logger = get_logger(__name__)


class Tracer:
    """Structured trace logger for execution tracking.

    Records all execution steps, tool calls, and sub-agent sessions.
    """

    def __init__(
        self,
        task_id: str,
        state_manager: StateManager,
    ) -> None:
        """Initialize the tracer.

        Args:
            task_id: Task ID to trace
            state_manager: State manager for persistence
        """
        self.task_id = task_id
        self.state_manager = state_manager
        self.trace = TraceLog(task_id=task_id)

    def log_step(
        self,
        step_name: str,
        message: str,
        agent: str,
        status: str = "info",
        tool_calls: Optional[list[ToolCallRecord]] = None,
        duration_ms: int = 0,
    ) -> StepRecord:
        """Log an execution step.

        Args:
            step_name: Step identifier
            message: Step description
            agent: Executing agent
            status: Step status (info/warning/error)
            tool_calls: Tools invoked in this step
            duration_ms: Step duration in milliseconds

        Returns:
            Created step record
        """
        step = StepRecord(
            step_name=step_name,
            message=message,
            timestamp=datetime.now(),
            status=status,
            agent=agent,
            tool_calls=tool_calls or [],
            duration_ms=duration_ms,
        )

        self.trace.add_step(step)
        self._save_incremental()

        return step

    def log_tool_call(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any],
        result: Any,
        error: Optional[str] = None,
        duration_ms: int = 0,
    ) -> ToolCallRecord:
        """Log a tool call.

        Args:
            server: MCP server name
            tool: Tool name
            arguments: Tool arguments
            result: Tool result
            error: Error if failed
            duration_ms: Call duration

        Returns:
            Created tool call record
        """
        tool_call = ToolCallRecord(
            server=server,
            tool=tool,
            arguments=arguments,
            result={"output": str(result)} if error is None else None,
            error=error,
            duration_ms=duration_ms,
        )

        return tool_call

    def log_sub_agent_session(
        self,
        session_id: str,
        agent: str,
        message_count: int,
        status: str,
    ) -> None:
        """Log a sub-agent session.

        Args:
            session_id: Session ID
            agent: Sub-agent name
            message_count: Number of messages in session
            status: Session status
        """
        info = SubAgentSessionInfo(
            session_id=session_id,
            agent=agent,
            message_count=message_count,
            status=status,
        )

        self.trace.add_sub_agent_session(session_id, info)
        self._save_incremental()

    def get_trace(self) -> TraceLog:
        """Get the current trace log.

        Returns:
            Trace log
        """
        return self.trace

    def load_trace(self) -> Optional[TraceLog]:
        """Load trace from storage.

        Returns:
            Loaded trace or None if not found
        """
        try:
            trace_file = self.state_manager.task_dir / "trace.json"
            if trace_file.exists():
                data = json.loads(trace_file.read_text(encoding="utf-8"))
                return TraceLog(**data)
        except Exception as e:
            logger.error(f"Error loading trace: {e}")

        return None

    def _save_incremental(self) -> None:
        """Incrementally save trace to disk."""
        try:
            trace_file = self.state_manager.task_dir / "trace.json"
            trace_file.write_text(self.trace.model_dump_json(indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Error saving trace: {e}")

    def pretty_print(self) -> str:
        """Generate a pretty-printed trace summary.

        Returns:
            Formatted trace string
        """
        lines: list[str] = []
        lines.append(f"Trace for task: {self.task_id}")
        lines.append(f"Total steps: {self.trace.step_count}")
        lines.append(f"Total duration: {self.trace.total_duration_ms}ms")
        lines.append("")

        for step in self.trace.steps:
            lines.append(f"[{step.timestamp.isoformat()}] {step.step_name} ({step.agent})")
            lines.append(f"  Status: {step.status}")
            lines.append(f"  Message: {step.message}")

            if step.tool_calls:
                lines.append(f"  Tool calls: {len(step.tool_calls)}")
                for tc in step.tool_calls:
                    lines.append(f"    - {tc.server}:{tc.tool}")
                    if tc.error:
                        lines.append(f"      Error: {tc.error}")

            lines.append("")

        if self.trace.sub_agent_sessions:
            lines.append("Sub-agent sessions:")
            for session_id, info in self.trace.sub_agent_sessions.items():
                lines.append(f"  {session_id}: {info.agent} ({info.message_count} messages, {info.status})")

        return "\n".join(lines)

    def get_error_summary(self) -> list[dict[str, Any]]:
        """Get summary of errors in the trace.

        Returns:
            List of error summaries
        """
        errors: list[dict[str, Any]] = []

        for step in self.trace.get_error_steps():
            error_info = {
                "step": step.step_name,
                "message": step.message,
                "timestamp": step.timestamp.isoformat(),
                "agent": step.agent,
            }

            # Add tool call errors
            tool_errors = [tc.error for tc in step.tool_calls if tc.error]
            if tool_errors:
                error_info["tool_errors"] = tool_errors

            errors.append(error_info)

        return errors

    def get_tool_call_summary(self) -> dict[str, Any]:
        """Get summary of tool calls.

        Returns:
            Tool call statistics
        """
        total_calls = 0
        failed_calls = 0
        total_duration = 0
        by_tool: dict[str, dict[str, Any]] = {}

        for step in self.trace.steps:
            for tc in step.tool_calls:
                total_calls += 1
                total_duration += tc.duration_ms

                if tc.error:
                    failed_calls += 1

                key = f"{tc.server}:{tc.tool}"
                if key not in by_tool:
                    by_tool[key] = {"count": 0, "errors": 0, "total_duration_ms": 0}

                by_tool[key]["count"] += 1
                by_tool[key]["total_duration_ms"] += tc.duration_ms
                if tc.error:
                    by_tool[key]["errors"] += 1

        return {
            "total_calls": total_calls,
            "failed_calls": failed_calls,
            "success_rate": (total_calls - failed_calls) / total_calls if total_calls > 0 else 0,
            "total_duration_ms": total_duration,
            "by_tool": by_tool,
        }

    def export_json(self, file_path: Optional[Path] = None) -> str:
        """Export trace as JSON.

        Args:
            file_path: Optional file to write to

        Returns:
            JSON string
        """
        json_data = self.trace.model_dump_json(indent=2)

        if file_path:
            file_path.write_text(json_data, encoding="utf-8")

        return json_data

    def filter_by_agent(self, agent_name: str) -> TraceLog:
        """Filter trace by agent.

        Args:
            agent_name: Agent name to filter by

        Returns:
            Filtered trace log
        """
        filtered_steps = self.trace.get_steps_by_agent(agent_name)

        return TraceLog(
            task_id=self.task_id,
            steps=filtered_steps,
            sub_agent_sessions=self.trace.sub_agent_sessions,
        )

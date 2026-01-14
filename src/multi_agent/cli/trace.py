"""CLI commands for trace log inspection.

This module provides command-line interface for viewing and searching trace logs.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from tabulate import tabulate

from ..config.paths import get_default_config_dir
from ..models import TraceLog
from ..utils import get_logger

logger = get_logger(__name__)


def get_tasks_dir() -> Path:
    """Get the tasks directory.

    Returns:
        Path to tasks directory
    """
    config_dir = get_default_config_dir()
    tasks_dir = config_dir / "tasks"
    return tasks_dir


def load_trace(task_id: str) -> Optional[TraceLog]:
    """Load trace log for a task.

    Args:
        task_id: Task ID

    Returns:
        Trace log or None if not found
    """
    tasks_dir = get_tasks_dir()
    trace_file = tasks_dir / task_id / "trace.json"

    if not trace_file.exists():
        return None

    try:
        data = json.loads(trace_file.read_text(encoding="utf-8"))
        return TraceLog(**data)
    except Exception as e:
        logger.error(f"Failed to load trace: {e}")
        return None


def show_trace(task_id: str, agent: Optional[str] = None, json_output: bool = False) -> None:
    """Show trace log for a task.

    Args:
        task_id: Task ID
        agent: Filter by agent name
        json_output: Output as JSON instead of formatted
    """
    trace = load_trace(task_id)

    if trace is None:
        click.echo(f"Trace not found for task: {task_id}", err=True)
        return

    if agent:
        trace = TraceLog(
            task_id=trace.task_id,
            steps=trace.get_steps_by_agent(agent),
            sub_agent_sessions=trace.sub_agent_sessions,
        )

    if json_output:
        click.echo(trace.model_dump_json(indent=2))
    else:
        click.echo(f"Trace for task: {trace.task_id}")
        click.echo(f"Total steps: {trace.step_count}")
        click.echo(f"Total duration: {trace.total_duration_ms}ms")
        click.echo(f"Created: {trace.created_at.isoformat()}")
        click.echo(f"Updated: {trace.updated_at.isoformat()}")
        click.echo("")

        for step in trace.steps:
            status_icon = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}.get(step.status, "•")
            click.echo(f"{status_icon} [{step.timestamp.isoformat()}] {step.step_name} ({step.agent})")
            click.echo(f"  Status: {step.status}")
            click.echo(f"  Message: {step.message}")

            if step.tool_calls:
                click.echo(f"  Tool calls ({len(step.tool_calls)}):")
                for tc in step.tool_calls:
                    status = "✓" if not tc.error else "✗"
                    click.echo(f"    {status} {tc.server}:{tc.tool} ({tc.duration_ms}ms)")
                    if tc.error:
                        click.echo(f"      Error: {tc.error}")

            click.echo("")

        if trace.sub_agent_sessions:
            click.echo("Sub-agent sessions:")
            for session_id, info in trace.sub_agent_sessions.items():
                click.echo(f"  {session_id}: {info.agent} ({info.message_count} messages, {info.status})")


def search_traces(
    status: Optional[str] = None,
    agent: Optional[str] = None,
    tool: Optional[str] = None,
    has_errors: bool = False,
    limit: int = 50,
) -> None:
    """Search trace logs by criteria.

    Args:
        status: Filter by step status
        agent: Filter by agent name
        tool: Filter by tool name (server:tool format)
        has_errors: Only show traces with errors
        limit: Maximum results to show
    """
    tasks_dir = get_tasks_dir()
    if not tasks_dir.exists():
        click.echo("No tasks found.")
        return

    results = []

    for task_dir in sorted(tasks_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not task_dir.is_dir():
            continue

        trace_file = task_dir / "trace.json"
        if not trace_file.exists():
            continue

        try:
            data = json.loads(trace_file.read_text(encoding="utf-8"))
            trace = TraceLog(**data)

            # Apply filters
            steps = trace.steps

            if status:
                steps = [s for s in steps if s.status == status]

            if agent:
                steps = [s for s in steps if s.agent == agent]

            if tool:
                server, tool_name = tool.split(":") if ":" in tool else (None, tool)
                steps = [
                    s for s in steps
                    if any(tc.tool == tool_name and (not server or tc.server == server) for tc in s.tool_calls)
                ]

            if has_errors:
                steps = [s for s in steps if s.status == "error" or any(tc.error for tc in s.tool_calls)]

            if steps:
                results.append({
                    "task_id": trace.task_id,
                    "matching_steps": len(steps),
                    "total_steps": trace.step_count,
                    "created": trace.created_at.isoformat(),
                })

        except Exception as e:
            logger.warning(f"Failed to search trace {task_dir.name}: {e}")

    # Limit results
    results = results[:limit]

    # Display results
    if results:
        rows = []
        for r in results:
            created = r.get("created", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created)
                    created = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass

            rows.append([
                r["task_id"][:12],
                r["matching_steps"],
                r["total_steps"],
                created,
            ])

        headers = ["Task ID", "Matching Steps", "Total Steps", "Created"]
        click.echo(tabulate(rows, headers=headers, tablefmt="grid"))
    else:
        click.echo("No matching traces found.")


def show_errors(task_id: str) -> None:
    """Show errors from a trace log.

    Args:
        task_id: Task ID
    """
    trace = load_trace(task_id)

    if trace is None:
        click.echo(f"Trace not found for task: {task_id}", err=True)
        return

    error_steps = trace.get_error_steps()

    if not error_steps:
        click.echo(f"No errors found in task: {task_id}")
        return

    click.echo(f"Errors in task {task_id}:")
    click.echo("")

    for step in error_steps:
        click.echo(f"❌ [{step.timestamp.isoformat()}] {step.step_name} ({step.agent})")
        click.echo(f"   Message: {step.message}")

        tool_errors = [tc for tc in step.tool_calls if tc.error]
        if tool_errors:
            click.echo(f"   Tool errors:")
            for tc in tool_errors:
                click.echo(f"     - {tc.server}:{tc.tool}: {tc.error}")

        click.echo("")


def show_tool_summary(task_id: str) -> None:
    """Show tool call summary for a task.

    Args:
        task_id: Task ID
    """
    trace = load_trace(task_id)

    if trace is None:
        click.echo(f"Trace not found for task: {task_id}", err=True)
        return

    # Collect tool call stats
    total_calls = 0
    failed_calls = 0
    total_duration = 0
    by_tool: dict[str, dict[str, int]] = {}

    for step in trace.steps:
        for tc in step.tool_calls:
            total_calls += 1
            total_duration += tc.duration_ms

            if tc.error:
                failed_calls += 1

            key = f"{tc.server}:{tc.tool}"
            if key not in by_tool:
                by_tool[key] = {"count": 0, "errors": 0, "duration_ms": 0}

            by_tool[key]["count"] += 1
            by_tool[key]["duration_ms"] += tc.duration_ms
            if tc.error:
                by_tool[key]["errors"] += 1

    click.echo(f"Tool call summary for task: {task_id}")
    click.echo("")

    if total_calls == 0:
        click.echo("No tool calls recorded.")
        return

    click.echo(f"Total calls: {total_calls}")
    click.echo(f"Failed calls: {failed_calls}")
    click.echo(f"Success rate: {(total_calls - failed_calls) / total_calls * 100:.1f}%")
    click.echo(f"Total duration: {total_duration}ms")
    click.echo("")

    if by_tool:
        rows = []
        for tool, stats in sorted(by_tool.items()):
            rows.append([
                tool,
                stats["count"],
                stats["errors"],
                f"{stats['duration_ms']}ms",
            ])

        headers = ["Tool", "Calls", "Errors", "Total Duration"]
        click.echo(tabulate(rows, headers=headers, tablefmt="grid"))


@click.group()
def trace_cli() -> None:
    """Trace log inspection commands."""
    pass


@trace_cli.command("show")
@click.argument("task_id")
@click.option("--agent", "-a", help="Filter by agent name")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def show_cmd(task_id: str, agent: Optional[str], json_output: bool) -> None:
    """Show trace log for a task."""
    show_trace(task_id, agent, json_output)


@trace_cli.command("search")
@click.option("--status", "-s", help="Filter by step status")
@click.option("--agent", "-a", help="Filter by agent name")
@click.option("--tool", "-t", help="Filter by tool name (server:tool)")
@click.option("--errors", "has_errors", is_flag=True, help="Only show traces with errors")
@click.option("--limit", "-l", default=50, help="Maximum results to show")
def search_cmd(status: Optional[str], agent: Optional[str], tool: Optional[str], has_errors: bool, limit: int) -> None:
    """Search trace logs by criteria."""
    search_traces(status, agent, tool, has_errors, limit)


@trace_cli.command("errors")
@click.argument("task_id")
def errors_cmd(task_id: str) -> None:
    """Show errors from a trace log."""
    show_errors(task_id)


@trace_cli.command("summary")
@click.argument("task_id")
def summary_cmd(task_id: str) -> None:
    """Show tool call summary for a task."""
    show_tool_summary(task_id)


if __name__ == "__main__":
    trace_cli()

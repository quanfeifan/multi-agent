"""CLI commands for task management.

This module provides command-line interface for listing and inspecting tasks.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from tabulate import tabulate

from ..config.paths import get_default_config_dir
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


def list_tasks(
    status: Optional[str] = None,
    agent: Optional[str] = None,
    limit: int = 50,
    json_output: bool = False,
) -> None:
    """List tasks with optional filtering.

    Args:
        status: Filter by status (pending/running/completed/failed)
        agent: Filter by agent name
        limit: Maximum number of tasks to show
        json_output: Output as JSON instead of table
    """
    tasks_dir = get_tasks_dir()
    if not tasks_dir.exists():
        if json_output:
            click.echo(json.dumps({"tasks": []}))
        return

    tasks_data = []
    for task_dir in sorted(tasks_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not task_dir.is_dir():
            continue

        task_file = task_dir / "task.json"
        if not task_file.exists():
            continue

        try:
            data = json.loads(task_file.read_text(encoding="utf-8"))
            tasks_data.append(data)
        except Exception as e:
            logger.warning(f"Failed to read task {task_dir.name}: {e}")

    # Apply filters
    if status:
        tasks_data = [t for t in tasks_data if t.get("status") == status]

    if agent:
        tasks_data = [t for t in tasks_data if t.get("agent_name") == agent]

    # Limit results
    tasks_data = tasks_data[:limit]

    if json_output:
        click.echo(json.dumps({"tasks": tasks_data}, indent=2))
    else:
        # Format as table
        rows = []
        for task in tasks_data:
            created = task.get("created_at", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created)
                    created = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass

            rows.append([
                task.get("task_id", "")[:12],
                task.get("status", "unknown"),
                task.get("agent_name", "unknown"),
                task.get("description", "")[:50],
                created,
            ])

        if rows:
            headers = ["Task ID", "Status", "Agent", "Description", "Created"]
            click.echo(tabulate(rows, headers=headers, tablefmt="grid"))
        else:
            click.echo("No tasks found.")


def show_task(task_id: str, json_output: bool = False) -> None:
    """Show detailed information about a task.

    Args:
        task_id: Task ID to show
        json_output: Output as JSON instead of formatted
    """
    tasks_dir = get_tasks_dir()
    task_dir = tasks_dir / task_id

    if not task_dir.exists():
        click.echo(f"Task not found: {task_id}", err=True)
        return

    task_file = task_dir / "task.json"
    if not task_file.exists():
        click.echo(f"Task data not found: {task_id}", err=True)
        return

    try:
        data = json.loads(task_file.read_text(encoding="utf-8"))

        if json_output:
            click.echo(json.dumps(data, indent=2))
        else:
            click.echo(f"Task: {data.get('task_id')}")
            click.echo(f"Status: {data.get('status')}")
            click.echo(f"Agent: {data.get('agent_name')}")
            click.echo(f"Description: {data.get('description')}")
            click.echo(f"Created: {data.get('created_at')}")
            click.echo(f"Updated: {data.get('updated_at')}")

            if data.get("error"):
                click.echo(f"\nError: {data.get('error')}")

            if data.get("result"):
                click.echo(f"\nResult:\n{data.get('result')}")

    except Exception as e:
        click.echo(f"Error reading task: {e}", err=True)


def delete_task(task_id: str, confirm: bool = True) -> None:
    """Delete a task and its data.

    Args:
        task_id: Task ID to delete
        confirm: Ask for confirmation
    """
    tasks_dir = get_tasks_dir()
    task_dir = tasks_dir / task_id

    if not task_dir.exists():
        click.echo(f"Task not found: {task_id}", err=True)
        return

    if confirm:
        if not click.confirm(f"Delete task {task_id} and all its data?"):
            return

    try:
        import shutil
        shutil.rmtree(task_dir)
        click.echo(f"Task deleted: {task_id}")
    except Exception as e:
        click.echo(f"Error deleting task: {e}", err=True)


@click.group()
def task_cli() -> None:
    """Task management commands."""
    pass


@task_cli.command("list")
@click.option("--status", "-s", help="Filter by status")
@click.option("--agent", "-a", help="Filter by agent name")
@click.option("--limit", "-l", default=50, help="Maximum tasks to show")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def list_cmd(status: Optional[str], agent: Optional[str], limit: int, json_output: bool) -> None:
    """List all tasks."""
    list_tasks(status, agent, limit, json_output)


@task_cli.command("show")
@click.argument("task_id")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def show_cmd(task_id: str, json_output: bool) -> None:
    """Show detailed task information."""
    show_task(task_id, json_output)


@task_cli.command("delete")
@click.argument("task_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def delete_cmd(task_id: str, yes: bool) -> None:
    """Delete a task."""
    delete_task(task_id, confirm=not yes)


if __name__ == "__main__":
    task_cli()

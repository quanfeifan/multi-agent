"""CLI commands for checkpoint management.

This module provides command-line interface for HITL checkpoint operations.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from tabulate import tabulate

from ..config.paths import get_default_config_dir
from ..execution.hitl import CheckpointMetadata, list_all_checkpoints, load_checkpoint_global
from ..utils import get_logger

logger = get_logger(__name__)


def get_checkpoints_dir(task_id: str) -> Path:
    """Get the checkpoints directory for a task.

    Args:
        task_id: Task ID

    Returns:
        Path to checkpoints directory
    """
    config_dir = get_default_config_dir()
    return config_dir / "tasks" / task_id / "checkpoints"


def list_checkpoints(task_id: str, json_output: bool = False) -> None:
    """List all checkpoints for a task.

    Args:
        task_id: Task ID
        json_output: Output as JSON instead of table
    """
    checkpoints = list_all_checkpoints(task_id)

    if not checkpoints:
        click.echo(f"No checkpoints found for task: {task_id}")
        return

    if json_output:
        click.echo(json.dumps([c.model_dump(mode="json") for c in checkpoints], indent=2, default=str))
    else:
        rows = []
        for cp in checkpoints:
            created = cp.created_at.isoformat()
            try:
                dt = datetime.fromisoformat(created)
                created = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass

            feedback = cp.human_feedback[:30] + "..." if cp.human_feedback and len(cp.human_feedback) > 30 else cp.human_feedback or "-"

            rows.append([
                cp.checkpoint_id[:12],
                cp.sequence_number,
                cp.node_name,
                feedback,
                created,
            ])

        headers = ["Checkpoint ID", "Seq", "Node", "Feedback", "Created"]
        click.echo(tabulate(rows, headers=headers, tablefmt="grid"))


def show_checkpoint(task_id: str, checkpoint_id: str, json_output: bool = False) -> None:
    """Show detailed information about a checkpoint.

    Args:
        task_id: Task ID
        checkpoint_id: Checkpoint ID
        json_output: Output as JSON instead of formatted
    """
    checkpoint = load_checkpoint_global(task_id, checkpoint_id)

    if checkpoint is None:
        click.echo(f"Checkpoint not found: {checkpoint_id}", err=True)
        return

    if json_output:
        click.echo(checkpoint.model_dump_json(indent=2))
    else:
        click.echo(f"Checkpoint: {checkpoint.checkpoint_id}")
        click.echo(f"Task: {checkpoint.task_id}")
        click.echo(f"Sequence: {checkpoint.sequence_number}")
        click.echo(f"Node: {checkpoint.node_name}")
        click.echo(f"Created: {checkpoint.created_at.isoformat()}")

        if checkpoint.human_feedback:
            click.echo(f"\nHuman Feedback:\n{checkpoint.human_feedback}")

        click.echo(f"\nState:")
        click.echo(f"  Current Agent: {checkpoint.state.current_agent}")
        click.echo(f"  Next Action: {checkpoint.state.next_action or 'None'}")
        click.echo(f"  Messages: {len(checkpoint.state.messages)}")


def resume_checkpoint(task_id: str, checkpoint_id: str, feedback: str) -> None:
    """Resume from a checkpoint with feedback.

    Args:
        task_id: Task ID
        checkpoint_id: Checkpoint ID
        feedback: Human feedback to provide
    """
    checkpoint = load_checkpoint_global(task_id, checkpoint_id)

    if checkpoint is None:
        click.echo(f"Checkpoint not found: {checkpoint_id}", err=True)
        return

    # Update checkpoint with feedback
    checkpoints_dir = get_checkpoints_dir(task_id)
    checkpoint_file = checkpoints_dir / f"{checkpoint_id}.json"

    try:
        # Add feedback to checkpoint
        data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        data["human_feedback"] = feedback
        checkpoint_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        click.echo(f"Checkpoint {checkpoint_id} updated with feedback.")
        click.echo(f"Feedback: {feedback}")
        click.echo("\nNote: Actual task resume must be done through the orchestrator or workflow executor.")
    except Exception as e:
        click.echo(f"Error updating checkpoint: {e}", err=True)


def delete_checkpoint(task_id: str, checkpoint_id: str, confirm: bool = True) -> None:
    """Delete a checkpoint.

    Args:
        task_id: Task ID
        checkpoint_id: Checkpoint ID
        confirm: Ask for confirmation
    """
    checkpoints_dir = get_checkpoints_dir(task_id)
    checkpoint_file = checkpoints_dir / f"{checkpoint_id}.json"

    if not checkpoint_file.exists():
        click.echo(f"Checkpoint not found: {checkpoint_id}", err=True)
        return

    if confirm:
        if not click.confirm(f"Delete checkpoint {checkpoint_id}?"):
            return

    try:
        checkpoint_file.unlink()
        click.echo(f"Checkpoint deleted: {checkpoint_id}")
    except Exception as e:
        click.echo(f"Error deleting checkpoint: {e}", err=True)


@click.group()
def checkpoint_cli() -> None:
    """Checkpoint management commands."""
    pass


@checkpoint_cli.command("list")
@click.argument("task_id")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def list_cmd(task_id: str, json_output: bool) -> None:
    """List all checkpoints for a task."""
    list_checkpoints(task_id, json_output)


@checkpoint_cli.command("show")
@click.argument("task_id")
@click.argument("checkpoint_id")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def show_cmd(task_id: str, checkpoint_id: str, json_output: bool) -> None:
    """Show detailed checkpoint information."""
    show_checkpoint(task_id, checkpoint_id, json_output)


@checkpoint_cli.command("resume")
@click.argument("task_id")
@click.argument("checkpoint_id")
@click.option("--feedback", "-f", required=True, help="Human feedback to provide")
def resume_cmd(task_id: str, checkpoint_id: str, feedback: str) -> None:
    """Resume from a checkpoint with feedback."""
    resume_checkpoint(task_id, checkpoint_id, feedback)


@checkpoint_cli.command("delete")
@click.argument("task_id")
@click.argument("checkpoint_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def delete_cmd(task_id: str, checkpoint_id: str, yes: bool) -> None:
    """Delete a checkpoint."""
    delete_checkpoint(task_id, checkpoint_id, confirm=not yes)


if __name__ == "__main__":
    checkpoint_cli()

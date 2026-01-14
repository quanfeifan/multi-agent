"""Main CLI entry point for multi-agent framework.

This module provides the command-line interface for all framework operations.
"""

import click
from pathlib import Path

from .. import __version__
from .checkpoint import checkpoint_cli
from .task import task_cli
from .trace import trace_cli


@click.group()
@click.version_option(version=__version__)
@click.option("--config-dir", type=click.Path(exists=True), help="Configuration directory")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def main(ctx: click.Context, config_dir: Path, verbose: bool) -> None:
    """Multi-Agent Framework CLI.

    A framework for orchestrating AI agents with MCP tool integration,
    state machine execution, and human-in-the-loop capabilities.
    """
    ctx.ensure_object(dict)
    ctx.obj["config_dir"] = config_dir
    ctx.obj["verbose"] = verbose


# Add command groups
main.add_command(task_cli, name="task")
main.add_command(trace_cli, name="trace")
main.add_command(checkpoint_cli, name="checkpoint")


@main.command()
@click.argument("name", required=False)
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def agents(name: str, output_format: str) -> None:
    """List or show agent configurations.

    If NAME is provided, show that agent's configuration.
    Otherwise, list all available agents.
    """
    from ..config.paths import get_default_config_dir
    from ..config.loader import load_agent_config
    import json
    from tabulate import tabulate

    config_dir = get_default_config_dir()
    agents_dir = config_dir / "agents"

    if not agents_dir.exists():
        click.echo("No agents configured.")
        return

    if name:
        # Show specific agent
        agent_file = agents_dir / f"{name}.yaml"
        if not agent_file.exists():
            click.echo(f"Agent not found: {name}", err=True)
            return

        try:
            config = load_agent_config(agent_file)
            if output_format == "json":
                click.echo(config.model_dump_json(indent=2))
            else:
                click.echo(f"Agent: {config.name}")
                click.echo(f"Role: {config.role}")
                click.echo(f"LLM: {config.llm_config.model} ({config.llm_config.api_type})")
                click.echo(f"Tools: {', '.join(config.tools)}")
                click.echo(f"Max Iterations: {config.max_iterations}")
        except Exception as e:
            click.echo(f"Error loading agent: {e}", err=True)
    else:
        # List all agents
        agents = []
        for agent_file in sorted(agents_dir.glob("*.yaml")):
            try:
                config = load_agent_config(agent_file)
                agents.append({
                    "name": config.name,
                    "role": config.role,
                    "model": config.llm_config.model,
                })
            except Exception:
                pass

        if output_format == "json":
            click.echo(json.dumps(agents, indent=2))
        else:
            if agents:
                rows = [[a["name"], a["role"], a["model"]] for a in agents]
                click.echo(tabulate(rows, headers=["Name", "Role", "Model"], tablefmt="grid"))
            else:
                click.echo("No agents found.")


@main.command()
@click.argument("name", required=False)
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def workflows(name: str, output_format: str) -> None:
    """List or show workflow configurations.

    If NAME is provided, show that workflow's configuration.
    Otherwise, list all available workflows.
    """
    from ..config.paths import get_default_config_dir
    from ..execution import load_workflow_from_file, validate_workflow
    import json
    from tabulate import tabulate

    config_dir = get_default_config_dir()
    workflows_dir = config_dir / "workflows"

    if not workflows_dir.exists():
        click.echo("No workflows configured.")
        return

    if name:
        # Show specific workflow
        workflow_file = workflows_dir / f"{name}.yaml"
        if not workflow_file.exists():
            workflow_file = workflows_dir / f"{name}.yml"

        if not workflow_file.exists():
            click.echo(f"Workflow not found: {name}", err=True)
            return

        try:
            workflow = load_workflow_from_file(workflow_file)
            errors = validate_workflow(workflow)

            if output_format == "json":
                output = workflow.model_dump(mode="json")
                output["validation_errors"] = errors
                click.echo(json.dumps(output, indent=2, default=str))
            else:
                click.echo(f"Workflow: {workflow.name}")
                click.echo(f"Entry Point: {workflow.entry_point}")
                click.echo(f"Nodes: {workflow.node_count}")
                click.echo(f"Edges: {workflow.edge_count}")
                click.echo(f"Patterns: {', '.join(workflow.patterns) if workflow.patterns else 'none'}")

                if errors:
                    click.echo(f"\nValidation Errors ({len(errors)}):")
                    for error in errors:
                        click.echo(f"  - {error}")
                else:
                    click.echo("\n✓ Workflow is valid")
        except Exception as e:
            click.echo(f"Error loading workflow: {e}", err=True)
    else:
        # List all workflows
        workflows_list = []
        for workflow_file in sorted((workflows_dir.glob("*.yaml")) + list(workflows_dir.glob("*.yml"))):
            try:
                workflow = load_workflow_from_file(workflow_file)
                errors = validate_workflow(workflow)
                workflows_list.append({
                    "name": workflow.name,
                    "patterns": ", ".join(workflow.patterns) if workflow.patterns else "-",
                    "nodes": workflow.node_count,
                    "valid": len(errors) == 0,
                })
            except Exception:
                pass

        if output_format == "json":
            click.echo(json.dumps(workflows_list, indent=2))
        else:
            if workflows_list:
                rows = [[
                    w["name"],
                    w["patterns"],
                    w["nodes"],
                    "✓" if w["valid"] else "✗",
                ] for w in workflows_list]
                click.echo(tabulate(rows, headers=["Name", "Patterns", "Nodes", "Valid"], tablefmt="grid"))
            else:
                click.echo("No workflows found.")


@main.command()
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def mcp(output_format: str) -> None:
    """List configured MCP servers and their tools."""
    from ..config.paths import get_default_config_dir
    from ..config.loader import load_mcp_servers_config
    import json
    from tabulate import tabulate

    config_dir = get_default_config_dir()
    servers_file = config_dir / "mcp-servers.yaml"

    if not servers_file.exists():
        click.echo("No MCP servers configured.")
        return

    try:
        servers_config = load_mcp_servers_config(servers_file)

        if output_format == "json":
            output = []
            for name, config in servers_config.items():
                output.append({
                    "name": name,
                    "transport": config.transport,
                    "command": config.command if config.transport == "stdio" else None,
                    "url": config.url if config.transport == "sse" else None,
                })
            click.echo(json.dumps(output, indent=2))
        else:
            rows = []
            for name, config in servers_config.items():
                if config.transport == "stdio":
                    details = f"stdio: {config.command}"
                else:
                    details = f"sse: {config.url}"
                rows.append([name, details])

            if rows:
                click.echo(tabulate(rows, headers=["Server", "Transport"], tablefmt="grid"))
            else:
                click.echo("No MCP servers found.")
    except Exception as e:
        click.echo(f"Error loading MCP servers: {e}", err=True)


@main.command()
@click.option("--seconds", "-s", type=int, default=60, help="Retention time in seconds")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without deleting")
def cleanup(seconds: int, dry_run: bool) -> None:
    """Clean up old task data based on retention policy.

    Removes tasks older than the specified number of seconds.
    """
    from ..config.paths import get_default_config_dir
    from datetime import datetime, timedelta

    config_dir = get_default_config_dir()
    tasks_dir = config_dir / "tasks"

    if not tasks_dir.exists():
        click.echo("No tasks to clean up.")
        return

    cutoff = datetime.now() - timedelta(seconds=seconds)
    deleted_count = 0
    total_size = 0

    for task_dir in tasks_dir.iterdir():
        if not task_dir.is_dir():
            continue

        # Check task file for timestamp
        task_file = task_dir / "task.json"
        if not task_file.exists():
            continue

        try:
            import json
            data = json.loads(task_file.read_text(encoding="utf-8"))
            created_at = data.get("created_at")
            if created_at:
                created_dt = datetime.fromisoformat(created_at)
                if created_dt < cutoff:
                    # Calculate size
                    size = sum(f.stat().st_size for f in task_dir.rglob("*") if f.is_file())

                    if dry_run:
                        click.echo(f"Would delete: {task_dir.name} ({size / 1024:.1f} KB)")
                    else:
                        import shutil
                        shutil.rmtree(task_dir)
                        deleted_count += 1
                        total_size += size
        except Exception as e:
            click.echo(f"Error processing {task_dir.name}: {e}", err=True)

    if dry_run:
        click.echo(f"\nDry run complete. Use --no-dry-run to actually delete.")
    else:
        click.echo(f"Deleted {deleted_count} tasks ({total_size / 1024:.1f} KB freed)")


if __name__ == "__main__":
    main()

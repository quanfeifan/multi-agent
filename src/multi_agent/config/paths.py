"""Path utilities for multi-agent framework configuration.

This module provides utilities for detecting and managing configuration paths.
"""

import os
from pathlib import Path


def get_default_config_dir() -> Path:
    """Get the default configuration directory path.

    Returns ~/.multi-agent/ directory, creating it if it doesn't exist.

    Returns:
        Path to the default configuration directory
    """
    config_dir = Path.home() / ".multi-agent"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_agents_dir(config_dir: Path | None = None) -> Path:
    """Get the agents configuration directory.

    Args:
        config_dir: Base configuration directory (default: ~/.multi-agent/)

    Returns:
        Path to the agents directory
    """
    if config_dir is None:
        config_dir = get_default_config_dir()
    agents_dir = config_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    return agents_dir


def get_workflows_dir(config_dir: Path | None = None) -> Path:
    """Get the workflows configuration directory.

    Args:
        config_dir: Base configuration directory (default: ~/.multi-agent/)

    Returns:
        Path to the workflows directory
    """
    if config_dir is None:
        config_dir = get_default_config_dir()
    workflows_dir = config_dir / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    return workflows_dir


def get_config_subdir(config_dir: Path | None = None) -> Path:
    """Get the configuration subdirectory for system configs.

    Args:
        config_dir: Base configuration directory (default: ~/.multi-agent/)

    Returns:
        Path to the config subdirectory
    """
    if config_dir is None:
        config_dir = get_default_config_dir()
    subdir = config_dir / "config"
    subdir.mkdir(parents=True, exist_ok=True)
    return subdir


def get_tasks_dir(config_dir: Path | None = None) -> Path:
    """Get the tasks storage directory.

    Args:
        config_dir: Base configuration directory (default: ~/.multi-agent/)

    Returns:
        Path to the tasks directory
    """
    if config_dir is None:
        config_dir = get_default_config_dir()
    tasks_dir = config_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    return tasks_dir


def get_task_dir(task_id: str, config_dir: Path | None = None) -> Path:
    """Get the directory for a specific task.

    Args:
        task_id: Unique task identifier
        config_dir: Base configuration directory (default: ~/.multi-agent/)

    Returns:
        Path to the task directory
    """
    tasks_dir = get_tasks_dir(config_dir)
    task_dir = tasks_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def resolve_config_path(
    config_name: str,
    config_type: str = "agents",
    config_dir: Path | None = None,
) -> Path:
    """Resolve a configuration file path.

    Args:
        config_name: Name of the configuration (with or without extension)
        config_type: Type of configuration ("agents", "workflows", etc.)
        config_dir: Base configuration directory

    Returns:
        Resolved path to the configuration file

    Raises:
        FileNotFoundError: If the configuration file is not found
    """
    if config_dir is None:
        config_dir = get_default_config_dir()

    # Determine the subdirectory based on type
    type_dirs = {
        "agents": "agents",
        "workflows": "workflows",
        "mcp_servers": "config",
        "config": "config",
    }

    if config_type not in type_dirs:
        raise ValueError(f"Unknown config type: {config_type}")

    subdir = config_dir / type_dirs[config_type]

    # Try different extensions
    for ext in [".yaml", ".yml", ".json"]:
        path = subdir / f"{config_name}{ext}"
        if path.exists():
            return path

    # If not found, try with the name as-is (might include extension)
    path = subdir / config_name
    if path.exists():
        return path

    raise FileNotFoundError(f"Configuration not found: {config_name} in {subdir}")


def get_data_dir() -> Path:
    """Get the data directory for runtime data.

    Uses XDG_DATA_HOME on Linux/macOS, APPDATA on Windows.

    Returns:
        Path to the data directory
    """
    if os.name == "nt":  # Windows
        data_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        data_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    app_data_dir = data_dir / "multi-agent"
    app_data_dir.mkdir(parents=True, exist_ok=True)
    return app_data_dir


def get_cache_dir() -> Path:
    """Get the cache directory for temporary files.

    Uses XDG_CACHE_HOME on Linux/macOS, TEMP on Windows.

    Returns:
        Path to the cache directory
    """
    if os.name == "nt":  # Windows
        cache_dir = Path(os.environ.get("TEMP", Path.home() / "AppData" / "Local" / "Temp"))
    else:
        cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))

    app_cache_dir = cache_dir / "multi-agent"
    app_cache_dir.mkdir(parents=True, exist_ok=True)
    return app_cache_dir

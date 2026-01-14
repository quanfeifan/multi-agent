"""Configuration loader for multi-agent framework.

This module provides functionality for loading YAML and JSON configurations
with environment variable expansion support.
"""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .schemas import (
    AgentConfig,
    MCPServerConfig,
    RetentionPolicyConfig,
    WorkflowConfig,
    validate_agent_config,
    validate_mcp_server_config,
    validate_workflow_config,
)


# Pattern for environment variable substitution: ${VAR_NAME} or ${VAR_NAME:-default}
ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand environment variables in a value.

    Supports ${VAR} and ${VAR:-default} syntax.

    Args:
        value: The value to expand (can be str, dict, list)

    Returns:
        The value with environment variables expanded
    """
    if isinstance(value, str):
        def replace_env_var(match: re.Match[str]) -> str:
            var_name = match.group(1)
            default = match.group(2) if match.group(2) is not None else ""
            return os.environ.get(var_name, default)

        return ENV_VAR_PATTERN.sub(replace_env_var, value)

    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}

    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]

    return value


def get_default_config_dir() -> Path:
    """Get the default configuration directory path.

    Returns ~/.multi-agent/ directory, creating it if it doesn't exist.

    Returns:
        Path to the default configuration directory
    """
    config_dir = Path.home() / ".multi-agent"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def load_yaml_file(file_path: str | Path) -> dict[str, Any]:
    """Load a YAML file and return its contents as a dictionary.

    Args:
        file_path: Path to the YAML file

    Returns:
        Dictionary containing the YAML contents

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the file is not valid YAML
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config_file(
    file_path: str | Path,
    config_type: str = "auto",
    expand_env: bool = True,
) -> dict[str, Any]:
    """Load a configuration file (YAML or JSON) with optional environment variable expansion.

    Args:
        file_path: Path to the configuration file
        config_type: Type of config ("yaml", "json", or "auto" to detect from extension)
        expand_env: Whether to expand environment variables

    Returns:
        Dictionary containing the configuration

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file type is unsupported or invalid
    """
    path = Path(file_path)

    # Auto-detect file type
    if config_type == "auto":
        suffix = path.suffix.lower()
        if suffix in [".yaml", ".yml"]:
            config_type = "yaml"
        elif suffix == ".json":
            config_type = "json"
        else:
            raise ValueError(f"Cannot detect config type from extension: {suffix}")

    # Load based on type
    if config_type == "yaml":
        config = load_yaml_file(path)
    elif config_type == "json":
        import json

        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        raise ValueError(f"Unsupported config type: {config_type}")

    # Expand environment variables
    if expand_env:
        config = _expand_env_vars(config)

    return config


def load_agent_config(file_path: str | Path) -> AgentConfig:
    """Load and validate an agent configuration file.

    Args:
        file_path: Path to the agent configuration file

    Returns:
        Validated AgentConfig object

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValidationError: If the configuration is invalid
    """
    config_data = load_config_file(file_path)
    return validate_agent_config(config_data)


def load_workflow_config(file_path: str | Path) -> WorkflowConfig:
    """Load and validate a workflow configuration file.

    Args:
        file_path: Path to the workflow configuration file

    Returns:
        Validated WorkflowConfig object

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValidationError: If the configuration is invalid
    """
    config_data = load_config_file(file_path)
    return validate_workflow_config(config_data)


def load_mcp_servers_config(file_path: str | Path | None = None) -> dict[str, MCPServerConfig]:
    """Load and validate MCP server configurations.

    Args:
        file_path: Path to the MCP servers config file (default: ~/.multi-agent/config/mcp_servers.yaml)

    Returns:
        Dictionary mapping server names to MCPServerConfig objects

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValidationError: If the configuration is invalid
    """
    if file_path is None:
        file_path = get_default_config_dir() / "config" / "mcp_servers.yaml"

    config_data = load_config_file(file_path)

    # Handle the mcp_servers wrapper structure from the contract
    if "mcp_servers" in config_data:
        servers_data = config_data["mcp_servers"]
    else:
        servers_data = config_data

    return validate_mcp_server_config(servers_data)


def load_retention_policy(file_path: str | Path | None = None) -> RetentionPolicyConfig:
    """Load retention policy configuration.

    Args:
        file_path: Path to the retention policy config file

    Returns:
        RetentionPolicyConfig object

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValidationError: If the configuration is invalid
    """
    if file_path is None:
        file_path = get_default_config_dir() / "config" / "retention_policy.yaml"

    try:
        config_data = load_config_file(file_path)
    except FileNotFoundError:
        # Return default policy if file doesn't exist
        return RetentionPolicyConfig()

    return RetentionPolicyConfig(**config_data)


def load_tool_overrides(file_path: str | Path | None = None) -> dict[str, Any]:
    """Load tool override configuration (timeouts, fallbacks, retry rules).

    Args:
        file_path: Path to the tool overrides config file

    Returns:
        Dictionary of tool overrides

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    if file_path is None:
        file_path = get_default_config_dir() / "config" / "tool_overrides.yaml"

    try:
        config_data = load_config_file(file_path)
    except FileNotFoundError:
        return {}

    # Expand environment variables in override configs
    return _expand_env_vars(config_data)


def find_all_configs(
    config_dir: Path | None = None,
    config_type: str = "agents",
) -> dict[str, Path]:
    """Find all configuration files of a specific type in the config directory.

    Args:
        config_dir: Configuration directory (default: ~/.multi-agent/)
        config_type: Type of configs to find ("agents", "workflows", "mcp_servers")

    Returns:
        Dictionary mapping config names to their file paths
    """
    if config_dir is None:
        config_dir = get_default_config_dir()

    type_subdirs = {
        "agents": "agents",
        "workflows": "workflows",
        "mcp_servers": "config",
    }

    if config_type not in type_subdirs:
        raise ValueError(f"Unknown config type: {config_type}")

    subdir = config_dir / type_subdirs[config_type]
    if not subdir.exists():
        return {}

    configs: dict[str, Path] = {}
    for file_path in subdir.glob("*.yaml"):
        configs[file_path.stem] = file_path

    for file_path in subdir.glob("*.yml"):
        configs[file_path.stem] = file_path

    return configs

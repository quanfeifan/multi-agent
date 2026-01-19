"""System tools for system information."""

from typing import List

from .time import SystemGetTimeTool
from .env import SystemGetEnvTool
from .processes import SystemListProcessesTool

__all__ = [
    "SystemGetTimeTool",
    "SystemGetEnvTool",
    "SystemListProcessesTool",
    "register_system_tools",
]


def register_system_tools() -> List:
    """Return all system tool instances.

    Returns:
        List of system tool instances
    """
    return [
        SystemGetTimeTool(),
        SystemGetEnvTool(),
        SystemListProcessesTool(),
    ]

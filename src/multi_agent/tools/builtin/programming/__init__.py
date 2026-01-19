"""Programming tools for code execution and calculations."""

from typing import List

from .calculate import ProgrammingCalculateTool
from .execute import ProgrammingExecuteTool

__all__ = [
    "ProgrammingCalculateTool",
    "ProgrammingExecuteTool",
    "register_programming_tools",
]


def register_programming_tools() -> List:
    """Return all programming tool instances.

    Returns:
        List of programming tool instances
    """
    return [
        ProgrammingCalculateTool(),
        ProgrammingExecuteTool(),
    ]

"""File system tools for built-in tool library."""

from typing import List

from .read import FileReadTool
from .write import FileWriteTool
from .list import FileListTool
from .info import FileInfoTool

__all__ = [
    "FileReadTool",
    "FileWriteTool",
    "FileListTool",
    "FileInfoTool",
    "register_file_tools",
]


def register_file_tools() -> List:
    """Return all file tool instances.

    Returns:
        List of file tool instances
    """
    return [
        FileReadTool(),
        FileWriteTool(),
        FileListTool(),
        FileInfoTool(),
    ]

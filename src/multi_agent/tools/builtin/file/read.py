"""File read tool for built-in tool library."""

import os
from pathlib import Path
from typing import Dict, Any

from ..result import ToolResult


class FileReadTool:
    """Tool for reading text file contents.

    Reads files from the local filesystem within the allowed directory
    (current working directory and subdirectories).
    """

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "Read the contents of a text file. Returns file content as string."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read (relative to current directory)",
                }
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        """Read file contents.

        Args:
            path: Path to the file

        Returns:
            ToolResult with file contents or error
        """
        path = kwargs.get("path", "")
        if not path:
            return ToolResult(success=False, error="Path parameter is required")

        try:
            # Resolve path and validate it's within allowed directory
            target_path = Path(path).resolve()
            cwd = Path.cwd().resolve()

            # Check if path is within CWD + subdirectories
            try:
                target_path.relative_to(cwd)
            except ValueError:
                return ToolResult(
                    success=False,
                    error=f"Access denied: path outside allowed directory (CWD only)"
                )

            # Check if path exists and is a file
            if not target_path.exists():
                return ToolResult(success=False, error=f"File not found: {path}")

            if not target_path.is_file():
                return ToolResult(success=False, error=f"Not a file: {path}")

            # Read file with size limit
            content = target_path.read_text(encoding="utf-8")
            return ToolResult.from_string(content, enforce_limit=True)

        except PermissionError:
            return ToolResult(success=False, error=f"Permission denied: {path}")
        except UnicodeDecodeError:
            return ToolResult(success=False, error=f"File is not valid UTF-8 text: {path}")
        except Exception as e:
            return ToolResult(success=False, error=f"Error reading file: {e}")

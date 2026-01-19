"""File write tool for built-in tool library."""

from pathlib import Path
from typing import Dict, Any

from ..result import ToolResult


class FileWriteTool:
    """Tool for writing content to text files.

    Writes files to the local filesystem within the allowed directory
    (current working directory and subdirectories).
    """

    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return "Write content to a text file. Creates parent directories if needed."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write (relative to current directory)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        """Write content to file.

        Args:
            path: Path to the file
            content: Content to write

        Returns:
            ToolResult indicating success or failure
        """
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")

        if not path:
            return ToolResult(success=False, error="Path parameter is required")
        if content is None:
            return ToolResult(success=False, error="Content parameter is required")

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

            # Create parent directories if needed
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            target_path.write_text(content, encoding="utf-8")

            return ToolResult(success=True, data=f"Successfully wrote {len(content)} bytes to {path}")

        except PermissionError:
            return ToolResult(success=False, error=f"Permission denied: {path}")
        except Exception as e:
            return ToolResult(success=False, error=f"Error writing file: {e}")

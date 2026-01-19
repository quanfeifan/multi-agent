"""File list tool for built-in tool library."""

from pathlib import Path
from typing import Dict, Any

from ..result import ToolResult


class FileListTool:
    """Tool for listing directory contents.

    Lists files and directories in a given path with size information.
    """

    @property
    def name(self) -> str:
        return "file_list"

    @property
    def description(self) -> str:
        return "List files and directories in a given path."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the directory to list (default: current directory)",
                }
            },
            "required": [],
        }

    async def execute(self, **kwargs) -> ToolResult:
        """List directory contents.

        Args:
            path: Path to the directory (default: ".")

        Returns:
            ToolResult with directory listing or error
        """
        path = kwargs.get("path", ".")

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

            # Check if path exists
            if not target_path.exists():
                return ToolResult(success=False, error=f"Path not found: {path}")

            # Check if path is a directory
            if not target_path.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Not a directory: {path}"
                )

            # List directory contents
            items = []
            for item in sorted(target_path.iterdir()):
                try:
                    size = item.stat().st_size if item.is_file() else 0
                    item_type = "DIR" if item.is_dir() else "FILE"
                    items.append(f"{item.name} ({item_type}, {size} bytes)")
                except PermissionError:
                    items.append(f"{item.name} (Permission denied)")

            result = f"Contents of {path}:\n" + "\n".join(items)
            return ToolResult.from_string(result, enforce_limit=True)

        except PermissionError:
            return ToolResult(success=False, error=f"Permission denied: {path}")
        except Exception as e:
            return ToolResult(success=False, error=f"Error listing directory: {e}")

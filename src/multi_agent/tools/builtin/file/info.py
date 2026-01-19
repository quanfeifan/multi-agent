"""File info tool for built-in tool library."""

import datetime
import os
from pathlib import Path
from typing import Dict, Any

from ..result import ToolResult


class FileInfoTool:
    """Tool for getting file information.

    Returns metadata about a file or directory including size,
    type, and modification time.
    """

    @property
    def name(self) -> str:
        return "file_info"

    @property
    def description(self) -> str:
        return "Get information about a file or directory (size, type, permissions)."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file or directory",
                }
            },
            "required": ["path"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        """Get file information.

        Args:
            path: Path to the file or directory

        Returns:
            ToolResult with file information or error
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

            # Check if path exists
            if not target_path.exists():
                return ToolResult(success=False, error=f"Path not found: {path}")

            # Get file stats
            stat = target_path.stat()

            # Determine type
            if target_path.is_file():
                item_type = "file"
            elif target_path.is_dir():
                item_type = "directory"
            elif target_path.is_symlink():
                item_type = "symlink"
            else:
                item_type = "unknown"

            # Get modification time
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc)
            mtime_iso = mtime.strftime("%Y-%m-%d %H:%M:%S UTC")

            # Format result
            result = f"Path: {path}\n"
            result += f"Type: {item_type}\n"
            result += f"Size: {stat.st_size} bytes\n"
            result += f"Modified: {mtime_iso}\n"
            result += f"Readable: {target_path.is_file() and os.access(target_path, os.R_OK)}\n"
            result += f"Writable: {target_path.is_file() and os.access(target_path, os.W_OK)}"

            return ToolResult(success=True, data=result)

        except PermissionError:
            return ToolResult(success=False, error=f"Permission denied: {path}")
        except Exception as e:
            return ToolResult(success=False, error=f"Error getting file info: {e}")

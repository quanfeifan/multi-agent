"""System list processes tool for built-in tool library."""

import psutil
from typing import Dict, Any, List

from ..result import ToolResult


class SystemListProcessesTool:
    """Tool for listing running processes."""

    @property
    def name(self) -> str:
        return "system_list_processes"

    @property
    def description(self) -> str:
        return "List running processes on the system (name and PID only)."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "number",
                    "description": "Maximum number of processes to return (default: 20)",
                }
            },
            "required": [],
        }

    async def execute(self, **kwargs) -> ToolResult:
        """List running processes.

        Args:
            limit: Maximum number of processes to return (default: 20)

        Returns:
            ToolResult with process list
        """
        limit = kwargs.get("limit", 20)

        try:
            limit = int(limit)
            if limit <= 0:
                return ToolResult(success=False, error="Limit must be positive")
        except (ValueError, TypeError):
            return ToolResult(success=False, error="Invalid limit value")

        try:
            # Get list of processes
            processes = []
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    proc_info = proc.info
                    processes.append(
                        f"PID: {proc_info['pid']}, Name: {proc_info.get('name', 'unknown')}"
                    )
                    if len(processes) >= limit:
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            result = f"Running processes (showing {len(processes)}):\n" + "\n".join(
                processes
            )
            return ToolResult.from_string(result, enforce_limit=True)

        except ImportError:
            # psutil not available, use fallback
            return ToolResult(
                success=False,
                error="psutil package not installed. Install with: pip install psutil"
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Error listing processes: {e}")

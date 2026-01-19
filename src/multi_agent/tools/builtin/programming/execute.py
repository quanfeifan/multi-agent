"""Programming execute tool for built-in tool library.

Provides safe Python code execution with restricted namespace.
"""

import io
import math
from contextlib import redirect_stdout
from typing import Dict, Any

from ..result import ToolResult


class ProgrammingExecuteTool:
    """Tool for executing Python code in a restricted environment.

    Executes Python code with restricted globals to prevent access to
    dangerous functions like import, open, eval, etc.
    """

    @property
    def name(self) -> str:
        return "execute"

    @property
    def description(self) -> str:
        return "Execute Python code in a restricted environment. Limited to math operations and safe built-ins. No file access or imports allowed."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute (e.g., 'result = 2 + 2')",
                }
            },
            "required": ["code"],
        }

    # Safe globals for code execution - no imports or dangerous functions
    _SAFE_GLOBALS = {
        "__builtins__": {
            "abs": abs,
            "all": all,
            "any": any,
            "bin": bin,
            "bool": bool,
            "dict": dict,
            "divmod": divmod,
            "enumerate": enumerate,
            "filter": filter,
            "float": float,
            "hex": hex,
            "int": int,
            "isinstance": isinstance,
            "issubclass": issubclass,
            "iter": iter,
            "len": len,
            "list": list,
            "map": map,
            "max": max,
            "min": min,
            "oct": oct,
            "ord": ord,
            "pow": pow,
            "print": print,
            "range": range,
            "reversed": reversed,
            "round": round,
            "set": set,
            "sorted": sorted,
            "str": str,
            "sum": sum,
            "tuple": tuple,
            "zip": zip,
        },
        "math": math,
    }

    async def execute(self, **kwargs) -> ToolResult:
        """Execute Python code in restricted environment.

        Args:
            code: Python code to execute

        Returns:
            ToolResult with execution output
        """
        code = kwargs.get("code", "")
        if not code:
            return ToolResult(success=False, error="Code parameter is required")

        # Capture stdout
        stdout_buffer = io.StringIO()

        try:
            # Local namespace for execution
            local_vars: Dict[str, Any] = {}

            # Execute code with restricted globals and stdout capture
            with redirect_stdout(stdout_buffer):
                exec(code, self._SAFE_GLOBALS, local_vars)

            # Get captured stdout
            stdout_value = stdout_buffer.getvalue()

            # If there's stdout output, use it
            if stdout_value:
                return ToolResult.from_string(stdout_value, enforce_limit=True)

            # Check for 'result' variable (common pattern)
            if "result" in local_vars:
                result_str = str(local_vars["result"])
                return ToolResult.from_string(result_str, enforce_limit=True)

            # Check for last expression that produced a value
            # This is a simple heuristic - not perfect but useful
            for var_name in reversed(list(local_vars.keys())):
                if not var_name.startswith("_"):
                    value = local_vars[var_name]
                    if not callable(value):
                        result_str = str(value)
                        return ToolResult.from_string(result_str, enforce_limit=True)

            # No output, return success message
            return ToolResult(success=True, data="Code executed successfully (no output)")

        except SyntaxError as e:
            return ToolResult(success=False, error=f"Syntax error: {e}")
        except IndentationError as e:
            return ToolResult(success=False, error=f"Indentation error: {e}")
        except NameError as e:
            return ToolResult(
                success=False,
                error=f"Name error: {e}. Imports and many built-ins are not available."
            )
        except TypeError as e:
            return ToolResult(success=False, error=f"Type error: {e}")
        except Exception as e:
            return ToolResult(success=False, error=f"Execution error: {e}")

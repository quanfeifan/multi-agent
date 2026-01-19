"""Programming calculate tool for built-in tool library.

Provides mathematical expression evaluation with restricted globals.
"""

import math
from typing import Dict, Any

from ..result import ToolResult


class ProgrammingCalculateTool:
    """Tool for evaluating mathematical expressions.

    Evaluates math expressions using safe, restricted globals.
    Only the math module and safe built-ins are available.
    """

    @property
    def name(self) -> str:
        return "calculate"

    @property
    def description(self) -> str:
        return "Calculate a mathematical expression. Supports +, -, *, /, **, %, and math functions."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": 'Mathematical expression to evaluate (e.g., "2 * (10 + 5)", "math.sqrt(16)")',
                }
            },
            "required": ["expression"],
        }

    # Safe globals for expression evaluation
    _SAFE_GLOBALS = {
        "__builtins__": {
            "abs": abs,
            "min": min,
            "max": max,
            "sum": sum,
            "len": len,
            "range": range,
            "round": round,
            "pow": pow,
        },
        "math": math,
    }

    async def execute(self, **kwargs) -> ToolResult:
        """Evaluate a mathematical expression.

        Args:
            expression: Mathematical expression to evaluate

        Returns:
            ToolResult with calculation result
        """
        expression = kwargs.get("expression", "")
        if not expression:
            return ToolResult(success=False, error="Expression parameter is required")

        try:
            # Evaluate expression with restricted globals
            result = eval(expression, self._SAFE_GLOBALS, {})

            # Convert result to string
            result_str = str(result)

            return ToolResult(success=True, data=result_str)

        except SyntaxError as e:
            return ToolResult(success=False, error=f"Syntax error in expression: {e}")
        except NameError as e:
            return ToolResult(
                success=False,
                error=f"Invalid name in expression: {e}. Only math functions and safe built-ins are available."
            )
        except TypeError as e:
            return ToolResult(success=False, error=f"Type error: {e}")
        except ZeroDivisionError:
            return ToolResult(success=False, error="Division by zero")
        except Exception as e:
            return ToolResult(success=False, error=f"Error evaluating expression: {e}")

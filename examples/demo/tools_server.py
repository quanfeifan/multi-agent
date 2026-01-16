#!/usr/bin/env python3
"""Simple MCP tool server for demo.

This server provides built-in tools for calculator, file operations, etc.
Run with: python examples/demo/tools_server.py
"""

import asyncio
import json
import sys
from pathlib import Path


async def handle_message(message: dict) -> dict:
    """Handle an MCP message.

    Args:
        message: Incoming MCP message

    Returns:
        Response message
    """
    method = message.get("method")

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "tools": [
                    {
                        "name": "calculator",
                        "description": "Perform mathematical calculations. Supports +, -, *, /, ** operations.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "expression": {
                                    "type": "string",
                                    "description": "Mathematical expression to evaluate (e.g., '2 + 2', '10 * 5')"
                                }
                            },
                            "required": ["expression"]
                        }
                    },
                    {
                        "name": "read_file",
                        "description": "Read the contents of a text file.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": "Path to the file"
                                }
                            },
                            "required": ["path"]
                        }
                    },
                    {
                        "name": "list_files",
                        "description": "List files in a directory.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": "Path to the directory (default: current)"
                                }
                            },
                            "required": []
                        }
                    },
                    {
                        "name": "get_time",
                        "description": "Get the current date and time.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                ]
            }
        }

    elif method == "tools/call":
        params = message.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments", {})

        result = await execute_tool(name, arguments)

        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": result
                    }
                ]
            }
        }

    elif method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "demo-tools",
                    "version": "1.0.0"
                },
                "capabilities": {
                    "tools": {}
                }
            }
        }

    else:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }


async def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        Tool result
    """
    if name == "calculator":
        expression = arguments.get("expression", "")
        try:
            result = eval(expression)
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"

    elif name == "read_file":
        path = arguments.get("path", "")
        try:
            content = Path(path).read_text(encoding="utf-8")
            return content[:2000]  # Limit output
        except Exception as e:
            return f"Error: {e}"

    elif name == "list_files":
        path = arguments.get("path", ".")
        try:
            files = sorted(Path(path).iterdir())
            result = f"Files in {path}:\n"
            for f in files:
                result += f"  {f.name} ({f.stat().st_size} bytes)\n"
            return result
        except Exception as e:
            return f"Error: {e}"

    elif name == "get_time":
        from datetime import datetime
        return f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    else:
        return f"Unknown tool: {name}"


async def main() -> None:
    """Run the MCP stdio server."""
    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.readline
            )
            if not line:
                break

            message = json.loads(line.strip())
            response = await handle_message(message)
            print(json.dumps(response), flush=True)

        except json.JSONDecodeError:
            continue
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    asyncio.run(main())

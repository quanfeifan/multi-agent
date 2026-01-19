"""Network fetch tool for built-in tool library.

Provides HTTP/HTTPS content fetching with timeout and retry.
"""

import httpx
from typing import Dict, Any

from ..result import ToolResult


class NetworkFetchTool:
    """Tool for fetching content from URLs.

    Fetches web content via HTTP GET with 5-second timeout and 1 retry.
    Only HTTP/HTTPS URLs are allowed.
    """

    @property
    def name(self) -> str:
        return "network_fetch"

    @property
    def description(self) -> str:
        return "Fetch content from a URL via HTTP GET request. Returns text content. Supports 5-second timeout with 1 retry."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch (must start with http:// or https://)",
                }
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        """Fetch content from URL.

        Args:
            url: URL to fetch

        Returns:
            ToolResult with fetched content or error
        """
        url = kwargs.get("url", "")
        if not url:
            return ToolResult(success=False, error="URL parameter is required")

        # Validate URL scheme
        if not url.startswith(("http://", "https://")):
            return ToolResult(
                success=False,
                error="Invalid URL scheme: only HTTP and HTTPS are supported"
            )

        # Create transport with retry
        transport = httpx.AsyncHTTPTransport(retries=1)

        try:
            async with httpx.AsyncClient(
                transport=transport,
                timeout=5.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)

                # Check for HTTP errors
                response.raise_for_status()

                # Get content as text
                content = response.text

                # Enforce size limit
                return ToolResult.from_string(content, enforce_limit=True)

        except httpx.TimeoutException:
            return ToolResult(success=False, error="Request timeout after 5 seconds")
        except httpx.TooManyRedirects:
            return ToolResult(success=False, error="Too many redirects")
        except httpx.HTTPStatusError as e:
            return ToolResult(
                success=False,
                error=f"HTTP error {e.response.status_code}: {e.response.reason_phrase}"
            )
        except httpx.ConnectError:
            return ToolResult(success=False, error="Connection error: could not connect to server")
        except httpx.UnsupportedProtocol:
            return ToolResult(success=False, error="Unsupported protocol")
        except Exception as e:
            return ToolResult(success=False, error=f"Error fetching URL: {e}")

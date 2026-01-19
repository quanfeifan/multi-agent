"""Network tools for web content fetching."""

from typing import List

from .fetch import NetworkFetchTool

__all__ = [
    "NetworkFetchTool",
    "register_network_tools",
]


def register_network_tools() -> List:
    """Return all network tool instances.

    Note: web_search tool is deferred until external API integration is ready.

    Returns:
        List of network tool instances
    """
    return [
        NetworkFetchTool(),
        # Note: web_search tool will be added when API integration is implemented
    ]

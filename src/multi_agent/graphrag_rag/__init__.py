"""GraphRAG integration for multi-agent framework.

This module provides knowledge graph-enhanced RAG capabilities using GraphRAG.
"""

from .client import GraphRAGClient, GraphRAGQueryConfig
from .agent import GraphRAGAgent
from .utils import setup_sample_index

__all__ = [
    "GraphRAGClient",
    "GraphRAGQueryConfig",
    "GraphRAGAgent",
    "setup_sample_index",
]

"""GraphRAG client for multi-agent framework.

This module provides a client interface for querying GraphRAG knowledge graphs.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict

from ..utils import get_logger

logger = get_logger(__name__)


class GraphRAGQueryConfig(BaseModel):
    """Configuration for GraphRAG queries.

    Attributes:
        search_type: Type of search ('local', 'global', 'basic', 'drift')
        community_level: Community level to search at (for global search)
        dynamic_community_selection: Enable dynamic community selection
        response_type: Type of response ('free_form', 'multiple_paragraphs', etc.)
        use_context_data: Whether to return context data with results
        max_results: Maximum number of results to return
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    search_type: str = "global"
    community_level: Optional[int] = None
    dynamic_community_selection: bool = True
    response_type: str = "free_form"
    use_context_data: bool = False
    max_results: int = 10


class GraphRAGClient:
    """Client for querying GraphRAG knowledge graphs.

    This client wraps the GraphRAG query API and provides a simplified
    interface for multi-agent systems to access knowledge graph data.

    Attributes:
        config_path: Path to GraphRAG configuration
        output_path: Path to GraphRAG output directory
        data: Loaded graph data (entities, communities, reports)
    """

    def __init__(
        self,
        output_path: str | Path,
        config_path: Optional[str | Path] = None,
    ) -> None:
        """Initialize GraphRAG client.

        Args:
            output_path: Path to GraphRAG output directory (contains parquet files)
            config_path: Path to GraphRAG settings.yaml (optional)
        """
        self.output_path = Path(output_path)
        self.config_path = Path(config_path) if config_path else None

        self.data: dict[str, pd.DataFrame] = {}
        self._load_data()

    def _load_data(self) -> None:
        """Load graph data from parquet files.

        Loads entities, relationships, communities, and community reports.
        """
        logger.info(f"Loading GraphRAG data from {self.output_path}")

        # Load entities
        entities_path = self.output_path / "create_final_entities.parquet"
        if entities_path.exists():
            self.data["entities"] = pd.read_parquet(entities_path)
            logger.info(f"Loaded {len(self.data['entities'])} entities")
        else:
            logger.warning(f"Entities file not found: {entities_path}")
            self.data["entities"] = pd.DataFrame()

        # Load relationships
        rels_path = self.output_path / "create_final_relationships.parquet"
        if rels_path.exists():
            self.data["relationships"] = pd.read_parquet(rels_path)
            logger.info(f"Loaded {len(self.data['relationships'])} relationships")
        else:
            logger.warning(f"Relationships file not found: {rels_path}")
            self.data["relationships"] = pd.DataFrame()

        # Load communities
        comm_path = self.output_path / "create_final_communities.parquet"
        if comm_path.exists():
            self.data["communities"] = pd.read_parquet(comm_path)
            logger.info(f"Loaded {len(self.data['communities'])} communities")
        else:
            logger.warning(f"Communities file not found: {comm_path}")
            self.data["communities"] = pd.DataFrame()

        # Load community reports
        reports_path = self.output_path / "create_final_community_reports.parquet"
        if reports_path.exists():
            self.data["community_reports"] = pd.read_parquet(reports_path)
            logger.info(f"Loaded {len(self.data['community_reports'])} community reports")
        else:
            logger.warning(f"Community reports file not found: {reports_path}")
            self.data["community_reports"] = pd.DataFrame()

    async def query(
        self,
        query_text: str,
        config: Optional[GraphRAGQueryConfig] = None,
    ) -> dict[str, Any]:
        """Query the knowledge graph.

        Args:
            query_text: Query text
            config: Query configuration (uses defaults if None)

        Returns:
            Dictionary with response and optional context data
        """
        if config is None:
            config = GraphRAGQueryConfig()

        # Check if data is loaded
        if not any(len(df) > 0 for df in self.data.values()):
            logger.warning("No graph data available, returning empty result")
            return {
                "response": "No knowledge graph data available. Please build the index first.",
                "context_data": {},
            }

        # Simple implementation: search through entities and reports
        # In a full implementation, this would use the GraphRAG query engines
        result = await self._simple_search(query_text, config)

        return result

    async def _simple_search(
        self,
        query_text: str,
        config: GraphRAGQueryConfig,
    ) -> dict[str, Any]:
        """Simple search implementation.

        This is a simplified version that searches through the loaded data.
        In production, use GraphRAG's actual query engines.

        Args:
            query_text: Query text
            config: Query configuration

        Returns:
            Search results
        """
        query_lower = query_text.lower()
        context_data = {}

        # Search entities
        if len(self.data["entities"]) > 0:
            matching_entities = self.data["entities"][
                self.data["entities"]["title"].str.lower().str.contains(query_lower, na=False) |
                self.data["entities"].get("description", pd.Series([""] * len(self.data["entities"]))) \
                    .str.lower().str.contains(query_lower, na=False)
            ]

            if len(matching_entities) > 0:
                context_data["entities"] = matching_entities.head(config.max_results).to_dict(orient="records")

        # Search community reports
        if len(self.data["community_reports"]) > 0:
            matching_reports = self.data["community_reports"][
                self.data["community_reports"]["title"].str.lower().str.contains(query_lower, na=False) |
                self.data["community_reports"]["summary"].str.lower().str.contains(query_lower, na=False)
            ]

            if len(matching_reports) > 0:
                context_data["community_reports"] = matching_reports.head(config.max_results).to_dict(orient="records")

        # Generate response based on found data
        if context_data:
            response_parts = []

            if "entities" in context_data:
                response_parts.append(f"Found {len(context_data['entities'])} related entities:")
                for entity in context_data["entities"][:3]:
                    response_parts.append(f"  - {entity.get('title', 'Unknown')}: {entity.get('description', 'No description')[:100]}...")

            if "community_reports" in context_data:
                response_parts.append(f"\nFound {len(context_data['community_reports'])} relevant community reports:")
                for report in context_data["community_reports"][:2]:
                    response_parts.append(f"  - {report.get('title', 'Unknown')}: {report.get('summary', 'No summary')[:150]}...")

            response = "\n".join(response_parts)
        else:
            response = f"No matching information found for query: '{query_text}'"

        return {
            "response": response,
            "context_data": context_data if config.use_context_data else {},
            "search_type": config.search_type,
        }

    async def global_search(
        self,
        query_text: str,
        community_level: Optional[int] = None,
    ) -> dict[str, Any]:
        """Perform global search across the entire knowledge graph.

        Args:
            query_text: Query text
            community_level: Community level to search at

        Returns:
            Search results
        """
        config = GraphRAGQueryConfig(
            search_type="global",
            community_level=community_level,
        )
        return await self.query(query_text, config)

    async def local_search(
        self,
        query_text: str,
    ) -> dict[str, Any]:
        """Perform local search around specific entities.

        Args:
            query_text: Query text

        Returns:
            Search results
        """
        config = GraphRAGQueryConfig(
            search_type="local",
        )
        return await self.query(query_text, config)

    def get_entity_info(self, entity_name: str) -> Optional[dict[str, Any]]:
        """Get information about a specific entity.

        Args:
            entity_name: Name of the entity

        Returns:
            Entity information or None if not found
        """
        if len(self.data["entities"]) == 0:
            return None

        entity_name_lower = entity_name.lower()
        matching = self.data["entities"][
            self.data["entities"]["title"].str.lower() == entity_name_lower
        ]

        if len(matching) > 0:
            return matching.iloc[0].to_dict()

        return None

    def get_entity_relationships(self, entity_name: str) -> list[dict[str, Any]]:
        """Get relationships for a specific entity.

        Args:
            entity_name: Name of the entity

        Returns:
            List of relationships
        """
        if len(self.data["relationships"]) == 0:
            return []

        entity_name_lower = entity_name.lower()
        matching = self.data["relationships"][
            (self.data["relationships"]["source"].str.lower() == entity_name_lower) |
            (self.data["relationships"]["target"].str.lower() == entity_name_lower)
        ]

        return matching.to_dict(orient="records")

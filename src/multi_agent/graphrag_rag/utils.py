"""Utility functions for GraphRAG integration.

This module provides helper functions for setting up and managing GraphRAG data.
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..utils import get_logger

logger = get_logger(__name__)


def setup_sample_index(output_path: str | Path) -> bool:
    """Create a sample knowledge graph index for testing and demonstration.

    This function creates a minimal set of parquet files representing a knowledge graph
    with entities, relationships, communities, and community reports.

    Args:
        output_path: Path where to create the sample index

    Returns:
        True if successful, False otherwise
    """
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Creating sample GraphRAG index at {output_path}")

    try:
        # Create sample entities
        entities = pd.DataFrame([
            {
                "id": 0,
                "title": "Machine Learning",
                "type": "Concept",
                "description": "A field of artificial intelligence that uses statistical techniques to give computer systems the ability to learn from data.",
                "degree": 3,
                "rank": 0.9,
            },
            {
                "id": 1,
                "title": "Neural Networks",
                "type": "Concept",
                "description": "Computing systems inspired by the biological neural networks that constitute animal brains.",
                "degree": 2,
                "rank": 0.8,
            },
            {
                "id": 2,
                "title": "GraphRAG",
                "type": "Methodology",
                "description": "A retrieval-augmented generation system that uses knowledge graphs to enhance LLM responses.",
                "degree": 2,
                "rank": 0.7,
            },
            {
                "id": 3,
                "title": "Knowledge Graph",
                "type": "Structure",
                "description": "A graph that represents real-world entities and the relationships between them.",
                "degree": 2,
                "rank": 0.75,
            },
            {
                "id": 4,
                "title": "Multi-Agent Systems",
                "type": "Architecture",
                "description": "Systems composed of multiple interacting intelligent agents.",
                "degree": 2,
                "rank": 0.65,
            },
            {
                "id": 5,
                "title": "LLM",
                "type": "Technology",
                "description": "Large Language Models - AI models trained on vast amounts of text data.",
                "degree": 3,
                "rank": 0.85,
            },
        ])

        entities_path = output_path / "create_final_entities.parquet"
        entities.to_parquet(entities_path)
        logger.info(f"Created entities: {len(entities)} entities")

        # Create sample relationships
        relationships = pd.DataFrame([
            {
                "id": 0,
                "source": "Machine Learning",
                "target": "Neural Networks",
                "description": "includes",
                "weight": 0.9,
            },
            {
                "id": 1,
                "source": "GraphRAG",
                "target": "Knowledge Graph",
                "description": "uses",
                "weight": 0.95,
            },
            {
                "id": 2,
                "source": "GraphRAG",
                "target": "LLM",
                "description": "enhances",
                "weight": 0.9,
            },
            {
                "id": 3,
                "source": "Multi-Agent Systems",
                "target": "LLM",
                "description": "leverages",
                "weight": 0.85,
            },
            {
                "id": 4,
                "source": "Knowledge Graph",
                "target": "LLM",
                "description": "provides context for",
                "weight": 0.8,
            },
            {
                "id": 5,
                "source": "Neural Networks",
                "target": "LLM",
                "description": "is a key component of",
                "weight": 0.85,
            },
        ])

        rels_path = output_path / "create_final_relationships.parquet"
        relationships.to_parquet(rels_path)
        logger.info(f"Created relationships: {len(relationships)} relationships")

        # Create sample communities
        communities = pd.DataFrame([
            {
                "id": 0,
                "title": "AI Core Technologies",
                "level": 0,
                "title_embed": [],
                "size": 3,
                "rank": 0.9,
            },
            {
                "id": 1,
                "title": "GraphRAG Architecture",
                "level": 0,
                "title_embed": [],
                "size": 2,
                "rank": 0.85,
            },
            {
                "id": 2,
                "title": "System Integration",
                "level": 0,
                "title_embed": [],
                "size": 2,
                "rank": 0.8,
            },
        ])

        comm_path = output_path / "create_final_communities.parquet"
        communities.to_parquet(comm_path)
        logger.info(f"Created communities: {len(communities)} communities")

        # Create sample community reports
        community_reports = pd.DataFrame([
            {
                "id": 0,
                "community": 0,
                "level": 0,
                "title": "AI Core Technologies Overview",
                "summary": "This community focuses on fundamental AI technologies including Machine Learning, Neural Networks, and Large Language Models (LLMs). These technologies form the foundation for advanced AI applications and are deeply interconnected. Machine Learning encompasses statistical techniques for learning from data, while Neural Networks are biologically-inspired architectures that enable deep learning capabilities. LLMs leverage these foundations to process and generate natural language.",
                "rank": 0.9,
                "size": 3,
                "full_content": "AI Core Technologies Overview\n\nThe AI Core Technologies community represents the foundational technologies driving modern artificial intelligence:\n\n1. Machine Learning: Statistical techniques enabling systems to learn from data patterns\n2. Neural Networks: Biologically-inspired architectures for deep learning\n3. Large Language Models: Advanced models trained on vast text corpora\n\nThese technologies are interconnected and often used in combination to build sophisticated AI systems.",
            },
            {
                "id": 1,
                "community": 1,
                "level": 0,
                "title": "GraphRAG Architecture and Components",
                "summary": "This community covers GraphRAG's key components: Knowledge Graphs and their integration with LLMs. GraphRAG leverages knowledge graphs to provide structured, contextual information to LLMs, enhancing their ability to answer complex questions with greater accuracy and trustworthiness.",
                "rank": 0.85,
                "size": 2,
                "full_content": "GraphRAG Architecture and Components\n\nGraphRAG combines two powerful approaches:\n\n1. Knowledge Graphs: Structured representations of entities and their relationships\n2. LLM Integration: Using graph data to enhance language model responses\n\nThis architecture enables:\n- Better semantic understanding through explicit entity relationships\n- Multi-hop reasoning across connected concepts\n- Increased answer accuracy and trustworthiness\n- Context-aware responses backed by structured data",
            },
            {
                "id": 2,
                "community": 2,
                "level": 0,
                "title": "Multi-Agent Systems and LLM Integration",
                "summary": "This community explores how Multi-Agent Systems leverage LLMs to create more sophisticated AI solutions. Multi-agent architectures enable parallel processing, specialized task delegation, and improved system reliability.",
                "rank": 0.8,
                "size": 2,
                "full_content": "Multi-Agent Systems and LLM Integration\n\nMulti-agent systems provide several advantages:\n\n1. Parallel Processing: Multiple agents can work simultaneously\n2. Specialization: Each agent can focus on specific domains or tasks\n3. Resilience: System remains robust even if one agent fails\n4. Scalability: Easy to add new capabilities by adding new agents\n\nWhen combined with LLMs, multi-agent systems can coordinate complex workflows, delegate tasks appropriately, and synthesize results from multiple perspectives.",
            },
        ])

        reports_path = output_path / "create_final_community_reports.parquet"
        community_reports.to_parquet(reports_path)
        logger.info(f"Created community reports: {len(community_reports)} reports")

        logger.info(f"Sample GraphRAG index created successfully at {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to create sample GraphRAG index: {e}")
        return False


def export_graph_to_json(
    output_path: str | Path,
    json_path: str | Path,
) -> bool:
    """Export GraphRAG parquet data to JSON for visualization or analysis.

    Args:
        output_path: Path to GraphRAG output directory
        json_path: Path where to write the JSON file

    Returns:
        True if successful, False otherwise
    """
    output_path = Path(output_path)
    json_path = Path(json_path)

    try:
        data: dict[str, Any] = {
            "entities": [],
            "relationships": [],
            "communities": [],
            "community_reports": [],
        }

        # Load entities
        entities_path = output_path / "create_final_entities.parquet"
        if entities_path.exists():
            entities = pd.read_parquet(entities_path)
            data["entities"] = entities.to_dict(orient="records")

        # Load relationships
        rels_path = output_path / "create_final_relationships.parquet"
        if rels_path.exists():
            relationships = pd.read_parquet(rels_path)
            data["relationships"] = relationships.to_dict(orient="records")

        # Load communities
        comm_path = output_path / "create_final_communities.parquet"
        if comm_path.exists():
            communities = pd.read_parquet(comm_path)
            data["communities"] = communities.to_dict(orient="records")

        # Load community reports
        reports_path = output_path / "create_final_community_reports.parquet"
        if reports_path.exists():
            community_reports = pd.read_parquet(reports_path)
            data["community_reports"] = community_reports.to_dict(orient="records")

        # Write JSON
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Exported GraphRAG data to {json_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to export GraphRAG data: {e}")
        return False

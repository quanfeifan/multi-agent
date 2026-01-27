#!/usr/bin/env python3
"""
GraphRAG Knowledge Graph RAG Demo

This demo demonstrates how GraphRAG knowledge graph-enhanced RAG works with multi-agent systems:
1. Creates a sample knowledge graph
2. Initializes a GraphRAG agent
3. Shows how the agent queries the knowledge graph
4. Demonstrates parallel use with other agents for more trustworthy results

The GraphRAG system provides:
- Structured semantic understanding through entity-relationship graphs
- Multi-hop reasoning capabilities across connected concepts
- Community-level insights through hierarchical organization
- Enhanced trustworthiness through structured knowledge

Usage:
    PYTHONPATH=src python3 examples/demo/graphrag_rag_demo.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

# Disable proxy to avoid unsupported protocol error (socks://)
# httpx only supports http://, https://, and socks5://
proxy_keys = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]
for key in proxy_keys:
    if key in os.environ:
        del os.environ[key]

from multi_agent.agent.base import BaseAgent
from multi_agent.agent.session import SubAgentSessionManager
from multi_agent.agent.supervisor import SupervisorAgent, SubAgentTool
from multi_agent.config.schemas import AgentConfig, LLMConfig
from multi_agent.graphrag_rag import GraphRAGAgent, setup_sample_index
from multi_agent.models import Message, State
from multi_agent.state.base import create_initial_state
from multi_agent.state import StateManager
from multi_agent.tools import ToolExecutor
from multi_agent.tools.builtin import register_builtin_tools
from multi_agent.tracing import Tracer
from multi_agent.utils import get_logger

logger = get_logger(__name__)


async def demo_basic_graphrag_usage():
    """Demonstrate basic GraphRAG agent usage."""
    print("=" * 70)
    print("Demo 1: Basic GraphRAG Agent Usage")
    print("=" * 70)
    print()

    # Check API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxxxx"):
        print("⚠️  Set OPENAI_API_KEY in .env file")
        return

    # Create LLM config
    llm_config = LLMConfig(
        endpoint=os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
        model=os.environ.get("DEFAULT_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
        api_key_env="OPENAI_API_KEY"
    )

    # Create sample knowledge graph
    sample_graph_path = Path("/tmp/graphrag_sample")
    print(f"📊 Creating sample knowledge graph at {sample_graph_path}...")
    if setup_sample_index(sample_graph_path):
        print("✓ Sample knowledge graph created successfully")
    else:
        print("✗ Failed to create sample knowledge graph")
        return
    print()

    # Initialize GraphRAG agent
    print(f"🤖 Initializing GraphRAG agent...")
    graphrag_agent = GraphRAGAgent(
        llm_config=llm_config,
        graphrag_output_path=str(sample_graph_path),
    )
    print("✓ GraphRAG agent initialized")
    print()

    # Test queries
    questions = [
        "What is GraphRAG and how does it work?",
        "What are the relationships between Machine Learning and Neural Networks?",
    ]

    for question in questions:
        print("=" * 70)
        print(f"👤 User: {question}")
        print("-" * 70)

        # Create initial state
        state = create_initial_state(
            agent_name="graphrag_agent",
            task_description=question
        )

        # Execute agent
        print("🤖 GraphRAG agent reasoning...")
        result = await graphrag_agent.execute(
            task_description=question,
            initial_state=state,
        )

        # Display result
        print(f"✅ Agent Response:")
        print(result.output)
        print()


async def demo_parallel_agents_with_graphrag():
    """Demonstrate parallel use of GraphRAG with other agents for trustworthy results."""
    print("=" * 70)
    print("Demo 2: Parallel Agents with GraphRAG for Trustworthy Results")
    print("=" * 70)
    print()
    print("This demo shows how multiple agents can work in parallel:")
    print("- GraphRAG Agent: Provides knowledge from the structured graph")
    print("- Standard Agent: Uses general LLM reasoning")
    print("- Supervisor: Synthesizes both perspectives for a more trustworthy answer")
    print()

    # Check API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-xxxxx"):
        print("⚠️  Set OPENAI_API_KEY in .env file")
        return

    # Create LLM config
    llm_config = LLMConfig(
        endpoint=os.environ.get("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
        model=os.environ.get("DEFAULT_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
        api_key_env="OPENAI_API_KEY"
    )

    # Create sample knowledge graph
    sample_graph_path = Path("/tmp/graphrag_sample")
    print(f"📊 Using knowledge graph at {sample_graph_path}")
    print()

    # Initialize GraphRAG agent
    graphrag_agent = GraphRAGAgent(
        llm_config=llm_config,
        graphrag_output_path=str(sample_graph_path),
    )

    # Initialize a standard agent without graph access
    from multi_agent.models import Agent as AgentModel
    standard_agent = BaseAgent(
        agent=AgentModel(
            name="standard_agent",
            role="General Assistant",
            system_prompt="""You are a helpful assistant. Answer questions based on your general knowledge.
Be honest about what you know and don't know. Avoid making up facts.""",
            tools=[],
            max_iterations=10,
            llm_config=llm_config,
            temperature=0.5,
        ),
        tool_executor=None,
    )

    # Create supervisor agent
    supervisor = SupervisorAgent(
        agent=AgentModel(
            name="supervisor",
            role="Synthesis Coordinator",
            system_prompt="""You are a supervisor that coordinates responses from multiple agents.

Available agents:
1. GraphRAG Agent: Provides answers backed by structured knowledge graph data
2. Standard Agent: Provides general LLM reasoning

When a user asks a question:
1. For questions about knowledge graphs or GraphRAG, use delegate_graphrag_agent
2. For general questions, use delegate_standard_agent
3. Synthesize their responses to provide the most accurate and trustworthy answer

IMPORTANT: Provide a final answer directly. Do NOT keep delegating after getting results from agents.""",
            tools=[],
            max_iterations=3,
            llm_config=llm_config,
            temperature=0.3,
        ),
        sub_agents={
            "graphrag_agent": graphrag_agent,
            "standard_agent": standard_agent,
        },
    )

    # Test queries that benefit from multiple perspectives
    questions = [
        "Explain how GraphRAG improves LLM performance and why knowledge graphs are useful.",
    ]

    # Create state manager and session manager
    task_id = f"demo_task_{hash('graphrag_demo') & 0xffffffff}"
    state_manager = StateManager(task_id=task_id)
    tracer = Tracer(task_id=task_id, state_manager=state_manager)
    session_manager = SubAgentSessionManager(
        parent_task_id=task_id,
        state_manager=state_manager,
        tracer=tracer,
    )

    for question in questions:
        print("=" * 70)
        print(f"👤 User: {question}")
        print("-" * 70)

        # Create initial state
        state = create_initial_state(
            agent_name="supervisor",
            task_description=question
        )

        # Execute supervisor with session manager
        print("🎮 Supervisor coordinating agents...")
        result = await supervisor.execute_with_session_manager(
            task_description=question,
            session_manager=session_manager,
            initial_state=state,
        )

        # Display result
        print(f"✅ Synthesized Response:")
        print(result.output)
        print()


async def demo_graph_tools_directly():
    """Demonstrate using GraphRAG tools directly."""
    print("=" * 70)
    print("Demo 3: Direct GraphRAG Tool Usage")
    print("=" * 70)
    print()

    # Check API key is not needed for direct tool usage
    sample_graph_path = Path("/tmp/graphrag_sample")

    # Create GraphRAG client
    from multi_agent.graphrag_rag import GraphRAGClient

    print(f"📊 Initializing GraphRAG client...")
    client = GraphRAGClient(output_path=str(sample_graph_path))
    print("✓ Client initialized")
    print()

    # Test various query methods
    queries = [
        ("What is GraphRAG?", "global_search"),
        ("Neural Networks", "local_search"),
    ]

    for query_text, method in queries:
        print("-" * 70)
        print(f"🔍 Query: {query_text}")
        print(f"📊 Method: {method}")
        print("-" * 70)

        if method == "global_search":
            result = await client.global_search(query_text)
        else:
            result = await client.local_search(query_text)

        print(f"Response: {result['response']}")
        print()

        # Display context data if available
        if result.get("context_data"):
            print("Context Data:")
            print(json.dumps(result["context_data"], indent=2, default=str))
            print()

    # Test entity lookup
    print("-" * 70)
    print("🔍 Entity Lookup: Machine Learning")
    print("-" * 70)
    entity_info = client.get_entity_info("Machine Learning")
    if entity_info:
        print(f"Found: {entity_info['title']}")
        print(f"Description: {entity_info['description']}")
    print()

    # Test entity relationships
    print("-" * 70)
    print("🔍 Entity Relationships: GraphRAG")
    print("-" * 70)
    relationships = client.get_entity_relationships("GraphRAG")
    print(f"Found {len(relationships)} relationships:")
    for rel in relationships:
        print(f"  {rel['source']} --[{rel['description']}]--> {rel['target']}")
    print()


async def main():
    """Run all demos."""
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 10 + "GraphRAG Knowledge Graph RAG Demonstration" + " " * 14 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    print("GraphRAG Design Significance:")
    print("-" * 70)
    print("1. Structured Semantic Understanding:")
    print("   Knowledge graphs provide explicit entity-relationship structures")
    print("   that capture semantic meaning beyond simple vector similarity.")
    print()
    print("2. Multi-Hop Reasoning:")
    print("   Graph traversal enables reasoning across indirectly related concepts,")
    print("   allowing agents to answer questions requiring multiple inference steps.")
    print()
    print("3. Community-Level Insights:")
    print("   Hierarchical community organization provides both fine-grained details")
    print("   and high-level thematic perspectives.")
    print()
    print("4. Enhanced Trustworthiness:")
    print("   Multiple agents working in parallel can cross-validate answers from")
    print("   different perspectives (GraphRAG for structured knowledge,")
    print("   standard agents for general reasoning).")
    print()
    print("5. Context-Rich Responses:")
    print("   Integration of entities, relationships, and community reports")
    print("   provides comprehensive context for more accurate and detailed answers.")
    print("=" * 70)
    print()

    try:
        # Demo 1: Basic usage
        await demo_basic_graphrag_usage()

        # Demo 2: Parallel agents
        await demo_parallel_agents_with_graphrag()

        # Demo 3: Direct tool usage
        await demo_graph_tools_directly()

        print("=" * 70)
        print("✅ All demos completed successfully!")
        print("=" * 70)
        print()
        print("Key Takeaways:")
        print("- GraphRAG agents can access structured knowledge from the knowledge graph")
        print("- Multiple agents can work in parallel for different perspectives")
        print("- Supervisors can synthesize responses for more trustworthy results")
        print("- Direct tool access allows fine-grained control over graph queries")
        print()

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"✗ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

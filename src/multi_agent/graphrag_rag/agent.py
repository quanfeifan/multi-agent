"""GraphRAG agent for multi-agent framework.

This module provides an agent that leverages knowledge graph data for enhanced reasoning.
"""

from typing import Any, Optional

from pydantic import ConfigDict

from ..agent.base import BaseAgent
from ..config.schemas import AgentConfig, LLMConfig
from ..models import Agent as AgentModel, State
from ..tools import ToolExecutor
from ..tracing import Tracer
from .client import GraphRAGClient, GraphRAGQueryConfig
from ..utils import get_logger

logger = get_logger(__name__)


class GraphRAGAgent(BaseAgent):
    """Agent with knowledge graph-enhanced capabilities.

    This agent uses GraphRAG to access structured knowledge from the knowledge graph,
    providing more accurate and context-aware responses.

    The agent can:
    - Query entities and relationships in the knowledge graph
    - Use community reports for high-level insights
    - Perform local and global searches across the graph
    - Integrate graph data with LLM reasoning
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(
        self,
        llm_config: LLMConfig,
        graphrag_output_path: str,
        graphrag_config_path: Optional[str] = None,
        agent_config: Optional[AgentConfig] = None,
        tool_executor: Optional[ToolExecutor] = None,
        tracer: Optional[Tracer] = None,
    ) -> None:
        """Initialize GraphRAG agent.

        Args:
            llm_config: LLM configuration
            graphrag_output_path: Path to GraphRAG output directory
            graphrag_config_path: Path to GraphRAG configuration (optional)
            agent_config: Agent configuration (optional)
            tool_executor: Tool executor (optional)
            tracer: Tracer for execution tracking (optional)
        """
        # Create agent model if not provided
        from ..models import Agent as AgentModel

        if agent_config is None:
            agent_model = AgentModel(
                name="graphrag_agent",
                role="Knowledge Graph Specialist",
                system_prompt="""You are a specialized agent with access to a knowledge graph through GraphRAG.
Your role is to:

1. Query the knowledge graph to find relevant entities, relationships, and insights
2. Use community reports to understand high-level themes and structures
3. Provide answers backed by structured knowledge from the graph
4. When uncertain, use the graph_search tool to find relevant information
5. Synthesize information from the graph with your reasoning capabilities

Use the available tools to:
- graph_search: Query the knowledge graph for entities and relationships
- graph_global_search: Perform global search across the entire graph
- graph_local_search: Search around specific entities
- graph_entity_info: Get detailed information about specific entities
- graph_entity_relationships: Get relationships for a specific entity

Always verify information from the graph and cite sources when possible.""",
                tools=[],
                max_iterations=10,
                llm_config=llm_config,
                temperature=0.3,  # Lower temperature for more factual responses
            )
        else:
            # Create agent from config
            agent_model = AgentModel(
                name=agent_config.name,
                role=agent_config.role,
                system_prompt=agent_config.system_prompt,
                tools=agent_config.tools,
                max_iterations=agent_config.max_iterations,
                llm_config=agent_config.llm_config,
                temperature=agent_config.temperature,
            )

        # Initialize base agent
        super().__init__(
            agent=agent_model,
            tool_executor=tool_executor,
        )

        # Initialize GraphRAG client
        self.graphrag_client = GraphRAGClient(
            output_path=graphrag_output_path,
            config_path=graphrag_config_path,
        )
        logger.info(f"Initialized GraphRAG agent with data from {graphrag_output_path}")

    async def query_graph(
        self,
        query_text: str,
        search_type: str = "global",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Query the knowledge graph.

        Args:
            query_text: Query text
            search_type: Type of search ('global', 'local', 'basic', 'drift')
            **kwargs: Additional arguments for GraphRAGQueryConfig

        Returns:
            Query results
        """
        config = GraphRAGQueryConfig(
            search_type=search_type,
            **kwargs,
        )
        result = await self.graphrag_client.query(query_text, config)
        return result

    async def get_entity_info(self, entity_name: str) -> Optional[dict[str, Any]]:
        """Get information about a specific entity.

        Args:
            entity_name: Name of the entity

        Returns:
            Entity information or None if not found
        """
        return self.graphrag_client.get_entity_info(entity_name)

    async def get_entity_relationships(self, entity_name: str) -> list[dict[str, Any]]:
        """Get relationships for a specific entity.

        Args:
            entity_name: Name of the entity

        Returns:
            List of relationships
        """
        return self.graphrag_client.get_entity_relationships(entity_name)

    async def _reasoning_step(self, state: State) -> State:
        """Execute reasoning step with graph-aware context.

        Args:
            state: Current state

        Returns:
            Updated state
        """
        # Prepare tools
        tools = self._prepare_tools()

        # Add graph-specific tools
        tools.extend(self._prepare_graph_tools())

        # Prepare messages
        messages = self._prepare_messages(state)

        # Call LLM
        response = await self.llm_client.complete(
            messages=messages,
            temperature=self.agent.get_effective_temperature(),
            tools=tools,
        )

        # Add assistant message
        from ..models import Message
        from ..models.state import ToolCall

        tool_calls_list = []
        for tc in response["tool_calls"]:
            tool_call = ToolCall(
                id=tc["id"],
                server="graphrag",
                tool=tc["tool"],
                arguments=tc["arguments"],
            )
            tool_calls_list.append(tool_call)

        assistant_message = Message(
            role="assistant",
            content=response["content"],
            tool_calls=tool_calls_list,
        )
        state = state.add_message(assistant_message)

        # Execute tool calls
        if response["tool_calls"]:
            state = await self._execute_tool_calls(state, response["tool_calls"])

        return state

    def _prepare_graph_tools(self) -> list[dict[str, Any]]:
        """Prepare graph-related tools for LLM.

        Returns:
            List of tool definitions
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "graph_search",
                    "description": "Query the knowledge graph for relevant entities and relationships",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Query text to search for",
                            },
                            "search_type": {
                                "type": "string",
                                "enum": ["global", "local", "basic", "drift"],
                                "description": "Type of search to perform",
                            },
                            "use_context_data": {
                                "type": "boolean",
                                "description": "Whether to return detailed context data",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "graph_entity_info",
                    "description": "Get detailed information about a specific entity in the knowledge graph",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_name": {
                                "type": "string",
                                "description": "Name of the entity to look up",
                            },
                        },
                        "required": ["entity_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "graph_entity_relationships",
                    "description": "Get all relationships for a specific entity",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_name": {
                                "type": "string",
                                "description": "Name of the entity",
                            },
                        },
                        "required": ["entity_name"],
                    },
                },
            },
        ]

    async def _execute_tool_calls(self, state: State, tool_calls: list[dict[str, Any]]) -> State:
        """Execute tool calls including graph tools.

        Args:
            state: Current state
            tool_calls: Tool calls to execute

        Returns:
            Updated state
        """
        from ..models import Message

        for tool_call in tool_calls:
            tool_name = tool_call["tool"]
            tool_args = tool_call["arguments"]
            call_id = tool_call["id"]

            try:
                if tool_name == "graph_search":
                    result = await self.query_graph(**tool_args)
                    tool_result = str(result)

                elif tool_name == "graph_entity_info":
                    result = await self.get_entity_info(**tool_args)
                    tool_result = str(result) if result else "Entity not found"

                elif tool_name == "graph_entity_relationships":
                    result = await self.get_entity_relationships(**tool_args)
                    tool_result = str(result)

                else:
                    # Let the parent handle other tools
                    if self.tool_executor:
                        result = await self.tool_executor.execute_one(
                            id=call_id,
                            server="graphrag",
                            tool=tool_name,
                            arguments=tool_args,
                        )
                        tool_result = result.content[0].text
                    else:
                        tool_result = "Tool executor not available"

                # Add tool result message
                tool_message = Message(
                    role="tool",
                    content=tool_result,
                )
                state = state.add_message(tool_message)

            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                error_message = Message(
                    role="tool",
                    content=f"Error: {str(e)}",
                )
                state = state.add_message(error_message)

        return state

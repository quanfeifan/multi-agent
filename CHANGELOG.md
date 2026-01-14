# Changelog

All notable changes to the Multi-Agent Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Phase 1: Project Setup
- Python project structure with src/, tests/ directories
- pyproject.toml with dependencies (pydantic, mcp, aiohttp, networkx, openai)
- Setup configuration for Python 3.10+
- Development tools configuration (pytest, black, ruff, mypy)

#### Phase 2: Foundational Components
- Configuration loader with environment variable expansion
- Pydantic schemas for validation (AgentConfig, LLMConfig, WorkflowConfig, MCPServerConfig)
- Path utilities for config directory detection
- Core data models: Task, Agent, State, Message, ToolCall, Tool, MCPServer, TraceLog, SubAgentSession, Checkpoint, Workflow
- State management with reducer pattern
- State serializer (JSON) and persistence manager
- Graph-based state machine using networkx
- Utilities: UUID generator, retry decorator, timeout decorator, structured logging

#### Phase 3: Single-Agent Execution
- MCP stdio client with subprocess management
- MCP SSE client with aiohttp
- MCP session initialization and tool discovery
- BaseAgent class with LLM client (OpenAI-compatible)
- Agent reasoning loop with max_iterations
- Tool call invocation and state updates
- Completion condition detection
- Task class with status management
- Orchestrator with FIFO queue
- Task status persistence
- Tracer with structured logging and incremental saving

#### Phase 4: Supervisor Pattern
- SubAgentSession manager with isolation guarantees
- Isolated message history per session
- Session summary generation
- SupervisorAgent class for multi-agent coordination
- Sub-agent delegation and tool-to-sub-agent routing
- Result aggregation from sub-agents
- Per-agent tool filtering and access validation

#### Phase 5: Fault Tolerance
- FallbackManager for automatic retry
- Tool timeout enforcement (default 5 min)
- Fallback tool invocation
- Retry logic with exponential backoff
- Error classification (retryable detection)
- ContextLimitError exception
- Progressive message history removal for LLM context limits

#### Phase 6: Enhanced Tracing & CLI
- Enhanced tracing with duration_ms tracking
- Sub-agent session tracking in trace logs
- Error state capture and failure point identification
- Trace log pretty-print utility
- CLI commands for task listing and inspection
- CLI commands for viewing and searching trace logs

#### Phase 7: Human-in-the-Loop
- Checkpoint save/load functionality
- Checkpoint sequence numbering
- Checkpoint-based resume
- interrupt_before node flag in state machine
- Human feedback handler and state updates
- Historical checkpoint listing
- CLI commands for checkpoint management

#### Phase 8: Workflow Patterns
- Pattern base class and composer
- ReAct pattern (Reason → Act → Observe)
- Reflection pattern (generate → critique → refine)
- Chain-of-Thought pattern
- Workflow loader from YAML config
- Workflow execution engine
- Conditional edge routing based on state
- Workflow validation (DAG cycle detection)

#### Phase 9: Parallel Execution
- Dependency analyzer for task relationships
- LLM-based produces/consumes extraction
- DAG building from task dependencies
- Topological sort using networkx
- Parallel batch generator
- Task queue with semaphore (100 concurrent limit)
- Parallel task executor
- FIFO queue for pending tasks
- Circular dependency detection

#### Phase 10: Polish & Documentation
- Performance metrics tracking (MetricsTracker)
- Data retention policy and cleanup
- Main CLI entry point with all commands
- Agent configuration validation command
- Workflow validation command
- MCP server test command
- API reference documentation
- Example configurations (agents, workflows, MCP servers)
- Contribution guidelines

## [0.1.0] - 2026-01-12

### Added
- Initial release of Multi-Agent Framework
- Full implementation of all 7 user stories
- Complete CLI interface
- Comprehensive API documentation

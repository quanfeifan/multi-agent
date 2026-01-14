"""State management for multi-agent framework."""

from .base import StateReducerBuilder, create_initial_state, create_state_reducer, reduce_state
from .machine import ConditionalEdge, NodeHandler, StateMachine
from .manager import StateManager
from .serializer import FileStateSerializer, StateSerializer

__all__ = [
    # Base
    "create_initial_state",
    "reduce_state",
    "create_state_reducer",
    "StateReducerBuilder",
    # Machine
    "StateMachine",
    "NodeHandler",
    "ConditionalEdge",
    # Manager
    "StateManager",
    # Serializer
    "StateSerializer",
    "FileStateSerializer",
]

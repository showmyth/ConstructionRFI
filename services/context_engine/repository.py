from abc import ABC, abstractmethod
from typing import Optional, Dict

from packages.shared_schemas.graph import ContextGraph


class GraphRepository(ABC):
    """Abstract base class for graph storage."""
    
    @abstractmethod
    def get_graph(self, session_id: str) -> Optional[ContextGraph]:
        pass

    @abstractmethod
    def save_graph(self, graph: ContextGraph) -> None:
        pass


class MemoryGraphRepository(GraphRepository):
    """In-memory implementation for testing and development."""
    
    def __init__(self):
        self._storage: Dict[str, ContextGraph] = {}

    def get_graph(self, session_id: str) -> Optional[ContextGraph]:
        return self._storage.get(session_id)

    def save_graph(self, graph: ContextGraph) -> None:
        # Pydantic schemas are safe to store directly
        self._storage[graph.metadata.session_id] = graph
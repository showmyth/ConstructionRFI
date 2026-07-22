from typing import Dict, Optional
from uuid import UUID, uuid4
from datetime import datetime, UTC

from packages.shared_schemas.graph import ContextGraph, GraphMetadata, GraphNode, GraphEdge, Provenance
from packages.shared_schemas.observation import Observation
from .resolver import EntityResolver

class ContextGraphEngine:
    def __init__(self):
        self._active_sessions: Dict[str, ContextGraph] = {}
        self.resolver = EntityResolver()  # Instantiate the resolver

    def create_graph(self, session_id: str) -> ContextGraph:
        if session_id in self._active_sessions:
            raise ValueError(f"Session {session_id} already exists.")
        new_graph = ContextGraph(metadata=GraphMetadata(session_id=session_id))
        self._active_sessions[session_id] = new_graph
        return new_graph

    def get_graph(self, session_id: str) -> Optional[ContextGraph]:
        return self._active_sessions.get(session_id)

    def add_observation(self, session_id: str, observation: Observation) -> ContextGraph:
        graph = self.get_graph(session_id)
        if not graph:
            raise ValueError(f"Session {session_id} not found.")

        id_mapping: Dict[str, UUID] = {}

        # --- 1. RESOLVE OR CREATE NODES ---
        for obs_node in observation.nodes:
            # Check if this entity already exists in the graph
            existing_uuid = self.resolver.find_existing_node(graph, obs_node)

            if existing_uuid:
                # MERGE: The entity exists! Accumulate knowledge on the single node.
                self.resolver.merge_node(graph.nodes[existing_uuid], obs_node, observation)
                id_mapping[obs_node.local_id] = existing_uuid
            else:
                # CREATE: It's a brand new entity.
                canonical_id = uuid4()
                id_mapping[obs_node.local_id] = canonical_id

                prov = Provenance(
                    source_asset_id=observation.source_asset_id,
                    observation_id=str(observation.observation_id),
                    confidence=obs_node.confidence,
                    timestamp=observation.timestamp
                )

                graph_node = GraphNode(
                    id=canonical_id,
                    type=obs_node.type,
                    properties=obs_node.properties,
                    provenance_history=[prov]
                )

                graph.nodes[canonical_id] = graph_node
                graph.metadata.total_nodes += 1

        # --- 2. RESOLVE OR CREATE EDGES ---
        for obs_edge in observation.edges:
            source_uuid = id_mapping.get(obs_edge.source_local_id)
            target_uuid = id_mapping.get(obs_edge.target_local_id)

            if not source_uuid or not target_uuid:
                continue 

            # Check if this exact relationship already exists between these two nodes
            existing_edge = next(
                (e for e in graph.edges 
                 if e.source == source_uuid 
                 and e.target == target_uuid 
                 and e.relationship == obs_edge.relationship), 
                None
            )

            new_prov = Provenance(
                source_asset_id=observation.source_asset_id,
                observation_id=str(observation.observation_id),
                confidence=obs_edge.confidence,
                timestamp=observation.timestamp
            )

            if existing_edge:
                # MERGE: Just append the provenance to show we observed this relationship again
                existing_edge.provenance_history.append(new_prov)
                existing_edge.updated_at = datetime.now(UTC)
            else:
                # CREATE: New spatial or logical relationship discovered
                graph_edge = GraphEdge(
                    source=source_uuid,
                    target=target_uuid,
                    relationship=obs_edge.relationship,
                    provenance_history=[new_prov]
                )
                graph.edges.append(graph_edge)
                graph.metadata.total_edges += 1

        graph.metadata.version += 1
        return graph
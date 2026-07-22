from typing import Optional
from uuid import UUID
from datetime import datetime, UTC

from packages.shared_schemas.graph import ContextGraph, GraphNode, Provenance
from packages.shared_schemas.observation import Observation, ObservationNode
from packages.shared_schemas.ontology import NodeType

class EntityResolver:
    
    def find_existing_node(self, graph: ContextGraph, obs_node: ObservationNode) -> Optional[UUID]:
        """
        Determines if an observation node already exists in the graph.
        Returns the UUID of the canonical node if found, otherwise None.
        """
        for canonical_id, canonical_node in graph.nodes.items():
            # Rule 0: Must be the same entity type
            if canonical_node.type != obs_node.type:
                continue
        
            # Rule 1: Equipment Matching
            # If we see an excavator and we already have an excavator in this session, 
            # assume it is the same one (for this prototype).
            if canonical_node.type == NodeType.EQUIPMENT:
                canonical_class = getattr(canonical_node.properties, "equipment_class", None)
                obs_class = getattr(obs_node.properties, "equipment_class", None)
                if canonical_class and canonical_class == obs_class:
                    return canonical_id
                    
            # Rule 2: Worker Matching
            # Workers are harder without facial recognition or tracking IDs.
            # If they have a specific role_title (e.g., from an OCR'd permit), we can match on that.
            if canonical_node.type == NodeType.WORKER:
                canonical_role = getattr(canonical_node.properties, "role_title", None)
                obs_role = getattr(obs_node.properties, "role_title", None)
                if canonical_role and canonical_role == obs_role:
                    return canonical_id

            # Future Rules: Bounding Box Intersection (IoU), Distance checks, etc.
            
        return None

    def merge_node(self, graph_node: GraphNode, obs_node: ObservationNode, observation: Observation) -> None:
        """
        Merges new observation data into an existing canonical node.
        """
        # 1. Append to the provenance history (accumulate trust/evidence)
        new_prov = Provenance(
            source_asset_id=observation.source_asset_id,
            observation_id=str(observation.observation_id),
            confidence=obs_node.confidence,
            timestamp=observation.timestamp
        )
        graph_node.provenance_history.append(new_prov)
        
        # 2. Merge Properties (Latest non-null values win)
        # We extract only the fields that were actually set in the observation
        obs_props_dict = obs_node.properties.model_dump(exclude_unset=True, exclude_none=True)
        
        # Pydantic v2 model_copy allows updating specific fields safely
        updated_properties = graph_node.properties.model_copy(update=obs_props_dict)
        graph_node.properties = updated_properties
        
        # 3. Update modification timestamp
        graph_node.updated_at = datetime.now(UTC)
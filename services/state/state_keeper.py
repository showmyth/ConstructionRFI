from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol

from packages.shared_schemas.enums import StateStatus
from packages.shared_schemas.state_schema import StateSchema


# define an Object which resembles a typical Asset object, but with only the fields that are mandatorily required for initialization
class AssetLike(Protocol):
    id: str
    original_filename: str
    content_type: str
    stored_path: str


class StateKeeper:
    """State Container for Asset Lifecycle Tracking."""
    def __init__(self) -> None:
        self._states: dict[str, StateSchema] = {}

    def init_state(self, asset: AssetLike, correlation_id: str | None = None) -> StateSchema:
        """Create a new state record for an asset if one does not exist.
        Args:
            asset: Corresponding asset obtained from the Database
            correlation_id: an unique identifier tracing a specific transaction/set of events
        Returns:
            StateSchema: Returns a dict of shape:
                {
                    asset_id,
                    filename,
                    content_type,
                    final_path,
                    correlation_id,
                    status
                }
        """
        if asset.id in self._states:
            return self._states[asset.id]

        state = StateSchema(
            asset_id=asset.id,
            filename=asset.original_filename,
            content_type=asset.content_type,
            final_path=asset.stored_path,
            correlation_id=correlation_id,
            status=StateStatus.UPLOADED,
        )
        self._states[asset.id] = state
        return state

    def get_state(self, asset_id: str) -> StateSchema | None:
        """Retrieves the current state for the input asset.
        Args:
        
        """
        return self._states.get(asset_id)

    def update_status(self, asset_id: str, status: StateStatus) -> StateSchema:
        """Update the lifecycle state of an asset."""
        state = self._ensure_state(asset_id)
        state.status = status
        return state

    def add_finding(self, asset_id: str, source: str, payload: Any) -> StateSchema:
        """Attach a finding to the asset state under a named source."""
        state = self._ensure_state(asset_id)
        state.findings[source] = deepcopy(payload)
        return state

    def add_error(self, asset_id: str, error: str) -> StateSchema:
        """Append an error message to the asset state."""
        state = self._ensure_state(asset_id)
        if error not in state.errors:
            state.errors.append(error)
        return state

    def _ensure_state(self, asset_id: str) -> StateSchema:
        if asset_id not in self._states:
            raise KeyError(f"No state initialized for asset {asset_id}")
        return self._states[asset_id]

    def snapshot(self, asset_id: str) -> dict[str, Any]:
        """Return a plain dictionary snapshot of the state."""
        state = self.get_state(asset_id)
        if state is None:
            return {}
        return state.model_dump(mode="json")

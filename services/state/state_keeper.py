from __future__ import annotations

from copy import deepcopy
from typing import Any

from packages.shared_schemas.enums import StateStatus
from packages.shared_schemas.state_schema import StateSchema


class StateKeeper:
    """Simple in-memory state container for asset lifecycle tracking."""

    def __init__(self) -> None:
        self._states: dict[str, StateSchema] = {}

    def init_state(
        self,
        asset_id: str,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        final_path: str | None = None,
        correlation_id: str | None = None,
        status: StateStatus = StateStatus.UPLOADED,
    ) -> StateSchema:
        """Create a new state record for an asset if one does not exist."""
        if asset_id in self._states:
            state = self._states[asset_id]

            if filename is not None and state.filename is None:
                state.filename = filename
            if content_type is not None and state.content_type is None:
                state.content_type = content_type
            if final_path is not None and state.final_path is None:
                state.final_path = final_path
            if correlation_id is not None and state.correlation_id is None:
                state.correlation_id = correlation_id

            return state

        state = StateSchema(
            asset_id=asset_id,
            filename=filename,
            content_type=content_type,
            final_path=final_path,
            correlation_id=correlation_id,
            status=status,
        )
        self._states[asset_id] = state
        return state

    def get_state(self, asset_id: str) -> StateSchema | None:
        """Retrieve the current state for an asset."""
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
            return self.init_state(asset_id)
        return self._states[asset_id]

    def snapshot(self, asset_id: str) -> dict[str, Any]:
        """Return a plain dictionary snapshot of the state."""
        state = self.get_state(asset_id)
        if state is None:
            return {}
        return state.model_dump()
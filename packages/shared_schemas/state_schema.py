from pydantic import BaseModel, Field # type: ignore
from datetime import datetime, timezone
from .enums import StateStatus
from typing import Any

class StateSchema(BaseModel):
    asset_id: str

    filename: str | None = None

    content_type: str | None = None

    final_path: str | None = None

    created_at : datetime = Field(default_factory = lambda: datetime.now(timezone.utc))

    status: StateStatus = StateStatus.UPLOADED

    correlation_id: str | None = None

    findings: dict[str, Any] = Field(default_factory = dict)

    errors: list[str] = Field(default_factory = list)






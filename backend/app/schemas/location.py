from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LocationSuggestion(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    codes: list[str] = Field(default_factory=list)
    kind: Literal["location", "airport_code"]

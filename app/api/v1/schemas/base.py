"""Base schemas with camelCase serialization and dual-mode input handling."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class MobileApiSchema(BaseModel):
    """Base schema for Mobile API request and response models.

    - Accepts both snake_case and camelCase during validation (`populate_by_name=True`).
    - Serializes to camelCase by default to match Flutter client models (`by_alias=True`).
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        arbitrary_types_allowed=True,
    )


class StrictSnakeSchema(BaseModel):
    """Schema for endpoints that strictly expect snake_case (e.g. edge functions / raw JSON)."""

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )


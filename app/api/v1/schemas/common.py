from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PageMeta(BaseModel):
    limit: int
    offset: int


class Page(APIModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class ErrorBody(BaseModel):
    message: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    service: str = "zemen-backend"
    environment: str

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class PaginationMeta(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    next_cursor: str | None = None
    has_more: bool = False
    limit: int


class ApiMeta(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    request_id: str | None = None
    pagination: PaginationMeta | None = None
    warnings: list[str] = Field(default_factory=list)


class ApiEnvelope[TData](BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: TData
    meta: ApiMeta = Field(default_factory=ApiMeta)

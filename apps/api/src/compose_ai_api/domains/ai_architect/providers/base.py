from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0


@dataclass(frozen=True)
class StructuredProviderRequest:
    model: str
    system_prompt: str
    user_prompt: str
    output_schema: dict[str, Any]
    output_schema_name: str
    max_output_tokens: int


@dataclass(frozen=True)
class ChatProviderRequest:
    model: str
    system_prompt: str
    user_prompt: str
    max_output_tokens: int


@dataclass(frozen=True)
class StructuredProviderResponse:
    payload: dict[str, Any]
    usage: ProviderUsage
    provider_request_id: str | None = None


@dataclass(frozen=True)
class ProviderStreamEvent:
    event_type: str
    delta: str = ""
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    provider_request_id: str | None = None


@dataclass(frozen=True)
class ImageProviderRequest:
    model: str
    prompt: str
    negative_prompt: str | None = None
    width: int = 1024
    height: int = 1024
    seed: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImageProviderResult:
    content: bytes
    mime_type: str
    width: int
    height: int
    usage: ProviderUsage
    provider_request_id: str | None = None
    provider_asset_metadata: dict[str, Any] = field(default_factory=dict)
    safety_metadata: dict[str, Any] = field(default_factory=dict)


class AIProviderError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code


class AIProvider(Protocol):
    name: str

    async def generate_structured(
        self, request: StructuredProviderRequest
    ) -> StructuredProviderResponse: ...

    async def generate_image(self, request: ImageProviderRequest) -> ImageProviderResult: ...

    def stream_chat(self, request: ChatProviderRequest) -> AsyncIterator[ProviderStreamEvent]: ...

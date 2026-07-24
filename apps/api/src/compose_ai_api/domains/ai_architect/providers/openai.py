from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

from compose_ai_api.domains.ai_architect.providers.base import (
    AIProvider,
    AIProviderError,
    ChatProviderRequest,
    ImageProviderRequest,
    ImageProviderResult,
    ProviderStreamEvent,
    ProviderUsage,
    StructuredProviderRequest,
    StructuredProviderResponse,
)


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        organization: str | None,
        project: str | None,
        timeout_seconds: float,
    ) -> None:
        self.client = AsyncOpenAI(
            api_key=api_key,
            organization=organization,
            project=project,
            timeout=timeout_seconds,
            max_retries=0,
        )

    async def generate_structured(
        self, request: StructuredProviderRequest
    ) -> StructuredProviderResponse:
        try:
            response = await self.client.responses.create(
                model=request.model,
                instructions=request.system_prompt,
                input=request.user_prompt,
                max_output_tokens=request.max_output_tokens,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": request.output_schema_name,
                        "schema": request.output_schema,
                        "strict": True,
                    }
                },
            )
            payload = json.loads(response.output_text)
            return StructuredProviderResponse(
                payload=payload,
                usage=_response_usage(response),
                provider_request_id=response.id,
            )
        except (APIConnectionError, APIStatusError, APITimeoutError, RateLimitError) as error:
            raise _provider_error(error) from error
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise AIProviderError(
                "AI_SCHEMA_INVALID",
                "The provider returned an invalid structured response.",
                retryable=False,
            ) from error

    async def stream_chat(self, request: ChatProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        try:
            stream = await self.client.responses.create(
                model=request.model,
                instructions=request.system_prompt,
                input=request.user_prompt,
                max_output_tokens=request.max_output_tokens,
                stream=True,
            )
            async for event in stream:
                event_type = getattr(event, "type", "")
                if event_type == "response.output_text.delta":
                    yield ProviderStreamEvent(event_type="delta", delta=event.delta)
                elif event_type == "response.completed":
                    response = event.response
                    yield ProviderStreamEvent(
                        event_type="completed",
                        usage=_response_usage(response),
                        provider_request_id=response.id,
                    )
                elif event_type == "response.failed":
                    raise AIProviderError(
                        "AI_PROVIDER_UNAVAILABLE",
                        "The provider failed to complete the response.",
                        retryable=True,
                    )
        except (APIConnectionError, APIStatusError, APITimeoutError, RateLimitError) as error:
            raise _provider_error(error) from error

    async def generate_image(self, request: ImageProviderRequest) -> ImageProviderResult:
        raise AIProviderError(
            "AI_PROVIDER_CAPABILITY_UNSUPPORTED",
            "OpenAI image generation is not configured for this Compose AI deployment.",
            retryable=False,
        )


def _response_usage(response: Any) -> ProviderUsage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return ProviderUsage()
    input_details = getattr(usage, "input_tokens_details", None)
    return ProviderUsage(
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        cached_tokens=int(getattr(input_details, "cached_tokens", 0) or 0),
    )


def _provider_error(error: Exception) -> AIProviderError:
    if isinstance(error, RateLimitError):
        return AIProviderError(
            "AI_PROVIDER_RATE_LIMITED",
            "The AI provider is temporarily rate limited.",
            retryable=True,
            status_code=429,
        )
    if isinstance(error, APITimeoutError):
        return AIProviderError(
            "AI_RUN_TIMEOUT",
            "The AI provider request timed out.",
            retryable=True,
            status_code=504,
        )
    status_code = getattr(error, "status_code", None)
    retryable = status_code is None or status_code == 429 or status_code >= 500
    return AIProviderError(
        "AI_PROVIDER_UNAVAILABLE",
        "The AI provider is unavailable.",
        retryable=retryable,
        status_code=status_code,
    )

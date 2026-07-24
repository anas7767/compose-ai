from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.genai import types

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


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, *, api_key: str, timeout_seconds: float) -> None:
        self.client = genai.Client(api_key=api_key)
        self.timeout_seconds = timeout_seconds

    async def generate_structured(
        self, request: StructuredProviderRequest
    ) -> StructuredProviderResponse:
        try:
            response = await self._generate_json(request, include_response_schema=True)
        except TimeoutError as error:
            raise AIProviderError(
                "AI_RUN_TIMEOUT",
                "The AI provider request timed out.",
                retryable=True,
                status_code=504,
            ) from error
        except Exception as error:
            if not _should_retry_without_schema(error):
                raise _provider_error(error) from error
            try:
                response = await self._generate_json(request, include_response_schema=False)
            except TimeoutError as fallback_error:
                raise AIProviderError(
                    "AI_RUN_TIMEOUT",
                    "The AI provider request timed out.",
                    retryable=True,
                    status_code=504,
                ) from fallback_error
            except Exception as fallback_error:
                raise _provider_error(fallback_error) from fallback_error

        try:
            payload = _structured_payload(response)
            return StructuredProviderResponse(
                payload=payload,
                usage=_response_usage(response),
                provider_request_id=_provider_request_id(response),
            )
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise AIProviderError(
                "AI_SCHEMA_INVALID",
                "The provider returned an invalid structured response.",
                retryable=False,
            ) from error

    async def _generate_json(
        self,
        request: StructuredProviderRequest,
        *,
        include_response_schema: bool,
    ) -> Any:
        config_values: dict[str, Any] = {
            "systemInstruction": request.system_prompt,
            "responseMimeType": "application/json",
            "maxOutputTokens": request.max_output_tokens,
            "thinkingConfig": types.ThinkingConfig(thinkingBudget=0),
            "temperature": 0.2,
        }
        if include_response_schema:
            config_values["responseSchema"] = _gemini_response_schema(request.output_schema)
        contents = request.user_prompt
        if not include_response_schema:
            contents = (
                f"{request.user_prompt}\n\n"
                "OUTPUT JSON SCHEMA (authoritative, return one JSON object matching this shape):\n"
                f"{json.dumps(request.output_schema, sort_keys=True, separators=(',', ':'))}"
            )

        async with asyncio.timeout(self.timeout_seconds):
            return await self.client.aio.models.generate_content(
                model=request.model,
                contents=contents,
                config=types.GenerateContentConfig(**config_values),
            )

    async def stream_chat(self, request: ChatProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        usage = ProviderUsage()
        request_id: str | None = None
        try:
            async with asyncio.timeout(self.timeout_seconds):
                stream = await self.client.aio.models.generate_content_stream(
                    model=request.model,
                    contents=request.user_prompt,
                    config=types.GenerateContentConfig(
                        systemInstruction=request.system_prompt,
                        maxOutputTokens=request.max_output_tokens,
                        thinkingConfig=types.ThinkingConfig(thinkingBudget=0),
                        temperature=0.4,
                    ),
                )
                async for chunk in stream:
                    request_id = _provider_request_id(chunk) or request_id
                    usage = _response_usage(chunk) or usage
                    if chunk.text:
                        yield ProviderStreamEvent(event_type="delta", delta=chunk.text)
        except TimeoutError as error:
            raise AIProviderError(
                "AI_RUN_TIMEOUT",
                "The AI provider request timed out.",
                retryable=True,
                status_code=504,
            ) from error
        except Exception as error:
            raise _provider_error(error) from error

        yield ProviderStreamEvent(
            event_type="completed",
            usage=usage,
            provider_request_id=request_id,
        )

    async def generate_image(self, request: ImageProviderRequest) -> ImageProviderResult:
        model = _image_model_name(request.model)
        config_values: dict[str, Any] = {
            "temperature": 0.7,
            "responseModalities": ["IMAGE"],
        }
        if request.seed is not None:
            config_values["seed"] = request.seed
        prompt = request.prompt
        if request.negative_prompt:
            prompt = f"{prompt}\n\nAvoid: {request.negative_prompt}"
        try:
            async with asyncio.timeout(self.timeout_seconds):
                response = await self.client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_values),
                )
        except TimeoutError as error:
            raise AIProviderError(
                "AI_RUN_TIMEOUT",
                "The AI provider request timed out.",
                retryable=True,
                status_code=504,
            ) from error
        except Exception as error:
            raise _provider_error(error) from error

        content, mime_type = _image_content(response)
        return ImageProviderResult(
            content=content,
            mime_type=mime_type,
            width=request.width,
            height=request.height,
            usage=_response_usage(response),
            provider_request_id=_provider_request_id(response),
            provider_asset_metadata={"model": model},
            safety_metadata=_safety_metadata(response),
        )


async def check_gemini_text_health(
    *,
    api_key: str,
    model: str,
    timeout_seconds: float,
) -> tuple[bool, ProviderUsage]:
    provider = GeminiProvider(api_key=api_key, timeout_seconds=timeout_seconds)
    response = await provider.generate_structured(
        StructuredProviderRequest(
            model=model,
            system_prompt="Return only valid JSON that matches the requested schema.",
            user_prompt='Return {"ok": true}.',
            output_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            },
            output_schema_name="compose_gemini_health",
            max_output_tokens=256,
        )
    )
    return bool(response.payload.get("ok")), response.usage


async def check_gemini_image_model_access(
    *,
    api_key: str,
    model: str,
    timeout_seconds: float,
) -> bool:
    client = genai.Client(api_key=api_key)
    try:
        async with asyncio.timeout(timeout_seconds):
            await client.aio.models.get(model=_image_model_name(model))
    except TimeoutError as error:
        raise AIProviderError(
            "AI_RUN_TIMEOUT",
            "The AI provider request timed out.",
            retryable=True,
            status_code=504,
        ) from error
    except Exception as error:
        raise _provider_error(error) from error
    return True


def _structured_payload(response: Any) -> dict[str, Any]:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, dict):
        return parsed

    text = getattr(response, "text", None)
    if not text:
        raise ValueError("Gemini response did not include structured text.")
    payload = json.loads(_json_text(text))
    if not isinstance(payload, dict):
        raise TypeError("Gemini structured response must be a JSON object.")
    return payload


def _json_text(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _gemini_response_schema(schema: dict[str, Any]) -> dict[str, Any]:
    definitions = schema.get("$defs", {})

    def convert(value: Any, *, in_properties: bool = False) -> Any:
        if isinstance(value, list):
            return [convert(item) for item in value]
        if not isinstance(value, dict):
            return value

        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            definition_name = reference.rsplit("/", 1)[-1]
            definition = definitions.get(definition_name, {})
            merged = {**definition, **{key: item for key, item in value.items() if key != "$ref"}}
            return convert(merged, in_properties=in_properties)

        if "const" in value:
            return {"enum": [value["const"]]}

        if "anyOf" in value:
            variants = [convert(item) for item in value["anyOf"]]
            non_null_variants = [
                item
                for item in variants
                if not (isinstance(item, dict) and item.get("type") == "null")
            ]
            if len(non_null_variants) == 1:
                converted = dict(non_null_variants[0])
                converted["nullable"] = len(non_null_variants) != len(variants)
                return converted
            return {"anyOf": non_null_variants}

        unsupported = {
            "$defs",
            "$schema",
            "additionalProperties",
            "default",
            "examples",
            "exclusiveMaximum",
            "exclusiveMinimum",
            "pattern",
        }
        if not in_properties:
            unsupported.add("title")

        converted: dict[str, Any] = {}
        for key, item in value.items():
            if key in unsupported or item is None:
                continue
            if key == "properties" and isinstance(item, dict):
                converted[key] = {
                    property_name: convert(property_schema)
                    for property_name, property_schema in item.items()
                }
            else:
                converted[key] = convert(item, in_properties=in_properties)
        if converted.get("type") == "integer":
            converted["type"] = "number"
        return converted

    result = convert(schema)
    return result if isinstance(result, dict) else {"type": "object"}


def _response_usage(response: Any) -> ProviderUsage:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return ProviderUsage()
    return ProviderUsage(
        input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
        output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
        cached_tokens=int(getattr(usage, "cached_content_token_count", 0) or 0),
    )


def _provider_request_id(response: Any) -> str | None:
    value = getattr(response, "response_id", None) or getattr(response, "id", None)
    return str(value) if value else None


def _image_content(response: Any) -> tuple[bytes, str]:
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline_data = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
            if inline_data is None:
                continue
            data = getattr(inline_data, "data", None)
            mime_type = getattr(inline_data, "mime_type", None) or getattr(
                inline_data, "mimeType", None
            )
            if isinstance(data, str):
                data = base64.b64decode(data)
            if isinstance(data, bytes) and isinstance(mime_type, str):
                return data, mime_type
    raise AIProviderError(
        "AI_PROVIDER_RESPONSE_INVALID",
        "The provider did not return a usable generated image.",
        retryable=False,
    )


def _safety_metadata(response: Any) -> dict[str, Any]:
    candidates = getattr(response, "candidates", None) or []
    ratings: list[dict[str, Any]] = []
    for candidate in candidates:
        for rating in getattr(candidate, "safety_ratings", None) or []:
            ratings.append(
                {
                    "category": str(getattr(rating, "category", "")),
                    "probability": str(getattr(rating, "probability", "")),
                }
            )
    return {"safetyRatings": ratings}


def _provider_error(error: Exception) -> AIProviderError:
    status_code = _status_code(error)
    error_name = error.__class__.__name__.lower()
    message = str(error).lower()

    if _is_network_error(error_name, message):
        return AIProviderError(
            "AI_PROVIDER_NETWORK_UNREACHABLE",
            "The AI provider network endpoint is unreachable.",
            retryable=True,
            status_code=503,
        )
    if status_code == 429 or "resourceexhausted" in error_name or "quota" in message:
        return AIProviderError(
            "AI_PROVIDER_RATE_LIMITED",
            "The AI provider is temporarily rate limited.",
            retryable=True,
            status_code=429,
        )
    if status_code in {401, 403} or "permission" in message or "unauthorized" in message:
        return AIProviderError(
            "AI_PROVIDER_AUTH_FAILED",
            "Gemini provider authentication failed.",
            retryable=False,
            status_code=status_code,
        )
    if status_code is not None and 400 <= status_code < 500:
        return AIProviderError(
            "AI_PROVIDER_REQUEST_INVALID",
            "The AI provider rejected the request.",
            retryable=False,
            status_code=status_code,
        )

    return AIProviderError(
        "AI_PROVIDER_UNAVAILABLE",
        "The AI provider is unavailable.",
        retryable=True,
        status_code=status_code,
    )


def _image_model_name(model: str) -> str:
    if model.startswith("models/") or model.startswith("publishers/"):
        return model
    return f"models/{model}"


def _should_retry_without_schema(error: Exception) -> bool:
    if _status_code(error) == 400:
        return True
    message = str(error)
    return "response_schema" in message or "responseSchema" in message


def _is_network_error(error_name: str, message: str) -> bool:
    network_markers = (
        "connecterror",
        "connecttimeout",
        "networkerror",
        "all connection attempts failed",
        "temporary failure in name resolution",
        "name or service not known",
        "getaddrinfo failed",
        "nodename nor servname provided",
    )
    return any(marker in error_name or marker in message for marker in network_markers)


def _status_code(error: Exception) -> int | None:
    for attribute in ("status_code", "code"):
        value = getattr(error, attribute, None)
        if isinstance(value, int):
            return value
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    return int(value) if isinstance(value, int) else None

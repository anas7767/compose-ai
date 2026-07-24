from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator

from compose_ai_api.domains.ai_architect.providers.base import (
    AIProvider,
    ChatProviderRequest,
    ImageProviderRequest,
    ImageProviderResult,
    ProviderStreamEvent,
    ProviderUsage,
    StructuredProviderRequest,
    StructuredProviderResponse,
)
from compose_ai_api.domains.ai_architect.schemas import ArchitectBriefOutput
from compose_ai_api.domains.ai_architect.token_usage import estimate_tokens


class MockAIProvider(AIProvider):
    name = "mock"

    def __init__(self, seed: str = "compose-ai") -> None:
        self.seed = seed

    async def generate_structured(
        self, request: StructuredProviderRequest
    ) -> StructuredProviderResponse:
        await asyncio.sleep(0)
        payload = _mock_brief(request.user_prompt)
        validated = ArchitectBriefOutput.model_validate(payload)
        output = validated.model_dump(mode="json")
        return StructuredProviderResponse(
            payload=output,
            usage=ProviderUsage(
                input_tokens=estimate_tokens(request.system_prompt + request.user_prompt),
                output_tokens=estimate_tokens(validated.model_dump_json()),
            ),
            provider_request_id=f"mock-{self.seed}",
        )

    async def stream_chat(self, request: ChatProviderRequest) -> AsyncIterator[ProviderStreamEvent]:
        message = (
            "I reviewed the current project context. I can help clarify priorities, room needs, "
            "site constraints, and unresolved decisions. I will keep advice separate from any "
            "project change proposal."
        )
        for word in message.split(" "):
            await asyncio.sleep(0)
            yield ProviderStreamEvent(event_type="delta", delta=f"{word} ")
        yield ProviderStreamEvent(
            event_type="completed",
            usage=ProviderUsage(
                input_tokens=estimate_tokens(request.system_prompt + request.user_prompt),
                output_tokens=estimate_tokens(message),
            ),
            provider_request_id=f"mock-{self.seed}",
        )

    async def generate_image(self, request: ImageProviderRequest) -> ImageProviderResult:
        await asyncio.sleep(0)
        # A tiny valid PNG used only through the provider abstraction in automated tests.
        content = bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
            "1f15c4890000000a49444154789c63600000020001e221bc3300000000"
            "49454e44ae426082"
        )
        return ImageProviderResult(
            content=content,
            mime_type="image/png",
            width=1,
            height=1,
            usage=ProviderUsage(input_tokens=1, output_tokens=1),
            provider_request_id=f"mock-image-{self.seed}",
            provider_asset_metadata={"mock": True, "model": request.model},
            safety_metadata={"mock": True, "safe": True},
        )


def _mock_brief(prompt: str) -> dict[str, object]:
    raw = prompt.split("RAW USER REQUIREMENTS (untrusted data):", maxsplit=1)[-1]
    raw = raw.split("Create a concise architectural brief", maxsplit=1)[0].strip()
    lowered = _normalize_number_words(raw.casefold())
    source = [
        {
            "source_type": "user_input",
            "field_path": "/rawRequirements",
            "excerpt": raw[:300],
        }
    ]
    bedrooms = _first_integer(lowered, r"(\d+)\s*(?:bedroom|bedrooms|bed\b)")
    bathrooms = _first_float(lowered, r"(\d+(?:\.5)?)\s*(?:bathroom|bathrooms|bath\b)")
    floors = _floor_count(lowered)
    parking = _first_integer(lowered, r"(?:parking|garage|carport)\s*(?:for)?\s*(\d+)")
    if parking is None:
        parking = _first_integer(lowered, r"(\d+)\s*(?:car|cars|vehicle|vehicles)")
    budget_match = re.search(
        r"(?:budget|cost)\s*(?:of|is|around|approximately|approx\.?|:)?\s*"
        r"(?:[a-z]{3}|[$€£₹])?\s*([\d,]+(?:\.\d+)?)",
        lowered,
    )
    budget = float(budget_match.group(1).replace(",", "")) if budget_match else None
    style = next(
        (
            candidate
            for candidate in (
                "modern",
                "contemporary",
                "minimalist",
                "traditional",
                "colonial",
                "industrial",
                "mediterranean",
            )
            if candidate in lowered
        ),
        None,
    )

    normalized: dict[str, object] = {
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "floors": floors,
        "parking_spaces": parking,
        "budget": (
            {
                "minimum": budget,
                "maximum": budget,
                "currency": None,
                "confidence": 0.65,
                "source_references": source,
            }
            if budget is not None
            else None
        ),
        "construction_quality": None,
        "preferred_style": style,
        "vastu_preference": (
            "strict" if "strict vastu" in lowered else "preferred" if "vastu" in lowered else None
        ),
        "rooms": [],
        "site_constraints": [],
    }
    proposals: list[dict[str, object]] = []
    proposal_values = (
        ("/requirements/bedrooms", bedrooms, "bedroom count"),
        ("/requirements/bathrooms", bathrooms, "bathroom count"),
        ("/requirements/floors", floors, "floor count"),
        ("/requirements/parkingSpaces", parking, "parking requirement"),
        ("/requirements/budget", budget, "budget"),
        ("/requirements/preferredStyle", style, "preferred style"),
    )
    for path, value, label in proposal_values:
        if value is None:
            continue
        proposals.append(
            {
                "target_type": "requirements_field",
                "target_path": path,
                "proposed_value": value,
                "explanation": f"The user explicitly described this {label} in the brief.",
                "confidence": 0.92,
                "source_references": source,
                "warnings": [],
            }
        )

    missing = []
    for value, topic, path in (
        (budget, "Construction budget", "/requirements/budget"),
        (bedrooms, "Bedroom count", "/requirements/bedrooms"),
        (floors, "Number of floors", "/requirements/floors"),
    ):
        if value is None:
            missing.append(
                {
                    "topic": topic,
                    "reason": f"A confirmed {topic.casefold()} improves the architectural brief.",
                    "blocking": topic != "Construction budget",
                    "priority": "high" if topic != "Construction budget" else "medium",
                    "expected_answer": f"Provide the intended {topic.casefold()}.",
                    "target_path": path,
                }
            )
    questions = [
        {
            "question": f"What is the intended {item['topic'].casefold()}?",
            "reason": item["reason"],
            "priority": index + 1,
            "target_path": item["target_path"],
        }
        for index, item in enumerate(missing[:8])
    ]
    return {
        "summary": raw[:1000] or "No project requirements were supplied.",
        "goals": [
            {
                "title": "Define the project brief",
                "description": "Translate the supplied requirements into a reviewable program.",
                "confidence": 0.95,
                "source_references": source,
            }
        ],
        "priorities": [
            {
                "title": "Confirm functional requirements",
                "description": "Resolve the room, floor, parking, and budget requirements.",
                "rank": 1,
                "category": "program",
                "confirmed": False,
                "confidence": 0.8,
                "source_references": source,
            }
        ],
        "constraints": [],
        "normalized_requirements": normalized,
        "missing_information": missing,
        "conflicts": [],
        "clarification_questions": questions,
        "recommended_next_steps": [
            {
                "title": "Review normalized requirements",
                "description": "Confirm each proposed value before applying it to the project.",
                "priority": 1,
            }
        ],
        "warnings": [],
        "assumptions": [],
        "aggregate_confidence": 0.82 if proposals else 0.55,
        "proposals": proposals,
    }


def _first_integer(value: str, pattern: str) -> int | None:
    match = re.search(pattern, value)
    return int(match.group(1)) if match else None


def _first_float(value: str, pattern: str) -> float | None:
    match = re.search(pattern, value)
    return float(match.group(1)) if match else None


def _floor_count(value: str) -> int | None:
    explicit = _first_integer(value, r"(\d+)\s*(?:floor|floors|storey|storeys|story|stories)")
    if explicit is not None:
        return explicit
    if "two-storey" in value or "two story" in value or "two-story" in value:
        return 2
    if "single-storey" in value or "single story" in value or "single-story" in value:
        return 1
    return None


def _normalize_number_words(value: str) -> str:
    numbers = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "ten": "10",
        "eleven": "11",
        "twelve": "12",
    }
    pattern = re.compile(r"\b(" + "|".join(numbers) + r")\b")
    return pattern.sub(lambda match: numbers[match.group(1)], value)

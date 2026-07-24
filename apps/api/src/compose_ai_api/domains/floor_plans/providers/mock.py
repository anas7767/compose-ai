from __future__ import annotations

import asyncio
import math
import re
from typing import Any

from compose_ai_api.domains.ai_architect.providers.base import ProviderUsage
from compose_ai_api.domains.ai_architect.token_usage import estimate_tokens
from compose_ai_api.domains.floor_plans.providers.base import (
    FloorPlanProgramRequest,
    FloorPlanProgramResponse,
)
from compose_ai_api.domains.floor_plans.schemas import (
    FloorPlanDecision,
    FloorPlanProgramOutput,
    FloorPlanProgramRoom,
)


class MockFloorPlanProgramProvider:
    name = "mock"

    async def generate_program(self, request: FloorPlanProgramRequest) -> FloorPlanProgramResponse:
        await asyncio.sleep(0)
        program = build_deterministic_program(request.context)
        return FloorPlanProgramResponse(
            program=program,
            usage=ProviderUsage(
                input_tokens=estimate_tokens(str(request.context)),
                output_tokens=estimate_tokens(program.model_dump_json()),
            ),
            provider_request_id=f"floor-plan-mock-{request.deterministic_seed}",
        )


def build_deterministic_program(context: dict[str, Any]) -> FloorPlanProgramOutput:
    requirements = context.get("requirements", {})
    plot = context.get("plotIntelligence", {})
    floors = max(1, int(requirements.get("floors") or 1))
    bedrooms = max(0, int(requirements.get("bedrooms") or 0))
    bathrooms = max(0, math.ceil(float(requirements.get("bathrooms") or 0)))
    rooms: list[FloorPlanProgramRoom] = [
        _room("living", "Living Room", "living_room", 0, 20, 3.0, "public", ["dining", "entrance"]),
        _room("kitchen", "Kitchen", "kitchen", 0, 12, 2.4, "service", ["dining", "utility"]),
        _room("dining", "Dining", "dining", 0, 12, 2.4, "public", ["living", "kitchen"]),
    ]
    for floor_index in range(1, floors):
        rooms.append(
            _room(
                f"family-lounge-{floor_index + 1}",
                f"Family Lounge {floor_index + 1}",
                "family_lounge",
                floor_index,
                12,
                2.4,
                "public",
                [],
            )
        )
    for index in range(bedrooms):
        floor_index = 0 if floors == 1 else min(floors - 1, 1 + (index % (floors - 1)))
        rooms.append(
            _room(
                f"bedroom-{index + 1}",
                "Primary Bedroom" if index == 0 else f"Bedroom {index + 1}",
                "bedroom",
                floor_index,
                15 if index == 0 else 12,
                2.7,
                "private",
                [f"bathroom-{min(index + 1, max(1, bathrooms))}"],
            )
        )
    for index in range(bathrooms):
        floor_index = min(floors - 1, index % floors)
        rooms.append(
            _room(
                f"bathroom-{index + 1}",
                f"Bathroom {index + 1}",
                "bathroom",
                floor_index,
                5,
                1.5,
                "service",
                [f"bedroom-{min(index + 1, max(1, bedrooms))}"],
                requires_exterior=False,
            )
        )
    custom_index = 0
    existing_names = {room.name.casefold() for room in rooms}
    for custom in context.get("roomRequirements", []):
        quantity = max(1, int(custom.get("quantity") or 1))
        for quantity_index in range(quantity):
            name = str(custom.get("name") or "Custom Room")
            display_name = name if quantity == 1 else f"{name} {quantity_index + 1}"
            if display_name.casefold() in existing_names:
                continue
            custom_index += 1
            preferred_floor = custom.get("preferredFloor")
            floor_index = (
                min(floors - 1, max(0, int(preferred_floor) - 1))
                if preferred_floor is not None
                else custom_index % floors
            )
            area = float(custom.get("minimumArea") or 10)
            rooms.append(
                _room(
                    f"custom-{custom_index}-{_slug(name)}",
                    display_name,
                    str(custom.get("roomType") or "custom_room"),
                    floor_index,
                    max(4, area),
                    1.8,
                    "private",
                    [],
                )
            )
            existing_names.add(display_name.casefold())

    road_direction = str(plot.get("roadDirection") or "north")
    entrance_side = _cardinal_side(road_direction)
    return FloorPlanProgramOutput(
        floors=floors,
        rooms=rooms,
        circulation_width_m=1.2,
        parking_spaces=max(0, int(requirements.get("parkingSpaces") or 0)),
        entrance_side=entrance_side,
        major_decisions=[
            FloorPlanDecision(
                code="PUBLIC_ZONE_AT_ENTRY",
                title="Public spaces near the entrance",
                explanation=(
                    "Living and dining spaces are kept near the approach to reduce visitor travel "
                    "through private rooms."
                ),
                confidence=0.88,
            ),
            FloorPlanDecision(
                code="SERVICE_ZONE_GROUPING",
                title="Grouped service spaces",
                explanation=(
                    "Kitchen and bathroom spaces are grouped where practical to simplify "
                    "conceptual "
                    "service routing."
                ),
                confidence=0.78,
            ),
            FloorPlanDecision(
                code="DAYLIGHT_EDGE_PRIORITY",
                title="Habitable rooms on exterior edges",
                explanation=(
                    "Bedrooms and public rooms are prioritized along exterior walls to support "
                    "conceptual daylight and ventilation access."
                ),
                confidence=0.84,
            ),
        ],
        warnings=[],
    )


def _room(
    key: str,
    name: str,
    room_type: str,
    floor_index: int,
    area: float,
    minimum_width: float,
    zone: str,
    adjacency: list[str],
    *,
    requires_exterior: bool = True,
) -> FloorPlanProgramRoom:
    return FloorPlanProgramRoom(
        key=key,
        name=name,
        room_type=room_type,
        floor_index=floor_index,
        target_area_m2=area,
        minimum_width_m=minimum_width,
        zone=zone,
        requires_exterior=requires_exterior,
        adjacency_preferences=adjacency,
    )


def _cardinal_side(value: str) -> str:
    if "east" in value:
        return "east"
    if "south" in value:
        return "south"
    if "west" in value:
        return "west"
    return "north"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:32] or "room"

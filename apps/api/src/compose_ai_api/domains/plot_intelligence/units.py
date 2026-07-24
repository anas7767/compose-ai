from __future__ import annotations

from decimal import Decimal

from compose_ai_api.domains.projects.models import UnitSystem

METERS_PER_FOOT = Decimal("0.3048")
SQUARE_METERS_PER_SQUARE_FOOT = Decimal("0.09290304")


def length_to_meters(value: Decimal | None, unit_system: UnitSystem | str) -> Decimal | None:
    if value is None:
        return None
    return value * METERS_PER_FOOT if str(unit_system) == UnitSystem.IMPERIAL.value else value


def length_from_meters(value: Decimal | None, unit_system: UnitSystem | str) -> Decimal | None:
    if value is None:
        return None
    return value / METERS_PER_FOOT if str(unit_system) == UnitSystem.IMPERIAL.value else value


def area_to_square_meters(value: Decimal | None, unit_system: UnitSystem | str) -> Decimal | None:
    if value is None:
        return None
    return (
        value * SQUARE_METERS_PER_SQUARE_FOOT
        if str(unit_system) == UnitSystem.IMPERIAL.value
        else value
    )


def area_from_square_meters(value: Decimal | None, unit_system: UnitSystem | str) -> Decimal | None:
    if value is None:
        return None
    return (
        value / SQUARE_METERS_PER_SQUARE_FOOT
        if str(unit_system) == UnitSystem.IMPERIAL.value
        else value
    )

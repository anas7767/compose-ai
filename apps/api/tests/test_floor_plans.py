from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError
from shapely.geometry import Polygon

from compose_ai_api.domains.floor_plans.diversity import topology_diversity
from compose_ai_api.domains.floor_plans.geometry import geometry_hash
from compose_ai_api.domains.floor_plans.providers.mock import build_deterministic_program
from compose_ai_api.domains.floor_plans.schemas import (
    CONCEPTUAL_DISCLAIMER,
    FloorPlanGenerationRequest,
)
from compose_ai_api.domains.floor_plans.solver import solve_floor_plan
from compose_ai_api.domains.floor_plans.validation import validate_floor_plan


def _context() -> dict[str, object]:
    return {
        "requirements": {
            "bedrooms": 3,
            "bathrooms": 2,
            "floors": 2,
            "parkingSpaces": 1,
        },
        "roomRequirements": [],
        "plotIntelligence": {"roadDirection": "north"},
    }


def _plot() -> Polygon:
    return Polygon([(0, 0), (20_000, 0), (20_000, 15_000), (0, 15_000), (0, 0)])


def test_solver_is_reproducible_and_valid() -> None:
    program = build_deterministic_program(_context())
    first = solve_floor_plan(_plot(), program, deterministic_seed=42, solver_time_limit_seconds=1)
    second = solve_floor_plan(_plot(), program, deterministic_seed=42, solver_time_limit_seconds=1)

    assert geometry_hash(first.geometry) == geometry_hash(second.geometry)
    outcome = validate_floor_plan(first.geometry, _plot())
    assert outcome.valid, outcome.errors


def test_topology_diversity_detects_material_variation() -> None:
    program = build_deterministic_program(_context())
    horizontal = solve_floor_plan(
        _plot(), program, deterministic_seed=10, solver_time_limit_seconds=1
    )
    vertical = solve_floor_plan(
        _plot(), program, deterministic_seed=11, solver_time_limit_seconds=1
    )

    assert topology_diversity(vertical.topology_features, [horizontal.topology_features]) >= 0.25


def test_validation_rejects_overlapping_geometry_without_repair() -> None:
    program = build_deterministic_program(_context())
    solved = solve_floor_plan(_plot(), program, deterministic_seed=42, solver_time_limit_seconds=1)
    invalid = deepcopy(solved.geometry)
    invalid["floors"][0]["rooms"][1]["polygon"] = invalid["floors"][0]["rooms"][0]["polygon"]

    outcome = validate_floor_plan(invalid, _plot())

    assert not outcome.valid
    assert any(error["code"] == "SPACE_OVERLAP" for error in outcome.errors)


def test_generation_request_enforces_failure_budget() -> None:
    with pytest.raises(ValidationError):
        FloorPlanGenerationRequest.model_validate(
            {
                "optionCount": 3,
                "failureBudget": {
                    "maxSolverAttempts": 0,
                    "maxProviderRetries": 2,
                    "maxProcessingSeconds": 180,
                    "maxInvalidCandidates": 12,
                },
            }
        )


def test_required_conceptual_disclaimer_is_exact() -> None:
    assert CONCEPTUAL_DISCLAIMER == "Conceptual Design — Not for Construction."

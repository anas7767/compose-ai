from __future__ import annotations

from typing import Any

from compose_ai_api.domains.exterior_design.constants import (
    ALLOWED_IMAGE_MIME_TYPES,
    CONCEPTUAL_DISCLAIMER,
    EXTERIOR_VALIDATION_ENGINE_VERSION,
)


def validate_generated_option(
    *,
    asset_exists: bool,
    mime_type: str,
    byte_size: int,
    max_bytes: int,
    source_versions: dict[str, Any],
    disclaimer: str,
    safety_metadata: dict[str, Any],
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    if not asset_exists:
        issues.append(_issue("ASSET_MISSING", "Generated asset could not be found.", True))
    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        issues.append(
            _issue("ASSET_MIME_UNSUPPORTED", "Generated image MIME type is unsupported.", True)
        )
    if byte_size <= 0 or byte_size > max_bytes:
        issues.append(
            _issue("ASSET_SIZE_INVALID", "Generated image size is outside allowed limits.", True)
        )
    if not source_versions:
        issues.append(_issue("SOURCE_LINEAGE_MISSING", "Source version metadata is missing.", True))
    if disclaimer != CONCEPTUAL_DISCLAIMER:
        issues.append(
            _issue("DISCLAIMER_MISSING", "Conceptual design disclaimer is missing.", True)
        )
    if safety_metadata.get("blocked"):
        issues.append(
            _issue("PROVIDER_SAFETY_BLOCKED", "Provider safety metadata blocked the result.", True)
        )
    blocking_count = sum(1 for issue in issues if issue["blocking"])
    status = "invalid" if blocking_count else "valid"
    summary = {
        "status": status,
        "issueCount": len(issues),
        "blockingCount": blocking_count,
        "validationEngineVersion": EXTERIOR_VALIDATION_ENGINE_VERSION,
    }
    return status, summary, issues


def _issue(code: str, message: str, blocking: bool) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "blocking" if blocking else "warning",
        "message": message,
        "blocking": blocking,
    }

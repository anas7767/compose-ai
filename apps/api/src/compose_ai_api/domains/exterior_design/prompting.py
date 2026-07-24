from __future__ import annotations

from typing import Any

from compose_ai_api.domains.exterior_design.constants import EXTERIOR_PROMPT_VERSION


def build_exterior_prompt(context: dict[str, Any]) -> dict[str, Any]:
    generation = context["generation"]
    project = context["project"]
    scene = context["scene"]
    materials = ", ".join(generation["materialPreferences"] or ["architectural paint", "glass"])
    prompt = (
        "Create one clean conceptual architectural front elevation image for Compose AI. "
        f"Project: {project.get('name')}. Style: {generation['style']}. "
        f"View: {generation['viewType']} elevation. "
        f"Use these preferred material categories where suitable: {materials}. "
        "Respect the existing massing, floor count, openings and component positions from a "
        "compiled 3D scene with "
        f"{scene.get('objectCount')} objects. Keep the building as the focus. "
        "Produce a premium architectural presentation, not a construction drawing. "
        "Do not add impossible floors, unrelated windows, logos, watermarks, text labels, or "
        "dominant landscaping. "
        "Do not imply structural approval or regulatory compliance."
    )
    if generation.get("userInstructions"):
        prompt += f" User design notes: {generation['userInstructions']}."
    negative = (
        "construction document, blueprint annotations, watermarks, logos, unreadable text, "
        "extra floors, impossible structure, unrelated scenery"
    )
    if generation.get("negativeConstraints"):
        negative += f", {generation['negativeConstraints']}"
    return {
        "promptVersion": EXTERIOR_PROMPT_VERSION,
        "prompt": prompt,
        "negativePrompt": negative,
    }

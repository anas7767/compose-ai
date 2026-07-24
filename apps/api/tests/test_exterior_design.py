from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from compose_ai_api.domains.ai_architect.providers.base import ImageProviderRequest
from compose_ai_api.domains.ai_architect.providers.mock import MockAIProvider
from compose_ai_api.domains.exterior_design.constants import CONCEPTUAL_DISCLAIMER
from compose_ai_api.domains.exterior_design.schemas import ExteriorGenerationRequest
from compose_ai_api.domains.exterior_design.storage import AssetStorageError, LocalAssetStorage
from compose_ai_api.domains.exterior_design.validation import validate_generated_option
from compose_ai_api.main import app
from compose_ai_api.models.base import Base


def test_exterior_design_tables_are_registered() -> None:
    expected = {
        "exterior_design_runs",
        "exterior_design_context_snapshots",
        "exterior_design_options",
        "exterior_design_assets",
        "exterior_design_validation_results",
        "exterior_design_events",
    }

    assert expected.issubset(Base.metadata.tables)


def test_exterior_design_routes_require_authentication() -> None:
    response = TestClient(app).get(f"/api/v1/projects/{uuid4()}/exterior-design/readiness")

    assert response.status_code == 401


def test_phase_10a_rejects_non_front_generation() -> None:
    with pytest.raises(ValidationError):
        ExteriorGenerationRequest(style="modern", viewType="rear", optionCount=1)


def test_generation_request_deduplicates_materials() -> None:
    request = ExteriorGenerationRequest(
        style="modern",
        viewType="front",
        materialPreferences=["paint", "glass", "paint"],
        optionCount=1,
    )

    assert request.material_preferences == ["paint", "glass"]


@pytest.mark.asyncio
async def test_local_asset_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = LocalAssetStorage(root=tmp_path, public_base_url="/assets", max_image_bytes=1024)

    with pytest.raises(AssetStorageError) as error:
        await storage.exists("../secret.png")

    assert error.value.code == "ASSET_PATH_INVALID"


@pytest.mark.asyncio
async def test_local_asset_storage_persists_valid_image(tmp_path: Path) -> None:
    storage = LocalAssetStorage(root=tmp_path, public_base_url="/assets", max_image_bytes=1024)
    content = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000a49444154789c63600000020001e221bc3300000000"
        "49454e44ae426082"
    )

    stored = await storage.store_image(
        organization_id=uuid4(),
        project_id=uuid4(),
        option_id=uuid4(),
        content=content,
        mime_type="image/png",
    )

    assert stored.storage_provider == "local"
    assert stored.integrity_hash
    assert await storage.exists(stored.storage_key)
    assert await storage.read(stored.storage_key) == content


def test_validation_requires_conceptual_disclaimer() -> None:
    status, summary, issues = validate_generated_option(
        asset_exists=True,
        mime_type="image/png",
        byte_size=100,
        max_bytes=1000,
        source_versions={"sceneVersion": 1},
        disclaimer=CONCEPTUAL_DISCLAIMER,
        safety_metadata={},
    )

    assert status == "valid"
    assert summary["blockingCount"] == 0
    assert issues == []


@pytest.mark.asyncio
async def test_mock_provider_image_generation_uses_provider_abstraction() -> None:
    provider = MockAIProvider("phase-10a")

    result = await provider.generate_image(
        ImageProviderRequest(model="mock-image", prompt="front elevation")
    )

    assert result.mime_type == "image/png"
    assert result.content
    assert result.provider_asset_metadata["mock"] is True

from fastapi import APIRouter, HTTPException, status

from compose_ai_api.core.database import check_database_connection
from compose_ai_api.core.provider_health_checks import check_ai_provider_connectivity
from compose_ai_api.core.redis_health import check_redis_connection
from compose_ai_api.core.worker_health import check_worker
from compose_ai_api.domains.exterior_design.storage import AssetStorageError, create_asset_storage
from compose_ai_api.domains.infrastructure.models import WorkerKind
from compose_ai_api.schemas.health import HealthCheckResponse, HealthResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok", service="compose-ai-api")


@router.get("/ready", response_model=ReadinessResponse)
async def ready() -> ReadinessResponse:
    checks: dict[str, HealthCheckResponse] = {}
    database_ready = await check_database_connection()
    checks["postgresql"] = _check(database_ready)
    checks["redis"] = _check(await check_redis_connection())
    checks["ai_worker"] = _check(await check_worker(WorkerKind.AI_ARCHITECT))
    checks["floor_plan_worker"] = _check(await check_worker(WorkerKind.FLOOR_PLAN))
    checks["asset_storage"] = await _asset_storage_check()
    ai_ok, ai_code = await check_ai_provider_connectivity()
    checks["ai_provider"] = _check(ai_ok, code=ai_code)

    if any(item.status == "failed" for item in checks.values()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "One or more readiness checks failed.",
                "checks": {key: value.model_dump() for key, value in checks.items()},
            },
        )

    return ReadinessResponse(
        status="ok",
        service="compose-ai-api",
        checks=checks,
    )


def _check(
    ok: bool,
    *,
    code: str | None = None,
    message: str | None = None,
) -> HealthCheckResponse:
    return HealthCheckResponse(
        status="ok" if ok else "failed",
        code=None if ok else code,
        message=message,
    )


async def _asset_storage_check() -> HealthCheckResponse:
    try:
        storage = create_asset_storage()
        ok = await storage.health_check()
    except AssetStorageError as error:
        return _check(False, code=error.code, message=str(error))
    return _check(ok, code=None if ok else "ASSET_STORAGE_UNAVAILABLE")

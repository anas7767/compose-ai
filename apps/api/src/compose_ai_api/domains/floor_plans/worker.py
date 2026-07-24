from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import select

from compose_ai_api.core.config import get_settings
from compose_ai_api.core.database import AsyncSessionFactory
from compose_ai_api.core.worker_health import default_worker_id, record_worker_heartbeat
from compose_ai_api.domains.floor_plans.execution import process_generation_job
from compose_ai_api.domains.floor_plans.models import (
    FloorPlanGenerationJob,
    FloorPlanJobStatus,
)
from compose_ai_api.domains.infrastructure.models import WorkerKind


async def run_worker() -> None:
    settings = get_settings()
    worker_id = default_worker_id(WorkerKind.FLOOR_PLAN)
    heartbeat_task = asyncio.create_task(
        _heartbeat_loop(
            WorkerKind.FLOOR_PLAN,
            worker_id,
            settings.worker_heartbeat_interval_seconds,
        )
    )
    try:
        while True:
            job_id = await _next_job_id()
            if job_id is None:
                await asyncio.sleep(1)
                continue
            await process_generation_job(job_id)
    finally:
        heartbeat_task.cancel()


async def _heartbeat_loop(kind: WorkerKind, worker_id: str, interval_seconds: int) -> None:
    while True:
        await record_worker_heartbeat(kind, worker_id=worker_id)
        await asyncio.sleep(interval_seconds)


async def _next_job_id() -> UUID | None:
    async with AsyncSessionFactory() as session:
        return (
            await session.execute(
                select(FloorPlanGenerationJob.id)
                .where(FloorPlanGenerationJob.status == FloorPlanJobStatus.QUEUED)
                .order_by(
                    FloorPlanGenerationJob.priority,
                    FloorPlanGenerationJob.available_at,
                    FloorPlanGenerationJob.created_at,
                )
                .limit(1)
            )
        ).scalar_one_or_none()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
import socket
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.config import get_settings
from compose_ai_api.core.database import AsyncSessionFactory
from compose_ai_api.domains.infrastructure.models import (
    WorkerHeartbeat,
    WorkerKind,
    WorkerStatus,
)


def default_worker_id(kind: WorkerKind) -> str:
    return os.getenv("COMPOSE_WORKER_ID") or f"{kind.value}:{socket.gethostname()}:{os.getpid()}"


async def record_worker_heartbeat(
    kind: WorkerKind,
    *,
    worker_id: str | None = None,
    status: WorkerStatus = WorkerStatus.RUNNING,
) -> None:
    settings = get_settings()
    effective_worker_id = worker_id or default_worker_id(kind)
    now = datetime.now(UTC)
    async with AsyncSessionFactory() as session:
        heartbeat = (
            await session.execute(
                select(WorkerHeartbeat).where(
                    WorkerHeartbeat.worker_kind == kind.value,
                    WorkerHeartbeat.worker_id == effective_worker_id,
                )
            )
        ).scalar_one_or_none()
        if heartbeat is None:
            heartbeat = WorkerHeartbeat(
                id=uuid4(),
                worker_kind=kind.value,
                worker_id=effective_worker_id,
                status=status.value,
                last_seen_at=now,
                heartbeat_interval_seconds=settings.worker_heartbeat_interval_seconds,
                details={},
            )
            session.add(heartbeat)
        else:
            heartbeat.status = status.value
            heartbeat.last_seen_at = now
            heartbeat.heartbeat_interval_seconds = settings.worker_heartbeat_interval_seconds
        await session.commit()


async def worker_is_fresh(session: AsyncSession, kind: WorkerKind) -> bool:
    settings = get_settings()
    threshold = datetime.now(UTC) - timedelta(seconds=settings.worker_heartbeat_stale_seconds)
    heartbeat = (
        await session.execute(
            select(WorkerHeartbeat)
            .where(
                WorkerHeartbeat.worker_kind == kind.value,
                WorkerHeartbeat.status == WorkerStatus.RUNNING.value,
                WorkerHeartbeat.last_seen_at >= threshold,
            )
            .order_by(WorkerHeartbeat.last_seen_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return heartbeat is not None


async def check_worker(kind: WorkerKind) -> bool:
    async with AsyncSessionFactory() as session:
        return await worker_is_fresh(session, kind)

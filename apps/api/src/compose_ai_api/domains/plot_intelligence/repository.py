from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from compose_ai_api.core.auth import AuthContext
from compose_ai_api.domains.plot_intelligence.models import (
    PlotAnalysisSnapshot,
    PlotBoundaryRestoreAction,
    PlotBoundaryVersion,
    PlotRoadSide,
)
from compose_ai_api.domains.projects.models import Project, ProjectStatus


def plot_error(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "details": details or {}},
    )


def ensure_plot_read(context: AuthContext) -> None:
    if "projects:read" not in context.permissions:
        raise plot_error(status.HTTP_403_FORBIDDEN, "PROJECT_FORBIDDEN", "Plot access denied.")


def ensure_plot_manage(context: AuthContext) -> None:
    if "projects:manage" not in context.permissions:
        raise plot_error(
            status.HTTP_403_FORBIDDEN,
            "PROJECT_FORBIDDEN",
            "Plot management access denied.",
        )


async def load_plot_project(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    *,
    for_update: bool = False,
    manage: bool = False,
) -> Project:
    ensure_plot_manage(context) if manage else ensure_plot_read(context)
    statement = (
        select(Project)
        .where(
            Project.id == project_id,
            Project.organization_id == context.membership.organization_id,
            Project.deleted_at.is_(None),
        )
        .options(selectinload(Project.site), selectinload(Project.requirements))
    )
    if for_update:
        statement = statement.with_for_update()
    project = (await session.execute(statement)).scalar_one_or_none()
    if project is None:
        raise plot_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project not found.")
    if manage and project.status == ProjectStatus.ARCHIVED:
        raise plot_error(
            status.HTTP_409_CONFLICT,
            "PROJECT_ARCHIVED",
            "Archived projects must be restored before plot editing.",
        )
    return project


async def load_active_roads(
    session: AsyncSession, context: AuthContext, project_id: UUID
) -> list[PlotRoadSide]:
    return list(
        (
            await session.execute(
                select(PlotRoadSide)
                .where(
                    PlotRoadSide.project_id == project_id,
                    PlotRoadSide.organization_id == context.membership.organization_id,
                    PlotRoadSide.deleted_at.is_(None),
                )
                .order_by(PlotRoadSide.sort_order, PlotRoadSide.id)
            )
        )
        .scalars()
        .all()
    )


async def load_boundary(
    session: AsyncSession,
    context: AuthContext,
    boundary_id: UUID | None,
) -> PlotBoundaryVersion | None:
    if boundary_id is None:
        return None
    return (
        await session.execute(
            select(PlotBoundaryVersion).where(
                PlotBoundaryVersion.id == boundary_id,
                PlotBoundaryVersion.organization_id == context.membership.organization_id,
            )
        )
    ).scalar_one_or_none()


async def load_project_boundary(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    boundary_id: UUID,
) -> PlotBoundaryVersion:
    boundary = (
        await session.execute(
            select(PlotBoundaryVersion).where(
                PlotBoundaryVersion.id == boundary_id,
                PlotBoundaryVersion.project_id == project_id,
                PlotBoundaryVersion.organization_id == context.membership.organization_id,
            )
        )
    ).scalar_one_or_none()
    if boundary is None:
        raise plot_error(
            status.HTTP_404_NOT_FOUND,
            "PLOT_BOUNDARY_NOT_FOUND",
            "Plot boundary version not found.",
        )
    return boundary


async def load_analysis(
    session: AsyncSession,
    context: AuthContext,
    analysis_id: UUID | None,
) -> PlotAnalysisSnapshot | None:
    if analysis_id is None:
        return None
    return (
        await session.execute(
            select(PlotAnalysisSnapshot).where(
                PlotAnalysisSnapshot.id == analysis_id,
                PlotAnalysisSnapshot.organization_id == context.membership.organization_id,
            )
        )
    ).scalar_one_or_none()


async def next_boundary_version(session: AsyncSession, project_id: UUID) -> int:
    latest = (
        await session.execute(
            select(func.max(PlotBoundaryVersion.version)).where(
                PlotBoundaryVersion.project_id == project_id
            )
        )
    ).scalar_one()
    return int(latest or 0) + 1


async def load_active_undo(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    current_boundary_id: UUID | None,
) -> PlotBoundaryRestoreAction | None:
    if current_boundary_id is None:
        return None
    return (
        await session.execute(
            select(PlotBoundaryRestoreAction)
            .where(
                PlotBoundaryRestoreAction.project_id == project_id,
                PlotBoundaryRestoreAction.organization_id == context.membership.organization_id,
                PlotBoundaryRestoreAction.restored_boundary_version_id == current_boundary_id,
                PlotBoundaryRestoreAction.used_at.is_(None),
                PlotBoundaryRestoreAction.expires_at > datetime.now(UTC),
            )
            .order_by(PlotBoundaryRestoreAction.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def load_restore_action_for_update(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    action_id: UUID,
) -> PlotBoundaryRestoreAction:
    action = (
        await session.execute(
            select(PlotBoundaryRestoreAction)
            .where(
                PlotBoundaryRestoreAction.id == action_id,
                PlotBoundaryRestoreAction.project_id == project_id,
                PlotBoundaryRestoreAction.organization_id == context.membership.organization_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if action is None:
        raise plot_error(
            status.HTTP_404_NOT_FOUND,
            "PLOT_UNDO_NOT_FOUND",
            "Boundary restore undo action not found.",
        )
    return action

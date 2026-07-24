from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from compose_ai_api.core.auth import AuthContext, AuthRole
from compose_ai_api.domains.billing.models import Plan, Subscription, SubscriptionStatus
from compose_ai_api.domains.identity.models import Organization, User
from compose_ai_api.domains.plot_intelligence.units import (
    area_from_square_meters,
    area_to_square_meters,
    length_from_meters,
    length_to_meters,
)
from compose_ai_api.domains.projects.models import (
    AuditLog,
    IdempotencyRecord,
    Project,
    ProjectClient,
    ProjectRequirements,
    ProjectRoomRequirement,
    ProjectSite,
    ProjectStatus,
    ProjectTagAssignment,
    Tag,
    UnitSystem,
)
from compose_ai_api.domains.projects.schemas import (
    ProjectActivityResponse,
    ProjectClientResponse,
    ProjectCreateRequest,
    ProjectDashboardSummaryResponse,
    ProjectDetailResponse,
    ProjectDuplicateRequest,
    ProjectPlotSummaryResponse,
    ProjectRequirementsResponse,
    ProjectRoomRequirementResponse,
    ProjectSiteResponse,
    ProjectSummaryResponse,
    ProjectThumbnailResponse,
    ProjectUpdateRequest,
)

ACTIVE_SLOT_STATUSES = (ProjectStatus.DRAFT, ProjectStatus.ACTIVE)
ACTIVE_SUBSCRIPTION_STATUSES = (
    SubscriptionStatus.FREE,
    SubscriptionStatus.TRIALING,
    SubscriptionStatus.ACTIVE,
)


def project_error(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "details": details or {}},
    )


def ensure_project_read(context: AuthContext) -> None:
    if "projects:read" not in context.permissions:
        raise project_error(
            status.HTTP_403_FORBIDDEN, "PROJECT_FORBIDDEN", "Project access denied."
        )


def ensure_project_manage(context: AuthContext) -> None:
    if "projects:manage" not in context.permissions:
        raise project_error(
            status.HTTP_403_FORBIDDEN,
            "PROJECT_FORBIDDEN",
            "Project management access denied.",
        )


def ensure_project_delete(context: AuthContext) -> None:
    if context.role not in {AuthRole.OWNER, AuthRole.ADMIN}:
        raise project_error(
            status.HTTP_403_FORBIDDEN,
            "PROJECT_DELETE_FORBIDDEN",
            "Only organization owners and administrators can delete projects.",
        )


def project_select() -> Select[tuple[Project]]:
    return select(Project).options(
        selectinload(Project.client),
        selectinload(Project.site),
        selectinload(Project.requirements),
        selectinload(Project.room_requirements),
        selectinload(Project.tag_assignments).selectinload(ProjectTagAssignment.tag),
    )


async def create_project(
    session: AsyncSession,
    context: AuthContext,
    request: ProjectCreateRequest,
    idempotency_key: str,
    request_id: str,
) -> ProjectDetailResponse:
    ensure_project_manage(context)
    request_hash = _request_hash(request.model_dump(mode="json", by_alias=True))
    await _lock_organization(session, context)
    existing = await _load_idempotency(
        session, context, "project.create", idempotency_key, request_hash
    )
    if existing is not None:
        return ProjectDetailResponse.model_validate(existing.response_body)

    await _ensure_project_slot(session, context, organization_locked=True)
    project = Project(
        id=uuid4(),
        organization_id=context.membership.organization_id,
        created_by=context.user.id,
        updated_by=context.user.id,
        name=request.name,
        status=ProjectStatus.DRAFT,
        project_type=request.project_type,
        unit_system=request.unit_system,
        currency=request.currency,
        country=request.country,
        wizard_step=1,
        version=1,
        thumbnail_metadata={"placeholderSeed": str(uuid4())},
    )
    project.client = ProjectClient()
    project.site = ProjectSite()
    project.requirements = ProjectRequirements()
    project.room_requirements = []
    project.tag_assignments = []
    session.add(project)
    await session.flush()
    await _write_audit(
        session,
        context,
        project,
        "project.created",
        request_id,
        after_data={"name": project.name, "status": ProjectStatus.DRAFT.value},
    )
    response = build_project_detail(project)
    await _store_idempotency(
        session,
        context,
        "project.create",
        idempotency_key,
        request_hash,
        status.HTTP_201_CREATED,
        response.model_dump(mode="json", by_alias=True),
    )
    await session.commit()
    return await load_project_detail(session, context, project.id)


async def list_projects(
    session: AsyncSession,
    context: AuthContext,
    view: str,
    limit: int,
    cursor: str | None,
    query: str | None,
    project_type: str | None,
    tag: str | None,
) -> tuple[list[ProjectSummaryResponse], str | None, bool]:
    ensure_project_read(context)
    statement = project_select().where(
        Project.organization_id == context.membership.organization_id
    )

    if view == "trash":
        ensure_project_delete(context)
        statement = statement.where(Project.deleted_at.is_not(None))
    else:
        status_by_view = {
            "active": ProjectStatus.ACTIVE,
            "drafts": ProjectStatus.DRAFT,
            "archived": ProjectStatus.ARCHIVED,
        }
        selected_status = status_by_view.get(view)
        if selected_status is None:
            raise project_error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "PROJECT_VIEW_INVALID",
                "Unsupported project list view.",
            )
        statement = statement.where(Project.deleted_at.is_(None), Project.status == selected_status)

    if query:
        statement = statement.where(func.lower(Project.name).like(f"{query.strip().casefold()}%"))
    if project_type:
        statement = statement.where(Project.project_type == project_type)
    if tag:
        tag_project_ids = (
            select(ProjectTagAssignment.project_id)
            .join(Tag, Tag.id == ProjectTagAssignment.tag_id)
            .where(
                Tag.organization_id == context.membership.organization_id,
                Tag.normalized_name == tag.strip().casefold(),
            )
        )
        statement = statement.where(Project.id.in_(tag_project_ids))

    if cursor:
        cursor_time, cursor_id = decode_cursor(cursor)
        statement = statement.where(
            or_(
                Project.updated_at < cursor_time,
                (Project.updated_at == cursor_time) & (Project.id < cursor_id),
            )
        )

    statement = statement.order_by(Project.updated_at.desc(), Project.id.desc()).limit(limit + 1)
    projects = list((await session.execute(statement)).scalars().unique().all())
    has_more = len(projects) > limit
    visible_projects = projects[:limit]
    next_cursor = encode_cursor(visible_projects[-1]) if has_more and visible_projects else None
    return [build_project_summary(project) for project in visible_projects], next_cursor, has_more


async def load_project_detail(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    include_deleted: bool = False,
) -> ProjectDetailResponse:
    ensure_project_read(context)
    statement = project_select().where(
        Project.id == project_id,
        Project.organization_id == context.membership.organization_id,
    )
    if include_deleted:
        ensure_project_delete(context)
    else:
        statement = statement.where(Project.deleted_at.is_(None))
    project = (await session.execute(statement)).scalar_one_or_none()
    if project is None:
        raise project_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project not found.")
    return build_project_detail(project)


async def update_project(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    request: ProjectUpdateRequest,
    expected_version: int,
    request_id: str,
) -> ProjectDetailResponse:
    ensure_project_manage(context)
    project = await _load_project_model(session, context, project_id, for_update=True)
    _ensure_version(project, expected_version)
    if project.status == ProjectStatus.ARCHIVED:
        raise project_error(
            status.HTTP_409_CONFLICT,
            "PROJECT_ARCHIVED",
            "Archived projects must be restored before editing.",
        )

    changes = request.model_dump(exclude_unset=True)
    if not changes:
        return build_project_detail(project)

    before_data = {
        "name": project.name,
        "status": str(project.status),
        "version": project.version,
    }
    _apply_project_fields(project, request)
    _apply_client(project, request)
    _apply_site(project, request)
    _apply_requirements(project, request)
    _apply_room_requirements(project, request)
    await _apply_tags(session, context, project, request)
    _validate_site(project.site)
    if project.status == ProjectStatus.ACTIVE:
        _validate_project_completion(project)

    project.updated_by = context.user.id
    project.version += 1
    await session.flush()
    await _write_audit(
        session,
        context,
        project,
        "project.updated",
        request_id,
        before_data=before_data,
        after_data={"changedFields": sorted(changes), "version": project.version},
    )
    await session.commit()
    return await load_project_detail(session, context, project.id)


async def complete_project(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    expected_version: int,
    request_id: str,
) -> ProjectDetailResponse:
    ensure_project_manage(context)
    project = await _load_project_model(session, context, project_id, for_update=True)
    _ensure_version(project, expected_version)
    if project.status != ProjectStatus.DRAFT:
        raise project_error(
            status.HTTP_409_CONFLICT,
            "PROJECT_TRANSITION_INVALID",
            "Only draft projects can be completed.",
        )
    _validate_project_completion(project)
    project.status = ProjectStatus.ACTIVE
    project.completed_at = datetime.now(UTC)
    project.wizard_step = 5
    project.updated_by = context.user.id
    project.version += 1
    await _write_audit(
        session,
        context,
        project,
        "project.completed",
        request_id,
        after_data={"status": ProjectStatus.ACTIVE.value, "version": project.version},
    )
    await session.commit()
    return await load_project_detail(session, context, project.id)


async def archive_project(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    expected_version: int,
    request_id: str,
) -> ProjectDetailResponse:
    ensure_project_manage(context)
    project = await _load_project_model(session, context, project_id, for_update=True)
    _ensure_version(project, expected_version)
    if project.status == ProjectStatus.ARCHIVED:
        return build_project_detail(project)
    project.status = ProjectStatus.ARCHIVED
    project.archived_at = datetime.now(UTC)
    project.archived_by = context.user.id
    project.updated_by = context.user.id
    project.version += 1
    await _write_audit(
        session,
        context,
        project,
        "project.archived",
        request_id,
        after_data={"status": ProjectStatus.ARCHIVED.value, "version": project.version},
    )
    await session.commit()
    return await load_project_detail(session, context, project.id)


async def restore_archived_project(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    expected_version: int,
    request_id: str,
) -> ProjectDetailResponse:
    ensure_project_manage(context)
    project = await _load_project_model(session, context, project_id, for_update=True)
    _ensure_version(project, expected_version)
    if project.status != ProjectStatus.ARCHIVED:
        raise project_error(
            status.HTTP_409_CONFLICT,
            "PROJECT_TRANSITION_INVALID",
            "Only archived projects can be restored.",
        )
    await _ensure_project_slot(session, context)
    restored_status = ProjectStatus.ACTIVE if project.completed_at else ProjectStatus.DRAFT
    project.status = restored_status
    project.archived_at = None
    project.archived_by = None
    project.updated_by = context.user.id
    project.version += 1
    await _write_audit(
        session,
        context,
        project,
        "project.restored",
        request_id,
        after_data={"status": restored_status.value, "version": project.version},
    )
    await session.commit()
    return await load_project_detail(session, context, project.id)


async def duplicate_project(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    request: ProjectDuplicateRequest,
    idempotency_key: str,
    request_id: str,
) -> ProjectDetailResponse:
    ensure_project_manage(context)
    request_data = {"projectId": str(project_id), **request.model_dump(mode="json", by_alias=True)}
    request_hash = _request_hash(request_data)
    await _lock_organization(session, context)
    existing = await _load_idempotency(
        session, context, "project.duplicate", idempotency_key, request_hash
    )
    if existing is not None:
        return ProjectDetailResponse.model_validate(existing.response_body)
    source = await _load_project_model(session, context, project_id)
    await _ensure_project_slot(session, context, organization_locked=True)
    name = request.name or await _unique_copy_name(session, context, source.name)
    duplicate = Project(
        id=uuid4(),
        organization_id=context.membership.organization_id,
        created_by=context.user.id,
        updated_by=context.user.id,
        name=name,
        status=ProjectStatus.DRAFT,
        project_type=source.project_type,
        description=source.description,
        unit_system=source.unit_system,
        currency=source.currency,
        country=source.country,
        wizard_step=5,
        version=1,
        duplicate_source_id=source.id,
        thumbnail_metadata={"placeholderSeed": str(uuid4())},
    )
    duplicate.client = _copy_client(source.client)
    duplicate.site = _copy_site(source.site)
    duplicate.requirements = _copy_requirements(source.requirements)
    duplicate.room_requirements = [_copy_room(room) for room in source.room_requirements]
    duplicate.tag_assignments = [
        ProjectTagAssignment(tag_id=assignment.tag_id) for assignment in source.tag_assignments
    ]
    session.add(duplicate)
    await session.flush()
    await _write_audit(
        session,
        context,
        duplicate,
        "project.duplicated",
        request_id,
        after_data={"sourceProjectId": str(source.id), "name": duplicate.name},
    )
    response = build_project_detail(duplicate)
    await _store_idempotency(
        session,
        context,
        "project.duplicate",
        idempotency_key,
        request_hash,
        status.HTTP_201_CREATED,
        response.model_dump(mode="json", by_alias=True),
    )
    await session.commit()
    return await load_project_detail(session, context, duplicate.id)


async def soft_delete_project(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    expected_version: int,
    request_id: str,
) -> None:
    ensure_project_delete(context)
    project = await _load_project_model(session, context, project_id, for_update=True)
    _ensure_version(project, expected_version)
    project.deleted_at = datetime.now(UTC)
    project.deleted_by = context.user.id
    project.updated_by = context.user.id
    project.version += 1
    await _write_audit(
        session,
        context,
        project,
        "project.deleted",
        request_id,
        after_data={"softDeleted": True, "version": project.version},
    )
    await session.commit()


async def restore_deleted_project(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    expected_version: int,
    request_id: str,
) -> ProjectDetailResponse:
    ensure_project_delete(context)
    project = await _load_project_model(
        session, context, project_id, include_deleted=True, for_update=True
    )
    _ensure_version(project, expected_version)
    if project.deleted_at is None:
        return build_project_detail(project)
    if project.status in ACTIVE_SLOT_STATUSES:
        await _ensure_project_slot(session, context)
    project.deleted_at = None
    project.deleted_by = None
    project.updated_by = context.user.id
    project.version += 1
    await _write_audit(
        session,
        context,
        project,
        "project.deleted_restored",
        request_id,
        after_data={"softDeleted": False, "version": project.version},
    )
    await session.commit()
    return await load_project_detail(session, context, project.id)


async def project_dashboard_summary(
    session: AsyncSession, context: AuthContext
) -> ProjectDashboardSummaryResponse:
    ensure_project_read(context)
    rows = (
        await session.execute(
            select(Project.status, Project.deleted_at.is_not(None), func.count(Project.id))
            .where(Project.organization_id == context.membership.organization_id)
            .group_by(Project.status, Project.deleted_at.is_not(None))
        )
    ).all()
    counts = {"active": 0, "draft": 0, "archived": 0, "deleted": 0}
    for project_status, is_deleted, count in rows:
        if is_deleted:
            counts["deleted"] += count
        else:
            counts[str(project_status)] = count
    return ProjectDashboardSummaryResponse(
        active_count=counts["active"],
        draft_count=counts["draft"],
        archived_count=counts["archived"],
        deleted_count=counts["deleted"],
        used_project_slots=counts["active"] + counts["draft"],
    )


async def project_activity(
    session: AsyncSession,
    context: AuthContext,
    limit: int,
    project_id: UUID | None = None,
) -> list[ProjectActivityResponse]:
    ensure_project_read(context)
    statement = (
        select(AuditLog, Project.name, User.name)
        .join(Project, Project.id == AuditLog.entity_id)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(
            AuditLog.organization_id == context.membership.organization_id,
            AuditLog.entity_type == "project",
            Project.organization_id == context.membership.organization_id,
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    )
    if project_id is not None:
        statement = statement.where(AuditLog.entity_id == project_id)
    rows = (await session.execute(statement)).all()
    return [
        ProjectActivityResponse(
            id=audit.id,
            project_id=audit.entity_id,
            project_name=project_name,
            action=audit.action,
            actor_name=actor_name,
            created_at=audit.created_at,
        )
        for audit, project_name, actor_name in rows
    ]


async def project_tag_suggestions(
    session: AsyncSession, context: AuthContext, query: str | None, limit: int
) -> list[str]:
    ensure_project_read(context)
    statement = select(Tag.display_name).where(
        Tag.organization_id == context.membership.organization_id
    )
    if query:
        statement = statement.where(Tag.normalized_name.like(f"{query.strip().casefold()}%"))
    statement = statement.order_by(Tag.display_name).limit(limit)
    return list((await session.execute(statement)).scalars().all())


async def _load_project_model(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    include_deleted: bool = False,
    for_update: bool = False,
) -> Project:
    statement = project_select().where(
        Project.id == project_id,
        Project.organization_id == context.membership.organization_id,
    )
    statement = (
        statement.where(Project.deleted_at.is_not(None))
        if include_deleted
        else statement.where(Project.deleted_at.is_(None))
    )
    if for_update:
        statement = statement.with_for_update()
    project = (await session.execute(statement)).scalar_one_or_none()
    if project is None:
        raise project_error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project not found.")
    return project


async def _lock_organization(session: AsyncSession, context: AuthContext) -> None:
    await session.execute(
        select(Organization.id)
        .where(Organization.id == context.membership.organization_id)
        .with_for_update()
    )


async def _ensure_project_slot(
    session: AsyncSession,
    context: AuthContext,
    *,
    organization_locked: bool = False,
) -> None:
    if not organization_locked:
        await _lock_organization(session, context)
    plan_limit = (
        await session.execute(
            select(Plan.project_limit)
            .join(Subscription, Subscription.plan_id == Plan.id)
            .where(
                Subscription.organization_id == context.membership.organization_id,
                Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
                Subscription.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if plan_limit is None:
        raise project_error(
            status.HTTP_428_PRECONDITION_REQUIRED,
            "PROJECT_PLAN_UNAVAILABLE",
            "The organization plan is not initialized.",
        )
    used_slots = (
        await session.execute(
            select(func.count(Project.id)).where(
                Project.organization_id == context.membership.organization_id,
                Project.status.in_(ACTIVE_SLOT_STATUSES),
                Project.deleted_at.is_(None),
            )
        )
    ).scalar_one()
    if used_slots >= plan_limit:
        raise project_error(
            status.HTTP_409_CONFLICT,
            "PROJECT_LIMIT_REACHED",
            "The current plan project limit has been reached.",
            {"limit": plan_limit, "used": used_slots},
        )


def _apply_project_fields(project: Project, request: ProjectUpdateRequest) -> None:
    for field in (
        "name",
        "project_type",
        "description",
        "unit_system",
        "currency",
        "country",
        "wizard_step",
    ):
        if field in request.model_fields_set:
            setattr(project, field, getattr(request, field))


def _apply_client(project: Project, request: ProjectUpdateRequest) -> None:
    if "client" not in request.model_fields_set:
        return
    if project.client is None:
        project.client = ProjectClient()
    if request.client is None:
        for field in ("name", "company", "email", "phone", "address"):
            setattr(project.client, field, None)
        return
    for field, value in request.client.model_dump(exclude_unset=True).items():
        setattr(project.client, field, str(value) if field == "email" and value else value)


def _apply_site(project: Project, request: ProjectUpdateRequest) -> None:
    if "site" not in request.model_fields_set:
        return
    if project.site is None:
        project.site = ProjectSite()
    if request.site is None:
        project.site = ProjectSite()
        return
    values = request.site.model_dump(exclude_unset=True)
    for field, value in values.items():
        if field == "plot_length":
            value = length_to_meters(value, UnitSystem(str(project.unit_system)))
        if field == "plot_width":
            value = length_to_meters(value, UnitSystem(str(project.unit_system)))
        if field == "plot_area":
            value = area_to_square_meters(value, UnitSystem(str(project.unit_system)))
        setattr(project.site, field, value)
    if (
        project.site.plot_shape in {"rectangle", "square"}
        and project.site.plot_length is not None
        and project.site.plot_width is not None
        and "plot_area" not in values
    ):
        project.site.plot_area = project.site.plot_length * project.site.plot_width
        project.site.area_source = "dimensions"
    elif "plot_area" in values:
        project.site.area_source = "declared" if project.site.plot_area is not None else "unknown"


def _apply_requirements(project: Project, request: ProjectUpdateRequest) -> None:
    if "requirements" not in request.model_fields_set:
        return
    if project.requirements is None:
        project.requirements = ProjectRequirements()
    if request.requirements is None:
        project.requirements = ProjectRequirements()
        return
    for field, value in request.requirements.model_dump(exclude_unset=True).items():
        setattr(project.requirements, field, value)


def _apply_room_requirements(project: Project, request: ProjectUpdateRequest) -> None:
    if "room_requirements" not in request.model_fields_set:
        return
    existing_by_id = {room.id: room for room in project.room_requirements}
    updated_rooms: list[ProjectRoomRequirement] = []
    seen_ids: set[UUID] = set()
    for room in request.room_requirements or []:
        if room.id is not None:
            if room.id in seen_ids:
                raise project_error(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "PROJECT_ROOM_DUPLICATE",
                    "A custom room cannot appear more than once.",
                    {"roomId": str(room.id)},
                )
            room_model = existing_by_id.get(room.id)
            if room_model is None:
                raise project_error(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "PROJECT_ROOM_INVALID",
                    "The custom room does not belong to this project.",
                    {"roomId": str(room.id)},
                )
            seen_ids.add(room.id)
        else:
            room_model = ProjectRoomRequirement(id=uuid4())
        room_model.name = room.name
        room_model.room_type = room.room_type
        room_model.quantity = room.quantity
        room_model.preferred_floor = room.preferred_floor
        room_model.minimum_area = room.minimum_area
        room_model.notes = room.notes
        room_model.sort_order = room.sort_order
        updated_rooms.append(room_model)
    project.room_requirements = updated_rooms


async def _apply_tags(
    session: AsyncSession,
    context: AuthContext,
    project: Project,
    request: ProjectUpdateRequest,
) -> None:
    if "tags" not in request.model_fields_set:
        return
    display_tags = request.tags or []
    normalized_tags = [tag.casefold() for tag in display_tags]
    existing_tags = list(
        (
            await session.execute(
                select(Tag).where(
                    Tag.organization_id == context.membership.organization_id,
                    Tag.normalized_name.in_(normalized_tags),
                )
            )
        )
        .scalars()
        .all()
    )
    by_name = {tag.normalized_name: tag for tag in existing_tags}
    tags: list[Tag] = []
    for display_name, normalized_name in zip(display_tags, normalized_tags, strict=True):
        tag = by_name.get(normalized_name)
        if tag is None:
            tag = Tag(
                id=uuid4(),
                organization_id=context.membership.organization_id,
                normalized_name=normalized_name,
                display_name=display_name,
            )
            session.add(tag)
            by_name[normalized_name] = tag
        tags.append(tag)
    await session.flush()
    project.tag_assignments = [ProjectTagAssignment(tag_id=tag.id, tag=tag) for tag in tags]


def _validate_project_completion(project: Project) -> None:
    missing: list[str] = []
    if len(project.name.strip()) < 2:
        missing.append("name")
    if project.project_type is None:
        missing.append("projectType")
    if project.country is None:
        missing.append("country")
    if missing:
        raise project_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PROJECT_COMPLETION_INVALID",
            "The project is missing required details.",
            {"missingFields": missing},
        )
    _validate_site(project.site)


def _validate_site(site: ProjectSite | None) -> None:
    if site is None:
        return
    if (site.latitude is None) != (site.longitude is None):
        raise project_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PROJECT_SITE_INVALID",
            "Latitude and longitude must be supplied together.",
        )
    if site.open_sides > 0 and site.road_direction_primary is None:
        raise project_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PROJECT_SITE_INVALID",
            "A primary road direction is required when the plot has open sides.",
        )
    if site.corner_plot and site.open_sides < 2:
        raise project_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PROJECT_SITE_INVALID",
            "Corner plots require at least two open sides.",
        )
    if site.corner_plot and site.road_direction_secondary is None:
        raise project_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PROJECT_SITE_INVALID",
            "Corner plots require a secondary road direction.",
        )
    if site.road_direction_primary == site.road_direction_secondary and site.road_direction_primary:
        raise project_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PROJECT_SITE_INVALID",
            "Primary and secondary road directions must differ.",
        )
    if site.plot_shape == "square" and site.plot_length and site.plot_width:
        largest = max(site.plot_length, site.plot_width)
        if abs(site.plot_length - site.plot_width) / largest > Decimal("0.01"):
            raise project_error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "PROJECT_SITE_INVALID",
                "Square plot dimensions must be within one percent of each other.",
            )


def _ensure_version(project: Project, expected_version: int) -> None:
    if project.version != expected_version:
        raise project_error(
            status.HTTP_409_CONFLICT,
            "PROJECT_VERSION_CONFLICT",
            "The project changed after it was loaded.",
            {"expectedVersion": expected_version, "currentVersion": project.version},
        )


async def _write_audit(
    session: AsyncSession,
    context: AuthContext,
    project: Project,
    action: str,
    request_id: str,
    before_data: dict[str, object] | None = None,
    after_data: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditLog(
            id=uuid4(),
            organization_id=context.membership.organization_id,
            actor_user_id=context.user.id,
            action=action,
            entity_type="project",
            entity_id=project.id,
            request_id=request_id,
            before_data=before_data,
            after_data=after_data,
            created_at=datetime.now(UTC),
        )
    )


async def _load_idempotency(
    session: AsyncSession,
    context: AuthContext,
    scope: str,
    key: str,
    request_hash: str,
) -> IdempotencyRecord | None:
    record = (
        await session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.organization_id == context.membership.organization_id,
                IdempotencyRecord.actor_user_id == context.user.id,
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.idempotency_key == key,
                IdempotencyRecord.expires_at > datetime.now(UTC),
            )
        )
    ).scalar_one_or_none()
    if record and record.request_hash != request_hash:
        raise project_error(
            status.HTTP_409_CONFLICT,
            "IDEMPOTENCY_CONFLICT",
            "The idempotency key was already used with a different request.",
        )
    return record


async def _store_idempotency(
    session: AsyncSession,
    context: AuthContext,
    scope: str,
    key: str,
    request_hash: str,
    response_status: int,
    response_body: dict[str, object],
) -> None:
    session.add(
        IdempotencyRecord(
            id=uuid4(),
            organization_id=context.membership.organization_id,
            actor_user_id=context.user.id,
            scope=scope,
            idempotency_key=key,
            request_hash=request_hash,
            response_status=response_status,
            response_body=response_body,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )


def _request_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def encode_cursor(project: Project) -> str:
    payload = json.dumps({"updatedAt": project.updated_at.isoformat(), "id": str(project.id)})
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        return datetime.fromisoformat(payload["updatedAt"]), UUID(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise project_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PAGINATION_CURSOR_INVALID",
            "The pagination cursor is invalid.",
        ) from error


def build_project_summary(project: Project) -> ProjectSummaryResponse:
    tags = sorted(assignment.tag.display_name for assignment in project.tag_assignments)
    site = project.site
    unit_system = UnitSystem(str(project.unit_system))
    return ProjectSummaryResponse(
        id=project.id,
        organization_id=project.organization_id,
        name=project.name,
        status=project.status,
        project_type=project.project_type,
        unit_system=project.unit_system,
        currency=project.currency,
        country=project.country,
        wizard_step=project.wizard_step,
        profile_completeness=_profile_completeness(project),
        version=project.version,
        thumbnail=ProjectThumbnailResponse(
            source=project.thumbnail_source,
            url=None,
            mime_type=project.thumbnail_mime_type,
            width=project.thumbnail_width,
            height=project.thumbnail_height,
            version=project.thumbnail_version,
            generated_at=project.thumbnail_generated_at,
            metadata=project.thumbnail_metadata,
        ),
        plot_summary=ProjectPlotSummaryResponse(
            completeness=site.plot_completeness if site else 0,
            health_score=site.plot_health_score if site else 0,
            health_status=site.plot_health_status if site else "insufficient_data",
            feasibility_status=site.plot_feasibility_status if site else "insufficient_data",
            validation_error_count=site.plot_validation_error_count if site else 0,
            validation_warning_count=site.plot_validation_warning_count if site else 0,
            pre_regulation_buildable_area=area_from_square_meters(
                site.pre_regulation_buildable_area_m2 if site else None, unit_system
            ),
            parking_status=site.parking_feasibility_status if site else "indeterminate",
            analysis_updated_at=site.analysis_updated_at if site else None,
        ),
        city=site.city if site else None,
        tags=tags,
        completed_at=project.completed_at,
        archived_at=project.archived_at,
        deleted_at=project.deleted_at,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def build_project_detail(project: Project) -> ProjectDetailResponse:
    summary = build_project_summary(project)
    client = project.client or ProjectClient()
    site = project.site or ProjectSite()
    requirements = project.requirements or ProjectRequirements()
    unit_system = UnitSystem(str(project.unit_system))
    return ProjectDetailResponse(
        **summary.model_dump(),
        description=project.description,
        client=ProjectClientResponse(
            name=client.name,
            company=client.company,
            email=client.email,
            phone=client.phone,
            address=client.address,
        ),
        site=ProjectSiteResponse(
            plot_length=length_from_meters(site.plot_length, unit_system),
            plot_width=length_from_meters(site.plot_width, unit_system),
            plot_area=area_from_square_meters(site.plot_area, unit_system),
            plot_shape=site.plot_shape,
            road_direction_primary=site.road_direction_primary,
            road_direction_secondary=site.road_direction_secondary,
            open_sides=site.open_sides or 0,
            corner_plot=site.corner_plot or False,
            address_line_1=site.address_line_1,
            address_line_2=site.address_line_2,
            city=site.city,
            region=site.region,
            postal_code=site.postal_code,
            latitude=site.latitude,
            longitude=site.longitude,
            boundary_status="captured" if site.boundary_geojson else "not_captured",
            orientation_degrees=site.orientation_degrees,
            north_rotation_degrees=site.north_rotation_degrees,
            north_reference=site.north_reference,
            profile_revision=site.profile_revision,
        ),
        requirements=ProjectRequirementsResponse(
            bedrooms=requirements.bedrooms or 0,
            bathrooms=requirements.bathrooms or Decimal(0),
            floors=requirements.floors or 1,
            parking_spaces=requirements.parking_spaces or 0,
            budget=requirements.budget,
            construction_quality=requirements.construction_quality,
            preferred_style=requirements.preferred_style,
            vastu_preference=requirements.vastu_preference or "not_required",
            notes=requirements.notes,
        ),
        room_requirements=[
            ProjectRoomRequirementResponse(
                id=room.id,
                name=room.name,
                room_type=room.room_type,
                quantity=room.quantity,
                preferred_floor=room.preferred_floor,
                minimum_area=room.minimum_area,
                notes=room.notes,
                sort_order=room.sort_order,
            )
            for room in project.room_requirements
        ],
        duplicate_source_id=project.duplicate_source_id,
    )


def _profile_completeness(project: Project) -> int:
    score = 20
    score += 20 if project.project_type else 0
    score += 10 if project.country else 0
    score += 10 if project.client and (project.client.name or project.client.company) else 0
    score += 15 if project.site and (project.site.city or project.site.plot_area) else 0
    score += 15 if project.requirements and project.requirements.floors else 0
    score += 10 if project.tag_assignments else 0
    return min(score, 100)


async def _unique_copy_name(session: AsyncSession, context: AuthContext, source_name: str) -> str:
    base = f"Copy of {source_name}"[:160]
    candidate = base
    suffix = 2
    while (
        await session.execute(
            select(Project.id).where(
                Project.organization_id == context.membership.organization_id,
                func.lower(Project.name) == candidate.casefold(),
                Project.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none():
        marker = f" ({suffix})"
        candidate = f"{base[: 160 - len(marker)]}{marker}"
        suffix += 1
    return candidate


def _copy_client(source: ProjectClient | None) -> ProjectClient:
    return ProjectClient(
        name=source.name if source else None,
        company=source.company if source else None,
        email=source.email if source else None,
        phone=source.phone if source else None,
        address=source.address if source else None,
    )


def _copy_site(source: ProjectSite | None) -> ProjectSite:
    if source is None:
        return ProjectSite()
    return ProjectSite(
        plot_length=source.plot_length,
        plot_width=source.plot_width,
        plot_area=source.plot_area,
        plot_shape=source.plot_shape,
        road_direction_primary=source.road_direction_primary,
        road_direction_secondary=source.road_direction_secondary,
        open_sides=source.open_sides,
        corner_plot=source.corner_plot,
        address_line_1=source.address_line_1,
        address_line_2=source.address_line_2,
        city=source.city,
        region=source.region,
        postal_code=source.postal_code,
        latitude=source.latitude,
        longitude=source.longitude,
        area_source=source.area_source,
        orientation_degrees=source.orientation_degrees,
        north_rotation_degrees=source.north_rotation_degrees,
        north_reference=source.north_reference,
        profile_revision=1,
    )


def _copy_requirements(source: ProjectRequirements | None) -> ProjectRequirements:
    if source is None:
        return ProjectRequirements()
    return ProjectRequirements(
        bedrooms=source.bedrooms,
        bathrooms=source.bathrooms,
        floors=source.floors,
        parking_spaces=source.parking_spaces,
        budget=source.budget,
        construction_quality=source.construction_quality,
        preferred_style=source.preferred_style,
        vastu_preference=source.vastu_preference,
        notes=source.notes,
    )


def _copy_room(source: ProjectRoomRequirement) -> ProjectRoomRequirement:
    return ProjectRoomRequirement(
        id=uuid4(),
        name=source.name,
        room_type=source.room_type,
        quantity=source.quantity,
        preferred_floor=source.preferred_floor,
        minimum_area=source.minimum_area,
        notes=source.notes,
        sort_order=source.sort_order,
    )

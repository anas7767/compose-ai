from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext, get_auth_context
from compose_ai_api.core.database import get_db_session
from compose_ai_api.domains.floor_plan_editor.schemas import (
    EditorCheckpointCreateRequest,
    EditorCheckpointResponse,
    EditorDesignVersionCreateRequest,
    EditorDocumentResponse,
    EditorHistoryResponse,
    EditorOperationBatchRequest,
    EditorOperationBatchResponse,
    EditorSnapshot,
    EditorValidationRequest,
    EditorValidationResponse,
)
from compose_ai_api.domains.floor_plan_editor.service import (
    apply_operation_batch,
    create_checkpoint,
    create_design_version_checkpoint,
    list_history,
    load_editor_document,
    load_editor_snapshot,
    restore_checkpoint,
    validate_editor_document,
)
from compose_ai_api.schemas.api import ApiEnvelope, ApiMeta

router = APIRouter(prefix="/projects/{project_id}/editor", tags=["floor-plan-editor"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=128),
]


@router.get("", response_model=ApiEnvelope[EditorDocumentResponse])
async def editor_document(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[EditorDocumentResponse]:
    return ApiEnvelope(
        data=await load_editor_document(session, context, project_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/snapshot", response_model=ApiEnvelope[EditorSnapshot])
async def editor_snapshot(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[EditorSnapshot]:
    return ApiEnvelope(
        data=await load_editor_snapshot(session, context, project_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post("/operations", response_model=ApiEnvelope[EditorOperationBatchResponse])
async def editor_operations(
    project_id: UUID,
    request: EditorOperationBatchRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[EditorOperationBatchResponse]:
    return ApiEnvelope(
        data=await apply_operation_batch(session, context, project_id, request, idempotency_key),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post("/validate", response_model=ApiEnvelope[EditorValidationResponse])
async def editor_validate(
    project_id: UUID,
    request: EditorValidationRequest,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[EditorValidationResponse]:
    return ApiEnvelope(
        data=await validate_editor_document(session, context, project_id, request),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/revisions", response_model=ApiEnvelope[EditorHistoryResponse])
async def editor_revisions(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[EditorHistoryResponse]:
    return ApiEnvelope(
        data=await list_history(session, context, project_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/checkpoints",
    response_model=ApiEnvelope[EditorCheckpointResponse],
    status_code=status.HTTP_201_CREATED,
)
async def editor_checkpoint(
    project_id: UUID,
    request: EditorCheckpointCreateRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[EditorCheckpointResponse]:
    return ApiEnvelope(
        data=await create_checkpoint(session, context, project_id, request.name, idempotency_key),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/checkpoints/{checkpoint_id}/restore", response_model=ApiEnvelope[EditorDocumentResponse]
)
async def editor_checkpoint_restore(
    project_id: UUID,
    checkpoint_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[EditorDocumentResponse]:
    return ApiEnvelope(
        data=await restore_checkpoint(session, context, project_id, checkpoint_id, idempotency_key),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/design-version",
    response_model=ApiEnvelope[EditorCheckpointResponse],
    status_code=status.HTTP_201_CREATED,
)
async def editor_design_version(
    project_id: UUID,
    request: EditorDesignVersionCreateRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[EditorCheckpointResponse]:
    return ApiEnvelope(
        data=await create_design_version_checkpoint(
            session,
            context,
            project_id,
            request.checkpoint_id,
            request.name,
            idempotency_key,
        ),
        meta=ApiMeta(request_id=str(uuid4())),
    )

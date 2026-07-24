from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import get_current_principal
from compose_ai_api.core.database import get_db_session
from compose_ai_api.core.security import AuthenticatedPrincipal
from compose_ai_api.domains.identity.schemas import (
    AuthBootstrapRequest,
    AuthContextResponse,
    AuthSessionResponse,
)
from compose_ai_api.domains.identity.service import (
    bootstrap_identity,
    build_auth_session_response,
    load_auth_context_response,
)
from compose_ai_api.schemas.api import ApiEnvelope, ApiMeta

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/bootstrap", response_model=ApiEnvelope[AuthContextResponse])
async def bootstrap(
    request: AuthBootstrapRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiEnvelope[AuthContextResponse]:
    context = await bootstrap_identity(session=session, principal=principal, request=request)

    return ApiEnvelope(data=context, meta=ApiMeta(request_id=str(uuid4())))


@router.get("/me", response_model=ApiEnvelope[AuthContextResponse])
async def me(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiEnvelope[AuthContextResponse]:
    context = await load_auth_context_response(session=session, principal=principal)

    return ApiEnvelope(data=context, meta=ApiMeta(request_id=str(uuid4())))


@router.get("/session", response_model=ApiEnvelope[AuthSessionResponse])
async def session(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> ApiEnvelope[AuthSessionResponse]:
    session_context = build_auth_session_response(principal)

    return ApiEnvelope(data=session_context, meta=ApiMeta(request_id=str(uuid4())))

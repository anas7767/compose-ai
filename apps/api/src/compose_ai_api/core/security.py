from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, status
from jwt import InvalidTokenError

from compose_ai_api.core.config import get_settings


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    clerk_user_id: str
    clerk_session_id: str | None
    clerk_organization_id: str | None
    clerk_organization_role: str | None
    expires_at: int | None
    issued_at: int | None
    claims: dict[str, Any]


class ClerkJWTVerifier:
    def __init__(self) -> None:
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_cache_expires_at = 0.0

    async def verify(self, token: str) -> AuthenticatedPrincipal:
        settings = get_settings()
        jwks_url = self._resolve_jwks_url()

        try:
            unverified_header = jwt.get_unverified_header(token)
        except InvalidTokenError as exc:
            raise self._unauthorized("Invalid session token header.") from exc

        key_id = unverified_header.get("kid")
        algorithm = unverified_header.get("alg")

        if not key_id or not algorithm:
            raise self._unauthorized("Invalid session token header.")

        jwks = await self._get_jwks(jwks_url)
        jwk = next((key for key in jwks.get("keys", []) if key.get("kid") == key_id), None)

        if jwk is None:
            self._jwks_cache = None
            jwks = await self._get_jwks(jwks_url)
            jwk = next((key for key in jwks.get("keys", []) if key.get("kid") == key_id), None)

        if jwk is None:
            raise self._unauthorized("Session signing key was not found.")

        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
        decode_kwargs: dict[str, Any] = {
            "key": public_key,
            "algorithms": [algorithm],
            "options": {"verify_aud": False},
        }

        if settings.clerk_issuer:
            decode_kwargs["issuer"] = settings.clerk_issuer

        try:
            claims = jwt.decode(token, **decode_kwargs)
        except InvalidTokenError as exc:
            raise self._unauthorized("Invalid or expired session token.") from exc

        self._validate_authorized_party(claims)

        clerk_user_id = claims.get("sub")

        if not isinstance(clerk_user_id, str) or not clerk_user_id:
            raise self._unauthorized("Session token is missing a subject.")

        clerk_organization_id, clerk_organization_role = self._organization_context(claims)

        return AuthenticatedPrincipal(
            clerk_user_id=clerk_user_id,
            clerk_session_id=self._optional_string(claims.get("sid")),
            clerk_organization_id=clerk_organization_id,
            clerk_organization_role=clerk_organization_role,
            expires_at=self._optional_int(claims.get("exp")),
            issued_at=self._optional_int(claims.get("iat")),
            claims=claims,
        )

    def _resolve_jwks_url(self) -> str:
        settings = get_settings()

        if settings.clerk_jwks_url:
            return settings.clerk_jwks_url

        if settings.clerk_issuer:
            return f"{settings.clerk_issuer.rstrip('/')}/.well-known/jwks.json"

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Clerk JWT verification is not configured.",
        )

    async def _get_jwks(self, jwks_url: str) -> dict[str, Any]:
        now = time.monotonic()

        if self._jwks_cache and self._jwks_cache_expires_at > now:
            return self._jwks_cache

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(jwks_url)
            response.raise_for_status()

        jwks = response.json()
        self._jwks_cache = jwks
        self._jwks_cache_expires_at = now + 300

        return jwks

    def _validate_authorized_party(self, claims: dict[str, Any]) -> None:
        settings = get_settings()

        if not settings.clerk_authorized_parties:
            return

        authorized_party = claims.get("azp")

        if authorized_party not in settings.clerk_authorized_parties:
            raise self._unauthorized("Session token authorized party is not allowed.")

    @classmethod
    def _organization_context(cls, claims: dict[str, Any]) -> tuple[str | None, str | None]:
        organization_id = cls._optional_string(claims.get("org_id"))
        organization_role = cls._optional_string(claims.get("org_role"))
        compact_organization = claims.get("o")

        if isinstance(compact_organization, dict):
            organization_id = organization_id or cls._optional_string(
                compact_organization.get("id")
            )
            organization_role = organization_role or cls._optional_string(
                compact_organization.get("rol")
            )

        return organization_id, organization_role

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        return value if isinstance(value, int) else None

    @staticmethod
    def _unauthorized(message: str) -> HTTPException:
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)


clerk_jwt_verifier = ClerkJWTVerifier()

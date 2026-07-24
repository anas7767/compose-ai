from fastapi.testclient import TestClient

from compose_ai_api.core.security import ClerkJWTVerifier
from compose_ai_api.domains.identity.models import OrganizationMemberStatus
from compose_ai_api.domains.identity.service import _select_membership_for_principal
from compose_ai_api.main import app


def test_auth_session_requires_bearer_token() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/auth/session")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer session token."


def test_clerk_organization_context_supports_compact_claims() -> None:
    organization_id, organization_role = ClerkJWTVerifier._organization_context(
        {"o": {"id": "org_compose", "rol": "admin", "slg": "compose"}}
    )

    assert organization_id == "org_compose"
    assert organization_role == "admin"


class _Principal:
    clerk_organization_id = None


class _Organization:
    def __init__(self, clerk_organization_id: str | None) -> None:
        self.clerk_organization_id = clerk_organization_id


class _Membership:
    def __init__(self, clerk_organization_id: str | None) -> None:
        self.organization = _Organization(clerk_organization_id)
        self.status = OrganizationMemberStatus.ACTIVE


def test_auth_context_uses_single_membership_when_clerk_org_claim_is_missing() -> None:
    membership = _Membership("org_compose")

    selected = _select_membership_for_principal([membership], _Principal())

    assert selected is membership

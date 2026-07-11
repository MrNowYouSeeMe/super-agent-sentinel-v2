import pytest

from app.domain.auth.models import Permission, Principal, Role
from app.domain.auth.policy import AuthorizationError, authorize


def test_provider_scope_is_enforced() -> None:
    principal = Principal(
        user_id="u1",
        role=Role.CENTRAL_OPERATIONS,
        permissions={Permission.ALERT_READ},
        provider_scopes={"bkash"},
        area_scopes={"sylhet"},
        outlet_scopes={"*"},
    )
    authorize(
        principal,
        Permission.ALERT_READ,
        provider_id="bkash",
        area_id="sylhet",
        outlet_id="OUT-1",
    )
    with pytest.raises(AuthorizationError):
        authorize(
            principal,
            Permission.ALERT_READ,
            provider_id="nagad",
            area_id="sylhet",
            outlet_id="OUT-1",
        )

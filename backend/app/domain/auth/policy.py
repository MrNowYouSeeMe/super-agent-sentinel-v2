from app.domain.auth.models import Permission, Principal, Role


class AuthorizationError(PermissionError):
    pass


def _inside(scope: set[str], value: str | None) -> bool:
    if value is None:
        return True
    return "*" in scope or value in scope


def authorize(
    principal: Principal,
    permission: Permission,
    *,
    provider_id: str | None = None,
    area_id: str | None = None,
    outlet_id: str | None = None,
) -> None:
    if principal.role == Role.ADMIN:
        return
    if permission not in principal.permissions:
        raise AuthorizationError(f"Missing permission: {permission.value}")
    if not _inside(principal.provider_scopes, provider_id):
        raise AuthorizationError("Provider scope denied")
    if not _inside(principal.area_scopes, area_id):
        raise AuthorizationError("Area scope denied")
    if not _inside(principal.outlet_scopes, outlet_id):
        raise AuthorizationError("Outlet scope denied")

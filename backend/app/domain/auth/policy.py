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


def can_read_resource(
    principal: Principal,
    *,
    resource_id: str,
    area_id: str,
    outlet_id: str,
) -> bool:
    provider_id = None if resource_id == "shared_cash" else resource_id
    try:
        authorize(
            principal,
            Permission.ALERT_READ,
            provider_id=provider_id,
            area_id=area_id,
            outlet_id=outlet_id,
        )
        return True
    except AuthorizationError:
        return False


def visible_resource_ids(
    principal: Principal,
    *,
    resource_ids: list[str],
    area_id: str,
    outlet_id: str,
) -> list[str]:
    return [
        resource_id
        for resource_id in resource_ids
        if can_read_resource(
            principal,
            resource_id=resource_id,
            area_id=area_id,
            outlet_id=outlet_id,
        )
    ]


from __future__ import annotations

import hashlib
import hmac
import json
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Any

from fastapi import Header, HTTPException, status
from pydantic import BaseModel, Field

from app.domain.auth.models import Permission, Principal, Role

LOCAL_AUTH_SECRET = b"superagent-sentinel-v2-local-demo-secret"
TOKEN_TTL_SECONDS = 12 * 60 * 60


class DemoUserProfile(BaseModel):
    profile_id: str
    user_id: str
    display_name: str
    role: Role
    permissions: list[Permission]
    provider_scopes: list[str]
    area_scopes: list[str]
    outlet_scopes: list[str]
    description: str


class DemoLoginRequest(BaseModel):
    profile_id: str = Field(min_length=2, max_length=64)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    principal: Principal
    profile: DemoUserProfile


class PrincipalView(BaseModel):
    user_id: str
    role: Role
    permissions: list[Permission]
    provider_scopes: list[str]
    area_scopes: list[str]
    outlet_scopes: list[str]


DEMO_USERS: dict[str, DemoUserProfile] = {
    "outlet-sylhet-001": DemoUserProfile(
        profile_id="outlet-sylhet-001",
        user_id="USR-OUTLET-001",
        display_name="Sylhet Outlet Operator",
        role=Role.OUTLET_OPERATOR,
        permissions=[Permission.ANALYSIS_CREATE, Permission.ALERT_READ],
        provider_scopes=["*"],
        area_scopes=["sylhet"],
        outlet_scopes=["OUT-1", "OUT-1001"],
        description="Can inspect own outlet resources but cannot assign/escalate cases.",
    ),
    "area-manager-sylhet": DemoUserProfile(
        profile_id="area-manager-sylhet",
        user_id="USR-AM-SYLHET",
        display_name="Sylhet Area Manager",
        role=Role.AREA_MANAGER,
        permissions=[
            Permission.ANALYSIS_CREATE,
            Permission.ALERT_READ,
            Permission.ALERT_ASSIGN,
            Permission.CASE_REVIEW,
        ],
        provider_scopes=["*"],
        area_scopes=["sylhet"],
        outlet_scopes=["*"],
        description="Can run combined provider analysis inside Sylhet and own review workflow.",
    ),
    "bkash-ops-sylhet": DemoUserProfile(
        profile_id="bkash-ops-sylhet",
        user_id="USR-BKASH-OPS",
        display_name="bKash Operations Viewer",
        role=Role.CENTRAL_OPERATIONS,
        permissions=[Permission.ALERT_READ, Permission.CASE_REVIEW],
        provider_scopes=["bkash"],
        area_scopes=["sylhet"],
        outlet_scopes=["*"],
        description="Can view bKash-scoped evidence plus shared-cash exposure, not competitor raw data.",
    ),
    "nagad-ops-sylhet": DemoUserProfile(
        profile_id="nagad-ops-sylhet",
        user_id="USR-NAGAD-OPS",
        display_name="Nagad Operations Viewer",
        role=Role.CENTRAL_OPERATIONS,
        permissions=[Permission.ALERT_READ, Permission.CASE_REVIEW],
        provider_scopes=["nagad"],
        area_scopes=["sylhet"],
        outlet_scopes=["*"],
        description="Can view Nagad-scoped evidence plus shared-cash exposure, not competitor raw data.",
    ),
    "risk-reviewer": DemoUserProfile(
        profile_id="risk-reviewer",
        user_id="USR-RISK-001",
        display_name="Risk Reviewer",
        role=Role.RISK_REVIEWER,
        permissions=[Permission.ALERT_READ, Permission.CASE_REVIEW, Permission.CASE_ESCALATE],
        provider_scopes=["*"],
        area_scopes=["*"],
        outlet_scopes=["*"],
        description="Can review evidence and escalate, but still cannot move funds or declare fraud.",
    ),
    "admin": DemoUserProfile(
        profile_id="admin",
        user_id="USR-ADMIN-001",
        display_name="System Admin",
        role=Role.ADMIN,
        permissions=list(Permission),
        provider_scopes=["*"],
        area_scopes=["*"],
        outlet_scopes=["*"],
        description="Full local demo access for setup and testing.",
    ),
}


def principal_from_profile(profile: DemoUserProfile) -> Principal:
    return Principal(
        user_id=profile.user_id,
        role=profile.role,
        permissions=set(profile.permissions),
        provider_scopes=set(profile.provider_scopes),
        area_scopes=set(profile.area_scopes),
        outlet_scopes=set(profile.outlet_scopes),
    )


def list_demo_users() -> list[DemoUserProfile]:
    return list(DEMO_USERS.values())


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _b64(data: bytes) -> str:
    return urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return urlsafe_b64decode((data + padding).encode("ascii"))


def _signature(payload_part: str) -> str:
    digest = hmac.new(LOCAL_AUTH_SECRET, payload_part.encode("ascii"), hashlib.sha256).digest()
    return _b64(digest)


def _payload_from_principal(principal: Principal, *, issued_at: int | None = None) -> dict[str, Any]:
    now = int(time.time()) if issued_at is None else issued_at
    return {
        "user_id": principal.user_id,
        "role": principal.role.value,
        "permissions": sorted(item.value for item in principal.permissions),
        "provider_scopes": sorted(principal.provider_scopes),
        "area_scopes": sorted(principal.area_scopes),
        "outlet_scopes": sorted(principal.outlet_scopes),
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
        "demo": True,
    }


def _principal_from_payload(payload: dict[str, Any]) -> Principal:
    return Principal(
        user_id=str(payload["user_id"]),
        role=Role(str(payload["role"])),
        permissions={Permission(item) for item in payload.get("permissions", [])},
        provider_scopes={str(item) for item in payload.get("provider_scopes", [])},
        area_scopes={str(item) for item in payload.get("area_scopes", [])},
        outlet_scopes={str(item) for item in payload.get("outlet_scopes", [])},
    )


def create_access_token(principal: Principal) -> str:
    payload_part = _b64(_json_bytes(_payload_from_principal(principal)))
    return f"{payload_part}.{_signature(payload_part)}"


def authenticate_token(token: str) -> Principal:
    try:
        payload_part, signature = token.split(".", 1)
        expected = _signature(payload_part)
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad signature")
        payload = json.loads(_unb64(payload_part).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired token")
        return _principal_from_payload(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired demo access token.",
        ) from exc


def demo_login(request: DemoLoginRequest) -> AuthTokenResponse:
    profile = DEMO_USERS.get(request.profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown demo profile.")
    principal = principal_from_profile(profile)
    return AuthTokenResponse(
        access_token=create_access_token(principal),
        expires_in_seconds=TOKEN_TTL_SECONDS,
        principal=principal,
        profile=profile,
    )


def principal_view(principal: Principal) -> PrincipalView:
    return PrincipalView(
        user_id=principal.user_id,
        role=principal.role,
        permissions=sorted(principal.permissions, key=lambda item: item.value),
        provider_scopes=sorted(principal.provider_scopes),
        area_scopes=sorted(principal.area_scopes),
        outlet_scopes=sorted(principal.outlet_scopes),
    )


def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token. Use /api/v1/auth/demo-login for local demo access.",
        )
    return authenticate_token(authorization.split(" ", 1)[1].strip())


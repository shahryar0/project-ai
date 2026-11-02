"""Local API token authentication. A role is derived from a configured secret, never a request field."""

import hmac
import os
from dataclasses import dataclass
from fastapi import Header, HTTPException


@dataclass(frozen=True)
class Actor:
    role: str
    actor_id: str
    tenant_id: str


def authenticate(authorization: str | None = Header(default=None)) -> Actor:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="A configured human bearer token is required.")
    token = authorization[7:].strip()
    configured = [("owner", os.getenv("AI_EMPLOYEE_OWNER_TOKEN", "")),
                  ("approver", os.getenv("AI_EMPLOYEE_APPROVER_TOKEN", ""))]
    for role, secret in configured:
        if secret and hmac.compare_digest(token, secret):
            return Actor(role=role, actor_id=role, tenant_id=os.getenv("AI_EMPLOYEE_TENANT_ID", "local"))
    raise HTTPException(status_code=403, detail="This identity is not authorized for human review actions.")


def require_role(actor: Actor, *roles: str) -> Actor:
    if actor.role not in roles:
        raise HTTPException(status_code=403, detail="This human role cannot perform that action.")
    return actor


def require_tenant(actor: Actor, tenant_id: str) -> str:
    if not hmac.compare_digest(actor.tenant_id, tenant_id):
        raise HTTPException(status_code=404, detail="Record not found.")
    return tenant_id

"""Human-only draft edits, approval decisions and audit reads. No scheduling or publishing routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from app.approval.service import ApprovalConflict, ApprovalService
from app.approval.revisions import run_draft_revision
from app.security.roles import Actor, authenticate, require_role, require_tenant
from app.storage.errors import RecordNotFoundError, StorageUnavailableError
from app.storage.errors import CampaignConflictError
from app.storage.factory import get_repository

router = APIRouter(tags=["Human draft review"])


class EditDraft(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    media_suggestion: str = Field(default="", max_length=2000)


class Comment(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)


class Decision(BaseModel):
    version: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    comment: str = Field(default="", max_length=2000)


def _service():
    try:
        return ApprovalService(get_repository())
    except (StorageUnavailableError, SQLAlchemyError) as exc:
        raise HTTPException(status_code=503, detail="Draft storage is unavailable.") from exc


def _invoke(call):
    try:
        return call()
    except RecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApprovalConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (StorageUnavailableError, SQLAlchemyError) as exc:
        raise HTTPException(status_code=503, detail="Draft storage is unavailable.") from exc


@router.patch("/drafts/{draft_id}")
def edit_draft(draft_id: str, body: EditDraft, tenant_id: str = Query(default="local"), actor: Actor = Depends(authenticate)):
    require_role(actor, "owner")
    require_tenant(actor, tenant_id)
    return _invoke(lambda: _service().edit(tenant_id, draft_id, body.text, body.media_suggestion, actor.actor_id))


@router.post("/drafts/{draft_id}/request-changes")
def request_changes(draft_id: str, body: Comment, tenant_id: str = Query(default="local"), actor: Actor = Depends(authenticate)):
    require_role(actor, "owner", "approver")
    require_tenant(actor, tenant_id)
    return _invoke(lambda: _service().request_changes(tenant_id, draft_id, body.comment, actor.actor_id))


@router.post("/drafts/{draft_id}/revise")
def revise_draft(draft_id: str, body: Comment, tenant_id: str = Query(default="local"), actor: Actor = Depends(authenticate)):
    require_role(actor, "owner", "approver")
    require_tenant(actor, tenant_id)
    try:
        return run_draft_revision(get_repository(), tenant_id, draft_id, body.comment)
    except RecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ApprovalConflict, CampaignConflictError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (StorageUnavailableError, SQLAlchemyError) as exc:
        raise HTTPException(status_code=503, detail="Draft storage is unavailable.") from exc
    except Exception as exc:
        # Do not echo provider messages, prompts or credentials into the API response.
        raise HTTPException(status_code=502, detail="The revision workflow could not complete. Check provider status and saved draft state.") from exc


@router.post("/drafts/{draft_id}/approve")
def approve_draft(draft_id: str, body: Decision, tenant_id: str = Query(default="local"), actor: Actor = Depends(authenticate)):
    require_role(actor, "owner", "approver")
    require_tenant(actor, tenant_id)
    return _invoke(lambda: _service().decide(tenant_id, draft_id, body.version, body.content_hash, actor.actor_id, True, body.comment))


@router.post("/drafts/{draft_id}/reject")
def reject_draft(draft_id: str, body: Decision, tenant_id: str = Query(default="local"), actor: Actor = Depends(authenticate)):
    require_role(actor, "owner", "approver")
    require_tenant(actor, tenant_id)
    return _invoke(lambda: _service().decide(tenant_id, draft_id, body.version, body.content_hash, actor.actor_id, False, body.comment))


@router.get("/audit")
def audit_events(tenant_id: str = Query(default="local"), entity_id: str | None = None, actor: Actor = Depends(authenticate)):
    require_role(actor, "owner", "approver")
    require_tenant(actor, tenant_id)
    return _invoke(lambda: _service().audit(tenant_id, entity_id))

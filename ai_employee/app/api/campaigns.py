"""Phase 1 read-only endpoints. Human approval/auth are a later phase."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from app.storage.errors import RecordNotFoundError, StorageUnavailableError
from app.storage.factory import get_repository
from app.storage.views import CampaignView, DraftView

router = APIRouter(tags=["Saved campaigns and drafts"])


def read_record(kind, record_id, tenant_id):
    try:
        repository = get_repository()
        return getattr(repository, "get_" + kind)(tenant_id, record_id)
    except RecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (StorageUnavailableError, SQLAlchemyError) as exc:
        raise HTTPException(status_code=503, detail="Draft storage is unavailable.") from exc


@router.get("/campaigns/{campaign_id}", response_model=CampaignView)
def get_campaign(campaign_id: str, tenant_id: str = Query(default="local", pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")):
    return read_record("campaign", campaign_id, tenant_id)


@router.get("/drafts/{draft_id}", response_model=DraftView)
def get_draft(draft_id: str, tenant_id: str = Query(default="local", pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")):
    return read_record("draft", draft_id, tenant_id)

"""Read-only status for a saved campaign. It has no state-changing capability."""

import json
from langchain.tools import ToolRuntime, tool
from app.context import WorkflowContext


@tool(response_format="content_and_artifact")
def get_campaign_status(campaign_id: str, runtime: ToolRuntime[WorkflowContext]) -> tuple[str, dict]:
    """Read the actual persisted campaign and draft states for the current tenant. Never changes data."""
    context = runtime.context
    if context is None or context.repository is None or context.brief is None:
        result = {"error": "No saved campaign status is available in this workflow."}
    else:
        try:
            campaign = context.repository.get_campaign(context.brief.tenant_id, campaign_id)
            result = {"campaign_id": campaign["campaign_id"], "campaign_status": campaign["status"],
                "drafts": [{"draft_id": draft["draft_id"], "platform": draft["platform"],
                    "state": draft["state"], "current_version": draft["current_version"],
                    "content_hash": draft["current"]["content_hash"]} for draft in campaign["drafts"]],
                "published": False, "connector_status": "not_connected"}
        except Exception:
            result = {"error": "Campaign status is unavailable for this tenant."}
    return json.dumps(result, ensure_ascii=False), result

"""Wire CEO -> manager tool -> content tool -> local platform preview tools."""

import json
from langchain.tools import ToolRuntime, tool
from app.agents.ceo import build_ceo
from app.agents.results import collect_result
from app.agents.social.content_writer import build_content_writer
from app.agents.social.manager import build_social_manager
from app.context import WorkflowContext, brief_with_context
from app import config
from app.briefs import handoff_error
from app.schemas import CampaignBrief


def build_hierarchy(provider: config.ModelProvider = "bedrock"):
    manager = build_social_manager(build_content_writer(provider), provider)

    @tool(response_format="content_and_artifact")
    def social_media_manager(brief: CampaignBrief, runtime: ToolRuntime[WorkflowContext], notes: str = "") -> tuple[str, dict]:
        """Delegate the unchanged authoritative CampaignBrief for content writing and saved draft previews. No publishing."""
        error = handoff_error(brief, runtime.context)
        if error:
            return json.dumps(error, ensure_ascii=False), error
        result = manager.invoke(
            {"messages": [("user", brief_with_context(notes or "Prepare this campaign.", runtime.context))]},
            context=runtime.context, config={**runtime.config, "recursion_limit": 12},
        )
        payload = collect_result(result, "social_media_manager")
        return json.dumps(payload, ensure_ascii=False), payload

    return build_ceo([social_media_manager], provider=provider)

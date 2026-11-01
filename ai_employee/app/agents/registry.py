"""Wire CEO -> manager tool -> content tool -> local platform preview tools."""

import json
from langchain.tools import ToolRuntime, tool
from app.agents.ceo import build_ceo
from app.agents.results import collect_result
from app.agents.social.content_writer import build_content_writer
from app.agents.social.manager import build_social_manager
from app.context import WorkflowContext, brief_with_context


def build_hierarchy():
    manager = build_social_manager(build_content_writer())

    @tool(response_format="content_and_artifact")
    def social_media_manager(brief: str, runtime: ToolRuntime[WorkflowContext]) -> tuple[str, dict]:
        """Delegate a complete social campaign brief to the social media manager for content writing and draft previews. No publishing."""
        result = manager.invoke(
            {"messages": [("user", brief_with_context(brief, runtime.context))]},
            context=runtime.context, config={**runtime.config, "recursion_limit": 12},
        )
        payload = collect_result(result, "social_media_manager")
        return json.dumps(payload, ensure_ascii=False), payload

    return build_ceo([social_media_manager])

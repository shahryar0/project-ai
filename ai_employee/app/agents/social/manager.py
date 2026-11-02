import json
from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool
from app.agents.results import collect_result
from app.context import WorkflowContext, brief_with_context
from app.llm import get_llm
from app.prompts.social_manager import SOCIAL_MANAGER_PROMPT
from app import config
from app.briefs import handoff_error
from app.schemas import CampaignBrief


def build_social_manager(content_agent, provider: config.ModelProvider = "bedrock"):
    @tool(response_format="content_and_artifact")
    def content_writer(brief: CampaignBrief, runtime: ToolRuntime[WorkflowContext], notes: str = "") -> tuple[str, dict]:
        """Ask the writer to draft the unchanged authoritative CampaignBrief. Use notes for creative guidance or correction issues."""
        error = handoff_error(brief, runtime.context)
        if error:
            return json.dumps(error, ensure_ascii=False), error
        result = content_agent.invoke(
            {"messages": [("user", brief_with_context(notes or "Write this campaign.", runtime.context))]},
            context=runtime.context, config={**runtime.config, "recursion_limit": 12},
        )
        payload = collect_result(result, "content_writer")
        return json.dumps(payload, ensure_ascii=False), payload

    return create_agent(
        get_llm(max_tokens=1536, provider=provider), tools=[content_writer], system_prompt=SOCIAL_MANAGER_PROMPT,
        context_schema=WorkflowContext, name="social_media_manager",
    )

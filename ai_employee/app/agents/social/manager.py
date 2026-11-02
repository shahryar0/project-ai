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
from app.agents.social.brand_guardian import build_brand_guardian, GuardianVerdict


def build_social_manager(content_agent, provider: config.ModelProvider = "bedrock"):
    guardian = build_brand_guardian(provider)
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

    @tool(response_format="content_and_artifact")
    def brand_guardian(brief: CampaignBrief, runtime: ToolRuntime[WorkflowContext]) -> tuple[str, dict]:
        """Run a read-only, schema-validated review of the saved campaign drafts. Never edits or approves."""
        error = handoff_error(brief, runtime.context)
        if error:
            return json.dumps(error, ensure_ascii=False), error
        try:
            result = guardian.invoke({"messages": [("user", brief_with_context(
                "Review the saved campaign drafts now. Return the required structured verdict.", runtime.context))]},
                context=runtime.context, config={**runtime.config, "recursion_limit": 8})
            verdict = GuardianVerdict.model_validate(result["structured_response"]).model_dump()
            artifact = {"guardian_verdict": verdict}
        except Exception:
            # Invalid schema/provider output is surfaced as a review failure, never a pass.
            artifact = {"guardian_verdict": {"verdict": "changes_needed", "issues": [],
                "review_error": "Guardian returned an invalid structured response."}}
        return json.dumps(artifact, ensure_ascii=False), artifact

    return create_agent(
        get_llm(max_tokens=1536, provider=provider), tools=[content_writer, brand_guardian], system_prompt=SOCIAL_MANAGER_PROMPT,
        context_schema=WorkflowContext, name="social_media_manager",
    )

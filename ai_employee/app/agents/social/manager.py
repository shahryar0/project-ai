import json
from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool
from app.agents.results import collect_result
from app.context import WorkflowContext, brief_with_context
from app.llm import get_llm
from app.prompts.social_manager import SOCIAL_MANAGER_PROMPT


def build_social_manager(content_agent):
    @tool(response_format="content_and_artifact")
    def content_writer(brief: str, runtime: ToolRuntime[WorkflowContext]) -> tuple[str, dict]:
        """Ask the content specialist to write and render platform-specific draft previews for the complete campaign brief."""
        result = content_agent.invoke(
            {"messages": [("user", brief_with_context(brief, runtime.context))]},
            context=runtime.context, config={**runtime.config, "recursion_limit": 12},
        )
        payload = collect_result(result, "content_writer")
        return json.dumps(payload, ensure_ascii=False), payload

    return create_agent(
        get_llm(max_tokens=1536), tools=[content_writer], system_prompt=SOCIAL_MANAGER_PROMPT,
        context_schema=WorkflowContext, name="social_media_manager",
    )

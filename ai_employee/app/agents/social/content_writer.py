from langchain.agents import create_agent
from app.context import WorkflowContext
from app.llm import get_llm
from app.prompts.content_writer import CONTENT_WRITER_PROMPT
from app.tools.facebook import preview_facebook_post
from app.tools.instagram import preview_instagram_post
from app.tools.x import preview_x_post
from app.tools.linkedin import preview_linkedin_post
from app import config


def build_content_writer(provider: config.ModelProvider = "bedrock"):
    return create_agent(
        get_llm(max_tokens=4096, provider=provider), system_prompt=CONTENT_WRITER_PROMPT,
        tools=[preview_facebook_post, preview_instagram_post, preview_x_post, preview_linkedin_post],
        context_schema=WorkflowContext, name="content_writer",
    )

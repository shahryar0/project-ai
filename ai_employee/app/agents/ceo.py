from langchain.agents import create_agent
from app.context import WorkflowContext
from app.llm import get_llm
from app.prompts.ceo import CEO_PROMPT
from app import config


def build_ceo(manager_tools: list | None = None, provider: config.ModelProvider = "bedrock"):
    return create_agent(
        get_llm(provider=provider), tools=manager_tools or [], system_prompt=CEO_PROMPT,
        context_schema=WorkflowContext, name="ceo",
    )

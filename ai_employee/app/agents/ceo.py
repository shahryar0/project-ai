from app.llm import get_llm
from app.prompts.ceo import CEO_PROMPT
from app.memory.checkpointer import get_checkpointer

try:  # newer LangChain
    from langchain.agents import create_agent

    def _build(llm, tools, prompt, checkpointer):
        return create_agent(llm, tools=tools, system_prompt=prompt,
                            checkpointer=checkpointer)
except ImportError:  # older LangGraph
    from langgraph.prebuilt import create_react_agent

    def _build(llm, tools, prompt, checkpointer):
        return create_react_agent(llm, tools=tools, prompt=prompt,
                                  checkpointer=checkpointer)


def build_ceo(manager_tools: list | None = None):
    """CEO agent. Managers are passed in as tools (empty for now)."""
    return _build(get_llm(), manager_tools or [], CEO_PROMPT, get_checkpointer())

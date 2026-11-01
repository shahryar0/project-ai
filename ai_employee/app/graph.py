"""First connection test: START -> model -> END."""

from functools import lru_cache

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.llm import get_llm


@lru_cache(maxsize=1)
def get_graph() -> CompiledStateGraph:
    """Create the model on the first chat request; no tools or memory yet."""
    model = get_llm()

    def call_model(state: MessagesState) -> dict:
        reply = model.invoke([
            SystemMessage(content="You are a helpful assistant. Answer questions clearly and briefly."),
            *state["messages"],
        ])
        return {"messages": [reply]}

    builder = StateGraph(MessagesState)
    builder.add_node("model", call_model)
    builder.add_edge(START, "model")
    builder.add_edge("model", END)
    return builder.compile()

"""The active graph is the CEO-led social content hierarchy."""

from functools import lru_cache
from app.agents.registry import build_hierarchy
from app import config


@lru_cache(maxsize=2)
def get_graph(provider: config.ModelProvider = "bedrock"):
    """Share compiled, stateless agents; context and tool artifacts stay per request."""
    return build_hierarchy(provider)

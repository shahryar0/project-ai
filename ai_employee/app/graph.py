"""The active graph is the CEO-led social content hierarchy."""

from functools import lru_cache
from app.agents.registry import build_hierarchy


@lru_cache(maxsize=1)
def get_graph():
    """Share compiled, stateless agents; context and tool artifacts stay per request."""
    return build_hierarchy()

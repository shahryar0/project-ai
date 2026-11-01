"""Builds the whole hierarchy in one place.

Today: CEO only.
NEXT:  social_manager = build_social_manager()  ->  build_ceo([social_manager_tool])
"""
from app.agents.ceo import build_ceo


def build_hierarchy():
    return build_ceo(manager_tools=[])

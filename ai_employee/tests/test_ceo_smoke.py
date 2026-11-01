import os
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_MODEL_TESTS") != "1",
    reason="Set RUN_LIVE_MODEL_TESTS=1 to enable the live Gemini CEO test",
)


def test_ceo_replies():
    from app.agents.registry import build_hierarchy
    from app.context import RunContext

    ceo = build_hierarchy()
    ctx = RunContext(tenant_id="t1", chat_id="c1")
    out = ceo.invoke({"messages": [("user", "Say hello in one sentence.")]},
                     ctx.to_config())
    assert out["messages"][-1].content

import os
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_MODEL_TESTS") != "1",
    reason="Set RUN_LIVE_MODEL_TESTS=1 to enable the live model test",
)


def test_ceo_replies():
    from app.runner import run_workflow
    from app.context import WorkflowContext

    out = run_workflow("Say hello in one sentence.", WorkflowContext())
    assert out.result["messages"][-1].content

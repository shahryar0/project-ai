from langchain.tools import ToolRuntime, tool
from app.context import WorkflowContext
from app.tools.preview import render_preview


@tool(response_format="content_and_artifact")
def preview_x_post(text: str, runtime: ToolRuntime[WorkflowContext], media_suggestion: str = "") -> tuple[str, dict]:
    """Render a local X draft preview containing the exact final post text and an optional visual idea. Does not publish or connect an account."""
    return render_preview("x", text, media_suggestion, runtime.context)

"""Carry real tool artifacts up the hierarchy without relying on model prose."""

from langchain_core.messages import AIMessage, ToolMessage
from app.schemas import PLATFORMS, PostPreview, ToolCallRecord


def collect_result(result: dict, agent: str) -> dict:
    messages = result["messages"]
    outputs = {message.tool_call_id: message for message in messages if isinstance(message, ToolMessage)}
    previews: dict[str, dict] = {}
    calls = []
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                output = outputs.get(call["id"])
                status = "incomplete" if output is None else output.status
                if status == "success":
                    status = "error" if isinstance(output.artifact, dict) and output.artifact.get("error") else "completed"
                calls.append(ToolCallRecord(agent=agent, tool=call["name"], status=status).model_dump())
        if isinstance(message, ToolMessage) and isinstance(message.artifact, dict):
            for preview in message.artifact.get("previews", []):
                validated = PostPreview.model_validate(preview)
                previous = previews.get(validated.platform)
                if previous is None or validated.version >= previous["version"]:
                    previews[validated.platform] = validated.model_dump()
            calls.extend(message.artifact.get("tool_calls", []))
    return {
        "summary": messages[-1].text.strip(),
        "previews": [previews[platform] for platform in PLATFORMS if platform in previews],
        "tool_calls": calls,
    }


def format_previews(previews: list[PostPreview]) -> str:
    sections = ["Draft posts for your review:"]
    for post in previews:
        sections.append(f"{post.platform.upper()}\n{post.text}")
        if post.media_suggestion:
            sections.append(f"Suggested visual: {post.media_suggestion}")
        sections.append(f"Saved draft: {post.draft_id}, version {post.version}")
        sections.extend(f"{issue.severity.upper()} [{issue.code}]: {issue.message}" for issue in post.qa_issues)
    sections.append("Preview only. Nothing was published; social connectors are not connected.")
    return "\n\n".join(sections)

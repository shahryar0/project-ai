from dataclasses import dataclass


@dataclass(frozen=True)
class RunContext:
    """Identity of one run. Injected by YOUR code, never chosen by the model.

    In production the backend (Express) verifies the user and sends these.
    """
    tenant_id: str
    chat_id: str
    integration_id: str | None = None

    def to_config(self) -> dict:
        """LangGraph config: thread_id = chat_id keeps each chat's memory separate."""
        return {"configurable": {
            "thread_id": self.chat_id,
            "tenant_id": self.tenant_id,
            "integration_id": self.integration_id,
        }}

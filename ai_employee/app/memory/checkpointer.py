from langgraph.checkpoint.memory import InMemorySaver


def get_checkpointer():
    """Short-term memory per chat (thread_id = chat_id).

    In-memory for now: lost when the process stops.
    LATER: swap for Postgres (PostgresSaver / AsyncPostgresSaver).
    """
    return InMemorySaver()

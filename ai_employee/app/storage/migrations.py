"""Initial, additive schema migration. Never reset a running database."""

from sqlalchemy.orm import Session
from app.storage.models import Base, SchemaVersion


def initialize_schema(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        current = session.get(SchemaVersion, 1)
        if current is None:
            session.add(SchemaVersion(id=1, version=1))
        elif current.version != 1:
            raise RuntimeError("Unsupported draft database schema version.")

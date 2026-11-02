from functools import lru_cache
from sqlalchemy.exc import SQLAlchemyError
from app import config
from app.storage.errors import StorageUnavailableError
from app.storage.sqlalchemy_repository import SQLAlchemyDraftRepository


@lru_cache(maxsize=1)
def get_repository():
    try:
        return SQLAlchemyDraftRepository(config.DATABASE_URL)
    except (SQLAlchemyError, ValueError, OSError, RuntimeError, ImportError) as exc:
        raise StorageUnavailableError("Draft storage is unavailable. Check DATABASE_URL and the database folder permissions.") from exc

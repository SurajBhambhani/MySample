from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import get_settings


settings = get_settings()

if settings.database_url:
    engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
else:
    engine = None
    SessionLocal = None


@contextmanager
def session_scope() -> Iterator[SessionLocal]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured; database access is unavailable")

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

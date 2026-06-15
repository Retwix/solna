from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from config import get_settings

settings = get_settings()

_url = settings.database_url
_connect_args: dict = {}
_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}
if _url.startswith("sqlite"):
    # Allow SQLite use from FastAPI's threadpool and (for in-memory) keep one
    # shared connection so tables created at startup are visible to requests.
    _connect_args["check_same_thread"] = False
    if ":memory:" in _url:
        _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(_url, connect_args=_connect_args, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

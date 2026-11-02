from __future__ import annotations

from collections.abc import Generator
from contextvars import ContextVar
from contextlib import asynccontextmanager

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


settings = get_settings()
_engine_kwargs: dict = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    _engine_kwargs.update(connect_args={"check_same_thread": False}, poolclass=StaticPool)
engine = create_engine(settings.database_url, **_engine_kwargs)
_default_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
session_context: ContextVar[sessionmaker | None] = ContextVar("session_context", default=None)
demo_gate_context: ContextVar = ContextVar("demo_gate_context", default=None)


@asynccontextmanager
async def demo_database_turn():
    gate = demo_gate_context.get()
    if gate is None:
        yield
    else:
        async with gate:
            yield


def SessionLocal(**kwargs) -> Session:
    return (session_context.get() or _default_sessions)(**kwargs)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

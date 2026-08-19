"""Connection factories for synchronous SQLAlchemy usage."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker


DatabaseURL = str | URL


def build_engine(database_url: DatabaseURL, *, echo: bool = False) -> Engine:
    """Build a synchronous engine without opening a connection.

    Connections are established lazily by SQLAlchemy when the returned engine
    is first used.  ``pool_pre_ping`` keeps long-lived worker processes from
    reusing connections that PostgreSQL has closed.
    """

    return create_engine(database_url, echo=echo, pool_pre_ping=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a synchronous session factory bound to ``engine``."""

    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

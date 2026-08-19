"""Declarative SQLAlchemy metadata shared by persistence models."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


# Explicit, stable names make generated migrations and database diagnostics
# deterministic across environments.
CONSTRAINT_NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all ORM models owned by this service."""

    metadata = MetaData(naming_convention=CONSTRAINT_NAMING_CONVENTION)

"""Database engine and per-request session."""
from collections.abc import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """All ORM models inherit from this; it keeps the table registry."""


def ensure_columns(bind=None) -> None:
    """Stopgap until Alembic: `create_all` doesn't alter existing tables, so add columns that are new.

    Only ADD COLUMN, idempotent, so it is safe to run on every startup.
    """
    wanted = {
        "todos": {
            "due_date": "DATE",
            "priority": "VARCHAR(6) NOT NULL DEFAULT 'medium'",
        }
    }
    bind = bind or engine
    inspector = inspect(bind)
    with bind.begin() as conn:
        for table, columns in wanted.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            if "due_date" in columns and "due_date" not in existing:
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_due_date ON {table} (due_date)"))


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    with SessionLocal() as session:
        yield session

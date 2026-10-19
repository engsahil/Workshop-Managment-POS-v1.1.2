"""Database engine, session factory and safe schema initialisation.

SQLite is the default. The engine/session factories are module-level but the
engine can be rebuilt (backup restore) via `rebind_engine()`.
PostgreSQL support: set AWP_DATABASE_URL=postgresql://user:pass@host/db —
all models use portable SQLAlchemy types, so no rewrite is needed.
"""
import logging
import os
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from .config import DATABASE_URL

log = logging.getLogger("awp.db")

_engine = None
_session_factory = None


class Base(DeclarativeBase):
    pass


def _build_engine(url: str = None):
    url = url or DATABASE_URL
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False}, pool_pre_ping=True)
    else:
        eng = create_engine(url, pool_pre_ping=True)

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, rec):
        if url.startswith("sqlite"):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return eng


def get_engine():
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


def rebind_engine(url: str = None):
    """Replace the engine (used after a database restore)."""
    global _engine, _session_factory
    dispose_engine()
    _engine = _build_engine(url)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def dispose_engine():
    global _engine, _session_factory
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
    _engine = None
    _session_factory = None


def get_db():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session():
    db = get_session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def upgrade_schema(eng) -> None:
    """Non-destructive schema migration helper for existing databases.

    Inspects existing tables/columns and applies safe additive ALTER TABLE /
    CREATE INDEX statements when upgrading an older database file in place.
    Never drops tables or deletes rows.
    """
    from sqlalchemy import inspect
    insp = inspect(eng)
    existing_tables = set(insp.get_table_names())
    # Additive column migrations: (table, column, sql_type_default)
    migrations = [
        ("sale_returns", "credit_amount_paisa", "BIGINT DEFAULT 0"),
        ("invoices", "credited_amount_paisa", "BIGINT DEFAULT 0"),
        ("invoices", "vehicle_id", "INTEGER"),
        ("vehicles", "vehicle_type", "VARCHAR(24) DEFAULT 'motorcycle'"),
        ("vehicles", "fuel_type", "VARCHAR(24)"),
        ("job_cards", "warranty_days", "INTEGER DEFAULT 0"),
        ("warranty_claims", "inspection_notes", "TEXT"),
        ("warranty_claims", "action_taken", "VARCHAR(80)"),
    ]
    with eng.begin() as conn:
        for table, col, col_def in migrations:
            if table in existing_tables:
                cols = {c["name"] for c in insp.get_columns(table)}
                if col not in cols:
                    log.info("Upgrading schema: adding %s.%s", table, col)
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"))


def init_db() -> None:
    """Create all tables if missing and run non-destructive schema upgrades."""
    from .. import models  # noqa: F401  (import all models so they register)
    eng = get_engine()
    Base.metadata.create_all(bind=eng)
    try:
        upgrade_schema(eng)
    except Exception as exc:
        log.warning("Schema upgrade check warning: %s", exc)


def db_file_path() -> str:
    url = DATABASE_URL
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "", 1)
    return ""

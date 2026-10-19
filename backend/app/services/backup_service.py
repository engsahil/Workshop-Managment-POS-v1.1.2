"""Backup / restore / data export.

- Backups are written to data/backups/ via the SQLite online-backup API.
- Restore validates the candidate file (integrity check) before replacing
  the live database, then rebinds the engine.
"""
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect

from ..core.config import BACKUP_DIR, DB_PATH
from ..core.database import get_engine, rebind_engine, dispose_engine


def _safe_name(filename: str) -> Path:
    """Reject path traversal — backups live only inside BACKUP_DIR."""
    name = Path(filename).name
    if name != filename or ".." in name:
        raise ValueError("Invalid backup filename")
    return BACKUP_DIR / name


def create_backup() -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"auto_workshop_backup_{stamp}.db"
    target = BACKUP_DIR / filename
    src = sqlite3.connect(str(DB_PATH))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    return {"filename": filename, "size_bytes": target.stat().st_size,
            "created_at": datetime.now().isoformat()}


def list_backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    out = []
    for p in sorted(BACKUP_DIR.glob("*.db"), reverse=True):
        out.append({"filename": p.name, "size_bytes": p.stat().st_size,
                    "created_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat()})
    return out


def validate_backup(filename: str) -> dict:
    path = _safe_name(filename)
    if not path.exists():
        raise ValueError("Backup file not found")
    test = Path(str(path) + ".validate")
    shutil.copy2(path, test)
    try:
        conn = sqlite3.connect(str(test))
        try:
            check = conn.execute("PRAGMA integrity_check").fetchone()[0]
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        finally:
            conn.close()
    finally:
        test.unlink(missing_ok=True)
    if check != "ok":
        raise ValueError(f"Backup integrity check failed: {check}")
    required = {"users", "customers", "products", "invoices"}
    missing = required - set(tables)
    if missing:
        raise ValueError(f"Backup is missing required tables: {', '.join(sorted(missing))}")
    return {"filename": filename, "size_bytes": path.stat().st_size,
            "tables": len(tables), "ok": True}


def save_uploaded_backup(orig_filename: str, content: bytes) -> dict:
    if not content or not content.startswith(b"SQLite format 3\x00"):
        raise ValueError("Uploaded file is not a valid SQLite database")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    import re
    safe_base = re.sub(r"[^A-Za-z0-9._-]", "_", Path(orig_filename or "backup.db").stem)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"uploaded_{safe_base}_{stamp}.db"
    target = BACKUP_DIR / filename
    target.write_bytes(content)
    try:
        info = validate_backup(filename)
        return {**info, "validation": info}
    except Exception:
        target.unlink(missing_ok=True)
        raise


def restore_backup(filename: str) -> dict:
    path = _safe_name(filename)
    info = validate_backup(filename)
    pre_backup = None
    try:
        if DB_PATH.exists():
            pre_backup = create_backup().get("filename")
    except Exception:
        pre_backup = None
    # swap the database file safely, then rebuild the engine
    dispose_engine()
    tmp = DB_PATH.with_suffix(".db.restore-tmp")
    shutil.copy2(path, tmp)
    shutil.move(str(tmp), str(DB_PATH))
    rebind_engine()
    return {"ok": True, "restored": info["filename"],
            "pre_restore_backup": pre_backup,
            "message": "Backup restored. Application data reloaded."}


def export_all() -> dict:
    """Full JSON export of every table (data export workflow)."""
    from ..core.database import get_engine
    from ..models import Base
    import app.models  # ensure registration
    engine = get_engine()
    insp = inspect(engine)
    data = {}
    with engine.connect() as conn:
        for table in insp.get_table_names():
            rows = conn.exec_driver_sql(f"SELECT * FROM {table}").mappings().all()
            data[table] = [dict(r) for r in rows]
    return {"exported_at": datetime.now().isoformat(), "tables": data}

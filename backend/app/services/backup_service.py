"""Backup / restore / data export.

- SQLite deployments: hot backup via the SQLite online-backup API; restore
  validates the candidate file (integrity + required tables) before replacing
  the live database, then rebinds the engine.
- PostgreSQL deployments: a consistent JSON snapshot of every table is written
  instead.  Restore is intentionally not performed automatically on PostgreSQL
  (that would be a destructive operation); the snapshot can be archived and
  imported with standard PostgreSQL tooling by an administrator.
"""
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import inspect

from ..core.config import BACKUP_DIR, DATABASE_URL
from ..core.database import db_file_path, get_engine, rebind_engine, dispose_engine

REQUIRED_TABLES = {"users", "customers", "products", "invoices"}
BACKUP_FORMAT = "awp-json-backup"
BACKUP_FORMAT_VERSION = 1


def is_postgres() -> bool:
    return not DATABASE_URL.startswith("sqlite")


def _safe_name(filename: str) -> Path:
    """Reject path traversal — backups live only inside BACKUP_DIR."""
    name = Path(filename).name
    if name != filename or ".." in name:
        raise ValueError("Invalid backup filename")
    return BACKUP_DIR / name


def _json_snapshot() -> dict:
    return {
        "format": BACKUP_FORMAT,
        "format_version": BACKUP_FORMAT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database": "postgresql",
        "tables": export_all()["tables"],
    }


def _validate_json_backup(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Backup is not a valid JSON snapshot") from exc
    if not isinstance(payload, dict) or payload.get("format") != BACKUP_FORMAT:
        raise ValueError("File is not an Auto Workshop JSON backup")
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("Backup is missing the tables payload")
    missing = REQUIRED_TABLES - set(tables)
    if missing:
        raise ValueError(
            f"Backup is missing required tables: {', '.join(sorted(missing))}")
    return {"filename": path.name, "size_bytes": path.stat().st_size,
            "tables": len(tables), "ok": True, "format": "json",
            "created_at": payload.get("created_at")}


def create_backup() -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if is_postgres():
        filename = f"auto_workshop_backup_{stamp}.json"
        target = BACKUP_DIR / filename
        target.write_text(json.dumps(_json_snapshot(), indent=2, default=str),
                          encoding="utf-8")
        return {"filename": filename, "size_bytes": target.stat().st_size,
                "created_at": datetime.now().isoformat(), "format": "json"}
    db_path = Path(db_file_path()) if db_file_path() else None
    if db_path is None or not db_path.exists():
        raise ValueError("SQLite database file was not found")
    filename = f"auto_workshop_backup_{stamp}.db"
    target = BACKUP_DIR / filename
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    return {"filename": filename, "size_bytes": target.stat().st_size,
            "created_at": datetime.now().isoformat(), "format": "sqlite"}


def list_backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    out = []
    files = list(BACKUP_DIR.glob("*.db")) + list(BACKUP_DIR.glob("*.json"))
    for p in sorted(files, key=lambda f: f.stat().st_mtime, reverse=True):
        out.append({"filename": p.name, "size_bytes": p.stat().st_size,
                    "created_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                    "format": "json" if p.suffix.lower() == ".json" else "sqlite"})
    return out


def validate_backup(filename: str) -> dict:
    path = _safe_name(filename)
    if not path.exists():
        raise ValueError("Backup file not found")
    if path.suffix.lower() == ".json":
        return _validate_json_backup(path)
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
    missing = REQUIRED_TABLES - set(tables)
    if missing:
        raise ValueError(f"Backup is missing required tables: {', '.join(sorted(missing))}")
    return {"filename": filename, "size_bytes": path.stat().st_size,
            "tables": len(tables), "ok": True, "format": "sqlite"}


def save_uploaded_backup(orig_filename: str, content: bytes) -> dict:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    import re
    safe_base = re.sub(r"[^A-Za-z0-9._-]", "_", Path(orig_filename or "backup").stem)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if content.startswith(b"SQLite format 3\x00"):
        filename = f"uploaded_{safe_base}_{stamp}.db"
    elif content.lstrip().startswith(b"{"):
        filename = f"uploaded_{safe_base}_{stamp}.json"
    else:
        raise ValueError("Uploaded file is not a SQLite database or JSON snapshot")
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
    if is_postgres() or info.get("format") == "json":
        raise ValueError(
            "Automatic restore is only supported on SQLite deployments. "
            "This deployment uses PostgreSQL; use the JSON snapshot for archival "
            "and restore it with standard PostgreSQL tooling.")
    pre_backup = None
    try:
        if Path(db_file_path()).exists():
            pre_backup = create_backup().get("filename")
    except Exception:
        pre_backup = None
    # swap the database file safely, then rebuild the engine
    dispose_engine()
    tmp = Path(db_file_path()).with_suffix(".db.restore-tmp")
    shutil.copy2(path, tmp)
    shutil.move(str(tmp), str(db_file_path()))
    rebind_engine()
    return {"ok": True, "restored": info["filename"],
            "pre_restore_backup": pre_backup,
            "message": "Backup restored. Application data reloaded."}


def export_all() -> dict:
    """Full JSON export of every table (data export workflow)."""
    engine = get_engine()
    insp = inspect(engine)
    data = {}
    with engine.connect() as conn:
        for table in insp.get_table_names():
            rows = conn.exec_driver_sql(f'SELECT * FROM "{table}"').mappings().all()
            data[table] = [dict(r) for r in rows]
    return {"exported_at": datetime.now().isoformat(), "tables": data}

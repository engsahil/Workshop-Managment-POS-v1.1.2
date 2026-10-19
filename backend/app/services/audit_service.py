"""Audit logging for important actions."""
import json
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog, User


def log(db: Session, *, user_id: int | None, username: str | None = None, action: str,
        entity_type: str | None = None, entity_id: Any = None,
        old_values: dict | None = None, new_values: dict | None = None,
        ip_address: str | None = None) -> None:
    try:
        if not username and user_id:
            u = db.get(User, user_id)
            if u:
                username = u.username
        entry = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            old_values=json.dumps(old_values, default=str) if old_values else None,
            new_values=json.dumps(new_values, default=str) if new_values else None,
            ip_address=ip_address,
        )
        db.add(entry)
        db.flush()
        db.commit()
    except Exception:
        # Audit logging must never break the business action
        db.rollback()


def _safe(d: dict | None, limit: int = 2000) -> dict | None:
    if not d:
        return None
    s = json.dumps(d, default=str)
    if len(s) > limit:
        return {"_truncated": True}
    return d

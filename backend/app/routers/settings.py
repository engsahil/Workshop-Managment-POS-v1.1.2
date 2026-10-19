"""Settings, legal pages, notifications, audit log, backups, file serving."""
import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from ..core.config import DATA_DIR
from ..core.constants import ROLE_ADMIN
from ..core.deps import get_current_user, get_db, require_admin
from ..models import AuditLog, Notification, User
from ..schemas.settings import BusinessSettingsIn, LegalIn, LegalOut
from ..services import backup_service, notification_service
from ..services.audit_service import log as audit_log
from ..services.settings_service import (get_business_settings,
                                           save_business_settings)

router = APIRouter(prefix="/api", tags=["settings"])


# ---------------------------------------------------------------- business settings
@router.get("/settings/business")
def business_settings(db=Depends(get_db), _: User = Depends(get_current_user)):
    return get_business_settings(db)


@router.put("/settings/business")
def update_business_settings(payload: BusinessSettingsIn, db=Depends(get_db),
                               admin: User = Depends(require_admin)):
    data = payload.model_dump(exclude_unset=True)
    logo = data.pop("logo_file", None)
    out = save_business_settings(db, data)
    audit_log(db, user_id=admin.id, username=admin.username,
              action="settings.business.update")
    return out


@router.post("/settings/logo")
async def upload_logo(request: Request, admin: User = Depends(require_admin)):
    form = await request.form()
    file = form.get("logo")
    if not file or not getattr(file, "filename", None):
        raise HTTPException(status_code=400, detail="No logo file provided")
    ext = Path(file.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        raise HTTPException(status_code=400,
                            detail="Logo must be a PNG, JPG, GIF or WebP image")
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo must be under 2 MB")
    # validate image magic bytes
    sig = content[:8]
    ok = (sig.startswith(b"\x89PNG") or sig.startswith(b"\xff\xd8")
          or sig.startswith(b"GIF8") or sig.startswith(b"RIFF"))
    if not ok:
        raise HTTPException(status_code=400, detail="File is not a valid image")
    uploads = DATA_DIR / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    name = f"logo_{int(time.time())}{ext}"
    (uploads / name).write_bytes(content)
    return {"ok": True, "path": f"uploads/{name}"}


# ---------------------------------------------------------------- legal pages
LEGAL_KEYS = ("privacy_policy", "terms_conditions")

DEFAULT_PRIVACY = """# Privacy Policy (template — review and adapt for your business)

This Auto Workshop Management POS stores customer names, phone numbers,
addresses, vehicle details and transaction history locally on the workshop
computer. Data never leaves the device unless you export or back it up
yourlyourself.

- Customer data is collected only to run the business (billing, job cards,
  vehicle history).
- Access is restricted to authorised staff accounts.
- Backups are stored locally in the data/backups folder; protect them
  accordingly.
- This template must be reviewed and adapted to your actual practices and
  applicable Pakistani law before use.
"""

DEFAULT_TERMS = """# Terms & Conditions (template — review and adapt for your business)

- Estimates are indicative and may change after inspection; final billing
  requires customer approval where configured.
- Payment is due on delivery unless a credit arrangement has been approved
  by management.
- Warranty on parts follows the supplier/manufacturer warranty terms
  recorded in the system; labour warranty is set per job by the workshop.
- Vehicles are accepted for repair at the owner's risk; existing damage is
  recorded at check-in.
- The workshop is not responsible for delays caused by parts availability.
- This template must be reviewed and adapted to your actual business terms
  before use.
"""


@router.get("/settings/legal/{key}")
def get_legal(key: str, db=Depends(get_db)):
    if key not in LEGAL_KEYS:
        raise HTTPException(status_code=404, detail="Unknown legal document")
    from ..services.settings_service import get_setting
    content = get_setting(db, f"legal.{key}")
    return {"key": key,
            "title": "Privacy Policy" if key == "privacy_policy" else "Terms & Conditions",
            "content": content or (DEFAULT_PRIVACY if key == "privacy_policy"
                                   else DEFAULT_TERMS),
            "is_default": content is None}


@router.put("/settings/legal/{key}")
def update_legal(key: str, payload: LegalIn, db=Depends(get_db),
                 admin: User = Depends(require_admin)):
    if key not in LEGAL_KEYS:
        raise HTTPException(status_code=404, detail="Unknown legal document")
    from ..services.settings_service import set_setting
    set_setting(db, f"legal.{key}", payload.content)
    db.commit()
    audit_log(db, user_id=admin.id, username=admin.username,
              action="settings.legal.update", entity_type="legal", entity_id=key)
    return {"ok": True}


# ---------------------------------------------------------------- notifications
@router.get("/settings/notifications")
def get_notification_settings(db=Depends(get_db),
                              _: User = Depends(get_current_user)):
    return notification_service.get_notification_prefs(db)


@router.put("/settings/notifications")
def update_notification_settings(payload: dict, db=Depends(get_db),
                                 admin: User = Depends(require_admin)):
    out = notification_service.save_notification_prefs(db, payload)
    audit_log(db, user_id=admin.id, username=admin.username,
              action="settings.notifications.update", new_values=out)
    return out


@router.get("/reports/daily-summary")
def get_reports_daily_summary(date: str | None = None, db=Depends(get_db),
                              _: User = Depends(get_current_user)):
    try:
        return notification_service.daily_summary_data(db, date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reports/daily-summary/notify")
def post_reports_daily_summary_notify(date: str | None = None,
                                      payload: dict | None = None,
                                      db=Depends(get_db),
                                      _: User = Depends(get_current_user)):
    target_date = date or ((payload or {}).get("date") if isinstance(payload, dict) else None)
    try:
        summary, notif = notification_service.generate_daily_summary_notification(db, target_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "ok": True,
        "summary": summary,
        "notification_id": notif.id if notif else None,
    }


@router.get("/notifications")
def notifications(limit: int = 50, unread_only: bool = False,
                  db=Depends(get_db), _: User = Depends(get_current_user)):
    rows = notification_service.list_notifications(db, limit=limit,
                                                       unread_only=unread_only)
    return {"items": [
        {"id": n.id, "type": n.type, "title": n.title, "message": n.message,
         "related_type": n.related_type, "related_id": n.related_id,
         "is_read": n.is_read,
         "created_at": n.created_at.isoformat() if n.created_at else None}
        for n in rows],
        "unread_count": notification_service.unread_count(db)}


@router.post("/notifications/read")
def mark_read(payload: dict, db=Depends(get_db),
              _: User = Depends(get_current_user)):
    ids = [int(i) for i in payload.get("ids", [])][:100]
    return {"ok": True, "marked": notification_service.mark_read(db, ids)}


@router.post("/notifications/read-all")
def mark_all_read(db=Depends(get_db), _: User = Depends(get_current_user)):
    return {"ok": True, "marked": notification_service.mark_all_read(db)}


@router.get("/notifications/daily-summary")
def get_daily_summary(date: str | None = None, db=Depends(get_db),
                      _: User = Depends(get_current_user)):
    try:
        return notification_service.daily_summary_data(db, date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/notifications/daily-summary")
def create_daily_summary(payload: dict | None = None, db=Depends(get_db),
                         _: User = Depends(get_current_user)):
    target_date = (payload or {}).get("date") if isinstance(payload, dict) else None
    try:
        summary, notif = notification_service.generate_daily_summary_notification(db, target_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "ok": True,
        "summary": summary,
        "notification_id": notif.id if notif else None,
    }


# ---------------------------------------------------------------- audit log
@router.get("/audit")
def audit_log_list(action: str | None = None, entity_type: str | None = None,
                   user_id: int | None = None, page: int = 1,
                   page_size: int = 50, db=Depends(get_db),
                   _: User = Depends(require_admin)):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        q = q.filter(AuditLog.entity_type.ilike(f"%{entity_type}%"))
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    total = q.count()
    rows = (q.order_by(AuditLog.id.desc())
            .offset((max(1, page) - 1) * 50).limit(50).all())
    return {"items": [{
        "id": a.id, "user_id": a.user_id, "username": a.username,
        "action": a.action, "entity_type": a.entity_type,
        "entity_id": a.entity_id, "old_values": a.old_values,
        "new_values": a.new_values, "ip_address": a.ip_address,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in rows], "total": total}


# ---------------------------------------------------------------- backups
@router.post("/backups")
def create_backup(db=Depends(get_db), admin: User = Depends(require_admin)):
    try:
        res = backup_service.create_backup()
        notification_service.backup_notification(db, res["filename"], action="created", ok=True)
        audit_log(db, user_id=admin.id, username=admin.username,
                  action="backup.create", entity_type="backup", entity_id=res["filename"])
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {e}")


@router.post("/backups/upload")
async def upload_backup(request: Request, db=Depends(get_db),
                        admin: User = Depends(require_admin)):
    form = await request.form()
    file = form.get("file")
    if not file or not getattr(file, "filename", None):
        raise HTTPException(status_code=400, detail="No backup file provided")
    content = await file.read()
    try:
        info = backup_service.save_uploaded_backup(file.filename, content)
        audit_log(db, user_id=admin.id, username=admin.username,
                  action="backup.upload", entity_type="backup", entity_id=info["filename"])
        return info
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/backups")
def list_backups(_: User = Depends(require_admin)):
    return {"items": backup_service.list_backups()}


@router.get("/backups/{filename}/download")
def download_backup(filename: str, _: User = Depends(require_admin)):
    try:
        path = backup_service._safe_name(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")
    return FileResponse(path, filename=filename,
                        media_type="application/octet-stream")


@router.post("/backups/validate")
def validate_backup(filename: str, db=Depends(get_db),
                    _: User = Depends(require_admin)):
    try:
        return backup_service.validate_backup(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/backups/{filename}/restore")
def restore_backup(filename: str, db=Depends(get_db),
                   admin: User = Depends(require_admin)):
    try:
        res = backup_service.restore_backup(filename)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {e}")


@router.delete("/backups/{filename}")
def delete_backup(filename: str, _: User = Depends(require_admin)):
    try:
        path = backup_service._safe_name(filename)
        if path.exists():
            path.unlink()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return {"ok": True}


# ---------------------------------------------------------------- data export
@router.get("/export")
def export_data(_: User = Depends(require_admin)):
    return backup_service.export_all()


# ---------------------------------------------------------------- uploaded files
@router.get("/files/uploads/{subpath:path}")
def serve_upload(subpath: str):
    target = (DATA_DIR / "uploads" / subpath).resolve()
    root = (DATA_DIR / "uploads").resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target)

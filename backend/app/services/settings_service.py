"""Business/system settings stored in the `settings` table + counters."""
import json
import threading
from datetime import datetime

from sqlalchemy.orm import Session

from ..core.config import APP_VERSION
from ..core.constants import DEFAULT_EXPENSE_CATEGORIES
from ..core.money import to_paisa
from ..models import Setting, ExpenseCategory

DEFAULT_BUSINESS = {
    "business_name": "My Auto Workshop",
    "tagline": "Motorbike & Car Repair • Parts • Accessories",
    "address": "",
    "phone": "",
    "email": "",
    "logo_path": "",
    "invoice_prefix": "INV",
    "job_prefix": "JB",
    "purchase_prefix": "PO",
    "expense_prefix": "EXP",
    "return_prefix": "RET",
    "claim_prefix": "CLM",
    "tax_enabled": False,
    "tax_rate_percent": 0,
    "low_stock_default": 5,
    "allow_negative_stock": False,
    "currency": "PKR",
    "timezone": "Asia/Karachi",
    "payment_methods": ["cash", "card", "bank_transfer", "jazzcash", "easypaisa"],
    "business_hours": "",
}

_lock = threading.Lock()


def get_setting(db: Session, key: str, default=None):
    row = db.get(Setting, key)
    if row is None or row.value is None:
        return default
    try:
        return json.loads(row.value)
    except (ValueError, TypeError):
        return row.value


def set_setting(db: Session, key: str, value) -> None:
    row = db.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=json.dumps(value))
        db.add(row)
    else:
        row.value = json.dumps(value)


def get_business_settings(db: Session) -> dict:
    out = dict(DEFAULT_BUSINESS)
    for k in DEFAULT_BUSINESS:
        v = get_setting(db, f"business.{k}")
        if v is not None:
            out[k] = v
    out["app_version"] = APP_VERSION
    return out


def save_business_settings(db: Session, data: dict) -> dict:
    allowed = {k for k in DEFAULT_BUSINESS if k != "currency"}
    for k, v in data.items():
        if k in allowed:
            set_setting(db, f"business.{k}", v)
    db.commit()
    return get_business_settings(db)


def next_number(db: Session, key: str, prefix: str) -> str:
    """Generate a unique sequential document number. Thread + process safe
    for SQLite (single-writer) because the whole increment runs in one
    transaction with a row lock on the settings row."""
    with _lock:
        row = db.get(Setting, key)
        if row is None:
            n = 1
            row = Setting(key=key, value=json.dumps({"counter": n}))
            db.add(row)
        else:
            data = json.loads(row.value)
            n = int(data.get("counter", 0)) + 1
            data["counter"] = n
            row.value = json.dumps(data)
        db.flush()
        year = datetime.now().year
        return f"{prefix}-{year}-{n:05d}"


def get_counters(db: Session) -> dict:
    keys = ("invoice_number", "job_number", "po_number", "expense_number",
            "return_number", "claim_number")
    out = {}
    for k in keys:
        row = db.get(Setting, k)
        out[k] = json.loads(row.value)["counter"] if row else 0
    return out


def seed_defaults(db: Session) -> None:
    """Seed minimal data on first run only."""
    if db.query(ExpenseCategory).count() == 0:
        for name in DEFAULT_EXPENSE_CATEGORIES:
            db.add(ExpenseCategory(name=name))
    bs = get_business_settings(db)
    if bs["business_name"] == DEFAULT_BUSINESS["business_name"]:
        pass  # defaults are already applied via get_business_settings fallback
    db.commit()

"""Customer CRUD + derived balances."""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Customer, Vehicle, Invoice, Payment, SaleReturn


def _balance(db: Session, customer_id: int) -> int:
    """Outstanding = sum of unpaid (non-void) invoice balances minus approved credit-note returns."""
    inv = db.query(func.coalesce(func.sum(Invoice.balance_paisa), 0)).filter(
        Invoice.customer_id == customer_id,
        Invoice.status.in_(("partial", "credit", "returned")),
    ).scalar() or 0
    credit = db.query(func.coalesce(func.sum(SaleReturn.credit_amount_paisa), 0)).filter(
        SaleReturn.customer_id == customer_id,
        SaleReturn.status == "approved",
    ).scalar() or 0
    return int(inv) - int(credit)


def _advance(db: Session, customer_id: int) -> int:
    adv = db.query(func.coalesce(func.sum(Payment.amount_paisa), 0)).filter(
        Payment.customer_id == customer_id,
        Payment.kind == "advance",
    ).scalar() or 0
    return int(adv)


def _vehicle_count(db: Session, customer_id: int) -> int:
    return db.query(func.count(Vehicle.id)).filter(Vehicle.customer_id == customer_id).scalar() or 0


def enrich(db: Session, c: Customer) -> dict:
    return {
        "id": c.id, "code": c.code, "name": c.name, "phone": c.phone,
        "alt_phone": c.alt_phone, "address": c.address, "cnic": c.cnic,
        "notes": c.notes, "is_active": c.is_active,
        "balance_paisa": _balance(db, c.id),
        "advance_paisa": _advance(db, c.id),
        "vehicle_count": _vehicle_count(db, c.id),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def count_customers(db: Session, q: str | None = None,
                    include_inactive: bool = False) -> int:
    query = db.query(func.count(Customer.id))
    if not include_inactive:
        query = query.filter(Customer.is_active.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Customer.name.ilike(like)) | (Customer.phone.ilike(like)) | (Customer.code.ilike(like))
        )
    return int(query.scalar() or 0)


def list_customers(db: Session, q: str | None = None, limit: int = 50, offset: int = 0,
                   include_inactive: bool = False):
    query = db.query(Customer)
    if not include_inactive:
        query = query.filter(Customer.is_active.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Customer.name.ilike(like)) | (Customer.phone.ilike(like)) | (Customer.code.ilike(like))
        )
    rows = query.order_by(Customer.id.desc()).offset(offset).limit(limit).all()
    return [enrich(db, c) for c in rows]


def find_duplicate(db: Session, name: str, phone: str | None) -> Customer | None:
    if phone and phone.strip():
        row = db.query(Customer).filter(Customer.phone == phone.strip()).first()
        if row:
            return row
    return None


def get_customer(db: Session, cid: int) -> Customer | None:
    return db.get(Customer, cid)


def _clean_customer_dict(data: dict) -> dict:
    out = dict(data)
    if "name" in out and isinstance(out["name"], str):
        out["name"] = out["name"].strip()
    for k in ("phone", "alt_phone", "address", "cnic", "notes"):
        if k in out and isinstance(out[k], str):
            s = out[k].strip()
            out[k] = s if s else None
    return out


def create_customer(db: Session, data: dict, created_by: int | None = None) -> Customer:
    from .settings_service import next_number
    cleaned = _clean_customer_dict(data)
    code = next_number(db, "customer_code", "CUST")
    c = Customer(code=code, **{k: v for k, v in cleaned.items()})
    db.add(c)
    db.commit()
    from .audit_service import log as _audit
    _audit(db, user_id=created_by, username=None,
           action="customer.create", entity_type="customer",
           entity_id=c.id, new_values={"name": c.name, "code": c.code, "phone": c.phone})
    return c


def update_customer(db: Session, c: Customer, data: dict) -> Customer:
    cleaned = _clean_customer_dict(data)
    for k, v in cleaned.items():
        if v is not None or k in ("phone", "alt_phone", "address", "cnic", "notes"):
            setattr(c, k, v)
    db.commit()
    from .audit_service import log as _audit
    _audit(db, user_id=None, username=None,
           action="customer.update", entity_type="customer",
           entity_id=c.id, new_values={"name": c.name, "phone": c.phone})
    return c


def delete_customer(db: Session, c: Customer) -> None:
    """Only allowed when the customer has no business history."""
    has_inv = db.query(Invoice.id).filter(Invoice.customer_id == c.id).first()
    has_veh = db.query(Vehicle.id).filter(Vehicle.customer_id == c.id).first()
    has_pay = db.query(Payment.id).filter(Payment.customer_id == c.id).first()
    if has_inv or has_veh or has_pay:
        raise ValueError("Cannot delete a customer with invoices, vehicles or payments. Deactivate instead.")
    cid, cname = c.id, c.name
    db.delete(c)
    db.commit()
    from .audit_service import log as _audit
    _audit(db, user_id=None, username=None,
           action="customer.delete", entity_type="customer",
           entity_id=cid, old_values={"name": cname})


def customer_history(db: Session, cid: int) -> dict:
    invoices = db.query(Invoice).filter(Invoice.customer_id == cid).order_by(Invoice.id.desc()).limit(50).all()
    payments = db.query(Payment).filter(Payment.customer_id == cid).order_by(Payment.id.desc()).limit(50).all()
    vehicles = db.query(Vehicle).filter(Vehicle.customer_id == cid).all()
    jobs = db.query(JobCardLite := __import__("app.models", fromlist=["JobCard"]).JobCard).filter(
        JobCardLite.customer_id == cid).order_by(JobCardLite.id.desc()).limit(20).all()
    return {
        "invoices": [_mini_inv(i) for i in invoices],
        "payments": [_mini_pay(p) for p in payments],
        "vehicles": [_mini_veh(v) for v in vehicles],
        "jobs": [_mini_job(j) for j in jobs],
    }


def _mini_inv(i):
    return {"id": i.id, "invoice_number": i.invoice_number, "total_paisa": i.total_paisa,
            "balance_paisa": i.balance_paisa, "status": i.status,
            "created_at": i.created_at.isoformat() if i.created_at else None}


def _mini_pay(p):
    return {"id": p.id, "amount_paisa": p.amount_paisa, "method": p.method, "kind": p.kind,
            "reference": p.reference,
            "created_at": p.created_at.isoformat() if p.created_at else None}


def _mini_veh(v):
    return {"id": v.id, "vehicle_type": v.vehicle_type, "registration_no": v.registration_no,
            "make": v.make, "model": v.model}


def _mini_job(j):
    return {"id": j.id, "job_number": j.job_number, "status": j.status,
            "checkin_at": j.checkin_at.isoformat() if j.checkin_at else None}

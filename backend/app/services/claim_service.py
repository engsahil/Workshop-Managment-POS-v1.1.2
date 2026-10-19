"""Warranty claims workflow with coverage validation and notifications."""
from datetime import timedelta
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.dates import ensure_datetime
from ..models import (
    Customer,
    Invoice,
    JobCard,
    Product,
    Service as ServiceModel,
    Vehicle,
    WarrantyClaim,
)
from ..services import audit_service, notification_service
from ..services.settings_service import next_number


def list_claims(
    db: Session,
    q: str | None = None,
    status: str | None = None,
    customer_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
):
    query = db.query(WarrantyClaim)
    if status:
        query = query.filter(WarrantyClaim.status == status)
    if customer_id:
        query = query.filter(WarrantyClaim.customer_id == customer_id)
    if q:
        like = f"%{q.strip()}%"
        cust_ids = [
            r[0]
            for r in db.query(Customer.id)
            .filter((Customer.name.ilike(like)) | (Customer.phone.ilike(like)))
            .all()
        ]
        veh_ids = [
            r[0]
            for r in db.query(Vehicle.id)
            .filter(Vehicle.registration_no.ilike(like))
            .all()
        ]
        conds = [
            WarrantyClaim.claim_number.ilike(like),
            WarrantyClaim.description.ilike(like),
            WarrantyClaim.resolution.ilike(like),
        ]
        if cust_ids:
            conds.append(WarrantyClaim.customer_id.in_(cust_ids))
        if veh_ids:
            conds.append(WarrantyClaim.vehicle_id.in_(veh_ids))
        query = query.filter(or_(*conds))
    total = query.count()
    rows = query.order_by(WarrantyClaim.id.desc()).offset(offset).limit(limit).all()
    return [claim_out(db, c) for c in rows], total


def claim_out(db: Session, c: WarrantyClaim) -> dict:
    cust = db.get(Customer, c.customer_id) if c.customer_id else None
    veh = db.get(Vehicle, c.vehicle_id) if c.vehicle_id else None
    prod = db.get(Product, c.product_id) if c.product_id else None
    svc = db.get(ServiceModel, c.service_id) if c.service_id else None
    inv = db.get(Invoice, c.invoice_id) if c.invoice_id else None
    job = db.get(JobCard, c.job_id) if c.job_id else None

    expiry_date = None
    is_within_warranty = None
    if c.purchase_date and (c.warranty_days or 0) > 0:
        exp_dt = c.purchase_date + timedelta(days=int(c.warranty_days))
        expiry_date = exp_dt.date().isoformat()
        ref_dt = c.claim_date or c.created_at
        if ref_dt:
            is_within_warranty = ref_dt.date() <= exp_dt.date()

    return {
        "id": c.id,
        "claim_number": c.claim_number,
        "customer_id": c.customer_id,
        "customer_name": cust.name if cust else None,
        "customer_phone": cust.phone if cust else None,
        "vehicle_id": c.vehicle_id,
        "vehicle_label": (
            f"{veh.registration_no or ''} {veh.make or ''} {veh.model or ''}".strip()
            if veh
            else None
        ),
        "invoice_id": c.invoice_id,
        "invoice_number": inv.invoice_number if inv else None,
        "job_id": c.job_id,
        "job_number": job.job_number if job else None,
        "item_type": c.item_type,
        "product_id": c.product_id,
        "product_name": prod.name if prod else None,
        "service_id": c.service_id,
        "service_name": svc.name if svc else None,
        "purchase_date": c.purchase_date.isoformat() if c.purchase_date else None,
        "warranty_days": c.warranty_days,
        "warranty_expiry_date": expiry_date,
        "is_within_warranty": is_within_warranty,
        "claim_date": c.claim_date.isoformat() if c.claim_date else None,
        "description": c.description,
        "inspection_notes": getattr(c, "inspection_notes", None),
        "action_taken": getattr(c, "action_taken", None),
        "status": c.status,
        "resolution": c.resolution,
        "cost_paisa": c.cost_paisa,
        "refund_amount_paisa": c.refund_amount_paisa,
        "created_by": c.created_by,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def create_claim(db: Session, data: dict, user_id: int | None = None) -> WarrantyClaim:
    cleaned = dict(data)
    if cleaned.get("customer_id") and not db.get(Customer, cleaned["customer_id"]):
        raise ValueError("Customer does not exist")
    if cleaned.get("vehicle_id") and not db.get(Vehicle, cleaned["vehicle_id"]):
        raise ValueError("Vehicle does not exist")
    inv = db.get(Invoice, cleaned["invoice_id"]) if cleaned.get("invoice_id") else None
    if cleaned.get("invoice_id") and not inv:
        raise ValueError("Invoice does not exist")
    job = db.get(JobCard, cleaned["job_id"]) if cleaned.get("job_id") else None
    if cleaned.get("job_id") and not job:
        raise ValueError("Job card does not exist")
    prod = db.get(Product, cleaned["product_id"]) if cleaned.get("product_id") else None
    if cleaned.get("product_id") and not prod:
        raise ValueError("Product does not exist")
    svc = db.get(ServiceModel, cleaned["service_id"]) if cleaned.get("service_id") else None
    if cleaned.get("service_id") and not svc:
        raise ValueError("Service does not exist")

    if not cleaned.get("customer_id"):
        if inv and inv.customer_id:
            cleaned["customer_id"] = inv.customer_id
        elif job and job.customer_id:
            cleaned["customer_id"] = job.customer_id
    if not cleaned.get("vehicle_id"):
        if inv and inv.vehicle_id:
            cleaned["vehicle_id"] = inv.vehicle_id
        elif job and job.vehicle_id:
            cleaned["vehicle_id"] = job.vehicle_id

    if cleaned.get("purchase_date") is not None:
        cleaned["purchase_date"] = ensure_datetime(cleaned["purchase_date"], default_now=False)
    else:
        if inv and inv.created_at:
            cleaned["purchase_date"] = inv.created_at
        elif job and (job.completed_at or job.checkin_at):
            cleaned["purchase_date"] = job.completed_at or job.checkin_at

    if not cleaned.get("warranty_days"):
        if prod and prod.warranty_days:
            cleaned["warranty_days"] = prod.warranty_days
        elif job and job.warranty_days:
            cleaned["warranty_days"] = job.warranty_days

    c = WarrantyClaim(
        claim_number=next_number(db, "claim_number", "CLM"),
        created_by=user_id,
        **cleaned,
    )
    db.add(c)
    db.commit()
    audit_service.log(
        db,
        user_id=user_id,
        username=None,
        action="claim.create",
        entity_type="claim",
        entity_id=c.id,
        new_values={"claim_number": c.claim_number, "status": c.status},
    )
    notification_service.warranty_claim_notification(db, c, is_new=True)
    return c


def update_claim(db: Session, c: WarrantyClaim, data: dict, user_id: int | None = None) -> WarrantyClaim:
    old_status = c.status
    for k, v in data.items():
        if k == "purchase_date" and v is not None:
            v = ensure_datetime(v, default_now=False)
        if v is not None:
            setattr(c, k, v)
    db.commit()
    audit_service.log(
        db,
        user_id=user_id,
        username=None,
        action="claim.update",
        entity_type="claim",
        entity_id=c.id,
        old_values={"status": old_status},
        new_values=data,
    )
    if c.status != old_status or data.get("resolution"):
        notification_service.warranty_claim_notification(db, c, is_new=False)
    return c

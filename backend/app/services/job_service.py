"""Workshop job cards: creation, estimates, approvals, status workflow,
labor services, parts consumption, history and notifications."""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.constants import JOB_STATUSES, JOB_TRANSITIONS, STOCK_JOB_CONSUME, STOCK_JOB_RESTORE
from ..models import (JobCard, JobService, JobPart, JobHistory, Mechanic,
                      Customer, Vehicle, Service as ServiceModel, Product,
                      Invoice)
from ..services import inventory_service, notification_service
from ..services.settings_service import next_number
from ..services.inventory_service import apply_stock
from ..core.dates import ensure_datetime, range_utc


ACTIVE_JOB_STATUSES = ("received", "inspection", "awaiting_approval", "approved",
                       "in_progress", "waiting_for_parts", "on_hold", "completed",
                       "ready_for_delivery")


# ---------------------------------------------------------------- helpers
def job_out(db: Session, j: JobCard) -> dict:
    cust = db.get(Customer, j.customer_id)
    veh = db.get(Vehicle, j.vehicle_id)
    mech = db.get(Mechanic, j.mechanic_id) if j.mechanic_id else None
    inv = db.get(Invoice, j.invoice_id) if j.invoice_id else None
    return {
        "id": j.id, "job_number": j.job_number,
        "customer_id": j.customer_id, "customer_name": cust.name if cust else None,
        "customer_phone": cust.phone if cust else None,
        "customer_address": cust.address if cust else None,
        "vehicle_id": j.vehicle_id,
        "vehicle_label": _veh_label(veh),
        "registration_no": veh.registration_no if veh else None,
        "vehicle_type": veh.vehicle_type if veh else None,
        "vehicle_make": veh.make if veh else None,
        "vehicle_model": veh.model if veh else None,
        "checkin_at": j.checkin_at.isoformat() if j.checkin_at else None,
        "odometer": j.odometer, "reported_issue": j.reported_issue,
        "complaint": j.complaint, "inspection": j.inspection,
        "vehicle_condition": j.vehicle_condition,
        "existing_damage": j.existing_damage, "fuel_level": j.fuel_level,
        "mechanic_id": j.mechanic_id, "mechanic_name": mech.name if mech else None,
        "mechanic_phone": mech.phone if mech else None,
        "est_labor_paisa": j.est_labor_paisa, "est_parts_paisa": j.est_parts_paisa,
        "est_total_paisa": j.est_labor_paisa + j.est_parts_paisa,
        "est_completion_date": j.est_completion_date.isoformat() if j.est_completion_date else None,
        "actual_completion_date": j.completed_at.isoformat() if j.completed_at else None,
        "priority": j.priority, "internal_notes": j.internal_notes,
        "customer_notes": j.customer_notes, "status": j.status,
        "approval_status": j.approval_status,
        "invoice_id": j.invoice_id,
        "invoice_number": inv.invoice_number if inv else None,
        "warranty_days": j.warranty_days,
        "actual_labor_paisa": j.actual_labor_paisa,
        "actual_parts_paisa": j.actual_parts_paisa,
        "actual_total_paisa": j.actual_labor_paisa + j.actual_parts_paisa,
        "created_by": j.created_by,
        "created_at": j.checkin_at.isoformat() if j.checkin_at else None,
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
    }


def _veh_label(v):
    if not v:
        return None
    return " ".join(x for x in [v.registration_no, v.make, v.model] if x)


def services_out(db: Session, j: JobCard) -> list[dict]:
    out = []
    for s in j.services:
        out.append({
            "id": s.id, "service_id": s.service_id,
            "service_name": (db.get(ServiceModel, s.service_id).name
                             if s.service_id and db.get(ServiceModel, s.service_id) else None),
            "description": s.description, "quantity": s.quantity,
            "unit_charge_paisa": s.unit_charge_paisa,
            "discount_paisa": s.discount_paisa,
            "line_total_paisa": s.line_total_paisa,
            "mechanic_id": s.mechanic_id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return out


def parts_out(db: Session, j: JobCard) -> list[dict]:
    out = []
    for p in j.parts:
        prod = db.get(Product, p.product_id)
        out.append({
            "id": p.id, "product_id": p.product_id,
            "product_name": prod.name if prod else None,
            "sku": prod.sku if prod else None,
            "quantity": p.quantity, "unit_price_paisa": p.unit_price_paisa,
            "line_total_paisa": p.line_total_paisa,
            "stock_deducted": p.stock_deducted,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return out


def history_out(j: JobCard) -> list[dict]:
    return [{"id": h.id, "from_status": h.from_status, "to_status": h.to_status,
             "notes": h.notes, "created_by": h.created_by,
             "created_at": h.created_at.isoformat() if h.created_at else None}
            for h in j.history]


# ---------------------------------------------------------------- CRUD
def list_jobs(db: Session, q: str | None = None, status: str | None = None,
              mechanic_id: int | None = None, customer_id: int | None = None,
              vehicle_id: int | None = None, date_from: str | None = None,
              date_to: str | None = None, limit: int = 50, offset: int = 0):
    date_from, date_to = range_utc(date_from, date_to)
    query = db.query(JobCard)
    if q:
        like = f"%{q}%"
        cust_ids = [r[0] for r in db.query(Customer.id).filter(
            (Customer.name.ilike(like)) | (Customer.phone.ilike(like))).all()]
        veh_ids = [r[0] for r in db.query(Vehicle.id).filter(
            Vehicle.registration_no.ilike(like)).all()]
        from sqlalchemy import or_
        conds = [
            JobCard.job_number.ilike(like),
            JobCard.reported_issue.ilike(like),
            JobCard.complaint.ilike(like),
        ]
        if cust_ids:
            conds.append(JobCard.customer_id.in_(cust_ids))
        if veh_ids:
            conds.append(JobCard.vehicle_id.in_(veh_ids))
        query = query.filter(or_(*conds))
    if status:
        query = query.filter(JobCard.status == status)
    if mechanic_id:
        query = query.filter(JobCard.mechanic_id == mechanic_id)
    if customer_id:
        query = query.filter(JobCard.customer_id == customer_id)
    if vehicle_id:
        query = query.filter(JobCard.vehicle_id == vehicle_id)
    if date_from:
        query = query.filter(JobCard.checkin_at >= date_from)
    if date_to:
        query = query.filter(JobCard.checkin_at <= date_to)
    total = query.count()
    rows = query.order_by(JobCard.id.desc()).offset(offset).limit(limit).all()
    return [job_out(db, j) for j in rows], total


def get_job(db: Session, jid: int) -> JobCard | None:
    return db.get(JobCard, jid)


def _validate_job(db: Session, data: dict):
    if not db.get(Customer, data["customer_id"]):
        raise ValueError("Customer does not exist")
    veh = db.get(Vehicle, data["vehicle_id"])
    if veh is None:
        raise ValueError("Vehicle does not exist")
    if veh.customer_id != data["customer_id"]:
        raise ValueError("Vehicle does not belong to this customer")
    if data.get("mechanic_id") and not db.get(Mechanic, data["mechanic_id"]):
        raise ValueError("Mechanic does not exist")


def create_job(db: Session, data: dict, user_id: int | None = None) -> dict:
    _validate_job(db, data)
    warning = None
    odo = data.get("odometer")
    last = None
    if odo is not None:
        last = _last_odometer(db, data["vehicle_id"])
        if last is not None and odo < last:
            warning = (f"Odometer {odo} is lower than the previous reading {last}. "
                       "Please verify.")
    approval = "not_required"
    if (data.get("est_labor_paisa") or 0) + (data.get("est_parts_paisa") or 0) > 0:
        approval = "pending"
    from ..core.security import utcnow
    est_date = ensure_datetime(data.get("est_completion_date"), default_now=False)
    job = JobCard(
        job_number=next_number(db, "job_number", "JB"),
        customer_id=data["customer_id"], vehicle_id=data["vehicle_id"],
        checkin_at=utcnow(), odometer=odo,
        reported_issue=data.get("reported_issue"), complaint=data.get("complaint"),
        inspection=data.get("inspection"), vehicle_condition=data.get("vehicle_condition"),
        existing_damage=data.get("existing_damage"), fuel_level=data.get("fuel_level"),
        mechanic_id=data.get("mechanic_id"),
        est_labor_paisa=data.get("est_labor_paisa", 0) or 0,
        est_parts_paisa=data.get("est_parts_paisa", 0) or 0,
        est_completion_date=est_date,
        priority=data.get("priority", "normal"),
        internal_notes=data.get("internal_notes"), customer_notes=data.get("customer_notes"),
        warranty_days=data.get("warranty_days", 0) or 0,
        status="received", approval_status=approval, created_by=user_id)
    db.add(job)
    db.flush()
    _add_history(db, job, None, "received", "Job card created", user_id)
    db.commit()
    from .audit_service import log as _audit
    _audit(db, user_id=user_id, username=None,
           action="job.create", entity_type="job_card",
           entity_id=job.id,
           new_values={"job_number": job.job_number,
                       "customer_id": job.customer_id})
    notification_service.job_created_notification(db, job)
    out = job_out(db, job)
    if warning:
        out["odometer_warning"] = warning
    return out


def _last_odometer(db: Session, vehicle_id: int):
    row = (db.query(JobCard.odometer)
           .filter(JobCard.vehicle_id == vehicle_id, JobCard.odometer.isnot(None))
           .order_by(JobCard.id.desc()).first())
    return row[0] if row else None


def update_job(db: Session, job: JobCard, data: dict, user_id: int | None = None) -> JobCard:
    editable_statuses = ("received", "inspection", "awaiting_approval", "on_hold")
    if job.status not in editable_statuses and data:
        # allow note edits but not structural changes after work started
        structural = {"customer_id", "vehicle_id", "mechanic_id", "est_labor_paisa",
                      "est_parts_paisa", "est_completion_date", "priority"}
        if any(k in data for k in structural):
            raise ValueError(
                f"Job is '{job.status}' — structural fields are locked. "
                "Move it back to Received/Inspection to edit.")
    if "vehicle_id" in data:
        veh = db.get(Vehicle, data["vehicle_id"])
        if veh and veh.customer_id != job.customer_id:
            raise ValueError("Vehicle does not belong to this customer")
    warning = None
    if data.get("odometer") is not None and data["odometer"] != job.odometer:
        last = _last_odometer(db, job.vehicle_id) if data["odometer"] else None
        # compare against previous *other* job readings
        prev = (db.query(JobCard.odometer)
                .filter(JobCard.vehicle_id == job.vehicle_id,
                        JobCard.id != job.id, JobCard.odometer.isnot(None))
                .order_by(JobCard.id.desc()).first())
        if prev and data["odometer"] < prev[0]:
            warning = f"Odometer {data['odometer']} is lower than previous reading {prev[0]}."
    for k, v in data.items():
        if k == "est_completion_date" and v is not None:
            v = ensure_datetime(v, default_now=False)
        if v is not None or k in ("internal_notes", "customer_notes", "est_completion_date"):
            setattr(job, k, v)
    if (data.get("est_labor_paisa") is not None or data.get("est_parts_paisa") is not None):
        total_est = (job.est_labor_paisa or 0) + (job.est_parts_paisa or 0)
        if total_est > 0 and job.approval_status == "not_required":
            job.approval_status = "pending"
        elif (job.approval_status == "approved" and
              (data.get("est_labor_paisa") is not None or
               data.get("est_parts_paisa") is not None)):
            # estimate changed after customer approval -> re-approval needed
            job.approval_status = "pending"
    db.commit()
    if warning:
        job.odometer_warning = warning  # transient attr for response building
    return job


# ---------------------------------------------------------------- workflow
def change_status(db: Session, job: JobCard, new_status: str, notes: str | None,
                  user_id: int | None = None) -> JobCard:
    if new_status not in JOB_STATUSES:
        raise ValueError("Unknown job status")
    allowed = JOB_TRANSITIONS.get(job.status, ())
    if new_status not in allowed:
        raise ValueError(
            f"Cannot move job from '{job.status}' to '{new_status}'. "
            f"Allowed: {', '.join(allowed) if allowed else 'none (terminal)'}")
    if new_status == "completed" and job.approval_status == "pending":
        raise ValueError(
            "Estimate not yet approved by the customer — get estimate "
            "approval before completing the job")
    old = job.status
    job.status = new_status
    if new_status == "completed":
        from ..core.security import utcnow
        job.completed_at = utcnow()
        job.actual_labor_paisa = sum(s.line_total_paisa for s in job.services)
        job.actual_parts_paisa = sum(p.line_total_paisa for p in job.parts)
    _add_history(db, job, old, new_status, notes, user_id)
    db.commit()
    notification_service.job_status_notification(db, job, old, None)
    if new_status == "cancelled":
        _restore_all_parts(db, job, user_id, reason="Job cancelled")
    return job


def set_approval(db: Session, job: JobCard, approval_status: str,
                 notes: str | None = None, user_id: int | None = None) -> JobCard:
    if approval_status not in ("not_required", "pending", "approved", "rejected"):
        raise ValueError("Invalid approval status")
    old = job.approval_status
    job.approval_status = approval_status
    _add_history(db, job, job.status, job.status,
                 f"Estimate approval: {old} → {approval_status}. {notes or ''}", user_id)
    db.commit()
    return job


def _add_history(db: Session, job: JobCard, from_status, to_status, notes, user_id):
    db.add(JobHistory(job_id=job.id, from_status=from_status, to_status=to_status,
                      notes=notes, created_by=user_id))


# ---------------------------------------------------------------- services on jobs
def add_job_service(db: Session, job: JobCard, data: dict,
                    user_id: int | None = None) -> JobService:
    svc = None
    if data.get("service_id"):
        svc = db.get(ServiceModel, data["service_id"])
        if svc is None:
            raise ValueError("Service does not exist")
        description = data.get("description") or svc.name
    else:
        description = data.get("description")
        if not description:
            raise ValueError("Service description is required")
    qty = int(data.get("quantity") or 1)
    charge = int(data.get("unit_charge_paisa") or 0)
    disc = int(data.get("discount_paisa") or 0)
    line = qty * charge - disc
    if line < 0:
        raise ValueError("Discount cannot exceed the line amount")
    js = JobService(job_id=job.id, service_id=data.get("service_id"),
                    description=description, quantity=qty,
                    unit_charge_paisa=charge, discount_paisa=disc,
                    line_total_paisa=line, mechanic_id=data.get("mechanic_id") or job.mechanic_id)
    db.add(js)
    _recalc_job(db, job)
    db.commit()
    return js


def update_job_service(db: Session, js: JobService, data: dict) -> JobService:
    for k in ("description", "quantity", "unit_charge_paisa", "discount_paisa", "mechanic_id"):
        if k in data and data[k] is not None:
            setattr(js, k, data[k])
    js.line_total_paisa = js.quantity * js.unit_charge_paisa - js.discount_paisa
    if js.line_total_paisa < 0:
        raise ValueError("Discount cannot exceed the line amount")
    _recalc_job(db, js.job)
    db.commit()
    return js


def delete_job_service(db: Session, js: JobService) -> None:
    job = js.job
    db.delete(js)
    _recalc_job(db, job)
    db.commit()


def add_job_part(db: Session, job: JobCard, data: dict,
                 user_id: int | None = None) -> JobPart:
    product = db.get(Product, data["product_id"])
    if product is None:
        raise ValueError("Product does not exist")
    if product.is_service:
        raise ValueError("Service items cannot be used as job parts")
    qty = int(data["quantity"])
    price = int(data.get("unit_price_paisa") or product.selling_price_paisa or 0)
    jp = JobPart(job_id=job.id, product_id=product.id, quantity=qty,
                 unit_price_paisa=price, line_total_paisa=qty * price)
    db.add(jp)
    db.flush()
    # Consume stock exactly once, tied to this job-part line
    mv = apply_stock(db, product, -qty, movement_type=STOCK_JOB_CONSUME,
                     reference_type="job", reference_id=job.id,
                     reference_number=job.job_number,
                     notes=f"Consumed on job {job.job_number}",
                     created_by=user_id, unit_cost_paisa=product.purchase_cost_paisa)
    jp.stock_deducted = True
    jp.stock_movement_id = mv.id
    _recalc_job(db, job)
    db.commit()
    return jp


def update_job_part(db: Session, jp: JobPart, data: dict,
                    user_id: int | None = None) -> JobPart:
    if "quantity" in data and data["quantity"] is not None:
        new_qty = int(data["quantity"])
        delta = new_qty - jp.quantity
        if delta != 0:
            product = db.get(Product, jp.product_id)
            apply_stock(db, product, -delta, movement_type=STOCK_JOB_CONSUME if delta > 0 else STOCK_JOB_RESTORE,
                        reference_type="job", reference_id=jp.job_id,
                        reference_number=jp.job.job_number,
                        notes=f"Job part quantity updated ({jp.quantity} → {new_qty})",
                        created_by=user_id, unit_cost_paisa=product.purchase_cost_paisa)
            jp.quantity = new_qty
    if data.get("unit_price_paisa") is not None:
        jp.unit_price_paisa = int(data["unit_price_paisa"])
    jp.line_total_paisa = jp.quantity * jp.unit_price_paisa
    _recalc_job(db, jp.job)
    db.commit()
    return jp


def delete_job_part(db: Session, jp: JobPart, user_id: int | None = None) -> None:
    if jp.stock_deducted:
        product = db.get(Product, jp.product_id)
        apply_stock(db, product, jp.quantity, movement_type=STOCK_JOB_RESTORE,
                    reference_type="job", reference_id=jp.job_id,
                    reference_number=jp.job.job_number,
                    notes=f"Job part line removed from {jp.job.job_number}",
                    created_by=user_id, unit_cost_paisa=product.purchase_cost_paisa)
        jp.stock_deducted = False
    job = jp.job
    db.delete(jp)
    _recalc_job(db, job)
    db.commit()


def _restore_all_parts(db: Session, job: JobCard, user_id: int | None, reason: str) -> None:
    for jp in job.parts:
        if jp.stock_deducted:
            product = db.get(Product, jp.product_id)
            apply_stock(db, product, jp.quantity, movement_type=STOCK_JOB_RESTORE,
                        reference_type="job", reference_id=job.id,
                        reference_number=job.job_number,
                        notes=f"{reason} (job {job.job_number})",
                        created_by=user_id, unit_cost_paisa=product.purchase_cost_paisa)
            jp.stock_deducted = False


def _recalc_job(db: Session, job: JobCard) -> None:
    job.actual_labor_paisa = sum(s.line_total_paisa for s in job.services)
    job.actual_parts_paisa = sum(p.line_total_paisa for p in job.parts)
    db.flush()


def vehicle_jobs(db: Session, vehicle_id: int) -> list[dict]:
    rows = (db.query(JobCard).filter(JobCard.vehicle_id == vehicle_id)
            .order_by(JobCard.id.desc()).limit(30).all())
    return [job_out(db, j) for j in rows]


def vehicle_service_history(db: Session, vehicle_id: int) -> list[dict]:
    jobs = (db.query(JobCard).filter(JobCard.vehicle_id == vehicle_id)
            .order_by(JobCard.id.desc()).limit(30).all())
    return [
        {"job_number": j.job_number, "status": j.status,
         "checkin_at": j.checkin_at.isoformat() if j.checkin_at else None,
         "odometer": j.odometer, "reported_issue": j.reported_issue,
         "actual_total_paisa": j.actual_labor_paisa + j.actual_parts_paisa}
        for j in jobs
    ]

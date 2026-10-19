"""Vehicle registry."""
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..models import Vehicle, Customer, JobCard, Invoice


def count_vehicles(db: Session, q: str | None = None,
                   customer_id: int | None = None,
                   vehicle_type: str | None = None) -> int:
    query = db.query(func.count(Vehicle.id))
    if customer_id:
        query = query.filter(Vehicle.customer_id == customer_id)
    if vehicle_type:
        query = query.filter(Vehicle.vehicle_type == vehicle_type)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Vehicle.registration_no.ilike(like))
            | (Vehicle.make.ilike(like))
            | (Vehicle.model.ilike(like))
            | (Vehicle.chassis_no.ilike(like))
        )
    return int(query.scalar() or 0)


def list_vehicles(db: Session, q: str | None = None, customer_id: int | None = None,
                  vehicle_type: str | None = None, limit: int = 50, offset: int = 0):
    query = db.query(Vehicle)
    if customer_id:
        query = query.filter(Vehicle.customer_id == customer_id)
    if vehicle_type:
        query = query.filter(Vehicle.vehicle_type == vehicle_type)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Vehicle.registration_no.ilike(like))
            | (Vehicle.make.ilike(like))
            | (Vehicle.model.ilike(like))
            | (Vehicle.chassis_no.ilike(like))
        )
    rows = query.order_by(Vehicle.id.desc()).offset(offset).limit(limit).all()
    return [enrich(db, v) for v in rows]


def enrich(db: Session, v: Vehicle) -> dict:
    cust = db.get(Customer, v.customer_id) if v.customer_id else None
    return {
        "id": v.id, "customer_id": v.customer_id,
        "customer_name": cust.name if cust else None,
        "customer_phone": cust.phone if cust else None,
        "vehicle_type": v.vehicle_type, "registration_no": v.registration_no,
        "make": v.make, "model": v.model, "year": v.year, "color": v.color,
        "engine_no": v.engine_no, "chassis_no": v.chassis_no,
        "odometer": v.odometer, "fuel_type": v.fuel_type, "notes": v.notes,
        "job_count": db.query(func.count(JobCard.id)).filter(JobCard.vehicle_id == v.id).scalar() or 0,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }


def get_vehicle(db: Session, vid: int) -> Vehicle | None:
    return db.get(Vehicle, vid)


def create_vehicle(db: Session, data: dict) -> Vehicle:
    cust = db.get(Customer, data["customer_id"])
    if cust is None:
        raise ValueError("Customer does not exist")
    v = Vehicle(**data)
    db.add(v)
    db.commit()
    return v


def update_vehicle(db: Session, v: Vehicle, data: dict) -> Vehicle:
    for k, val in data.items():
        if val is not None or k in ("registration_no", "engine_no", "chassis_no", "notes", "odometer"):
            setattr(v, k, val)
    db.commit()
    return v


def delete_vehicle(db: Session, v: Vehicle) -> None:
    has_jobs = db.query(JobCard.id).filter(JobCard.vehicle_id == v.id).first()
    if has_jobs:
        raise ValueError("Cannot delete a vehicle with workshop history. Keep the record for history.")
    db.delete(v)
    db.commit()


def last_odometer(db: Session, vehicle_id: int) -> int | None:
    row = (db.query(JobCard.odometer)
           .filter(JobCard.vehicle_id == vehicle_id, JobCard.odometer.isnot(None))
           .order_by(JobCard.id.desc()).first())
    if row and row[0] is not None:
        return int(row[0])
    v = db.get(Vehicle, vehicle_id)
    return int(v.odometer) if v and v.odometer is not None else None


def vehicle_invoices(db: Session, vehicle_id: int) -> list[dict]:
    job_ids = [r[0] for r in db.query(JobCard.id).filter(JobCard.vehicle_id == vehicle_id).all()]
    conds = [Invoice.vehicle_id == vehicle_id]
    if job_ids:
        conds.append(Invoice.job_id.in_(job_ids))
    rows = (db.query(Invoice)
            .filter(or_(*conds))
            .order_by(Invoice.id.desc())
            .all())
    return [{
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "job_id": inv.job_id,
        "total_paisa": inv.total_paisa,
        "paid_paisa": inv.paid_paisa,
        "balance_paisa": inv.balance_paisa,
        "status": inv.status,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
    } for inv in rows]


def odometer_history(db: Session, vehicle_id: int) -> list[dict]:
    v = db.get(Vehicle, vehicle_id)
    out = []
    if v and v.odometer is not None:
        out.append({
            "source": "vehicle_registry",
            "reference": v.registration_no or f"VEH-{v.id}",
            "odometer": int(v.odometer),
            "recorded_at": v.created_at.isoformat() if v.created_at else None,
        })
    jobs = (db.query(JobCard)
            .filter(JobCard.vehicle_id == vehicle_id, JobCard.odometer.isnot(None))
            .order_by(JobCard.id.asc())
            .all())
    for j in jobs:
        out.append({
            "source": "job_card",
            "reference": j.job_number,
            "odometer": int(j.odometer),
            "recorded_at": j.checkin_at.isoformat() if j.checkin_at else None,
        })
    return out

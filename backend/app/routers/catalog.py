"""Service catalog (labor) and mechanics/staff."""
from fastapi import APIRouter, Depends, HTTPException

from ..core.deps import get_current_user, get_db
from ..models import Mechanic, Service as ServiceModel, User
from ..schemas.catalog import MechanicIn, MechanicUpdateIn, ServiceIn, ServiceUpdateIn

router = APIRouter(prefix="/api", tags=["catalog"])


# ---------------------------------------------------------------- services
@router.get("/services")
def list_services(q: str | None = None, include_inactive: bool = False,
                  db=Depends(get_db), _: User = Depends(get_current_user)):
    query = db.query(ServiceModel)
    if not include_inactive:
        query = query.filter(ServiceModel.is_active.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter((ServiceModel.name.ilike(like))
                             | (ServiceModel.code.ilike(like)))
    return [{
        "id": s.id, "name": s.name, "code": s.code, "description": s.description,
        "default_charge_paisa": s.default_charge_paisa,
        "estimated_minutes": s.estimated_minutes,
        "vehicle_types": s.vehicle_types, "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    } for s in query.order_by(ServiceModel.name).all()]


@router.post("/services")
def create_service(payload: ServiceIn, db=Depends(get_db),
                   _: User = Depends(get_current_user)):
    svc = ServiceModel(**payload.model_dump())
    db.add(svc)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Service code already exists")
    return _service_out(svc)


def _service_out(s: ServiceModel) -> dict:
    return {"id": s.id, "name": s.name, "code": s.code,
            "description": s.description,
            "default_charge_paisa": s.default_charge_paisa,
            "estimated_minutes": s.estimated_minutes,
            "vehicle_types": s.vehicle_types, "is_active": s.is_active,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None}


@router.put("/services/{sid}")
def update_service(sid: int, payload: ServiceUpdateIn, db=Depends(get_db),
                   _: User = Depends(get_current_user)):
    s = db.get(ServiceModel, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="Service not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("vehicle_types") is not None:
        parts = [p.strip() for p in data["vehicle_types"].split(",") if p.strip()]
        data["vehicle_types"] = ",".join(parts) or "motorcycle,car"
    for k, v in data.items():
        if v is not None:
            setattr(s, k, v)
    db.commit()
    return _service_out(s)


@router.delete("/services/{sid}")
def delete_service(sid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    s = db.get(ServiceModel, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="Service not found")
    db.delete(s)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- mechanics
@router.get("/mechanics")
def list_mechanics(include_inactive: bool = False, db=Depends(get_db),
                   _: User = Depends(get_current_user)):
    q = db.query(Mechanic)
    if not include_inactive:
        q = q.filter(Mechanic.is_active.is_(True))
    return [_mech_out(db, m) for m in q.order_by(Mechanic.name).all()]


def _mech_out(db, m: Mechanic) -> dict:
    from ..models import JobCard
    from sqlalchemy import func
    jobs_total = db.query(func.count(JobCard.id)).filter(JobCard.mechanic_id == m.id).scalar() or 0
    jobs_done = db.query(func.count(JobCard.id)).filter(
        JobCard.mechanic_id == m.id,
        JobCard.status.in_(("completed", "ready_for_delivery", "delivered"))).scalar() or 0
    user = db.get(User, m.user_id) if m.user_id else None
    return {
        "id": m.id, "name": m.name, "phone": m.phone, "skill": m.skill,
        "commission_type": m.commission_type,
        "commission_value": m.commission_value,
        "commission_due_paisa": 0,
        "is_active": m.is_active, "hire_date": m.hire_date.isoformat() if m.hire_date else None,
        "notes": m.notes, "user_id": m.user_id,
        "username": user.username if user else None,
        "jobs_total": jobs_total, "jobs_done": jobs_done,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


@router.post("/mechanics")
def create_mechanic(payload: MechanicIn, db=Depends(get_db),
                    _: User = Depends(get_current_user)):
    m = Mechanic(**payload.model_dump())
    db.add(m)
    db.commit()
    return _mech_out(db, m)


@router.put("/mechanics/{mid}")
def update_mechanic(mid: int, payload: MechanicUpdateIn, db=Depends(get_db),
                    _: User = Depends(get_current_user)):
    m = db.get(Mechanic, mid)
    if m is None:
        raise HTTPException(status_code=404, detail="Mechanic not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(m, k, v)
    db.commit()
    return _mech_out(db, m)


@router.delete("/mechanics/{mid}")
def delete_mechanic(mid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    m = db.get(Mechanic, mid)
    if m is None:
        raise HTTPException(status_code=404, detail="Mechanic not found")
    from ..models import JobCard
    if db.query(JobCard.id).filter(JobCard.mechanic_id == mid).first():
        raise HTTPException(status_code=400,
                            detail="Mechanic has job history — deactivate instead")
    db.delete(m)
    db.commit()
    return {"ok": True}

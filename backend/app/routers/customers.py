"""Customers and vehicles."""
from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.deps import get_current_user, get_db
from ..models import Customer, User, Vehicle
from ..schemas.customers import CustomerIn, CustomerUpdateIn, VehicleIn, VehicleUpdateIn
from ..services import customer_service, vehicle_service
from ..services import job_service as _job_service

router = APIRouter(prefix="/api", tags=["customers"])


# ---------------------------------------------------------------- customers
@router.get("/customers")
def list_customers(q: str | None = None, page: int = 1, page_size: int = 25,
                   include_inactive: bool = False, db=Depends(get_db),
                   _: User = Depends(get_current_user)):
    limit = min(200, max(1, page_size))
    offset = (max(1, page) - 1) * limit
    total = customer_service.count_customers(db, q=q, include_inactive=include_inactive)
    rows = customer_service.list_customers(db, q=q, limit=limit, offset=offset,
                                            include_inactive=include_inactive)
    return {"items": rows, "total": total, "page": page, "page_size": limit}


@router.post("/customers")
def create_customer(payload: CustomerIn, db=Depends(get_db),
                    user: User = Depends(get_current_user)):
    dup = customer_service.find_duplicate(db, payload.name, payload.phone)
    if dup:
        raise HTTPException(status_code=409,
                            detail=f"A customer named '{payload.name}' with phone "
                                   f"{payload.phone} already exists (code {dup.code})")
    c = customer_service.create_customer(db, payload.model_dump(), user.id)
    return customer_service.enrich(db, c)


@router.get("/customers/lookup")
def lookup_customer(q: str = Query(min_length=1), db=Depends(get_db),
                    _: User = Depends(get_current_user)):
    rows = customer_service.list_customers(db, q=q, limit=20, include_inactive=True)
    return rows


@router.get("/customers/{cid}")
def get_customer(cid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    c = customer_service.get_customer(db, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer_service.enrich(db, c)


@router.put("/customers/{cid}")
def update_customer(cid: int, payload: CustomerUpdateIn, db=Depends(get_db),
                    _: User = Depends(get_current_user)):
    c = customer_service.get_customer(db, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer_service.update_customer(db, c, payload.model_dump(exclude_unset=True))
    return customer_service.enrich(db, c)


@router.delete("/customers/{cid}")
def delete_customer(cid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    c = customer_service.get_customer(db, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    try:
        customer_service.delete_customer(db, c)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/customers/{cid}/history")
def customer_history(cid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    c = customer_service.get_customer(db, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer_service.customer_history(db, cid)


# ---------------------------------------------------------------- vehicles
@router.get("/vehicles")
def list_vehicles(q: str | None = None, customer_id: int | None = None,
                  vehicle_type: str | None = None,
                  page: int = 1, page_size: int = 25, db=Depends(get_db),
                  _: User = Depends(get_current_user)):
    limit = min(200, max(1, page_size))
    offset = (max(1, page) - 1) * limit
    total = vehicle_service.count_vehicles(db, q=q, customer_id=customer_id,
                                            vehicle_type=vehicle_type)
    rows = vehicle_service.list_vehicles(db, q=q, customer_id=customer_id,
                                          vehicle_type=vehicle_type,
                                          limit=limit, offset=offset)
    return {"items": rows, "total": total, "page": page, "page_size": limit}


@router.post("/vehicles")
def create_vehicle(payload: VehicleIn, db=Depends(get_db),
                   _: User = Depends(get_current_user)):
    try:
        v = vehicle_service.create_vehicle(db, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return vehicle_service.enrich(db, v)


@router.get("/vehicles/{vid}")
def get_vehicle(vid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    v = vehicle_service.get_vehicle(db, vid)
    if v is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    out = vehicle_service.enrich(db, v)
    out["history"] = _job_service.vehicle_service_history(db, vid)
    out["invoices"] = vehicle_service.vehicle_invoices(db, vid)
    out["odometer_history"] = vehicle_service.odometer_history(db, vid)
    out["last_odometer"] = vehicle_service.last_odometer(db, vid)
    return out


@router.put("/vehicles/{vid}")
def update_vehicle(vid: int, payload: VehicleUpdateIn, db=Depends(get_db),
                   _: User = Depends(get_current_user)):
    v = vehicle_service.get_vehicle(db, vid)
    if v is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    vehicle_service.update_vehicle(db, v, payload.model_dump(exclude_unset=True))
    return vehicle_service.enrich(db, v)


@router.delete("/vehicles/{vid}")
def delete_vehicle(vid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    v = vehicle_service.get_vehicle(db, vid)
    if v is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    try:
        vehicle_service.delete_vehicle(db, v)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}

"""Workshop job cards."""
from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.deps import get_current_user, get_db, require_workshop
from ..models import JobCard, User
from ..schemas.jobs import (JobApprovalIn, JobCreateIn, JobEstimateIn,
                               JobPartIn, JobServiceIn, JobStatusIn,
                               JobUpdateIn)
from ..services import job_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def list_jobs(q: str | None = None, status: str | None = None,
              mechanic_id: int | None = None, customer_id: int | None = None,
              vehicle_id: int | None = None, date_from: str | None = None,
              date_to: str | None = None, page: int = 1, page_size: int = 25,
              db=Depends(get_db), _: User = Depends(require_workshop)):
    limit = min(200, max(1, page_size))
    offset = (max(1, page) - 1) * limit
    rows, total = job_service.list_jobs(
        db, q=q, status=status, mechanic_id=mechanic_id,
        customer_id=customer_id, vehicle_id=vehicle_id,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset)
    return {"items": rows, "total": total, "page": page, "page_size": limit}


@router.post("")
def create_job(payload: JobCreateIn, db=Depends(get_db),
               user: User = Depends(require_workshop)):
    return job_service.create_job(db, payload.model_dump(), user.id)


@router.get("/{jid}")
def get_job(jid: int, db=Depends(get_db), _: User = Depends(require_workshop)):
    job = job_service.get_job(db, jid)
    if job is None:
        raise HTTPException(status_code=404, detail="Job card not found")
    out = job_service.job_out(db, job)
    out["services"] = job_service.services_out(db, job)
    out["parts"] = job_service.parts_out(db, job)
    out["history"] = job_service.history_out(job)
    out["odometer_warning"] = getattr(job, "odometer_warning", None)
    return out


@router.put("/{jid}")
def update_job(jid: int, payload: JobUpdateIn, db=Depends(get_db),
               user: User = Depends(require_workshop)):
    job = job_service.get_job(db, jid)
    if job is None:
        raise HTTPException(status_code=404, detail="Job card not found")
    data = payload.model_dump(exclude_unset=True)
    try:
        job_service.update_job(db, job, data, user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    out = job_service.job_out(db, job)
    out["odometer_warning"] = getattr(job, "odometer_warning", None)
    return out


@router.post("/{jid}/status")
def change_status(jid: int, payload: JobStatusIn, db=Depends(get_db),
                  user: User = Depends(require_workshop)):
    job = job_service.get_job(db, jid)
    if job is None:
        raise HTTPException(status_code=404, detail="Job card not found")
    try:
        job_service.change_status(db, job, payload.status, payload.notes,
                                    user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return job_service.job_out(db, job)


@router.post("/{jid}/approval")
def set_approval(jid: int, payload: JobApprovalIn, db=Depends(get_db),
                 user: User = Depends(require_workshop)):
    job = job_service.get_job(db, jid)
    if job is None:
        raise HTTPException(status_code=404, detail="Job card not found")
    job_service.set_approval(db, job, payload.approval_status,
                             payload.notes, user.id)
    return job_service.job_out(db, job)


@router.post("/{jid}/estimate")
def update_estimate(jid: int, payload: JobEstimateIn, db=Depends(get_db),
                    user: User = Depends(require_workshop)):
    job = job_service.get_job(db, jid)
    if job is None:
        raise HTTPException(status_code=404, detail="Job card not found")
    job_service.update_job(db, job, payload.model_dump(exclude_unset=True),
                           user.id)
    return job_service.job_out(db, job)


# ---------------------------------------------------------------- services on job
@router.post("/{jid}/services")
def add_service(jid: int, payload: JobServiceIn, db=Depends(get_db),
                user: User = Depends(require_workshop)):
    job = job_service.get_job(db, jid)
    if job is None:
        raise HTTPException(status_code=404, detail="Job card not found")
    js = job_service.add_job_service(db, job, payload.model_dump(), user.id)
    return {"id": js.id, "line_total_paisa": js.line_total_paisa}


@router.put("/services/{sid}")
def update_service(sid: int, payload: JobServiceIn, db=Depends(get_db),
                   _: User = Depends(require_workshop)):
    from ..models import JobService
    js = db.get(JobService, sid)
    if js is None:
        raise HTTPException(status_code=404, detail="Job service not found")
    job_service.update_job_service(db, js, payload.model_dump(exclude_unset=True))
    return {"ok": True}


@router.delete("/services/{sid}")
def delete_service(sid: int, db=Depends(get_db),
                   _: User = Depends(require_workshop)):
    from ..models import JobService
    js = db.get(JobService, sid)
    if js is None:
        raise HTTPException(status_code=404, detail="Job service not found")
    job_service.delete_job_service(db, js)
    return {"ok": True}


# ---------------------------------------------------------------- parts on job
@router.post("/{jid}/parts")
def add_part(jid: int, payload: JobPartIn, db=Depends(get_db),
             user: User = Depends(require_workshop)):
    job = job_service.get_job(db, jid)
    if job is None:
        raise HTTPException(status_code=404, detail="Job card not found")
    try:
        jp = job_service.add_job_part(db, job, payload.model_dump(), user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": jp.id, "line_total_paisa": jp.line_total_paisa}


@router.put("/parts/{pid}")
def update_part(pid: int, payload: JobPartIn, db=Depends(get_db),
                user: User = Depends(require_workshop)):
    from ..models import JobPart
    jp = db.get(JobPart, pid)
    if jp is None:
        raise HTTPException(status_code=404, detail="Job part not found")
    try:
        job_service.update_job_part(db, jp, payload.model_dump(exclude_unset=True),
                                      user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.delete("/parts/{pid}")
def delete_part(pid: int, db=Depends(get_db),
                user: User = Depends(require_workshop)):
    from ..models import JobPart
    jp = db.get(JobPart, pid)
    if jp is None:
        raise HTTPException(status_code=404, detail="Job part not found")
    try:
        job_service.delete_job_part(db, jp, user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/vehicle/{vid}")
def vehicle_jobs(vid: int, db=Depends(get_db), _: User = Depends(require_workshop)):
    return job_service.vehicle_jobs(db, vid)


@router.post("/{jid}/invoice")
def invoice_job(jid: int, payload: dict = None, db=Depends(get_db),
                user: User = Depends(require_workshop)):
    """Generate the final bill for a job from its services and parts."""
    from ..services import invoice_service
    job = job_service.get_job(db, jid)
    if job is None:
        raise HTTPException(status_code=404, detail="Job card not found")
    if job.invoice_id:
        raise HTTPException(status_code=400, detail="Job is already invoiced")
    items = []
    for js in job.services:
        items.append({
            "item_type": "service", "service_id": js.service_id,
            "job_service_id": js.id, "description": js.description,
            "quantity": js.quantity, "unit": "job",
            "unit_price_paisa": js.unit_charge_paisa,
            "discount_paisa": js.discount_paisa})
    for jp in job.parts:
        items.append({
            "item_type": "product", "product_id": jp.product_id,
            "job_part_id": jp.id, "description": jp.product.name,
            "quantity": jp.quantity, "unit": jp.product.unit,
            "unit_price_paisa": jp.unit_price_paisa,
            "discount_paisa": 0})
    if not items:
        raise HTTPException(status_code=400,
                            detail="Job has no services or parts to bill")
    data = {
        "customer_id": job.customer_id, "vehicle_id": job.vehicle_id,
        "job_id": job.id, "items": items,
        "invoice_discount_paisa": 0, "payments": [],
        "is_credit": False, "notes": f"Job {job.job_number}",
    }
    if payload:
        payments = payload.get("payments", [])
        data["payments"] = payments
        data["invoice_discount_paisa"] = payload.get("invoice_discount_paisa", 0)
        data["is_credit"] = bool(payload.get("is_credit", False))
    try:
        out = invoice_service.create_invoice(db, data, user, from_job=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return out

"""Warranty claims."""
from fastapi import APIRouter, Depends, HTTPException

from ..core.deps import get_current_user, get_db
from ..models import User, WarrantyClaim
from ..schemas.claims import ClaimIn, ClaimUpdateIn
from ..services import claim_service

router = APIRouter(prefix="/api/claims", tags=["claims"])


@router.get("")
def list_claims(q: str | None = None, status: str | None = None,
                customer_id: int | None = None, page: int = 1,
                page_size: int = 25, db=Depends(get_db),
                _: User = Depends(get_current_user)):
    limit = min(200, max(1, page_size))
    offset = (max(1, page) - 1) * limit
    rows, total = claim_service.list_claims(
        db, q=q, status=status, customer_id=customer_id,
        limit=limit, offset=offset)
    return {"items": rows, "total": total, "page": page, "page_size": limit}


@router.get("/{cid}")
def get_claim(cid: int, db=Depends(get_db),
              _: User = Depends(get_current_user)):
    c = db.get(WarrantyClaim, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim_service.claim_out(db, c)


@router.post("")
def create_claim(payload: ClaimIn, db=Depends(get_db),
                 user: User = Depends(get_current_user)):
    try:
        c = claim_service.create_claim(db, payload.model_dump(), user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return claim_service.claim_out(db, c)


@router.put("/{cid}")
def update_claim(cid: int, payload: ClaimUpdateIn, db=Depends(get_db),
                 user: User = Depends(get_current_user)):
    c = db.get(WarrantyClaim, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    claim_service.update_claim(db, c, payload.model_dump(exclude_unset=True), user.id)
    return claim_service.claim_out(db, c)


@router.delete("/{cid}")
def delete_claim(cid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    c = db.get(WarrantyClaim, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    db.delete(c)
    db.commit()
    return {"ok": True}

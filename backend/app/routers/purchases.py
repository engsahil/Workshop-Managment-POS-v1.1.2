"""Suppliers, purchase orders, receiving, purchase payments and returns."""
from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.deps import get_current_user, get_db, require_financial
from ..models import User
from ..schemas.purchases import (PurchaseIn, PurchaseUpdateIn,
                                   PurchaseReceiveIn, PurchasePaymentIn,
                                   PurchaseReturnIn, SupplierIn,
                                   SupplierUpdateIn)
from ..services import purchase_service

router = APIRouter(prefix="/api", tags=["purchasing"])


# ---------------------------------------------------------------- suppliers
@router.get("/suppliers")
def list_suppliers(q: str | None = None, include_inactive: bool = False,
                   db=Depends(get_db), _: User = Depends(get_current_user)):
    return purchase_service.list_suppliers(db, q=q, include_inactive=include_inactive)


@router.post("/suppliers")
def create_supplier(payload: SupplierIn, db=Depends(get_db),
                    _: User = Depends(get_current_user)):
    return purchase_service.create_supplier(db, payload.model_dump())


@router.put("/suppliers/{sid}")
def update_supplier(sid: int, payload: SupplierUpdateIn, db=Depends(get_db),
                    _: User = Depends(get_current_user)):
    s = purchase_service.get_supplier(db, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    purchase_service.update_supplier(db, s, payload.model_dump(exclude_unset=True))
    s = purchase_service.get_supplier(db, sid)
    return {**{c: getattr(s, c) for c in (
        "id", "name", "contact_person", "phone", "alt_phone", "email",
        "address", "notes", "is_active")},
        "balance_paisa": purchase_service.supplier_balance(db, sid),
        "created_at": s.created_at.isoformat() if s.created_at else None}


@router.delete("/suppliers/{sid}")
def delete_supplier(sid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    s = purchase_service.get_supplier(db, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    try:
        purchase_service.delete_supplier(db, s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/suppliers/{sid}/statement")
def supplier_statement(sid: int, db=Depends(get_db),
                       _: User = Depends(get_current_user)):
    return purchase_service.supplier_statement(db, sid)


# ---------------------------------------------------------------- purchases
@router.get("/purchases")
def list_purchases(q: str | None = None, supplier_id: int | None = None,
                   status: str | None = None, date_from: str | None = None,
                   date_to: str | None = None, page: int = 1,
                   page_size: int = 25, db=Depends(get_db),
                   _: User = Depends(get_current_user)):
    limit = min(200, max(1, page_size))
    offset = (max(1, page) - 1) * limit
    rows, total = purchase_service.list_purchases(
        db, q=q, supplier_id=supplier_id, status=status,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset)
    return {"items": rows, "total": total, "page": page, "page_size": limit}


@router.post("/purchases")
def create_purchase(payload: PurchaseIn, db=Depends(get_db),
                    user: User = Depends(require_financial)):
    try:
        po = purchase_service.create_purchase(db, payload.model_dump(), user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return purchase_service.purchase_out(db, po)


@router.get("/purchases/{pid}")
def get_purchase(pid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    po = db.get(__import__("app.models", fromlist=["Purchase"]).Purchase, pid)
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return purchase_service.purchase_out(db, po)


@router.post("/purchases/{pid}/receive")
def receive_purchase(pid: int, payload: PurchaseReceiveIn, db=Depends(get_db),
                     user: User = Depends(get_current_user)):
    from ..models import Purchase
    po = db.get(Purchase, pid)
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    try:
        purchase_service.receive_purchase(db, po, payload.items, user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return purchase_service.purchase_out(db, po)


@router.post("/purchases/{pid}/cancel")
def cancel_purchase(pid: int, db=Depends(get_db),
                    user: User = Depends(require_financial)):
    from ..models import Purchase
    po = db.get(Purchase, pid)
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    try:
        purchase_service.cancel_purchase(db, po)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return purchase_service.purchase_out(db, po)


@router.post("/purchases/{pid}/payments")
def purchase_payment(pid: int, payload: PurchasePaymentIn, db=Depends(get_db),
                     user: User = Depends(require_financial)):
    from ..models import Purchase
    po = db.get(Purchase, pid)
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    try:
        purchase_service.add_purchase_payment(
            db, po, payload.amount_paisa, payload.method,
            payload.reference, payload.notes, user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return purchase_service.purchase_out(db, po)


# ---------------------------------------------------------------- purchase returns
@router.post("/purchase-returns")
def create_purchase_return(payload: PurchaseReturnIn, db=Depends(get_db),
                           user: User = Depends(require_financial)):
    try:
        pr = purchase_service.create_purchase_return(db, payload.model_dump(), user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "return_number": pr.return_number,
            "total_paisa": pr.total_paisa}


@router.get("/purchase-returns")
def list_purchase_returns(db=Depends(get_db), _: User = Depends(get_current_user)):
    from ..models import PurchaseReturn
    rows = db.query(PurchaseReturn).order_by(PurchaseReturn.id.desc()).limit(200).all()
    from ..models import Supplier
    return [{
        "id": r.id, "return_number": r.return_number, "status": r.status,
        "supplier_name": (db.get(Supplier, r.supplier_id).name
                          if db.get(Supplier, r.supplier_id) else None),
        "purchase_id": r.purchase_id, "total_paisa": r.total_paisa,
        "refund_amount_paisa": r.refund_amount_paisa, "method": r.method,
        "reference": r.reference, "notes": r.notes,
        "return_date": r.return_date.isoformat() if r.return_date else None,
    } for r in rows]

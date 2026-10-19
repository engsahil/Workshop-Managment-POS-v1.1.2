"""Invoice history, payments, voiding and sale returns."""
from fastapi import APIRouter, Depends, HTTPException

from ..core.deps import (get_current_user, get_db, require_financial,
                         require_pos)
from ..models import Invoice, User
from ..schemas.invoices import (InvoiceVoidIn, PaymentIn, SaleReturnIn,
                                   ReturnDecisionIn)
from ..services import invoice_service

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


@router.get("")
def list_invoices(q: str | None = None, customer_id: int | None = None,
                  cashier_id: int | None = None, status: str | None = None,
                  date_from: str | None = None, date_to: str | None = None,
                  page: int = 1, page_size: int = 25, db=Depends(get_db),
                  _: User = Depends(require_pos)):
    limit = min(200, max(1, page_size))
    offset = (max(1, page) - 1) * limit
    rows, total = invoice_service.list_invoices(
        db, q=q, customer_id=customer_id, cashier_id=cashier_id,
        status=status, date_from=date_from, date_to=date_to,
        limit=limit, offset=offset)
    return {"items": rows, "total": total, "page": page, "page_size": limit}


# ---------------------------------------------------------------- returns
@router.post("/returns")
def create_return(payload: SaleReturnIn, db=Depends(get_db),
                  user: User = Depends(require_financial)):
    try:
        sr = invoice_service.create_return(db, payload.model_dump(), user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "return_number": sr.return_number,
            "total_paisa": sr.total_paisa, "id": sr.id}


@router.post("/returns/{rid}/decide")
def decide_return(rid: int, payload: ReturnDecisionIn, db=Depends(get_db),
                  user: User = Depends(require_financial)):
    from ..models import SaleReturn
    sr = db.get(SaleReturn, rid)
    if sr is None:
        raise HTTPException(status_code=404, detail="Return not found")
    try:
        invoice_service.decide_return(db, sr, payload.status,
                                        payload.notes, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "status": sr.status}


@router.get("/returns")
def list_returns(status: str | None = None, page: int = 1, page_size: int = 25,
                 db=Depends(get_db), _: User = Depends(require_pos)):
    limit = min(200, max(1, page_size))
    offset = (max(1, page) - 1) * limit
    rows, total = invoice_service.list_returns(db, status=status,
                                                  limit=limit, offset=offset)
    return {"items": rows, "total": total, "page": page, "page_size": limit}


@router.get("/{iid}")
def get_invoice(iid: int, db=Depends(get_db), _: User = Depends(require_pos)):
    inv = db.get(Invoice, iid)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice_service.invoice_detail(db, inv)


@router.get("/{iid}/print-data")
def print_data(iid: int, db=Depends(get_db), _: User = Depends(require_pos)):
    """Everything the printable invoice template needs."""
    from ..services.settings_service import get_business_settings
    inv = db.get(Invoice, iid)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    detail = invoice_service.invoice_detail(db, inv)
    detail["business"] = get_business_settings(db)
    return detail


@router.post("/{iid}/payments")
def add_payment(iid: int, payload: PaymentIn, db=Depends(get_db),
                user: User = Depends(require_pos)):
    inv = db.get(Invoice, iid)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        invoice_service.add_payment(db, inv, payload.amount_paisa,
                                      payload.method, payload.reference,
                                      payload.notes, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return invoice_service.invoice_detail(db, inv)


@router.post("/{iid}/void")
def void_invoice(iid: int, payload: InvoiceVoidIn, db=Depends(get_db),
                 user: User = Depends(require_financial)):
    inv = db.get(Invoice, iid)
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        invoice_service.void_invoice(db, inv, payload.reason, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return invoice_service.invoice_detail(db, inv)


# ---------------------------------------------------------------- advances & repayments
@router.post("/advances")
def record_advance(payload: dict, db=Depends(get_db),
                   user: User = Depends(require_pos)):
    from ..schemas.finance import CustomerAdvanceIn
    try:
        pay = invoice_service.record_advance(
            db, payload["customer_id"], payload["amount_paisa"],
            payload.get("method", "cash"), payload.get("reference"),
            payload.get("notes"), user)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "payment_id": pay.id}


@router.post("/repayments")
def record_repayment(payload: dict, db=Depends(get_db),
                     user: User = Depends(require_pos)):
    from ..schemas.finance import RepaymentIn
    try:
        return invoice_service.record_repayment(
            db, payload["customer_id"], payload["amount_paisa"],
            payload.get("method", "cash"), payload.get("reference"),
            payload.get("notes"), user)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

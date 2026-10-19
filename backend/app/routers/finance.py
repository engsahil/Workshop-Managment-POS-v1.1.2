"""Expenses, cashier shifts, cash movements."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pathlib import Path

from ..core.config import DATA_DIR
from ..core.deps import (get_current_user, get_db, require_financial,
                         require_pos)
from ..models import Expense, User
from ..schemas.finance import (CashMovementIn, ShiftCloseIn, ShiftOpenIn,
                                 ExpenseIn, ExpenseUpdateIn,
                                 ExpenseCategoryIn)
from ..services import expense_service, shift_service

router = APIRouter(prefix="/api", tags=["finance"])

UPLOAD_DIR = DATA_DIR / "uploads"
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf"}
MAX_BYTES = 5 * 1024 * 1024


# ---------------------------------------------------------------- expenses
@router.get("/expenses")
def list_expenses(q: str | None = None, category_id: int | None = None,
                  method: str | None = None, date_from: str | None = None,
                  date_to: str | None = None, page: int = 1,
                  page_size: int = 25, db=Depends(get_db),
                  _: User = Depends(get_current_user)):
    limit = min(200, max(1, page_size))
    offset = (max(1, page) - 1) * limit
    rows, total = expense_service.list_expenses(
        db, q=q, category_id=category_id, method=method,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset)
    summary = expense_service.expense_summary(
        db, q=q, category_id=category_id, method=method,
        date_from=date_from, date_to=date_to)
    return {"items": rows, "total": total, "page": page, "page_size": limit, "summary": summary}


@router.post("/expenses")
def create_expense(payload: ExpenseIn, db=Depends(get_db),
                   user: User = Depends(require_financial)):
    try:
        e = expense_service.create_expense(db, payload.model_dump(), user.id)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    return expense_service.expense_out(db, e)


@router.put("/expenses/{eid}")
def update_expense(eid: int, payload: ExpenseUpdateIn, db=Depends(get_db),
                   user: User = Depends(require_financial)):
    e = db.get(Expense, eid)
    if e is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    expense_service.update_expense(db, e, payload.model_dump(exclude_unset=True),
                                     user.id)
    return expense_service.expense_out(db, e)


@router.delete("/expenses/{eid}")
def delete_expense(eid: int, db=Depends(get_db),
                   user: User = Depends(require_financial)):
    e = db.get(Expense, eid)
    if e is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    expense_service.delete_expense(db, e, user.id)
    return {"ok": True}


@router.get("/expense-categories")
def list_categories(db=Depends(get_db), _: User = Depends(get_current_user)):
    return expense_service.list_categories(db)


@router.post("/expense-categories")
def create_category(payload: ExpenseCategoryIn, db=Depends(get_db),
                    _: User = Depends(require_financial)):
    try:
        return expense_service.create_category(db, payload.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/uploads/expense")
async def upload_expense_attachment(file: UploadFile = File(...),
                                      user: User = Depends(require_financial)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400,
                            detail="Only images and PDFs are allowed")
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=400,
                            detail="File too large (max 5 MB)")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    import uuid
    name = f"expense_{uuid.uuid4().hex[:12]}{ext}"
    (UPLOAD_DIR / name).write_bytes(content)
    return {"ok": True, "attachment_path": f"uploads/{name}"}


# ---------------------------------------------------------------- shifts
@router.post("/shifts/open")
def open_shift(payload: ShiftOpenIn, db=Depends(get_db),
               user: User = Depends(require_pos)):
    try:
        return shift_service.shift_out(db, shift_service.open_shift(
            db, user.id, payload.opening_cash_paisa))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/shifts/current")
def current_shift(db=Depends(get_db), user: User = Depends(require_pos)):
    s = shift_service.current_shift(db, user.id)
    return shift_service.shift_out(db, s) if s else None


@router.post("/shifts/{sid}/cash-movements")
def cash_movement(sid: int, payload: CashMovementIn, db=Depends(get_db),
                  user: User = Depends(require_financial)):
    from ..models import CashShift
    shift = db.get(CashShift, sid)
    if shift is None:
        raise HTTPException(status_code=404, detail="Shift not found")
    try:
        shift_service.add_cash_movement(
            db, shift, payload.movement_type, payload.amount_paisa,
            payload.reason, payload.reference, user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return shift_service.shift_out(db, shift)


@router.post("/shifts/{sid}/close")
def close_shift(sid: int, payload: ShiftCloseIn, db=Depends(get_db),
                user: User = Depends(require_pos)):
    from ..models import CashShift
    shift = db.get(CashShift, sid)
    if shift is None:
        raise HTTPException(status_code=404, detail="Shift not found")
    try:
        shift_service.close_shift(db, shift, payload.counted_cash_paisa,
                                    payload.closing_notes, user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return shift_service.shift_out(db, shift)


@router.get("/shifts")
def list_shifts(user_id: int | None = None, status: str | None = None,
                page: int = 1, page_size: int = 25, db=Depends(get_db),
                _: User = Depends(get_current_user)):
    limit = min(200, max(1, page_size))
    offset = (max(1, page) - 1) * limit
    rows, total = shift_service.list_shifts(
        db, user_id=user_id, status=status, limit=limit, offset=offset)
    return {"items": rows, "total": total, "page": page, "page_size": limit}


@router.get("/shifts/{sid}/ledger")
def shift_ledger(sid: int, db=Depends(get_db),
                 _: User = Depends(require_financial)):
    try:
        return shift_service.shift_ledger(db, sid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

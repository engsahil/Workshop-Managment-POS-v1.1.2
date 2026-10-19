"""Cashier shift / cash drawer reconciliation.

Expected cash is computed ONLY from cash transactions:
  opening cash
+ cash payments received (sales, advances, repayments)
- cash refunds paid out
- cash expenses paid
+ approved cash additions
- approved cash withdrawals
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import CashShift, CashMovement, Payment, Expense
from ..services import audit_service


def current_shift(db: Session, user_id: int) -> CashShift | None:
    return (db.query(CashShift)
            .filter(CashShift.user_id == user_id, CashShift.status == "open")
            .order_by(CashShift.id.desc()).first())


def open_shift(db: Session, user_id: int, opening_cash_paisa: int) -> CashShift:
    if current_shift(db, user_id):
        raise ValueError("You already have an open shift. Close it first.")
    shift = CashShift(user_id=user_id, opening_cash_paisa=opening_cash_paisa,
                      expected_cash_paisa=opening_cash_paisa)
    db.add(shift)
    db.commit()
    return shift


def expected_cash(db: Session, shift: CashShift) -> int:
    expected = shift.opening_cash_paisa

    received = (db.query(func.coalesce(func.sum(Payment.amount_paisa), 0))
                .filter(Payment.shift_id == shift.id, Payment.method == "cash",
                        Payment.amount_paisa > 0,
                        Payment.kind.in_(("sale_payment", "advance", "repayment")))
                .scalar() or 0)
    refunded = (db.query(func.coalesce(func.sum(Payment.amount_paisa), 0))
                .filter(Payment.shift_id == shift.id, Payment.method == "cash",
                        Payment.amount_paisa < 0, Payment.kind == "refund")
                .scalar() or 0)
    expenses = (db.query(func.coalesce(func.sum(Expense.amount_paisa), 0))
                .filter(Expense.shift_id == shift.id, Expense.method == "cash")
                .scalar() or 0)
    additions = (db.query(func.coalesce(func.sum(CashMovement.amount_paisa), 0))
                 .filter(CashMovement.shift_id == shift.id,
                         CashMovement.movement_type == "addition").scalar() or 0)
    withdrawals = (db.query(func.coalesce(func.sum(CashMovement.amount_paisa), 0))
                   .filter(CashMovement.shift_id == shift.id,
                           CashMovement.movement_type == "withdrawal").scalar() or 0)

    expected = (expected + int(received) + int(refunded) - int(expenses)
                + int(additions) - int(withdrawals))
    shift.expected_cash_paisa = expected
    return expected


def add_cash_movement(db: Session, shift: CashShift, movement_type: str,
                      amount_paisa: int, reason: str, reference: str | None,
                      user_id: int | None) -> CashMovement:
    if shift.status != "open":
        raise ValueError("Shift is closed")
    mv = CashMovement(shift_id=shift.id, movement_type=movement_type,
                      amount_paisa=amount_paisa, reason=reason, reference=reference,
                      created_by=user_id)
    db.add(mv)
    expected_cash(db, shift)
    db.commit()
    return mv


def close_shift(db: Session, shift: CashShift, counted_cash_paisa: int,
                closing_notes: str | None, user) -> CashShift:
    if shift.status != "open":
        raise ValueError("Shift is already closed")
    expected = expected_cash(db, shift)
    difference = counted_cash_paisa - expected
    if difference != 0 and user.role not in ("admin", "manager"):
        raise PermissionError(
            f"Cash variance of Rs. {abs(difference)/100:,.2f} requires "
            "manager or administrator approval to close this shift")
    shift.expected_cash_paisa = expected
    shift.counted_cash_paisa = counted_cash_paisa
    shift.difference_paisa = difference
    shift.closing_notes = closing_notes
    shift.status = "closed"
    from ..core.security import utcnow
    shift.closed_at = utcnow()
    shift.closed_by = user.id
    db.commit()
    audit_service.log(db, user_id=user.id, username=user.username,
                      action="shift.close", entity_type="cash_shift",
                      entity_id=shift.id,
                      new_values={"expected_paisa": expected,
                                  "counted_paisa": counted_cash_paisa,
                                  "difference_paisa": difference})
    return shift


def shift_out(db: Session, shift: CashShift) -> dict:
    user = db.get(__import__("app.models", fromlist=["User"]).User, shift.user_id)
    expected = expected_cash(db, shift)
    return {
        "id": shift.id, "user_id": shift.user_id,
        "user_name": user.full_name if user else None,
        "opened_at": shift.opened_at.isoformat() if shift.opened_at else None,
        "opening_cash_paisa": shift.opening_cash_paisa,
        "expected_cash_paisa": expected,
        "counted_cash_paisa": shift.counted_cash_paisa,
        "difference_paisa": shift.difference_paisa,
        "closed_at": shift.closed_at.isoformat() if shift.closed_at else None,
        "closing_notes": shift.closing_notes, "status": shift.status,
        "closed_by": shift.closed_by,
    }


def list_shifts(db: Session, user_id: int | None = None, status: str | None = None,
                limit: int = 50, offset: int = 0):
    q = db.query(CashShift)
    if user_id:
        q = q.filter(CashShift.user_id == user_id)
    if status:
        q = q.filter(CashShift.status == status)
    total = q.count()
    rows = q.order_by(CashShift.id.desc()).offset(offset).limit(limit).all()
    return [shift_out(db, s) for s in rows], total


def shift_ledger(db: Session, shift_id: int) -> dict:
    shift = db.get(CashShift, shift_id)
    if shift is None:
        raise ValueError("Shift not found")
    payments = [{"id": p.id, "invoice_id": p.invoice_id,
                 "invoice_number": (p.invoice.invoice_number if p.invoice else None),
                 "amount_paisa": p.amount_paisa, "method": p.method, "kind": p.kind,
                 "reference": p.reference, "created_at": p.created_at.isoformat()}
                for p in db.query(Payment).filter(Payment.shift_id == shift_id)
                .order_by(Payment.id).all()]
    movements = [{"id": m.id, "movement_type": m.movement_type,
                  "amount_paisa": m.amount_paisa, "reason": m.reason,
                  "reference": m.reference, "created_at": m.created_at.isoformat()}
                 for m in db.query(CashMovement)
                 .filter(CashMovement.shift_id == shift_id).order_by(CashMovement.id).all()]
    expenses = [{"id": e.id, "expense_number": e.expense_number,
                 "amount_paisa": e.amount_paisa, "description": e.description,
                 "created_at": e.created_at.isoformat()}
                for e in db.query(Expense).filter(Expense.shift_id == shift_id)
                .order_by(Expense.id).all()]
    return {"shift": shift_out(db, shift), "payments": payments,
            "movements": movements, "expenses": expenses}

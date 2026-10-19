"""Expenses with categories, summary aggregations, and audit trail."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.dates import ensure_datetime, range_utc, today_local
from ..models import Expense, ExpenseCategory
from ..services.settings_service import next_number


def list_categories(db: Session):
    return [
        {"id": c.id, "name": c.name, "is_active": c.is_active}
        for c in db.query(ExpenseCategory).order_by(ExpenseCategory.name).all()
    ]


def create_category(db: Session, name: str) -> ExpenseCategory:
    name = name.strip()
    if db.query(ExpenseCategory).filter(func.lower(ExpenseCategory.name) == name.lower()).first():
        raise ValueError("Category already exists")
    c = ExpenseCategory(name=name)
    db.add(c)
    db.commit()
    return c


def expense_out(db: Session, e: Expense) -> dict:
    cat = db.get(ExpenseCategory, e.category_id) if e.category_id else None
    return {
        "id": e.id,
        "expense_number": e.expense_number,
        "category_id": e.category_id,
        "category_name": cat.name if cat else None,
        "amount_paisa": e.amount_paisa,
        "expense_date": e.expense_date.isoformat() if e.expense_date else None,
        "method": e.method,
        "payee": e.payee,
        "description": e.description,
        "reference": e.reference,
        "attachment_path": e.attachment_path,
        "shift_id": e.shift_id,
        "created_by": e.created_by,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


def _apply_expense_filters(query, *, q=None, category_id=None, method=None, u_from=None, u_to=None):
    if category_id:
        query = query.filter(Expense.category_id == category_id)
    if method:
        query = query.filter(Expense.method == method)
    if u_from:
        query = query.filter(Expense.expense_date >= u_from)
    if u_to:
        query = query.filter(Expense.expense_date <= u_to)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Expense.expense_number.ilike(like))
            | (Expense.description.ilike(like))
            | (Expense.payee.ilike(like))
            | (Expense.reference.ilike(like))
        )
    return query


def list_expenses(
    db: Session,
    q: str | None = None,
    category_id: int | None = None,
    method: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    u_from, u_to = range_utc(date_from, date_to)
    query = _apply_expense_filters(
        db.query(Expense),
        q=q,
        category_id=category_id,
        method=method,
        u_from=u_from,
        u_to=u_to,
    )
    total = query.count()
    rows = query.order_by(Expense.id.desc()).offset(offset).limit(limit).all()
    return [expense_out(db, e) for e in rows], total


def expense_summary(
    db: Session,
    q: str | None = None,
    category_id: int | None = None,
    method: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    u_from, u_to = range_utc(date_from, date_to)
    filtered_q = _apply_expense_filters(
        db.query(func.coalesce(func.sum(Expense.amount_paisa), 0)),
        q=q,
        category_id=category_id,
        method=method,
        u_from=u_from,
        u_to=u_to,
    )
    filtered_total = int(filtered_q.scalar() or 0)

    today = today_local()
    t_from, t_to = range_utc(today, today)
    today_q = db.query(func.coalesce(func.sum(Expense.amount_paisa), 0))
    if t_from:
        today_q = today_q.filter(Expense.expense_date >= t_from)
    if t_to:
        today_q = today_q.filter(Expense.expense_date <= t_to)
    today_total = int(today_q.scalar() or 0)

    month_start = today[:8] + "01"
    m_from, m_to = range_utc(month_start, today)
    month_q = db.query(func.coalesce(func.sum(Expense.amount_paisa), 0))
    if m_from:
        month_q = month_q.filter(Expense.expense_date >= m_from)
    if m_to:
        month_q = month_q.filter(Expense.expense_date <= m_to)
    month_total = int(month_q.scalar() or 0)

    return {
        "filtered_total_paisa": filtered_total,
        "today_total_paisa": today_total,
        "month_total_paisa": month_total,
    }


def create_expense(db: Session, data: dict, user_id: int | None = None) -> Expense:
    if not db.get(ExpenseCategory, data["category_id"]):
        raise ValueError("Expense category does not exist")
    cleaned = dict(data)
    cleaned["expense_date"] = ensure_datetime(cleaned.get("expense_date"), default_now=True)
    e = Expense(
        expense_number=next_number(db, "expense_number", "EXP"),
        **cleaned,
        created_by=user_id,
    )
    db.add(e)
    db.commit()
    from ..services import audit_service
    audit_service.log(
        db,
        user_id=user_id,
        username=None,
        action="expense.create",
        entity_type="expense",
        entity_id=e.id,
        new_values={
            "expense_number": e.expense_number,
            "amount_paisa": e.amount_paisa,
            "method": e.method,
            "payee": e.payee,
        },
    )
    return e


def update_expense(
    db: Session,
    e: Expense,
    data: dict,
    user_id: int | None = None,
) -> Expense:
    if "category_id" in data and data["category_id"] is not None:
        if not db.get(ExpenseCategory, data["category_id"]):
            raise ValueError("Expense category does not exist")
    old = {
        "amount_paisa": e.amount_paisa,
        "description": e.description,
        "method": e.method,
        "expense_date": str(e.expense_date),
    }
    for k, v in data.items():
        if k == "expense_date" and v is not None:
            v = ensure_datetime(v, default_now=False)
        if v is not None:
            setattr(e, k, v)
    db.commit()
    from ..services import audit_service
    audit_service.log(
        db,
        user_id=user_id,
        username=None,
        action="expense.update",
        entity_type="expense",
        entity_id=e.id,
        old_values=old,
        new_values={"amount_paisa": e.amount_paisa},
    )
    return e


def delete_expense(db: Session, e: Expense, user_id: int | None = None) -> None:
    from ..services import audit_service
    audit_service.log(
        db,
        user_id=user_id,
        username=None,
        action="expense.delete",
        entity_type="expense",
        entity_id=e.id,
        old_values={
            "amount_paisa": e.amount_paisa,
            "expense_number": e.expense_number,
        },
    )
    db.delete(e)
    db.commit()


def expenses_by_category(
    db: Session,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    u_from, u_to = range_utc(date_from, date_to)
    q = db.query(
        ExpenseCategory.name,
        func.coalesce(func.sum(Expense.amount_paisa), 0),
        func.count(Expense.id),
    ).outerjoin(Expense, Expense.category_id == ExpenseCategory.id)
    if u_from:
        q = q.filter(Expense.expense_date >= u_from)
    if u_to:
        q = q.filter(Expense.expense_date <= u_to)
    return [
        {"category": name, "amount_paisa": int(total), "count": cnt}
        for name, total, cnt in q.group_by(ExpenseCategory.name).all()
    ]

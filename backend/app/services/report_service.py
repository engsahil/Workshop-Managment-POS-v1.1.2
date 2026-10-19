"""Dashboard + reports. Every figure is computed live from the database."""
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.dates import range_utc, local_date_expr, today_local
from ..models import (Invoice, InvoiceItem, Payment, Expense, JobCard, JobService,
                      JobPart, Product, StockMovement, Customer, Supplier,
                      Purchase, PurchasePayment, PurchaseReturn, CashShift,
                      Mechanic, User, SaleReturn, Vehicle)
from ..services.inventory_service import inventory_valuation, low_stock_products


def today_karachi() -> str:
    return today_local()


def _range_args(date_from: str | None, date_to: str | None):
    return range_utc(date_from, date_to)


def _active_invoices(db, date_from=None, date_to=None):
    q = db.query(Invoice).filter(Invoice.status != "void")
    if date_from:
        q = q.filter(Invoice.created_at >= date_from)
    if date_to:
        q = q.filter(Invoice.created_at <= date_to)
    return q


# ---------------------------------------------------------------- dashboard
def dashboard(db: Session, date_from: str | None = None, date_to: str | None = None,
              user=None) -> dict:
    if not date_from or not date_to:
        today = today_karachi()
        date_from = date_from or today
        date_to = date_to or today
    _from, _to = _range_args(date_from, date_to)

    inv_q = _active_invoices(db, _from, _to)
    invoices = inv_q.all()
    revenue = sum(i.total_paisa for i in invoices)
    discounts = sum(i.discount_paisa for i in invoices)
    cogs = sum(i.cost_of_goods_paisa for i in invoices)
    tax = sum(i.tax_paisa for i in invoices)
    invoice_count = len(invoices)
    parts_sales = sum(
        it.line_total_paisa for i in invoices for it in i.items
        if it.item_type == "product"
    )
    service_sales = sum(
        it.line_total_paisa for i in invoices for it in i.items
        if it.item_type == "service"
    )

    pay_q = db.query(Payment).filter(Payment.amount_paisa > 0)
    if _from:
        pay_q = pay_q.filter(Payment.created_at >= _from)
    if _to:
        pay_q = pay_q.filter(Payment.created_at <= _to)
    payments = pay_q.all()
    collections = sum(p.amount_paisa for p in payments if p.kind != "refund")
    refunds_paid = -sum(p.amount_paisa for p in payments if p.amount_paisa < 0)

    cash_received = sum(p.amount_paisa for p in payments if p.method == "cash" and p.amount_paisa > 0)
    card_digital = sum(p.amount_paisa for p in payments
                       if p.method != "cash" and p.amount_paisa > 0)
    by_method = {}
    for p in payments:
        if p.amount_paisa > 0:
            by_method[p.method] = by_method.get(p.method, 0) + p.amount_paisa

    outstanding = (db.query(func.coalesce(func.sum(Invoice.balance_paisa), 0))
                   .filter(Invoice.status.in_(("partial", "credit", "returned"))).scalar() or 0)
    advances = (db.query(func.coalesce(func.sum(Payment.amount_paisa), 0))
                .filter(Payment.kind == "advance").scalar() or 0)
    credit_customers = (db.query(func.count(func.distinct(Invoice.customer_id)))
                        .filter(Invoice.balance_paisa > 0,
                                Invoice.status.in_(("partial", "credit", "returned"))).scalar() or 0)

    # gross profit: revenue minus COGS minus approved return value
    returns_value = (db.query(func.coalesce(func.sum(SaleReturn.total_paisa), 0))
                     .filter(SaleReturn.status == "approved")
                     .filter(SaleReturn.return_date >= _from if _from else True)
                     .filter(SaleReturn.return_date <= _to if _to else True)
                     .scalar() or 0)
    gross_profit = revenue - cogs - returns_value

    exp_q = db.query(Expense)
    if _from:
        exp_q = exp_q.filter(Expense.expense_date >= _from)
    if _to:
        exp_q = exp_q.filter(Expense.expense_date <= _to)
    expenses = sum(e.amount_paisa for e in exp_q.all())
    net_profit = gross_profit - expenses

    active_jobs = db.query(func.count(JobCard.id)).filter(
        JobCard.status.in_(("received", "inspection", "awaiting_approval", "approved",
                            "in_progress", "waiting_for_parts", "on_hold"))).scalar() or 0
    vehicles_in_service = (db.query(func.count(func.distinct(JobCard.vehicle_id)))
                           .filter(JobCard.status.in_(("in_progress", "waiting_for_parts",
                                                       "on_hold", "completed"))).scalar() or 0)
    jobs_done = db.query(func.count(JobCard.id)).filter(
        JobCard.status.in_(("completed", "ready_for_delivery", "delivered"))).scalar() or 0
    jobs_delivered_range = db.query(func.count(JobCard.id)).filter(
        JobCard.status == "delivered",
        JobCard.updated_at >= _from if _from else True).scalar() or 0

    low = low_stock_products(db)
    valuation = inventory_valuation(db)

    def _inv_vehicle(inv: Invoice) -> str:
        vid = inv.vehicle_id
        if not vid and inv.job_id:
            jb = db.get(JobCard, inv.job_id)
            if jb:
                vid = jb.vehicle_id
        if vid:
            v = db.get(Vehicle, vid)
            if v:
                parts = [p for p in (v.make, v.model) if p]
                return " ".join(parts) or v.registration_no or "—"
        if inv.customer_id:
            v = db.query(Vehicle).filter(Vehicle.customer_id == inv.customer_id).first()
            if v:
                parts = [p for p in (v.make, v.model) if p]
                return " ".join(parts) or v.registration_no or "—"
        return "—"

    recent_invoices = [
        {"id": i.id, "invoice_number": i.invoice_number,
         "customer_name": (db.get(Customer, i.customer_id).name
                           if i.customer_id and db.get(Customer, i.customer_id) else "Walk-in"),
         "vehicle": _inv_vehicle(i),
         "total_paisa": i.total_paisa, "balance_paisa": i.balance_paisa,
         "status": i.status, "created_at": i.created_at.isoformat() if i.created_at else None}
        for i in db.query(Invoice).filter(Invoice.status != "void")
        .order_by(Invoice.id.desc()).limit(8).all()]
    recent_jobs = [
        {"id": j.id, "job_number": j.job_number, "status": j.status,
         "customer_name": (db.get(Customer, j.customer_id).name
                           if db.get(Customer, j.customer_id) else None),
         "registration_no": (db.get(Vehicle, j.vehicle_id).registration_no
                             if db.get(Vehicle, j.vehicle_id) else None),
         "checkin_at": j.checkin_at.isoformat() if j.checkin_at else None}
        for j in db.query(JobCard).order_by(JobCard.id.desc()).limit(8).all()]
    recent_expenses = [
        {"id": e.id, "expense_number": e.expense_number,
         "amount_paisa": e.amount_paisa,
         "description": e.description,
         "expense_date": e.expense_date.isoformat() if e.expense_date else None}
        for e in db.query(Expense).order_by(Expense.id.desc()).limit(8).all()]

    return {
        "range": {"from": date_from, "to": date_to},
        "today_date": today_karachi(),
        "sales": {
            "revenue_paisa": revenue, "discounts_paisa": discounts,
            "tax_paisa": tax, "invoice_count": invoice_count,
            "refunds_paisa": refunds_paid,
            "net_revenue_paisa": revenue - returns_value,
            "parts_paisa": parts_sales,
            "services_paisa": service_sales,
        },
        "collections": {
            "total_paisa": collections, "cash_paisa": cash_received,
            "card_digital_paisa": card_digital,
            "by_method_paisa": by_method,
        },
        "receivables": {
            "outstanding_paisa": int(outstanding), "credit_customers": credit_customers,
            "advances_paisa": int(advances),
        },
        "profit": {
            "cogs_paisa": cogs, "gross_profit_paisa": gross_profit,
            "expenses_paisa": expenses, "net_profit_paisa": net_profit,
        },
        "jobs": {"active": active_jobs, "vehicles_in_service": vehicles_in_service,
                 "completed": jobs_done, "delivered_in_range": jobs_delivered_range},
        "inventory": {"low_stock_count": len(low), "low_stock_items": low[:10],
                      "valuation_paisa": valuation},
        "recent": {"invoices": recent_invoices, "jobs": recent_jobs,
                   "expenses": recent_expenses},
        "definitions": {
            "revenue": "Sum of non-void invoice totals in range",
            "collections": "Money actually received (payments) in range",
            "outstanding": "Unpaid balances on non-void invoices (all time)",
            "gross_profit": "Revenue − COGS − approved returns value",
            "net_profit": "Gross profit − expenses in range (estimate)",
        },
    }


# ---------------------------------------------------------------- sales reports
def sales_trend(db: Session, date_from: str, date_to: str, group: str = "day") -> list[dict]:
    _from, _to = _range_args(date_from, date_to)
    rows = (db.query(
                local_date_expr(Invoice.created_at).label("d"),
                func.coalesce(func.sum(Invoice.total_paisa), 0),
                func.count(Invoice.id))
            .filter(Invoice.status != "void")
            .filter(Invoice.created_at >= _from)
            .filter(Invoice.created_at <= _to)
            .group_by("d").order_by("d").all())
    return [{"date": r[0], "revenue_paisa": int(r[1]), "invoices": r[2]} for r in rows]


def sales_by(db: Session, field: str, date_from: str | None = None,
             date_to: str | None = None) -> list[dict]:
    """field in {product, service, category, cashier, method, brand, customer}"""
    _from, _to = _range_args(date_from, date_to)
    out = []
    if field in ("product", "service"):
        rows = (db.query(InvoiceItem.description,
                         func.sum(InvoiceItem.quantity),
                         func.sum(InvoiceItem.line_total_paisa))
                .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
                .filter(Invoice.status != "void")
                .filter(InvoiceItem.item_type == ("product" if field == "product" else "service")))
        if _from:
            rows = rows.filter(Invoice.created_at >= _from)
        if _to:
            rows = rows.filter(Invoice.created_at <= _to)
        rows = rows.group_by(InvoiceItem.description).order_by(
            func.sum(InvoiceItem.line_total_paisa).desc()).limit(100).all()
        out = [{"name": r[0], "quantity": float(r[1] or 0), "amount_paisa": int(r[2] or 0)}
               for r in rows]
    elif field == "category":
        rows = (db.query(Product.name, func.sum(InvoiceItem.line_total_paisa))
                .join(InvoiceItem, InvoiceItem.product_id == Product.id)
                .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
                .filter(Invoice.status != "void"))
        if _from:
            rows = rows.filter(Invoice.created_at >= _from)
        if _to:
            rows = rows.filter(Invoice.created_at <= _to)
        rows = rows.group_by(Product.name).order_by(func.sum(InvoiceItem.line_total_paisa).desc()).limit(100).all()
        out = [{"name": r[0], "quantity": None, "amount_paisa": int(r[1] or 0)} for r in rows]
    elif field == "cashier":
        rows = (db.query(User.full_name, func.sum(Invoice.total_paisa),
                         func.count(Invoice.id))
                .join(Invoice, Invoice.cashier_id == User.id)
                .filter(Invoice.status != "void"))
        if _from:
            rows = rows.filter(Invoice.created_at >= _from)
        if _to:
            rows = rows.filter(Invoice.created_at <= _to)
        rows = rows.group_by(User.full_name).all()
        out = [{"name": r[0], "quantity": r[2], "amount_paisa": int(r[1] or 0)} for r in rows]
    elif field == "method":
        rows = (db.query(Payment.method, func.sum(Payment.amount_paisa),
                         func.count(Payment.id))
                .filter(Payment.amount_paisa > 0))
        if _from:
            rows = rows.filter(Payment.created_at >= _from)
        if _to:
            rows = rows.filter(Payment.created_at <= _to)
        rows = rows.group_by(Payment.method).all()
        out = [{"name": r[0], "quantity": r[2], "amount_paisa": int(r[1] or 0)} for r in rows]
    elif field == "customer":
        rows = (db.query(Customer.name, func.sum(Invoice.total_paisa),
                         func.count(Invoice.id))
                .join(Invoice, Invoice.customer_id == Customer.id)
                .filter(Invoice.status != "void"))
        if _from:
            rows = rows.filter(Invoice.created_at >= _from)
        if _to:
            rows = rows.filter(Invoice.created_at <= _to)
        rows = rows.group_by(Customer.name).order_by(func.sum(Invoice.total_paisa).desc()).limit(100).all()
        out = [{"name": r[0], "quantity": r[2], "amount_paisa": int(r[1] or 0)} for r in rows]
    return out


def profit_report(db: Session, date_from: str | None = None,
                  date_to: str | None = None) -> dict:
    _from, _to = _range_args(date_from, date_to)
    inv_q = _active_invoices(db, _from, _to)
    invoices = inv_q.all()
    revenue = sum(i.total_paisa for i in invoices)
    cogs = sum(i.cost_of_goods_paisa for i in invoices)
    labor = (db.query(func.coalesce(func.sum(InvoiceItem.line_total_paisa), 0))
             .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
             .filter(Invoice.status != "void", InvoiceItem.item_type == "service"))
    if _from:
        labor = labor.filter(Invoice.created_at >= _from)
    if _to:
        labor = labor.filter(Invoice.created_at <= _to)
    labor = labor.scalar() or 0
    exp_q = db.query(func.coalesce(func.sum(Expense.amount_paisa), 0))
    if _from:
        exp_q = exp_q.filter(Expense.expense_date >= _from)
    if _to:
        exp_q = exp_q.filter(Expense.expense_date <= _to)
    expenses = exp_q.scalar() or 0
    returns_value = (db.query(func.coalesce(func.sum(SaleReturn.total_paisa), 0))
                     .filter(SaleReturn.status == "approved")
                     .scalar() or 0)
    gross = revenue - cogs - returns_value
    return {
        "revenue_paisa": revenue, "labor_revenue_paisa": labor,
        "cogs_paisa": cogs, "returns_value_paisa": returns_value,
        "gross_profit_paisa": gross, "expenses_paisa": int(expenses),
        "net_profit_paisa": gross - int(expenses),
        "methodology": "Gross profit = invoice revenue − COGS (weighted average cost at sale time) "
                       "− approved returns. Net profit = gross profit − recorded expenses. "
                       "This is an accounting estimate; it is not a cash-flow statement.",
    }


def payment_summary(db: Session, date_from: str | None = None,
                    date_to: str | None = None) -> list[dict]:
    _from, _to = _range_args(date_from, date_to)
    q = db.query(Payment.method, func.sum(Payment.amount_paisa), func.count(Payment.id))
    if _from:
        q = q.filter(Payment.created_at >= _from)
    if _to:
        q = q.filter(Payment.created_at <= _to)
    return [{"method": r[0], "amount_paisa": int(r[1] or 0), "count": r[2]}
            for r in q.group_by(Payment.method).all()]


# ---------------------------------------------------------------- inventory reports
def stock_report(db: Session, q: str | None = None, low_only: bool = False):
    query = db.query(Product).filter(Product.is_service.is_(False))
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    if low_only:
        query = query.filter(Product.quantity_on_hand <= Product.min_stock)
    rows = query.order_by(Product.name.asc()).all()
    return [{
        "id": p.id, "name": p.name, "sku": p.sku, "unit": p.unit,
        "quantity_on_hand": p.quantity_on_hand, "min_stock": p.min_stock,
        "avg_cost_paisa": p.purchase_cost_paisa,
        "selling_price_paisa": p.selling_price_paisa,
        "value_paisa": p.quantity_on_hand * p.purchase_cost_paisa,
        "status": ("out" if p.quantity_on_hand <= 0
                   else "low" if p.quantity_on_hand <= p.min_stock else "ok"),
    } for p in rows]


# ---------------------------------------------------------------- statements
def customer_statement(db: Session, customer_id: int,
                       date_from: str | None = None, date_to: str | None = None) -> dict:
    date_from, date_to = range_utc(date_from, date_to)
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise ValueError("Customer not found")
    rows = []
    q = db.query(Invoice).filter(Invoice.customer_id == customer_id)
    if date_from:
        q = q.filter(Invoice.created_at >= date_from)
    if date_to:
        q = q.filter(Invoice.created_at <= date_to)
    for i in q.order_by(Invoice.id).all():
        rows.append({"date": i.created_at.isoformat() if i.created_at else None,
                     "type": "invoice", "ref": i.invoice_number,
                     "charge_paisa": i.total_paisa,
                     "payment_paisa": 0, "note": f"Status: {i.status}",
                     "status": i.status})
    pq = db.query(Payment).filter(Payment.customer_id == customer_id,
                                  Payment.amount_paisa > 0)
    if date_from:
        pq = pq.filter(Payment.created_at >= date_from)
    if date_to:
        pq = pq.filter(Payment.created_at <= date_to)
    for p in pq.order_by(Payment.id).all():
        rows.append({"date": p.created_at.isoformat() if p.created_at else None,
                     "type": "payment", "ref": p.reference or p.kind,
                     "charge_paisa": 0, "payment_paisa": p.amount_paisa,
                     "note": f"{p.kind} via {p.method}", "status": "ok"})
    rq = db.query(SaleReturn).filter(SaleReturn.customer_id == customer_id,
                                     SaleReturn.status == "approved")
    for r in rq.all():
        rows.append({"date": r.return_date.isoformat() if r.return_date else None,
                     "type": "return", "ref": r.return_number,
                     "charge_paisa": 0, "payment_paisa": 0,
                     "note": f"Approved return ({r.restock_action}), "
                             f"refund {r.refund_method}, Rs. {r.total_paisa/100:,.2f}",
                     "status": r.status})
    rows.sort(key=lambda x: x["date"] or "")
    balance = sum(i.balance_paisa for i in
                  db.query(Invoice).filter(Invoice.customer_id == customer_id,
                                           Invoice.status.in_(("partial", "credit", "returned"))).all())
    credit = (db.query(func.coalesce(func.sum(SaleReturn.credit_amount_paisa), 0))
              .filter(SaleReturn.customer_id == customer_id,
                      SaleReturn.status == "approved").scalar() or 0)
    advance = (db.query(func.coalesce(func.sum(Payment.amount_paisa), 0))
               .filter(Payment.customer_id == customer_id,
                       Payment.kind == "advance").scalar() or 0)
    return {"customer": {"id": customer.id, "name": customer.name,
                         "phone": customer.phone},
            "entries": rows,
            "outstanding_paisa": int(balance) - int(credit),
            "advance_paisa": int(advance)}


def supplier_statement(db: Session, supplier_id: int) -> dict:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise ValueError("Supplier not found")
    from ..services.purchase_service import supplier_statement
    rows = supplier_statement(db, supplier_id)
    balance = 0
    for r in rows:
        balance += r["balance_impact"]
    return {"supplier": {"id": supplier.id, "name": supplier.name,
                         "phone": supplier.phone},
            "entries": rows, "balance_paisa": int(balance)}


# ---------------------------------------------------------------- jobs / mechanics
def jobs_report(db: Session, status: str | None = None, mechanic_id: int | None = None,
                date_from: str | None = None, date_to: str | None = None,
                limit: int = 100, offset: int = 0):
    date_from, date_to = range_utc(date_from, date_to)
    q = db.query(JobCard)
    if status:
        q = q.filter(JobCard.status == status)
    if mechanic_id:
        q = q.filter(JobCard.mechanic_id == mechanic_id)
    if date_from:
        q = q.filter(JobCard.checkin_at >= date_from)
    if date_to:
        q = q.filter(JobCard.checkin_at <= date_to)
    total = q.count()
    rows = q.order_by(JobCard.id.desc()).offset(offset).limit(limit).all()
    return rows, total


def mechanic_performance(db: Session, date_from: str | None = None,
                         date_to: str | None = None) -> list[dict]:
    _from, _to = _range_args(date_from, date_to)
    out = []
    mechanics = db.query(Mechanic).filter(Mechanic.is_active.is_(True)).all()
    for m in mechanics:
        jobs_q = db.query(JobCard).filter(JobCard.mechanic_id == m.id)
        jobs_done = jobs_q.filter(JobCard.status.in_(("completed", "ready_for_delivery",
                                                      "delivered"))).count()
        jobs_total = jobs_q.count()
        labor = (db.query(func.coalesce(func.sum(JobService.line_total_paisa), 0))
                 .join(JobCard, JobService.job_id == JobCard.id)
                 .filter(JobService.mechanic_id == m.id))
        if _from:
            labor = labor.filter(JobCard.checkin_at >= _from)
        if _to:
            labor = labor.filter(JobCard.checkin_at <= _to)
        labor_total = labor.scalar() or 0
        out.append({
            "mechanic_id": m.id, "name": m.name, "skill": m.skill,
            "jobs_assigned": jobs_total, "jobs_completed": jobs_done,
            "labor_revenue_paisa": int(labor_total),
            "commission_type": m.commission_type,
            "commission_value": m.commission_value,
            "commission_due_paisa": _commission_due(m, jobs_done, int(labor_total)),
        })
    return out


def _commission_due(m: Mechanic, jobs_done: int, labor_total: int) -> int:
    if m.commission_type == "percent_per_job":
        return int(labor_total * m.commission_value / 10000)  # value stored as percent*100
    if m.commission_type == "fixed_per_job":
        return jobs_done * m.commission_value
    return 0


def shifts_reconciliation(db: Session, limit: int = 50, offset: int = 0) -> list[dict]:
    from .shift_service import expected_cash
    rows = (db.query(CashShift).order_by(CashShift.id.desc())
            .offset(offset).limit(limit).all())
    out = []
    for s in rows:
        # open shifts: expected cash must reflect payments made since opening
        expected = (expected_cash(db, s) if s.status == "open"
                    else s.expected_cash_paisa)
        out.append(
            {"id": s.id, "user_id": s.user_id,
             "user_name": (db.get(User, s.user_id).full_name if db.get(User, s.user_id) else None),
             "opened_at": s.opened_at.isoformat(), "closed_at": s.closed_at.isoformat() if s.closed_at else None,
             "opening_cash_paisa": s.opening_cash_paisa,
             "expected_cash_paisa": expected,
             "counted_cash_paisa": s.counted_cash_paisa,
             "difference_paisa": s.difference_paisa, "status": s.status})
    return out


def returns_report(db: Session, date_from: str | None = None,
                   date_to: str | None = None) -> list[dict]:
    date_from, date_to = range_utc(date_from, date_to)
    q = db.query(SaleReturn)
    if date_from:
        q = q.filter(SaleReturn.return_date >= date_from)
    if date_to:
        q = q.filter(SaleReturn.return_date <= date_to)
    return [
        {"id": r.id, "return_number": r.return_number, "invoice_id": r.invoice_id,
         "customer": (db.get(Customer, r.customer_id).name
                      if r.customer_id and db.get(Customer, r.customer_id) else None),
         "reason": r.reason, "status": r.status,
         "restock_action": r.restock_action, "total_paisa": r.total_paisa,
         "refund_method": r.refund_method,
         "return_date": r.return_date.isoformat() if r.return_date else None}
        for r in q.order_by(SaleReturn.id.desc()).all()]


def tax_summary(db: Session, date_from: str | None = None, date_to: str | None = None) -> dict:
    _from, _to = _range_args(date_from, date_to)
    q = _active_invoices(db, _from, _to)
    total_tax = sum(i.tax_paisa for i in q.all())
    return {"tax_paisa": total_tax,
            "note": "Tax is only collected when enabled in business settings."}


def overdue_credit(db: Session) -> list[dict]:
    """Credit invoices unpaid for more than 7 days."""
    cutoff = datetime.now() - timedelta(days=7)
    rows = (db.query(Invoice).filter(Invoice.balance_paisa > 0,
                                     Invoice.status.in_(("partial", "credit", "returned")),
                                     Invoice.created_at < cutoff)
            .order_by(Invoice.id.asc()).limit(100).all())
    return [{
        "invoice_id": i.id, "invoice_number": i.invoice_number,
        "customer": (db.get(Customer, i.customer_id).name
                     if i.customer_id and db.get(Customer, i.customer_id) else "Walk-in"),
        "balance_paisa": i.balance_paisa,
        "created_at": i.created_at.isoformat(),
    } for i in rows]

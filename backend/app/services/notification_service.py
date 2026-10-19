"""In-app notifications (low stock, job status, invoices, payments, warranty claims, daily summary)."""
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ..core.dates import range_utc, today_local
from ..core.money import format_pkr
from ..models import (
    Customer,
    Expense,
    Invoice,
    JobCard,
    Notification,
    Payment,
    Product,
    Vehicle,
    WarrantyClaim,
)


def push(
    db: Session,
    *,
    type_: str | None = None,
    type: str | None = None,
    title: str,
    message: str = "",
    related_type: str | None = None,
    related_id: int | None = None,
    deduplicate_unread: bool = True,
) -> Notification | None:
    ntype = type_ or type or "info"
    try:
        if deduplicate_unread:
            q = db.query(Notification).filter(
                Notification.type == ntype,
                Notification.title == title[:200],
                Notification.is_read.is_(False),
            )
            if related_type is not None:
                q = q.filter(Notification.related_type == related_type)
            if related_id is not None:
                q = q.filter(Notification.related_id == related_id)
            existing = q.order_by(Notification.id.desc()).first()
            if existing:
                existing.message = (message or "")[:500]
                db.flush()
                db.commit()
                return existing

        n = Notification(
            type=ntype,
            title=title[:200],
            message=(message or "")[:500],
            related_type=related_type,
            related_id=related_id,
        )
        db.add(n)
        db.flush()
        db.commit()
        return n
    except Exception:
        db.rollback()
        return None


def list_notifications(db: Session, limit: int = 50, unread_only: bool = False):
    q = db.query(Notification)
    if unread_only:
        q = q.filter(Notification.is_read.is_(False))
    return q.order_by(Notification.id.desc()).limit(limit).all()


def mark_read(db: Session, ids: list[int]) -> int:
    if not ids:
        return 0
    n = db.query(Notification).filter(Notification.id.in_(ids)).update(
        {"is_read": True}, synchronize_session=False
    )
    db.commit()
    return n


def mark_all_read(db: Session) -> int:
    n = db.query(Notification).filter(Notification.is_read.is_(False)).update(
        {"is_read": True}, synchronize_session=False
    )
    db.commit()
    return n


def unread_count(db: Session) -> int:
    return db.query(Notification).filter(Notification.is_read.is_(False)).count()


def check_low_stock(db: Session) -> None:
    """Create a notification for every product below its minimum level."""
    low = (
        db.query(Product)
        .filter(
            and_(
                Product.is_active.is_(True),
                Product.is_service.is_(False),
                Product.min_stock > 0,
                Product.quantity_on_hand <= Product.min_stock,
            )
        )
        .all()
    )
    existing_titles = {
        n.title
        for n in db.query(Notification)
        .filter(Notification.type == "low_stock", Notification.is_read.is_(False))
        .all()
    }
    for p in low:
        title = f"Low stock: {p.name}"
        if title in existing_titles:
            continue
        push(
            db,
            type_="low_stock",
            title=title,
            message=f"Only {p.quantity_on_hand} {p.unit}(s) left (min level {p.min_stock}). SKU: {p.sku or '-'}",
            related_type="product",
            related_id=p.id,
        )


def job_created_notification(db: Session, job: JobCard) -> None:
    cust = job.customer or (db.get(Customer, job.customer_id) if job.customer_id else None)
    veh = job.vehicle or (db.get(Vehicle, job.vehicle_id) if job.vehicle_id else None)
    cust_name = cust.name if cust else "Customer"
    reg = veh.registration_no if veh and veh.registration_no else "Vehicle"
    push(
        db,
        type_="job_status",
        title=f"Service job opened: {job.job_number}",
        message=f"{reg} ({cust_name}) checked in for service.",
        related_type="job",
        related_id=job.id,
    )


def job_status_notification(db: Session, job: JobCard, old_status: str = "", user=None) -> None:
    cust = job.customer or (db.get(Customer, job.customer_id) if job.customer_id else None)
    veh = job.vehicle or (db.get(Vehicle, job.vehicle_id) if job.vehicle_id else None)
    cust_name = cust.name if cust else "Customer"
    reg = veh.registration_no if veh and veh.registration_no else "Vehicle"
    status_label = (job.status or "").replace("_", " ").title()
    if job.status == "ready_for_delivery":
        title = f"Ready for delivery: {job.job_number}"
        msg = f"{reg} ({cust_name}) is ready for customer handover."
    else:
        title = f"Job {job.job_number} - {status_label}"
        msg = f"{reg} ({cust_name}) moved from {(old_status or '').replace('_', ' ')} to {(job.status or '').replace('_', ' ')}."
    push(
        db,
        type_="job_status",
        title=title,
        message=msg,
        related_type="job",
        related_id=job.id,
        deduplicate_unread=False,
    )


def invoice_notification(db: Session, inv: Invoice) -> None:
    cust = db.get(Customer, inv.customer_id) if inv.customer_id else None
    cust_name = cust.name if cust else "Walk-in Customer"
    if (inv.balance_paisa or 0) > 0:
        push(
            db,
            type_="payment_due",
            title=f"Invoice {inv.invoice_number} — Balance Due",
            message=f"{cust_name}: Total {format_pkr(inv.total_paisa)}, unpaid balance {format_pkr(inv.balance_paisa)}.",
            related_type="invoice",
            related_id=inv.id,
        )
    else:
        push(
            db,
            type_="payment",
            title=f"Invoice {inv.invoice_number} issued",
            message=f"{cust_name}: Paid in full ({format_pkr(inv.total_paisa)}).",
            related_type="invoice",
            related_id=inv.id,
        )


def payment_notification(db: Session, inv: Invoice, amount_paisa: int, method: str = "cash") -> None:
    push(
        db,
        type_="payment",
        title=f"Payment received on {inv.invoice_number}",
        message=f"Collected {format_pkr(amount_paisa)} via {method}. Remaining balance: {format_pkr(inv.balance_paisa)}.",
        related_type="invoice",
        related_id=inv.id,
        deduplicate_unread=False,
    )


def warranty_claim_notification(db: Session, claim: WarrantyClaim, *, is_new: bool = True) -> None:
    cust = db.get(Customer, claim.customer_id) if claim.customer_id else None
    cust_name = cust.name if cust else "Customer"
    status_label = (claim.status or "open").replace("_", " ").title()
    if is_new:
        title = f"Warranty claim submitted: {claim.claim_number}"
        msg = f"{cust_name} — {(claim.description or 'New claim')[:100]}"
    else:
        title = f"Warranty claim {claim.claim_number} — {status_label}"
        msg = f"{cust_name} — {(claim.resolution or status_label)[:100]}"
    push(
        db,
        type_="warranty_claim",
        title=title,
        message=msg,
        related_type="claim",
        related_id=claim.id,
        deduplicate_unread=not is_new,
    )


def backup_notification(db: Session, filename: str, *, action: str = "created", ok: bool = True) -> None:
    title = f"Database backup {action}" if ok else f"Database backup {action} failed"
    push(
        db,
        type_="backup",
        title=title,
        message=f"File: {filename}",
        related_type="backup",
        deduplicate_unread=False,
    )


def daily_summary_data(db: Session, target_date: str | None = None) -> dict:
    day = (target_date or "").strip()[:10] or today_local()
    u_from, u_to = range_utc(day, day)

    inv_q = db.query(Invoice).filter(Invoice.status != "void")
    if u_from:
        inv_q = inv_q.filter(Invoice.created_at >= u_from)
    if u_to:
        inv_q = inv_q.filter(Invoice.created_at <= u_to)
    invoices = inv_q.all()

    invoiced_sales_paisa = sum(i.total_paisa or 0 for i in invoices)
    day_invoice_balance_paisa = sum(i.balance_paisa or 0 for i in invoices)

    pay_q = db.query(func.coalesce(func.sum(Payment.amount_paisa), 0)).filter(Payment.amount_paisa > 0)
    if u_from:
        pay_q = pay_q.filter(Payment.created_at >= u_from)
    if u_to:
        pay_q = pay_q.filter(Payment.created_at <= u_to)
    payments_received_paisa = int(pay_q.scalar() or 0)

    outstanding_balances_paisa = int(
        db.query(func.coalesce(func.sum(Invoice.balance_paisa), 0))
        .filter(Invoice.status.in_(("partial", "credit", "returned")))
        .scalar()
        or 0
    )

    jobs_opened_q = db.query(func.count(JobCard.id))
    jobs_completed_q = db.query(func.count(JobCard.id)).filter(
        JobCard.status.in_(("completed", "ready_for_delivery", "delivered"))
    )
    jobs_delivered_q = db.query(func.count(JobCard.id)).filter(JobCard.status == "delivered")
    if u_from:
        jobs_opened_q = jobs_opened_q.filter(JobCard.checkin_at >= u_from)
        jobs_completed_q = jobs_completed_q.filter(JobCard.updated_at >= u_from)
        jobs_delivered_q = jobs_delivered_q.filter(JobCard.updated_at >= u_from)
    if u_to:
        jobs_opened_q = jobs_opened_q.filter(JobCard.checkin_at <= u_to)
        jobs_completed_q = jobs_completed_q.filter(JobCard.updated_at <= u_to)
        jobs_delivered_q = jobs_delivered_q.filter(JobCard.updated_at <= u_to)

    jobs_opened = int(jobs_opened_q.scalar() or 0)
    jobs_completed = int(jobs_completed_q.scalar() or 0)
    jobs_delivered = int(jobs_delivered_q.scalar() or 0)

    exp_q = db.query(
        func.coalesce(func.sum(Expense.amount_paisa), 0),
        func.count(Expense.id),
    )
    if u_from:
        exp_q = exp_q.filter(Expense.expense_date >= u_from)
    if u_to:
        exp_q = exp_q.filter(Expense.expense_date <= u_to)
    exp_row = exp_q.one()
    expenses_paisa = int(exp_row[0] or 0)
    expenses_count = int(exp_row[1] or 0)

    low_stock_count = int(
        db.query(func.count(Product.id))
        .filter(
            Product.is_active.is_(True),
            Product.is_service.is_(False),
            Product.min_stock > 0,
            Product.quantity_on_hand <= Product.min_stock,
        )
        .scalar()
        or 0
    )

    warranty_claims_open = int(
        db.query(func.count(WarrantyClaim.id))
        .filter(WarrantyClaim.status.in_(("open", "under_review", "approved")))
        .scalar()
        or 0
    )
    claims_today_q = db.query(func.count(WarrantyClaim.id))
    if u_from:
        claims_today_q = claims_today_q.filter(WarrantyClaim.claim_date >= u_from)
    if u_to:
        claims_today_q = claims_today_q.filter(WarrantyClaim.claim_date <= u_to)
    warranty_claims_today = int(claims_today_q.scalar() or 0)

    return {
        "date": day,
        "invoiced_sales_paisa": invoiced_sales_paisa,
        "total_sales_paisa": invoiced_sales_paisa,
        "invoice_count": len(invoices),
        "payments_received_paisa": payments_received_paisa,
        "day_invoice_balance_paisa": day_invoice_balance_paisa,
        "outstanding_balances_paisa": outstanding_balances_paisa,
        "jobs_opened": jobs_opened,
        "jobs_completed": jobs_completed,
        "jobs_delivered": jobs_delivered,
        "expenses_paisa": expenses_paisa,
        "expenses_recorded_paisa": expenses_paisa,
        "expenses_count": expenses_count,
        "low_stock_count": low_stock_count,
        "low_stock_alerts": low_stock_count,
        "warranty_claims_open": warranty_claims_open,
        "warranty_claims_today": warranty_claims_today,
        "net_daily_operating_paisa": invoiced_sales_paisa - expenses_paisa,
    }


DEFAULT_NOTIFICATION_PREFS = {
    "job_alerts": True,
    "invoice_alerts": True,
    "low_stock_alerts": True,
    "warranty_alerts": True,
    "daily_summary_alerts": True,
    "system_alerts": True,
}


def get_notification_prefs(db: Session) -> dict:
    import json
    from .settings_service import get_setting

    raw = get_setting(db, "notification_preferences")
    if not raw:
        return dict(DEFAULT_NOTIFICATION_PREFS)
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(parsed, dict):
            return {**DEFAULT_NOTIFICATION_PREFS, **{k: bool(v) for k, v in parsed.items() if k in DEFAULT_NOTIFICATION_PREFS}}
    except Exception:
        pass
    return dict(DEFAULT_NOTIFICATION_PREFS)


def save_notification_prefs(db: Session, payload: dict) -> dict:
    import json
    from .settings_service import set_setting

    cur = get_notification_prefs(db)
    for k in DEFAULT_NOTIFICATION_PREFS:
        if k in payload:
            cur[k] = bool(payload[k])
    set_setting(db, "notification_preferences", json.dumps(cur))
    db.commit()
    return cur


def generate_daily_summary_notification(db: Session, target_date: str | None = None) -> tuple[dict, Notification | None]:
    summary = daily_summary_data(db, target_date)
    day = summary["date"]
    title = f"Daily Summary — {day}"
    message = (
        f"Invoiced Sales: {format_pkr(summary['invoiced_sales_paisa'])} | "
        f"Payments Received: {format_pkr(summary['payments_received_paisa'])} | "
        f"Jobs: {summary['jobs_opened']} opened, {summary['jobs_completed']} completed | "
        f"Expenses: {format_pkr(summary['expenses_paisa'])}"
    )
    existing = (
        db.query(Notification)
        .filter(Notification.type == "daily_summary", Notification.title == title)
        .order_by(Notification.id.desc())
        .first()
    )
    if existing:
        existing.message = message
        existing.is_read = False
        db.flush()
        db.commit()
        return summary, existing
    n = push(
        db,
        type_="daily_summary",
        title=title,
        message=message,
        related_type="daily_summary",
        deduplicate_unread=True,
    )
    return summary, n

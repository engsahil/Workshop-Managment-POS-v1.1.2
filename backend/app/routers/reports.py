"""Reports & dashboard — all computed live from the database."""
from fastapi import APIRouter, Depends, Query

from ..core.deps import get_current_user, get_db, require_report
from ..models import User
from ..services import report_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/dashboard")
def dashboard(date_from: str | None = None, date_to: str | None = None,
              from_: str | None = Query(default=None, alias="from"),
              to_: str | None = Query(default=None, alias="to"),
              db=Depends(get_db), user: User = Depends(get_current_user)):
    df = date_from or from_
    dt = date_to or to_
    return report_service.dashboard(db, df, dt, user)


@router.get("/sales-trend")
def sales_trend(date_from: str, date_to: str, group: str = "day",
                db=Depends(get_db), _: User = Depends(require_report)):
    return report_service.sales_trend(db, date_from, date_to, group)


@router.get("/sales-by/{field}")
def sales_by(field: str, date_from: str | None = None,
             date_to: str | None = None, db=Depends(get_db),
             _: User = Depends(require_report)):
    if field not in ("product", "service", "category", "cashier", "method",
                     "customer"):
        return {"error": "unknown field"}, 400
    return report_service.sales_by(db, field, date_from, date_to)


@router.get("/profit")
def profit(date_from: str | None = None, date_to: str | None = None,
           db=Depends(get_db), _: User = Depends(require_report)):
    return report_service.profit_report(db, date_from, date_to)


@router.get("/payments-summary")
def payments_summary(date_from: str | None = None, date_to: str | None = None,
                     db=Depends(get_db), _: User = Depends(require_report)):
    return report_service.payment_summary(db, date_from, date_to)


@router.get("/stock")
def stock(q: str | None = None, low_only: bool = False,
          db=Depends(get_db), _: User = Depends(require_report)):
    return report_service.stock_report(db, q=q, low_only=low_only)


@router.get("/customer-statement/{customer_id}")
def customer_statement(customer_id: int, date_from: str | None = None,
                       date_to: str | None = None, db=Depends(get_db),
                       _: User = Depends(require_report)):
    try:
        return report_service.customer_statement(db, customer_id,
                                                    date_from, date_to)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/supplier-statement/{supplier_id}")
def supplier_statement(supplier_id: int, db=Depends(get_db),
                       _: User = Depends(require_report)):
    try:
        return report_service.supplier_statement(db, supplier_id)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/mechanic-performance")
def mechanic_performance(date_from: str | None = None,
                         date_to: str | None = None, db=Depends(get_db),
                         _: User = Depends(require_report)):
    return report_service.mechanic_performance(db, date_from, date_to)


@router.get("/shift-reconciliation")
def shift_reconciliation(page: int = 1, page_size: int = 25,
                         db=Depends(get_db),
                         _: User = Depends(require_report)):
    limit = min(200, max(1, page_size))
    offset = (max(1, page) - 1) * limit
    return report_service.shifts_reconciliation(db, limit=limit, offset=offset)


@router.get("/returns")
def returns(date_from: str | None = None, date_to: str | None = None,
            db=Depends(get_db), _: User = Depends(require_report)):
    return report_service.returns_report(db, date_from, date_to)


@router.get("/tax-summary")
def tax_summary(date_from: str | None = None, date_to: str | None = None,
                db=Depends(get_db), _: User = Depends(require_report)):
    return report_service.tax_summary(db, date_from, date_to)


@router.get("/overdue-credit")
def overdue_credit(db=Depends(get_db), _: User = Depends(require_report)):
    return report_service.overdue_credit(db)


@router.get("/jobs")
def jobs(status: str | None = None, mechanic_id: int | None = None,
         date_from: str | None = None, date_to: str | None = None,
         page: int = 1, page_size: int = 100, db=Depends(get_db),
         _: User = Depends(require_report)):
    limit = min(200, max(1, page_size))
    offset = (max(1, page) - 1) * limit
    from ..services import job_service
    rows, total = report_service.jobs_report(
        db, status=status, mechanic_id=mechanic_id,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset)
    return {"items": [job_service.job_out(db, j) for j in rows],
            "total": total, "page": page, "page_size": limit}

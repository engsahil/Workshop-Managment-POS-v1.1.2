"""Invoices, payments, voids, sale returns, customer advances/repayments.

All amounts are integer paisa. Totals are always recomputed server-side
from the submitted line items — client arithmetic is never trusted.
"""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.constants import (STOCK_SALE, STOCK_RETURN, STOCK_VOID,
                              INVOICE_STATUSES)
from ..models import (Invoice, InvoiceItem, Payment, Product, Service as ServiceModel,
                      SaleReturn, SaleReturnItem, JobCard, Customer, Vehicle,
                      JobPart, JobService)
from ..services import inventory_service, notification_service, audit_service
from ..services.settings_service import get_setting, next_number
from ..core.dates import range_utc


# ---------------------------------------------------------------- search
def search_items(db: Session, q: str, limit: int = 20) -> dict:
    q = (q or "").strip()
    products, services = [], []
    if q:
        like = f"%{q}%"
        prods = (db.query(Product)
                 .filter(Product.is_active.is_(True), Product.is_service.is_(False))
                 .filter((Product.name.ilike(like)) | (Product.sku.ilike(like))
                         | (Product.barcode == q) | (Product.category_id.isnot(None)))
                 .order_by(Product.id.desc()).limit(limit).all())
        # exact barcode first
        exact = (db.query(Product)
                 .filter(Product.barcode == q, Product.is_active.is_(True))
                 .first())
        if exact and exact not in prods:
            prods.insert(0, exact)
        svcs = (db.query(ServiceModel)
                .filter(ServiceModel.is_active.is_(True))
                .filter((ServiceModel.name.ilike(like)) | (ServiceModel.code.ilike(like)))
                .limit(limit).all())
    else:
        prods = (db.query(Product).filter(Product.is_active.is_(True),
                                          Product.is_service.is_(False))
                 .order_by(Product.id.desc()).limit(limit).all())
        svcs = (db.query(ServiceModel).filter(ServiceModel.is_active.is_(True))
                .order_by(ServiceModel.id.desc()).limit(limit).all())
    for p in prods:
        products.append({"id": p.id, "type": "product", "name": p.name,
                         "sku": p.sku, "barcode": p.barcode,
                         "unit": p.unit, "price_paisa": p.selling_price_paisa,
                         "cost_paisa": p.purchase_cost_paisa,
                         "quantity_on_hand": p.quantity_on_hand,
                         "min_stock": p.min_stock,
                         "low_stock": p.quantity_on_hand <= p.min_stock,
                         "warranty_days": p.warranty_days})
    for s in svcs:
        services.append({"id": s.id, "type": "service", "name": s.name,
                         "code": s.code, "price_paisa": s.default_charge_paisa,
                         "estimated_minutes": s.estimated_minutes,
                         "vehicle_types": s.vehicle_types})
    return {"products": products, "services": services}


# ---------------------------------------------------------------- creation
def _totals(items: list[dict], invoice_discount_paisa: int, tax_rate: float,
            tax_enabled: bool) -> dict:
    gross = 0
    line_discount = 0
    for it in items:
        gross += int(round(it["quantity"] * it["unit_price_paisa"]))
        line_discount += int(it.get("discount_paisa") or 0)
    net = gross - line_discount
    if invoice_discount_paisa < 0:
        raise ValueError("Invoice discount cannot be negative")
    if invoice_discount_paisa > net:
        raise ValueError("Invoice discount exceeds the net sale amount")
    net -= invoice_discount_paisa
    tax = 0
    if tax_enabled and tax_rate > 0:
        tax = int(round(net * tax_rate / 100.0))
    total = net + tax
    return {"gross_paisa": gross, "line_discount_paisa": line_discount,
            "invoice_discount_paisa": invoice_discount_paisa,
            "tax_paisa": tax, "total_paisa": total}


def create_invoice(db: Session, data: dict, user, from_job: bool = False) -> dict:
    customer = None
    if data.get("customer_id"):
        customer = db.get(Customer, data["customer_id"])
        if customer is None:
            raise ValueError("Customer does not exist")
    vehicle = None
    if data.get("vehicle_id"):
        vehicle = db.get(Vehicle, data["vehicle_id"])
        if vehicle is None:
            raise ValueError("Vehicle does not exist")
        if customer and vehicle.customer_id != customer.id:
            raise ValueError("Vehicle does not belong to the selected customer")
    job = None
    if data.get("job_id"):
        job = db.get(JobCard, data["job_id"])
        if job is None:
            raise ValueError("Job card does not exist")
        if not from_job:
            raise ValueError("Use the job invoice endpoint for job billing")
        if job.invoice_id:
            raise ValueError("This job already has an invoice")

    items_data = data["items"]
    if not items_data:
        raise ValueError("Invoice must contain at least one item")

    items = []
    cost_of_goods = 0
    for it in items_data:
        qty = float(it["quantity"])
        price = int(it["unit_price_paisa"])
        disc = int(it.get("discount_paisa") or 0)
        if qty <= 0:
            raise ValueError("Item quantity must be positive")
        if price < 0 or disc < 0:
            raise ValueError("Prices and discounts cannot be negative")
        gross = int(round(qty * price))
        if disc > gross:
            raise ValueError(f"Discount exceeds line amount for '{it.get('description') or 'item'}'")
        line_total = gross - disc

        item_type = it.get("item_type", "product")
        product = service = job_part = job_service = None
        description = it.get("description")
        unit = it.get("unit", "pcs")
        unit_cost = None
        deduct_stock = True

        if item_type == "product":
            product = db.get(Product, it.get("product_id")) if it.get("product_id") else None
            if product is None:
                raise ValueError("A product line must reference a valid product")
            if not product.is_active:
                raise ValueError(f"'{product.name}' is deactivated")
            if product.is_service:
                raise ValueError(f"'{product.name}' is a service, not a stock item")
            description = description or product.name
            unit = product.unit
            unit_cost = product.purchase_cost_paisa
            cost_of_goods += int(unit_cost * qty)
            if it.get("job_part_id"):
                jp = db.get(JobPart, it["job_part_id"])
                if jp is None or jp.job_id != (job.id if job else -1):
                    raise ValueError("Invalid job part reference")
                job_part = jp
                deduct_stock = False      # stock was already consumed by the job
        else:
            service = db.get(ServiceModel, it.get("service_id")) if it.get("service_id") else None
            if it.get("service_id") and service is None:
                raise ValueError("A service line must reference a valid service")
            if service is not None and not service.is_active:
                raise ValueError(f"Service '{service.name}' is deactivated")
            description = description or (service.name if service else "Workshop Labor")
            unit = "job"
            if it.get("job_service_id"):
                js = db.get(JobService, it["job_service_id"])
                if js is None or js.job_id != (job.id if job else -1):
                    raise ValueError("Invalid job service reference")
                job_service = js

        items.append(InvoiceItem(
            item_type=item_type, product_id=product.id if product else None,
            service_id=service.id if service else None,
            job_part_id=job_part.id if job_part else None,
            job_service_id=job_service.id if job_service else None,
            description=description, quantity=qty, unit=unit,
            unit_price_paisa=price, discount_paisa=disc,
            line_total_paisa=line_total, unit_cost_paisa=unit_cost,
            is_warranty=bool(it.get("is_warranty"))))

    tax_enabled = bool(get_setting(db, "business.tax_enabled", False))
    tax_rate = float(get_setting(db, "business.tax_rate_percent", 0) or 0)
    calc = _totals(items_data, int(data.get("invoice_discount_paisa") or 0),
                   tax_rate, tax_enabled)

    paid_total = sum(int(p["amount_paisa"]) for p in data.get("payments", []))
    if paid_total > calc["total_paisa"]:
        raise ValueError("Total payment exceeds the invoice amount — use a customer advance instead")

    is_credit = bool(data.get("is_credit"))
    balance = calc["total_paisa"] - paid_total
    if balance > 0 and user.role not in ("admin", "manager"):
        # credit / partial billing is a financial-role operation,
        # enforced server-side regardless of client-supplied flags
        raise PermissionError(
            "Credit or partial billing requires manager or administrator rights")

    number = next_number(db, "invoice_number",
                         get_setting(db, "business.invoice_prefix", "INV") or "INV")
    inv = Invoice(
        invoice_number=number,
        customer_id=customer.id if customer else None,
        vehicle_id=vehicle.id if vehicle else None,
        job_id=job.id if job else None,
        subtotal_paisa=calc["gross_paisa"] - calc["line_discount_paisa"],
        discount_paisa=calc["line_discount_paisa"] + calc["invoice_discount_paisa"],
        tax_paisa=calc["tax_paisa"], total_paisa=calc["total_paisa"],
        paid_paisa=paid_total, balance_paisa=balance,
        cost_of_goods_paisa=cost_of_goods,
        status="paid" if balance <= 0 else ("partial" if paid_total > 0 else "credit"),
        cashier_id=user.id, is_credit=balance > 0,
        notes=data.get("notes"))
    inv.items = items
    db.add(inv)
    db.flush()

    # stock deduction — one movement per product line, tied to this invoice
    for it, inv_item in zip(items_data, items):
        if inv_item.item_type == "product" and not inv_item.job_part_id:
            product = db.get(Product, inv_item.product_id)
            inventory_service.apply_stock(
                db, product, -int(round(float(it["quantity"]))),
                movement_type=STOCK_SALE, reference_type="sale",
                reference_id=inv.id, reference_number=inv.invoice_number,
                notes=f"Sale {inv.invoice_number}", created_by=user.id,
                unit_cost_paisa=product.purchase_cost_paisa)

    # payments
    method_summary = {}
    open_shift = None
    from ..services.shift_service import current_shift
    open_shift = current_shift(db, user.id)
    for p in data.get("payments", []):
        amount = int(p["amount_paisa"])
        if amount <= 0:
            continue
        pay = Payment(invoice_id=inv.id, customer_id=inv.customer_id,
                      amount_paisa=amount, method=p["method"],
                      kind=p.get("kind", "sale_payment"),
                      reference=p.get("reference"), notes=p.get("notes"),
                      shift_id=open_shift.id if open_shift else None,
                      created_by=user.id)
        db.add(pay)
        method_summary[p["method"]] = method_summary.get(p["method"], 0) + amount
    inv.payment_method_summary = (", ".join(
        f"{k}:{v/100:.2f}" for k, v in method_summary.items())) or None

    if job is not None:
        job.invoice_id = inv.id
        job.status = "ready_for_delivery" if job.status != "delivered" else job.status

    db.commit()

    # refresh & enrich
    inv = db.get(Invoice, inv.id)
    out = invoice_detail(db, inv)
    out["odometer_warning"] = None
    audit_service.log(db, user_id=user.id, username=user.username,
                      action="invoice.create", entity_type="invoice",
                      entity_id=inv.id, new_values={"number": inv.invoice_number,
                                                    "total_paisa": inv.total_paisa})
    notification_service.invoice_notification(db, inv)
    return out


# ---------------------------------------------------------------- detail
def invoice_detail(db: Session, inv: Invoice) -> dict:
    customer = db.get(Customer, inv.customer_id) if inv.customer_id else None
    vehicle = db.get(Vehicle, inv.vehicle_id) if inv.vehicle_id else None
    job = db.get(JobCard, inv.job_id) if inv.job_id else None
    return {
        "id": inv.id, "invoice_number": inv.invoice_number,
        "customer_id": inv.customer_id,
        "customer_name": customer.name if customer else "Walk-in Customer",
        "customer_phone": customer.phone if customer else None,
        "vehicle_id": inv.vehicle_id,
        "vehicle_label": (f"{vehicle.registration_no or ''} {vehicle.make or ''} {vehicle.model or ''}".strip()
                          if vehicle else None),
        "job_id": inv.job_id, "job_number": job.job_number if job else None,
        "subtotal_paisa": inv.subtotal_paisa, "discount_paisa": inv.discount_paisa,
        "tax_paisa": inv.tax_paisa, "total_paisa": inv.total_paisa,
        "paid_paisa": inv.paid_paisa, "balance_paisa": inv.balance_paisa,
        "cost_of_goods_paisa": inv.cost_of_goods_paisa,
        "gross_profit_paisa": inv.total_paisa - inv.cost_of_goods_paisa,
        "status": inv.status, "is_credit": inv.is_credit,
        "payment_method_summary": inv.payment_method_summary,
        "cashier_id": inv.cashier_id,
        "cashier_name": (db.get(__import__("app.models", fromlist=["User"]).User,
                                inv.cashier_id).full_name if inv.cashier_id else None),
        "return_amount_paisa": inv.return_amount_paisa,
        "credited_amount_paisa": inv.credited_amount_paisa,
        "notes": inv.notes,
        "voided_at": inv.voided_at.isoformat() if inv.voided_at else None,
        "void_reason": inv.void_reason,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "items": [
            {"id": i.id, "item_type": i.item_type, "product_id": i.product_id,
             "service_id": i.service_id, "job_part_id": i.job_part_id,
             "job_service_id": i.job_service_id, "description": i.description,
             "quantity": float(i.quantity), "unit": i.unit,
             "unit_price_paisa": i.unit_price_paisa,
             "discount_paisa": i.discount_paisa,
             "line_total_paisa": i.line_total_paisa,
             "unit_cost_paisa": i.unit_cost_paisa,
             "is_warranty": i.is_warranty,
             "returned_quantity": max(0.0, round(float(i.quantity) - _returnable(db, i.id), 4))
             if i.item_type == "product" else 0.0,
             "returnable_quantity": max(0.0, round(_returnable(db, i.id), 4))
             if i.item_type == "product" else 0.0}
            for i in inv.items],
        "payments": [
            {"id": p.id, "amount_paisa": p.amount_paisa, "method": p.method,
             "kind": p.kind, "reference": p.reference,
             "created_at": p.created_at.isoformat() if p.created_at else None}
            for p in inv.payments],
    }


def list_invoices(db: Session, q: str | None = None, customer_id: int | None = None,
                  cashier_id: int | None = None, status: str | None = None,
                  date_from: str | None = None, date_to: str | None = None,
                  limit: int = 50, offset: int = 0):
    date_from, date_to = range_utc(date_from, date_to)
    query = db.query(Invoice)
    if q:
        query = query.filter(Invoice.invoice_number.ilike(f"%{q}%"))
    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)
    if cashier_id:
        query = query.filter(Invoice.cashier_id == cashier_id)
    if status:
        query = query.filter(Invoice.status == status)
    if date_from:
        query = query.filter(Invoice.created_at >= date_from)
    if date_to:
        query = query.filter(Invoice.created_at <= date_to)
    total = query.count()
    rows = query.order_by(Invoice.id.desc()).offset(offset).limit(limit).all()
    return [invoice_detail(db, i) for i in rows], total


# ---------------------------------------------------------------- payments
def add_payment(db: Session, inv: Invoice, amount_paisa: int, method: str,
                reference: str | None, notes: str | None, user) -> Payment:
    if inv.status == "void":
        raise ValueError("Cannot collect payment on a voided invoice")
    if amount_paisa <= 0:
        raise ValueError("Payment amount must be positive")
    if amount_paisa > inv.balance_paisa:
        raise ValueError("Payment exceeds the outstanding balance")
    from ..services.shift_service import current_shift
    shift = current_shift(db, user.id)
    pay = Payment(invoice_id=inv.id, customer_id=inv.customer_id,
                  amount_paisa=amount_paisa, method=method, kind="sale_payment",
                  reference=reference, notes=notes,
                  shift_id=shift.id if shift else None, created_by=user.id)
    db.add(pay)
    inv.paid_paisa += amount_paisa
    inv.balance_paisa -= amount_paisa
    if inv.balance_paisa <= 0:
        inv.balance_paisa = 0
        inv.status = "paid"
        inv.is_credit = False
    elif inv.paid_paisa > 0:
        inv.status = "partial"
    summary = {}
    if inv.payment_method_summary:
        for part in inv.payment_method_summary.split(", "):
            if ":" in part:
                k, v = part.rsplit(":", 1)
                summary[k] = float(v)
    summary[method] = summary.get(method, 0) + amount_paisa / 100
    inv.payment_method_summary = ", ".join(f"{k}:{v:.2f}" for k, v in summary.items())
    db.commit()
    notification_service.payment_notification(db, inv, amount_paisa, method)
    return pay


def record_advance(db: Session, customer_id: int, amount_paisa: int, method: str,
                   reference: str | None, notes: str | None, user) -> Payment:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise ValueError("Customer does not exist")
    from ..services.shift_service import current_shift
    shift = current_shift(db, user.id)
    pay = Payment(customer_id=customer.id, amount_paisa=amount_paisa,
                  method=method, kind="advance", reference=reference,
                  notes=notes, shift_id=shift.id if shift else None,
                  created_by=user.id)
    db.add(pay)
    db.commit()
    notification_service.push(db, type_="payment",
                              title=f"Advance received from {customer.name}",
                              message=f"Rs. {amount_paisa/100:,.2f} via {method}",
                              related_type="customer", related_id=customer.id)
    return pay


def record_repayment(db: Session, customer_id: int, amount_paisa: int, method: str,
                     reference: str | None, notes: str | None, user) -> dict:
    """Repay credit: allocate to oldest unpaid invoices; leftover becomes advance."""
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise ValueError("Customer does not exist")
    remaining = amount_paisa
    allocated = []
    invoices = (db.query(Invoice)
                .filter(Invoice.customer_id == customer_id,
                        Invoice.balance_paisa > 0,
                        Invoice.status.in_(("partial", "credit", "returned")))
                .order_by(Invoice.id.asc()).all())
    from ..services.shift_service import current_shift
    shift = current_shift(db, user.id)
    for inv in invoices:
        if remaining <= 0:
            break
        amt = min(remaining, inv.balance_paisa)
        pay = Payment(invoice_id=inv.id, customer_id=customer.id,
                      amount_paisa=amt, method=method, kind="repayment",
                      reference=reference, notes=notes,
                      shift_id=shift.id if shift else None, created_by=user.id)
        db.add(pay)
        inv.paid_paisa += amt
        inv.balance_paisa -= amt
        if inv.balance_paisa <= 0:
            inv.balance_paisa = 0
            inv.status = "paid"
            inv.is_credit = False
        allocated.append({"invoice_id": inv.id, "invoice_number": inv.invoice_number,
                          "amount_paisa": amt})
        remaining -= amt
    advance = 0
    if remaining > 0:
        pay = Payment(customer_id=customer.id, amount_paisa=remaining,
                      method=method, kind="advance", reference=reference,
                      notes=notes, shift_id=shift.id if shift else None,
                      created_by=user.id)
        db.add(pay)
        advance = remaining
    db.commit()
    return {"allocated": allocated, "advance_paisa": advance}


# ---------------------------------------------------------------- void
def void_invoice(db: Session, inv: Invoice, reason: str, user) -> Invoice:
    if inv.status == "void":
        raise ValueError("Invoice is already voided")
    # restore stock for physical product lines (job parts were consumed by the job)
    for item in inv.items:
        if item.item_type == "product" and not item.job_part_id:
            product = db.get(Product, item.product_id)
            inventory_service.apply_stock(
                db, product, int(round(float(item.quantity))),
                movement_type=STOCK_VOID, reference_type="sale_void",
                reference_id=inv.id, reference_number=inv.invoice_number,
                notes=f"Voided invoice {inv.invoice_number}", created_by=user.id,
                unit_cost_paisa=item.unit_cost_paisa)
    # reverse every payment on the invoice
    for pay in inv.payments:
        if pay.amount_paisa > 0:
            db.add(Payment(invoice_id=inv.id, customer_id=inv.customer_id,
                           amount_paisa=-pay.amount_paisa, method=pay.method,
                           kind="reversal", reference=f"VOID {inv.invoice_number}",
                           notes=f"Reversal of payment #{pay.id}", created_by=user.id))
    if inv.job_id:
        job = db.get(JobCard, inv.job_id)
        if job and job.invoice_id == inv.id:
            job.invoice_id = None
    from ..core.security import utcnow
    inv.status = "void"
    inv.voided_at = utcnow()
    inv.void_reason = reason
    inv.voided_by = user.id
    inv.paid_paisa = 0
    inv.balance_paisa = 0
    db.commit()
    audit_service.log(db, user_id=user.id, username=user.username,
                      action="invoice.void", entity_type="invoice",
                      entity_id=inv.id, old_values={"number": inv.invoice_number},
                      new_values={"reason": reason})
    return inv


# ---------------------------------------------------------------- returns
def _returnable(db: Session, invoice_item_id: int) -> float:
    invoiced_qty = (db.query(InvoiceItem.quantity)
                    .filter(InvoiceItem.id == invoice_item_id).scalar() or 0)
    returned = (db.query(func.coalesce(func.sum(SaleReturnItem.quantity), 0))
                .join(SaleReturn, SaleReturnItem.return_id == SaleReturn.id)
                .filter(SaleReturnItem.invoice_item_id == invoice_item_id,
                        SaleReturn.status == "approved")
                .scalar() or 0)
    return float(invoiced_qty) - float(returned)


def create_return(db: Session, data: dict, user) -> SaleReturn:
    inv = db.get(Invoice, data["invoice_id"])
    if inv is None or inv.status == "void":
        raise ValueError("Invoice not found or voided")
    items = []
    total = 0
    for ri in data["items"]:
        ii = db.get(InvoiceItem, ri["invoice_item_id"])
        if ii is None or ii.invoice_id != inv.id:
            raise ValueError("Return item does not belong to this invoice")
        if ii.item_type != "product":
            raise ValueError("Only product lines can be returned (adjust service invoices manually)")
        qty = float(ri["quantity"])
        returnable = _returnable(db, ii.id)
        if qty <= 0 or qty > returnable + 1e-9:
            raise ValueError(
                f"Invalid return quantity for '{ii.description}' "
                f"(returnable: {returnable:g})")
        unit_net = ii.line_total_paisa / float(ii.quantity)
        line_total = int(round(qty * unit_net))
        items.append(SaleReturnItem(invoice_item_id=ii.id, product_id=ii.product_id,
                                    description=ii.description, quantity=qty,
                                    unit_price_paisa=int(round(unit_net)),
                                    line_total_paisa=line_total))
        total += line_total
    if total <= 0:
        raise ValueError("Return total must be greater than zero")
    sr = SaleReturn(
        return_number=next_number(db, "return_number",
                                  get_setting(db, "business.return_prefix", "RET") or "RET"),
        invoice_id=inv.id, customer_id=inv.customer_id,
        reason=data.get("reason"), restock_action=data.get("restock_action", "restock"),
        total_paisa=total, refund_method=data.get("refund_method", "cash"),
        notes=data.get("notes"), created_by=user.id)
    sr.items = items
    db.add(sr)
    db.commit()
    return sr


def decide_return(db: Session, sr: SaleReturn, status: str, notes: str | None,
                  user) -> SaleReturn:
    if sr.status != "pending":
        raise ValueError("This return has already been processed")
    if status == "approved":
        for item in sr.items:
            returnable = _returnable(db, item.invoice_item_id)
            if float(item.quantity) > returnable + 1e-9:
                raise ValueError(
                    f"Return quantity for '{item.description}' exceeds remaining returnable quantity ({returnable:g})"
                )
    from ..core.security import utcnow
    sr.status = status
    sr.approved_by = user.id
    sr.approved_at = utcnow()
    if notes:
        sr.notes = f"{sr.notes} | {notes}" if sr.notes else notes
    inv = db.get(Invoice, sr.invoice_id)
    if status == "approved":
        for item in sr.items:
            if sr.restock_action == "restock" and item.product_id:
                product = db.get(Product, item.product_id)
                inventory_service.apply_stock(
                    db, product, float(item.quantity), movement_type=STOCK_RETURN,
                    reference_type="sale_return", reference_id=sr.id,
                    reference_number=sr.return_number,
                    notes=f"Returned from sale {inv.invoice_number}",
                    created_by=user.id, unit_cost_paisa=product.purchase_cost_paisa)
                item.restocked_quantity = float(item.quantity)
            elif sr.restock_action == "damaged" and item.product_id:
                product = db.get(Product, item.product_id)
                inventory_service.apply_stock(
                    db, product, 0, movement_type="damage",
                    reference_type="sale_return", reference_id=sr.id,
                    reference_number=sr.return_number,
                    notes=f"Returned damaged: {item.description}",
                    created_by=user.id)
        if sr.refund_method == "credit":
            inv.credited_amount_paisa += sr.total_paisa
        else:
            from ..services.shift_service import current_shift
            shift = current_shift(db, user.id)
            db.add(Payment(invoice_id=inv.id, customer_id=inv.customer_id,
                           amount_paisa=-sr.total_paisa, method=sr.refund_method,
                           kind="refund", reference=f"REFUND {sr.return_number}",
                           notes=sr.notes, shift_id=shift.id if shift else None,
                           created_by=user.id))
            # money went back out: reduce collected amount, restore balance
            inv.paid_paisa = max(0, inv.paid_paisa - sr.total_paisa)
            inv.balance_paisa = inv.total_paisa - inv.paid_paisa
        inv.return_amount_paisa += sr.total_paisa
        if inv.return_amount_paisa >= inv.total_paisa:
            inv.status = "returned"
        elif inv.balance_paisa > 0 and inv.paid_paisa > 0:
            inv.status = "partial"
        elif inv.balance_paisa > 0:
            inv.status = "credit"
        notification_service.push(db, type_="payment",
                                  title=f"Return approved: {sr.return_number}",
                                  message=f"Invoice {inv.invoice_number} — Rs. {sr.total_paisa/100:,.2f}",
                                  related_type="sale_return", related_id=sr.id)
    db.commit()
    audit_service.log(db, user_id=user.id, username=user.username,
                      action="return.decide", entity_type="sale_return",
                      entity_id=sr.id, new_values={"status": status})
    return sr


def list_returns(db: Session, status: str | None = None, limit: int = 50, offset: int = 0):
    q = db.query(SaleReturn)
    if status:
        q = q.filter(SaleReturn.status == status)
    total = q.count()
    rows = q.order_by(SaleReturn.id.desc()).offset(offset).limit(limit).all()
    out = []
    for r in rows:
        inv = db.get(Invoice, r.invoice_id)
        cid = r.customer_id or (inv.customer_id if inv else None)
        cust = db.get(Customer, cid) if cid else None
        out.append({
            "id": r.id, "return_number": r.return_number,
            "invoice_id": r.invoice_id,
            "invoice_number": inv.invoice_number if inv else None,
            "customer_id": cid,
            "customer_name": cust.name if cust else "Walk-in Customer",
            "reason": r.reason,
            "return_date": r.return_date.isoformat() if r.return_date else None,
            "status": r.status, "restock_action": r.restock_action,
            "total_paisa": r.total_paisa, "refund_method": r.refund_method,
            "notes": r.notes, "created_by": r.created_by,
            "approved_by": r.approved_by,
            "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            "items": [{"id": i.id, "invoice_item_id": i.invoice_item_id,
                       "product_id": i.product_id, "description": i.description,
                       "quantity": float(i.quantity),
                       "unit_price_paisa": i.unit_price_paisa,
                       "line_total_paisa": i.line_total_paisa,
                       "restocked_quantity": float(i.restocked_quantity)}
                      for i in r.items],
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out, total

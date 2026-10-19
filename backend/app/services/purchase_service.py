"""Suppliers, purchase orders, goods receiving, purchase returns, payments."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import (Supplier, Purchase, PurchaseItem, PurchasePayment,
                      PurchaseReturn, PurchaseReturnItem, Product)
from ..core.dates import range_utc
from ..services import inventory_service, notification_service
from ..services.settings_service import next_number


# ---------------------------------------------------------------- suppliers
def list_suppliers(db: Session, q: str | None = None, include_inactive: bool = False):
    query = db.query(Supplier)
    if not include_inactive:
        query = query.filter(Supplier.is_active.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Supplier.name.ilike(like)) | (Supplier.phone.ilike(like))
            | (Supplier.contact_person.ilike(like)))
    return [
        {**{c: getattr(s, c) for c in (
            "id", "name", "contact_person", "phone", "alt_phone", "email",
            "address", "notes", "is_active")},
         "balance_paisa": supplier_balance(db, s.id),
         "created_at": s.created_at.isoformat() if s.created_at else None}
        for s in query.order_by(Supplier.id.desc()).all()
    ]


def get_supplier(db: Session, sid: int) -> Supplier | None:
    return db.get(Supplier, sid)


def create_supplier(db: Session, data: dict) -> Supplier:
    s = Supplier(**data)
    db.add(s)
    db.commit()
    return s


def update_supplier(db: Session, s: Supplier, data: dict) -> Supplier:
    for k, v in data.items():
        if v is not None or k in ("phone", "alt_phone", "email", "address", "notes"):
            setattr(s, k, v)
    db.commit()
    return s


def delete_supplier(db: Session, s: Supplier) -> None:
    if db.query(Purchase.id).filter(Purchase.supplier_id == s.id).first():
        raise ValueError("Supplier has purchase history — deactivate instead.")
    db.delete(s)
    db.commit()


# ---------------------------------------------------------------- purchases
def purchase_out(db: Session, p: Purchase) -> dict:
    supplier = db.get(Supplier, p.supplier_id)
    return {
        "id": p.id, "po_number": p.po_number, "supplier_id": p.supplier_id,
        "supplier_name": supplier.name if supplier else None,
        "order_date": p.order_date.isoformat() if p.order_date else None,
        "status": p.status,
        "subtotal_paisa": p.subtotal_paisa, "discount_paisa": p.discount_paisa,
        "total_paisa": p.total_paisa, "paid_paisa": p.paid_paisa,
        "balance_paisa": p.total_paisa - p.paid_paisa,
        "notes": p.notes, "created_by": p.created_by,
        "items": [
            {"id": i.id, "product_id": i.product_id,
             "product_name": (db.get(Product, i.product_id).name
                              if db.get(Product, i.product_id) else None),
             "quantity": i.quantity, "received_quantity": i.received_quantity,
             "unit_cost_paisa": i.unit_cost_paisa,
             "line_total_paisa": i.line_total_paisa}
            for i in p.items],
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def list_purchases(db: Session, q: str | None = None, supplier_id: int | None = None,
                   status: str | None = None, date_from: str | None = None,
                   date_to: str | None = None, limit: int = 50, offset: int = 0):
    date_from, date_to = range_utc(date_from, date_to)
    query = db.query(Purchase)
    if supplier_id:
        query = query.filter(Purchase.supplier_id == supplier_id)
    if status:
        query = query.filter(Purchase.status == status)
    if date_from:
        query = query.filter(Purchase.order_date >= date_from)
    if date_to:
        query = query.filter(Purchase.order_date <= date_to)
    if q:
        query = query.filter(Purchase.po_number.ilike(f"%{q}%"))
    total = query.count()
    rows = query.order_by(Purchase.id.desc()).offset(offset).limit(limit).all()
    return [purchase_out(db, p) for p in rows], total


def create_purchase(db: Session, data: dict, user_id: int | None = None) -> Purchase:
    supplier = db.get(Supplier, data["supplier_id"])
    if supplier is None:
        raise ValueError("Supplier does not exist")
    if not supplier.is_active:
        raise ValueError("Supplier is deactivated")
    items = []
    subtotal = 0
    for it in data["items"]:
        product = db.get(Product, it["product_id"])
        if product is None:
            raise ValueError(f"Product #{it['product_id']} does not exist")
        if product.is_service:
            raise ValueError(f"'{product.name}' is a service, not a stock item")
        line_total = it["quantity"] * it["unit_cost_paisa"]
        subtotal += line_total
        items.append(PurchaseItem(
            product_id=product.id, quantity=it["quantity"],
            received_quantity=0, unit_cost_paisa=it["unit_cost_paisa"],
            line_total_paisa=line_total))
    discount = min(data.get("discount_paisa", 0) or 0, subtotal)
    po = Purchase(
        po_number=next_number(db, "po_number", data.get("prefix") or "PO"),
        supplier_id=supplier.id, subtotal_paisa=subtotal,
        discount_paisa=discount, total_paisa=subtotal - discount,
        notes=data.get("notes"), created_by=user_id)
    po.items = items
    db.add(po)
    db.commit()
    return po


def receive_purchase(db: Session, purchase: Purchase, receive_items: list[dict],
                     user_id: int | None = None) -> Purchase:
    """Confirm goods receipt. Stock increases exactly once per received unit."""
    if purchase.status == "cancelled":
        raise ValueError("Cannot receive a cancelled purchase order")
    if purchase.status == "received":
        raise ValueError("This purchase order has already been received")
    if not receive_items:
        # no explicit quantities: receive everything remaining
        receive_items = [
            {"product_id": i.product_id,
             "quantity": i.quantity - i.received_quantity}
            for i in purchase.items
            if i.received_quantity < i.quantity]
    for ri in receive_items:
        pid = int(ri["product_id"])
        qty = int(ri["quantity"])
        item = next((i for i in purchase.items if i.product_id == pid), None)
        if item is None:
            raise ValueError(f"Product #{pid} is not on this purchase order")
        remaining = item.quantity - item.received_quantity
        if qty <= 0:
            raise ValueError("Receive quantity must be positive")
        if qty > remaining:
            raise ValueError(
                f"Cannot receive {qty} units — only {remaining} remaining to receive")
        item.received_quantity += qty
        product = db.get(Product, pid)
        inventory_service.weighted_average_receive(db, product, qty, item.unit_cost_paisa)
        inventory_service.apply_stock(
            db, product, qty, movement_type="receive",
            reference_type="purchase", reference_id=purchase.id,
            reference_number=purchase.po_number,
            unit_cost_paisa=item.unit_cost_paisa, created_by=user_id)
    if all(i.received_quantity >= i.quantity for i in purchase.items):
        purchase.status = "received"
    elif any(i.received_quantity > 0 for i in purchase.items):
        purchase.status = "partial"
    db.commit()
    return purchase


def cancel_purchase(db: Session, purchase: Purchase) -> None:
    if any(i.received_quantity > 0 for i in purchase.items):
        raise ValueError("Goods already received — process a purchase return instead")
    purchase.status = "cancelled"
    db.commit()


# ---------------------------------------------------------------- payments / returns
def add_purchase_payment(db: Session, purchase: Purchase, amount_paisa: int,
                         method: str, reference: str | None, notes: str | None,
                         user_id: int | None = None) -> PurchasePayment:
    if purchase.status == "cancelled":
        raise ValueError("Cannot pay against a cancelled purchase order")
    balance = purchase.total_paisa - purchase.paid_paisa
    if amount_paisa <= 0:
        raise ValueError("Payment amount must be positive")
    if amount_paisa > balance:
        raise ValueError(f"Payment exceeds outstanding balance of {balance} paisa")
    pay = PurchasePayment(purchase_id=purchase.id, supplier_id=purchase.supplier_id,
                          amount_paisa=amount_paisa, method=method,
                          reference=reference, notes=notes, created_by=user_id)
    db.add(pay)
    purchase.paid_paisa += amount_paisa
    db.commit()
    return pay


def create_purchase_return(db: Session, data: dict, user_id: int | None = None) -> PurchaseReturn:
    purchase = db.get(Purchase, data["purchase_id"]) if data.get("purchase_id") else None
    sup_id = data.get("supplier_id") or (purchase.supplier_id if purchase else None)
    supplier = db.get(Supplier, sup_id) if sup_id else None
    if supplier is None:
        raise ValueError("Supplier does not exist")
    items = []
    total = 0
    for ri in data["items"]:
        product = db.get(Product, ri["product_id"])
        if product is None:
            raise ValueError(f"Product #{ri['product_id']} does not exist")
        qty = int(ri["quantity"])
        if qty <= 0:
            raise ValueError("Return quantity must be positive")
        # cannot return more than was received (minus already returned)
        received = (db.query(func.coalesce(func.sum(PurchaseItem.received_quantity), 0))
                    .filter(PurchaseItem.product_id == product.id)
                    .filter(PurchaseItem.purchase_id == (purchase.id if purchase else Purchase.id))
                    .scalar() or 0)
        if purchase:
            pi = next((i for i in purchase.items if i.product_id == product.id), None)
            received = pi.received_quantity if pi else 0
        already = (db.query(func.coalesce(func.sum(PurchaseReturnItem.quantity), 0))
                   .filter(PurchaseReturnItem.product_id == product.id)
                   .filter(PurchaseReturnItem.return_.has(PurchaseReturn.purchase_id == (purchase.id if purchase else -1)))
                   .scalar() or 0)
        if qty > received - already:
            raise ValueError(
                f"Cannot return {qty} of '{product.name}' — only "
                f"{received - already} received and not yet returned")
        cost = int(ri.get("unit_cost_paisa") or product.purchase_cost_paisa or 0)
        items.append(PurchaseReturnItem(product_id=product.id, quantity=qty,
                                        unit_cost_paisa=cost,
                                        line_total_paisa=qty * cost))
        total += qty * cost
        inventory_service.apply_stock(
            db, product, -qty, movement_type="purchase_return",
            reference_type="purchase_return", reference_number=None,
            notes=f"Returned to supplier {supplier.name}", created_by=user_id)
    pr = PurchaseReturn(
        return_number=next_number(db, "return_number", "PR"),
        purchase_id=purchase.id if purchase else None,
        supplier_id=supplier.id, total_paisa=total,
        refund_amount_paisa=data.get("refund_amount_paisa", total) or total,
        method=data.get("method", "cash"), reference=data.get("reference"),
        notes=data.get("notes"), created_by=user_id)
    pr.items = items
    db.add(pr)
    db.commit()
    return pr


# ---------------------------------------------------------------- balances
def supplier_balance(db: Session, sid: int) -> int:
    purchased = (db.query(func.coalesce(func.sum(Purchase.total_paisa), 0))
                 .filter(Purchase.supplier_id == sid, Purchase.status != "cancelled")
                 .scalar() or 0)
    paid = (db.query(func.coalesce(func.sum(PurchasePayment.amount_paisa), 0))
            .filter(PurchasePayment.supplier_id == sid).scalar() or 0)
    returned = (db.query(func.coalesce(func.sum(PurchaseReturn.total_paisa), 0))
                .filter(PurchaseReturn.supplier_id == sid,
                        PurchaseReturn.status == "approved").scalar() or 0)
    return int(purchased) - int(paid) - int(returned)


def supplier_statement(db: Session, sid: int) -> list[dict]:
    rows = []
    for p in db.query(Purchase).filter(Purchase.supplier_id == sid).order_by(Purchase.id).all():
        rows.append({"date": p.order_date.isoformat() if p.order_date else None,
                     "type": "purchase", "ref": p.po_number,
                     "amount_paisa": p.total_paisa, "balance_impact": p.total_paisa,
                     "notes": p.notes})
    for pay in db.query(PurchasePayment).filter(PurchasePayment.supplier_id == sid).order_by(PurchasePayment.id).all():
        rows.append({"date": pay.created_at.isoformat() if pay.created_at else None,
                     "type": "payment", "ref": pay.reference or "",
                     "amount_paisa": -pay.amount_paisa, "balance_impact": -pay.amount_paisa,
                     "notes": pay.method})
    for r in db.query(PurchaseReturn).filter(PurchaseReturn.supplier_id == sid).all():
        rows.append({"date": r.return_date.isoformat() if r.return_date else None,
                     "type": "purchase_return", "ref": r.return_number,
                     "amount_paisa": -r.total_paisa, "balance_impact": -r.total_paisa,
                     "notes": r.notes})
    rows.sort(key=lambda x: x.get("date") or "")
    return rows

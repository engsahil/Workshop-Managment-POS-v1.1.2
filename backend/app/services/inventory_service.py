"""Products, categories, brands and every stock mutation.

Costing method: weighted average cost.
`Product.purchase_cost_paisa` always holds the current weighted-average unit cost.
Every quantity change creates a StockMovement row (traceable source).
"""
import csv
import io

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.constants import STOCK_ADJUST, STOCK_DAMAGE, STOCK_RECEIVE
from ..core.dates import range_utc
from ..models import Product, StockMovement, Category, Brand
from ..services import notification_service
from ..services.settings_service import get_setting


# ------------------------------------------------------------------ helpers
def apply_stock(db: Session, product: Product, delta: int, *, movement_type: str,
                reference_type: str | None = None, reference_id: int | None = None,
                reference_number: str | None = None, notes: str | None = None,
                created_by: int | None = None, unit_cost_paisa: int | None = None,
                force: bool = False) -> StockMovement:
    """The single place where stock quantities change."""
    if product.is_service:
        raise ValueError("Services are not stock items and cannot hold inventory")
    new_qty = product.quantity_on_hand + delta
    allow_negative = bool(get_setting(db, "business.allow_negative_stock", False))
    if new_qty < 0 and not allow_negative and not force:
        raise ValueError(
            f"Insufficient stock for '{product.name}': requested {abs(delta)}, "
            f"available {product.quantity_on_hand}")
    product.quantity_on_hand = new_qty
    mv = StockMovement(
        product_id=product.id, movement_type=movement_type,
        quantity_delta=delta, quantity_after=new_qty,
        unit_cost_paisa=unit_cost_paisa if unit_cost_paisa is not None else product.purchase_cost_paisa,
        reference_type=reference_type, reference_id=reference_id,
        reference_number=reference_number, notes=notes, created_by=created_by,
    )
    db.add(mv)
    db.flush()
    notification_service.check_low_stock(db)
    return mv


def weighted_average_receive(db: Session, product: Product, qty: int, cost_paisa: int) -> None:
    old_qty = product.quantity_on_hand
    old_cost = product.purchase_cost_paisa or 0
    if old_qty + qty > 0:
        product.purchase_cost_paisa = (old_qty * old_cost + qty * cost_paisa) // (old_qty + qty)


# ------------------------------------------------------------------ products
def product_out(p: Product) -> dict:
    return {
        "id": p.id, "name": p.name, "sku": p.sku, "barcode": p.barcode,
        "category_id": p.category_id, "brand_id": p.brand_id,
        "compatibility": p.compatibility,
        "purchase_cost_paisa": p.purchase_cost_paisa,
        "selling_price_paisa": p.selling_price_paisa,
        "quantity_on_hand": p.quantity_on_hand, "min_stock": p.min_stock,
        "unit": p.unit, "supplier_id": p.supplier_id, "description": p.description,
        "is_service": p.is_service, "warranty_days": p.warranty_days,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def list_products(db: Session, q: str | None = None, category_id: int | None = None,
                  brand_id: int | None = None, include_inactive: bool = False,
                  include_services: bool = True, low_stock: bool = False,
                  limit: int = 50, offset: int = 0):
    query = db.query(Product)
    if not include_inactive:
        query = query.filter(Product.is_active.is_(True))
    if not include_services:
        query = query.filter(Product.is_service.is_(False))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if brand_id:
        query = query.filter(Product.brand_id == brand_id)
    if low_stock:
        query = query.filter(Product.quantity_on_hand <= Product.min_stock)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Product.name.ilike(like)) | (Product.sku.ilike(like))
            | (Product.barcode.ilike(like)) | (Product.compatibility.ilike(like))
        )
    total = query.count()
    rows = query.order_by(Product.id.desc()).offset(offset).limit(limit).all()
    return [product_out(p) for p in rows], total


def get_product(db: Session, pid: int) -> Product | None:
    return db.get(Product, pid)


def _check_sku_barcode_unique(db: Session, sku: str | None, barcode: str | None, exclude_id: int | None = None):
    if sku:
        q = db.query(Product).filter(Product.sku == sku.strip())
        if exclude_id:
            q = q.filter(Product.id != exclude_id)
        if q.first():
            raise ValueError(f"SKU '{sku}' is already used by another product")
    if barcode:
        q = db.query(Product).filter(Product.barcode == barcode.strip())
        if exclude_id:
            q = q.filter(Product.id != exclude_id)
        if q.first():
            raise ValueError(f"Barcode '{barcode}' is already used by another product")


def create_product(db: Session, data: dict, created_by: int | None = None) -> Product:
    _check_sku_barcode_unique(db, data.get("sku"), data.get("barcode"))
    p = Product(**data)
    if p.min_stock == 0:
        p.min_stock = get_setting(db, "business.low_stock_default", 0) or 0
    db.add(p)
    db.commit()
    from .audit_service import log as _audit
    _audit(db, user_id=created_by, username=None,
           action="product.create", entity_type="product",
           entity_id=p.id, new_values={"name": p.name, "sku": p.sku})
    return p


def update_product(db: Session, p: Product, data: dict) -> Product:
    _check_sku_barcode_unique(db, data.get("sku"), data.get("barcode"), exclude_id=p.id)
    for k, v in data.items():
        if v is not None or k in ("sku", "barcode", "description", "supplier_id",
                                  "category_id", "brand_id", "compatibility"):
            setattr(p, k, v)
    db.commit()
    return p


def delete_product(db: Session, p: Product) -> None:
    movements = db.query(StockMovement.id).filter(StockMovement.product_id == p.id).first()
    if movements:
        raise ValueError("Product has stock history — deactivate it instead of deleting.")
    db.delete(p)
    db.commit()


# ------------------------------------------------------------------ adjustments
def adjust_stock(db: Session, *, product_id: int, delta: int, movement_type: str,
                 reason: str, user_id: int | None) -> StockMovement:
    product = get_product(db, product_id)
    if product is None:
        raise ValueError("Product not found")
    mtype = STOCK_DAMAGE if movement_type == "damage" else STOCK_ADJUST
    mv = apply_stock(db, product, delta, movement_type=mtype,
                     reference_type="adjustment", notes=reason,
                     created_by=user_id, force=True)
    db.commit()
    return mv


def receive_stock(db: Session, *, product_id: int, quantity: int, unit_cost_paisa: int,
                  reference_number: str | None = None, notes: str | None = None,
                  user_id: int | None = None) -> StockMovement:
    product = get_product(db, product_id)
    if product is None:
        raise ValueError("Product not found")
    weighted_average_receive(db, product, quantity, unit_cost_paisa)
    mv = apply_stock(db, product, quantity, movement_type=STOCK_RECEIVE,
                     reference_type="purchase" if reference_number is None else "manual_receive",
                     reference_number=reference_number, notes=notes,
                     created_by=user_id, unit_cost_paisa=unit_cost_paisa)
    db.commit()
    return mv


# ------------------------------------------------------------------ movements
def list_movements(db: Session, product_id: int | None = None, movement_type: str | None = None,
                   reference_type: str | None = None, date_from: str | None = None,
                   date_to: str | None = None, limit: int = 100, offset: int = 0):
    date_from, date_to = range_utc(date_from, date_to)
    q = db.query(StockMovement)
    if product_id:
        q = q.filter(StockMovement.product_id == product_id)
    if movement_type:
        q = q.filter(StockMovement.movement_type == movement_type)
    if reference_type:
        q = q.filter(StockMovement.reference_type == reference_type)
    if date_from:
        q = q.filter(StockMovement.created_at >= date_from)
    if date_to:
        q = q.filter(StockMovement.created_at <= date_to)
    total = q.count()
    rows = (q.order_by(StockMovement.id.desc()).offset(offset).limit(limit).all())
    names = {p.id: (p.name, p.sku) for p in
             db.query(Product).filter(Product.id.in_([m.product_id for m in rows])).all()} if rows else {}
    out = []
    for m in rows:
        nm, sku = names.get(m.product_id, (None, None))
        out.append({
            "id": m.id, "product_id": m.product_id, "product_name": nm, "sku": sku,
            "movement_type": m.movement_type, "quantity_delta": m.quantity_delta,
            "quantity_after": m.quantity_after, "unit_cost_paisa": m.unit_cost_paisa,
            "reference_type": m.reference_type, "reference_id": m.reference_id,
            "reference_number": m.reference_number, "notes": m.notes,
            "created_by": m.created_by,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return out, total


def low_stock_products(db: Session):
    rows = db.query(Product).filter(
        Product.is_active.is_(True),
        Product.quantity_on_hand <= Product.min_stock,
    ).order_by(Product.quantity_on_hand.asc()).all()
    return [product_out(p) for p in rows]


def inventory_valuation(db: Session) -> int:
    rows = db.query(Product.quantity_on_hand, Product.purchase_cost_paisa).filter(
        Product.is_service.is_(False)).all()
    return int(sum(q * c for q, c in rows))


# ------------------------------------------------------------------ categories / brands
def list_categories(db: Session):
    return [{"id": c.id, "name": c.name, "is_active": c.is_active}
            for c in db.query(Category).order_by(Category.name).all()]


def create_category(db: Session, name: str) -> Category:
    name = name.strip()
    if db.query(Category).filter(func.lower(Category.name) == name.lower()).first():
        raise ValueError("Category already exists")
    c = Category(name=name)
    db.add(c)
    db.commit()
    return c


def list_brands(db: Session):
    return [{"id": b.id, "name": b.name, "is_active": b.is_active}
            for b in db.query(Brand).order_by(Brand.name).all()]


def create_brand(db: Session, name: str) -> Brand:
    name = name.strip()
    if db.query(Brand).filter(func.lower(Brand.name) == name.lower()).first():
        raise ValueError("Brand already exists")
    b = Brand(name=name)
    db.add(b)
    db.commit()
    return b


def delete_category(db: Session, cid: int) -> None:
    in_use = db.query(Product.id).filter(Product.category_id == cid).first()
    if in_use:
        raise ValueError("Category is in use by products")
    db.query(Category).filter(Category.id == cid).delete()
    db.commit()


def delete_brand(db: Session, bid: int) -> None:
    in_use = db.query(Product.id).filter(Product.brand_id == bid).first()
    if in_use:
        raise ValueError("Brand is in use by products")
    db.query(Brand).filter(Brand.id == bid).delete()
    db.commit()


# ------------------------------------------------------------------ CSV
def products_csv(db: Session, rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name", "sku", "barcode", "category", "brand", "compatibility",
                "purchase_cost_pkr", "selling_price_pkr", "quantity_on_hand",
                "min_stock", "unit", "supplier", "is_service", "active"])
    name_cat = {c.id: c.name for c in db.query(Category).all()}
    name_brand = {b.id: b.name for b in db.query(Brand).all()}
    for r in rows:
        w.writerow([r.get("name", ""), r.get("sku") or "", r.get("barcode") or "",
                    name_cat.get(r.get("category_id"), ""), name_brand.get(r.get("brand_id"), ""),
                    r.get("compatibility") or "",
                    (r.get("purchase_cost_paisa") or 0) / 100,
                    (r.get("selling_price_paisa") or 0) / 100,
                    r.get("quantity_on_hand", 0), r.get("min_stock", 0), r.get("unit", "pcs"),
                    "", "yes" if r.get("is_service") else "no",
                    "yes" if r.get("is_active", True) else "no"])
    return buf.getvalue()


def parse_products_csv(text: str) -> list[dict]:
    """Validate CSV rows for import. Returns list of parsed products."""
    reader = csv.DictReader(io.StringIO(text))
    required = {"name"}
    if reader.fieldnames is None or not required.issubset({f.strip() for f in reader.fieldnames}):
        raise ValueError("CSV must contain a 'name' column")
    out = []
    for i, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            continue
        try:
            out.append({
                "name": name,
                "sku": (row.get("sku") or "").strip() or None,
                "barcode": (row.get("barcode") or "").strip() or None,
                "category_id": _int_or_none(row.get("category_id")),
                "brand_id": _int_or_none(row.get("brand_id")),
                "compatibility": (row.get("compatibility") or "").strip() or None,
                "purchase_cost_paisa": int(round(float(row.get("purchase_cost_pkr") or 0) * 100)),
                "selling_price_paisa": int(round(float(row.get("selling_price_pkr") or 0) * 100)),
                "min_stock": _int_or_none(row.get("min_stock")) or 0,
                "unit": (row.get("unit") or "pcs").strip() or "pcs",
                "supplier_id": _int_or_none(row.get("supplier_id")),
                "is_service": str(row.get("is_service", "no")).strip().lower() in ("yes", "1", "true"),
                "is_active": str(row.get("active", "yes")).strip().lower() not in ("no", "0", "false"),
                "description": (row.get("description") or "").strip() or None,
            })
        except (ValueError, TypeError) as e:
            raise ValueError(f"Row {i}: {e}")
    if not out:
        raise ValueError("CSV contains no usable rows")
    return out


def _int_or_none(v):
    if v is None or str(v).strip() == "":
        return None
    return int(str(v).strip())

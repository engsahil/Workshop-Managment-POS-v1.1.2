"""Products, categories, brands, stock movements and adjustments."""
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

from ..core.constants import STOCK_ADJUST, STOCK_DAMAGE
from ..core.deps import get_current_user, get_db, require_financial
from ..models import Product, User
from ..schemas.inventory import (ProductIn, ProductUpdateIn,
                                   StockAdjustmentIn, StockReceiveIn)
from ..services import inventory_service

router = APIRouter(prefix="/api", tags=["inventory"])

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


@router.get("/products")
def list_products(q: str | None = None, category_id: int | None = None,
                  brand_id: int | None = None, low_stock: bool = False,
                  include_inactive: bool = False, include_services: bool = False,
                  page: int = 1, page_size: int = 50, db=Depends(get_db),
                  _: User = Depends(get_current_user)):
    limit = min(200, max(1, page_size))
    offset = (max(1, page) - 1) * limit
    rows, total = inventory_service.list_products(
        db, q=q, category_id=category_id, brand_id=brand_id,
        include_inactive=include_inactive, include_services=include_services,
        low_stock=low_stock, limit=limit, offset=offset)
    return {"items": rows, "total": total, "page": page, "page_size": limit}


@router.post("/products")
def create_product(payload: ProductIn, db=Depends(get_db),
                   _: User = Depends(get_current_user)):
    try:
        p = inventory_service.create_product(db, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return inventory_service.product_out(p)


@router.get("/products/{pid}")
def get_product(pid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    p = inventory_service.get_product(db, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="Product not found")
    out = inventory_service.product_out(p)
    out["movements"], _ = inventory_service.list_movements(db, product_id=pid, limit=20)
    return out


@router.put("/products/{pid}")
def update_product(pid: int, payload: ProductUpdateIn, db=Depends(get_db),
                   _: User = Depends(get_current_user)):
    p = inventory_service.get_product(db, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        inventory_service.update_product(db, p, payload.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return inventory_service.product_out(p)


@router.delete("/products/{pid}")
def delete_product(pid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    p = inventory_service.get_product(db, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        inventory_service.delete_product(db, p)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/products/export/csv")
def export_products_csv(db=Depends(get_db), _: User = Depends(get_current_user)):
    from fastapi.responses import PlainTextResponse
    rows, _ = inventory_service.list_products(db, limit=100000, include_inactive=True,
                                                 include_services=True)
    csv_text = inventory_service.products_csv(db, rows)
    return PlainTextResponse(csv_text, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=products.csv"})


@router.post("/products/import/csv")
def import_products_csv(file: UploadFile = File(...), db=Depends(get_db),
                        _: User = Depends(get_current_user)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")
    try:
        text = file.file.read().decode("utf-8")
        parsed = inventory_service.parse_products_csv(text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")
    created = 0
    updated = 0
    for row in parsed:
        existing = None
        if row.get("sku"):
            existing = db.query(Product).filter(Product.sku == row["sku"]).first()
        if existing:
            inventory_service.update_product(db, existing, row)
            updated += 1
        else:
            inventory_service.create_product(db, row)
            created += 1
    return {"ok": True, "created": created, "updated": updated,
            "rows": len(parsed)}


# ---------------------------------------------------------------- categories / brands
@router.get("/categories")
def list_categories(db=Depends(get_db), _: User = Depends(get_current_user)):
    return inventory_service.list_categories(db)


@router.post("/categories")
def create_category(payload: dict, db=Depends(get_db),
                    _: User = Depends(get_current_user)):
    try:
        return inventory_service.create_category(db, payload.get("name", ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/categories/{cid}")
def delete_category(cid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    try:
        inventory_service.delete_category(db, cid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/brands")
def list_brands(db=Depends(get_db), _: User = Depends(get_current_user)):
    return inventory_service.list_brands(db)


@router.post("/brands")
def create_brand(payload: dict, db=Depends(get_db), _: User = Depends(get_current_user)):
    try:
        return inventory_service.create_brand(db, payload.get("name", ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/brands/{bid}")
def delete_brand(bid: int, db=Depends(get_db), _: User = Depends(get_current_user)):
    try:
        inventory_service.delete_brand(db, bid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


# ---------------------------------------------------------------- stock ops
@router.post("/inventory/adjust")
def adjust_stock(payload: StockAdjustmentIn, db=Depends(get_db),
                 user: User = Depends(require_financial)):
    try:
        inventory_service.adjust_stock(
            db, product_id=payload.product_id, delta=payload.delta,
            movement_type=payload.movement_type, reason=payload.reason,
            user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.post("/inventory/receive")
def receive_stock(payload: StockReceiveIn, db=Depends(get_db),
                  user: User = Depends(get_current_user)):
    try:
        mv = inventory_service.receive_stock(
            db, product_id=payload.product_id, quantity=payload.quantity,
            unit_cost_paisa=payload.unit_cost_paisa,
            reference_number=payload.reference_number, notes=payload.notes,
            user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "movement_id": mv.id}


@router.get("/inventory/movements")
def list_movements(product_id: int | None = None, movement_type: str | None = None,
                   reference_type: str | None = None, date_from: str | None = None,
                   date_to: str | None = None, page: int = 1, page_size: int = 50,
                   db=Depends(get_db), _: User = Depends(get_current_user)):
    limit = min(200, max(1, page_size))
    offset = (max(1, page) - 1) * limit
    rows, total = inventory_service.list_movements(
        db, product_id=product_id, movement_type=movement_type,
        reference_type=reference_type, date_from=date_from, date_to=date_to,
        limit=limit, offset=offset)
    return {"items": rows, "total": total, "page": page, "page_size": limit}


@router.get("/inventory/low-stock")
def low_stock(db=Depends(get_db), _: User = Depends(get_current_user)):
    return inventory_service.low_stock_products(db)


@router.get("/inventory/valuation")
def valuation(db=Depends(get_db), _: User = Depends(get_current_user)):
    return {"valuation_paisa": inventory_service.inventory_valuation(db)}

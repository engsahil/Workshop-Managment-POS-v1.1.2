from pydantic import BaseModel, Field


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class BrandIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sku: str | None = Field(default=None, max_length=64)
    barcode: str | None = Field(default=None, max_length=80)
    category_id: int | None = None
    brand_id: int | None = None
    compatibility: str | None = Field(default=None, max_length=200)
    purchase_cost_paisa: int = Field(default=0, ge=0)
    selling_price_paisa: int = Field(default=0, ge=0)
    min_stock: int = Field(default=0, ge=0)
    unit: str = Field(default="pcs", max_length=24)
    supplier_id: int | None = None
    description: str | None = None
    is_service: bool = False
    warranty_days: int = Field(default=0, ge=0)
    is_active: bool = True


class ProductUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sku: str | None = Field(default=None, max_length=64)
    barcode: str | None = Field(default=None, max_length=80)
    category_id: int | None = None
    brand_id: int | None = None
    compatibility: str | None = Field(default=None, max_length=200)
    purchase_cost_paisa: int | None = Field(default=None, ge=0)
    selling_price_paisa: int | None = Field(default=None, ge=0)
    min_stock: int | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=24)
    supplier_id: int | None = None
    description: str | None = None
    is_service: bool | None = None
    warranty_days: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ProductOut(BaseModel):
    id: int
    name: str
    sku: str | None
    barcode: str | None
    category_id: int | None
    brand_id: int | None
    compatibility: str | None
    purchase_cost_paisa: int
    selling_price_paisa: int
    quantity_on_hand: int
    min_stock: int
    unit: str
    supplier_id: int | None
    description: str | None
    is_service: bool
    warranty_days: int
    is_active: bool
    created_at: object
    updated_at: object


class StockAdjustmentIn(BaseModel):
    product_id: int
    delta: int
    movement_type: str = "adjust"   # adjust | damage
    reason: str = Field(min_length=1, max_length=300)


class StockReceiveIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    unit_cost_paisa: int = Field(default=0, ge=0)
    reference_number: str | None = Field(default=None, max_length=48)
    notes: str | None = None


class StockMovementOut(BaseModel):
    id: int
    product_id: int
    product_name: str | None = None
    sku: str | None = None
    movement_type: str
    quantity_delta: int
    quantity_after: int
    unit_cost_paisa: int | None
    reference_type: str | None
    reference_id: int | None
    reference_number: str | None
    notes: str | None
    created_by: int | None
    created_at: object

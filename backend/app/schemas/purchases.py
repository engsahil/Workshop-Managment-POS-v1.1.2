from datetime import date
from pydantic import BaseModel, Field


class PurchaseItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    unit_cost_paisa: int = Field(ge=0)


class PurchaseIn(BaseModel):
    supplier_id: int
    order_date: date | None = None
    items: list[PurchaseItemIn] = Field(min_length=1)
    discount_paisa: int = Field(default=0, ge=0)
    notes: str | None = None


class PurchaseUpdateIn(BaseModel):
    status: str | None = None
    notes: str | None = None


class PurchaseReceiveIn(BaseModel):
    # optional partial receipt: [{product_id, quantity}] —
    # omit/empty to receive the full remaining quantity
    items: list[dict] = Field(default_factory=list)


class PurchasePaymentIn(BaseModel):
    amount_paisa: int = Field(gt=0)
    method: str = "cash"
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class PurchaseReturnIn(BaseModel):
    purchase_id: int | None = None
    supplier_id: int | None = None
    items: list[dict] = Field(min_length=1)  # [{product_id, quantity, unit_cost_paisa}]
    method: str = "cash"
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    alt_phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=160)
    address: str | None = Field(default=None, max_length=300)
    notes: str | None = None


class SupplierUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    alt_phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=160)
    address: str | None = Field(default=None, max_length=300)
    notes: str | None = None
    is_active: bool | None = None

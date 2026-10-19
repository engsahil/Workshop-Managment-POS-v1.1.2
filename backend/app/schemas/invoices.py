from pydantic import BaseModel, Field, field_validator

from ..core.constants import PAYMENT_METHODS, PAYMENT_KINDS, RESTOCK_CHOICES


class InvoiceItemIn(BaseModel):
    item_type: str = "product"          # product | service
    product_id: int | None = None
    service_id: int | None = None
    job_part_id: int | None = None
    job_service_id: int | None = None
    description: str | None = Field(default=None, max_length=300)
    quantity: float = Field(gt=0)
    unit: str = Field(default="pcs", max_length=24)
    unit_price_paisa: int = Field(ge=0)
    discount_paisa: int = Field(default=0, ge=0)
    is_warranty: bool = False

    @field_validator("item_type")
    @classmethod
    def type_ok(cls, v):
        if v not in ("product", "service"):
            raise ValueError("item_type must be product or service")
        return v


class PaymentIn(BaseModel):
    amount_paisa: int = Field(gt=0)
    method: str = "cash"
    reference: str | None = Field(default=None, max_length=120)
    kind: str = "sale_payment"
    notes: str | None = None

    @field_validator("method")
    @classmethod
    def method_ok(cls, v):
        if v not in PAYMENT_METHODS:
            raise ValueError("Unknown payment method")
        return v

    @field_validator("kind")
    @classmethod
    def kind_ok(cls, v):
        if v not in PAYMENT_KINDS:
            raise ValueError("Unknown payment kind")
        return v


class InvoiceCreateIn(BaseModel):
    customer_id: int | None = None
    vehicle_id: int | None = None
    job_id: int | None = None
    items: list[InvoiceItemIn] = Field(min_length=1)
    invoice_discount_paisa: int = Field(default=0, ge=0)
    payments: list[PaymentIn] = Field(default_factory=list)
    is_credit: bool = False
    notes: str | None = None


class InvoiceVoidIn(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


class SaleReturnItemIn(BaseModel):
    invoice_item_id: int
    quantity: float = Field(gt=0)


class SaleReturnIn(BaseModel):
    invoice_id: int
    reason: str | None = Field(default=None, max_length=120)
    restock_action: str = "restock"      # restock | damaged | discard
    refund_method: str = "cash"          # cash | card | ... | credit
    items: list[SaleReturnItemIn] = Field(min_length=1)
    notes: str | None = None

    @field_validator("restock_action")
    @classmethod
    def rs_ok(cls, v):
        if v not in RESTOCK_CHOICES:
            raise ValueError("restock_action must be restock, damaged or discard")
        return v

    @field_validator("refund_method")
    @classmethod
    def rm_ok(cls, v):
        if v not in PAYMENT_METHODS and v != "credit":
            raise ValueError("Invalid refund method")
        return v


class ReturnDecisionIn(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    notes: str | None = None

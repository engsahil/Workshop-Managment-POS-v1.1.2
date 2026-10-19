from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator, model_validator

from ..core.constants import PAYMENT_METHODS


class ExpenseCategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ExpenseIn(BaseModel):
    category_id: int
    amount_paisa: int = Field(gt=0)
    expense_date: date | None = None
    method: str = "cash"
    payee: str | None = Field(default=None, max_length=160)
    description: str | None = None
    reference: str | None = Field(default=None, max_length=120)
    attachment_path: str | None = Field(default=None, max_length=300)

    @model_validator(mode="before")
    @classmethod
    def coerce_empty(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for k in ("expense_date", "payee", "description", "reference", "attachment_path"):
                if data.get(k) == "":
                    data[k] = None
            if isinstance(data.get("expense_date"), str) and len(data["expense_date"]) > 10:
                data["expense_date"] = data["expense_date"][:10]
        return data

    @field_validator("method")
    @classmethod
    def m_ok(cls, v):
        if v not in PAYMENT_METHODS:
            raise ValueError("Unknown payment method")
        return v


class ExpenseUpdateIn(BaseModel):
    category_id: int | None = None
    amount_paisa: int | None = Field(default=None, gt=0)
    expense_date: date | None = None
    method: str | None = None
    payee: str | None = Field(default=None, max_length=160)
    description: str | None = None
    reference: str | None = Field(default=None, max_length=120)

    @model_validator(mode="before")
    @classmethod
    def coerce_empty(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for k in ("category_id", "expense_date", "payee", "description", "reference"):
                if data.get(k) == "":
                    data[k] = None
            if isinstance(data.get("expense_date"), str) and len(data["expense_date"]) > 10:
                data["expense_date"] = data["expense_date"][:10]
        return data

    @field_validator("method")
    @classmethod
    def m_ok(cls, v):
        if v is not None and v not in PAYMENT_METHODS:
            raise ValueError("Unknown payment method")
        return v


class ShiftOpenIn(BaseModel):
    opening_cash_paisa: int = Field(ge=0)


class CashMovementIn(BaseModel):
    movement_type: str = Field(pattern="^(addition|withdrawal)$")
    amount_paisa: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=200)
    reference: str | None = Field(default=None, max_length=120)


class ShiftCloseIn(BaseModel):
    counted_cash_paisa: int = Field(ge=0)
    closing_notes: str | None = Field(default=None, max_length=300)


class CustomerAdvanceIn(BaseModel):
    customer_id: int
    amount_paisa: int = Field(gt=0)
    method: str = "cash"
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class RepaymentIn(BaseModel):
    customer_id: int
    amount_paisa: int = Field(gt=0)
    method: str = "cash"
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = None

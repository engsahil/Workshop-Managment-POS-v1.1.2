from pydantic import BaseModel, Field


class BusinessSettingsIn(BaseModel):
    business_name: str | None = Field(default=None, max_length=160)
    tagline: str | None = Field(default=None, max_length=160)
    address: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=160)
    logo_path: str | None = Field(default=None, max_length=200)
    invoice_prefix: str | None = Field(default=None, max_length=16)
    job_prefix: str | None = Field(default=None, max_length=16)
    purchase_prefix: str | None = Field(default=None, max_length=16)
    expense_prefix: str | None = Field(default=None, max_length=16)
    return_prefix: str | None = Field(default=None, max_length=16)
    claim_prefix: str | None = Field(default=None, max_length=16)
    tax_enabled: bool | None = None
    tax_rate_percent: float | None = Field(default=None, ge=0, le=100)
    low_stock_default: int | None = Field(default=None, ge=0)
    allow_negative_stock: bool | None = None
    payment_methods: list[str] | None = None
    business_hours: str | None = None
    timezone: str | None = None


class LegalIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)


class LegalOut(BaseModel):
    key: str
    title: str
    content: str
    updated_at: object | None


class BackupOut(BaseModel):
    filename: str
    size_bytes: int
    created_at: str

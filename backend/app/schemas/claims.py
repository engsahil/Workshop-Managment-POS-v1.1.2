from datetime import date, datetime
from pydantic import BaseModel, Field, model_validator


class ClaimIn(BaseModel):
    customer_id: int | None = None
    vehicle_id: int | None = None
    invoice_id: int | None = None
    job_id: int | None = None
    item_type: str = "product"
    product_id: int | None = None
    service_id: int | None = None
    purchase_date: date | None = None
    warranty_days: int = Field(default=0, ge=0)
    description: str | None = None
    inspection_notes: str | None = None
    action_taken: str | None = None
    status: str = "open"
    resolution: str | None = None
    cost_paisa: int = Field(default=0, ge=0)
    refund_amount_paisa: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def coerce_empty(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for k in (
                "customer_id",
                "vehicle_id",
                "invoice_id",
                "job_id",
                "product_id",
                "service_id",
                "purchase_date",
                "description",
                "inspection_notes",
                "action_taken",
                "resolution",
            ):
                if data.get(k) == "":
                    data[k] = None
            for k in ("warranty_days", "cost_paisa", "refund_amount_paisa"):
                if data.get(k) in ("", None):
                    data[k] = 0
            if isinstance(data.get("purchase_date"), str) and len(data["purchase_date"]) > 10:
                data["purchase_date"] = data["purchase_date"][:10]
        return data


class ClaimUpdateIn(BaseModel):
    customer_id: int | None = None
    vehicle_id: int | None = None
    invoice_id: int | None = None
    job_id: int | None = None
    item_type: str | None = None
    product_id: int | None = None
    service_id: int | None = None
    purchase_date: date | None = None
    warranty_days: int | None = Field(default=None, ge=0)
    description: str | None = None
    inspection_notes: str | None = None
    action_taken: str | None = None
    status: str | None = None
    resolution: str | None = None
    cost_paisa: int | None = Field(default=None, ge=0)
    refund_amount_paisa: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def coerce_empty(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for k in (
                "customer_id",
                "vehicle_id",
                "invoice_id",
                "job_id",
                "product_id",
                "service_id",
                "purchase_date",
                "description",
                "inspection_notes",
                "action_taken",
                "resolution",
            ):
                if data.get(k) == "":
                    data[k] = None
            if isinstance(data.get("purchase_date"), str) and len(data["purchase_date"]) > 10:
                data["purchase_date"] = data["purchase_date"][:10]
        return data

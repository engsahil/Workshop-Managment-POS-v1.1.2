from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator, model_validator

from ..core.constants import JOB_PRIORITIES


class JobServiceIn(BaseModel):
    service_id: int | None = None
    description: str = Field(min_length=1, max_length=240)
    quantity: int = Field(default=1, ge=1)
    unit_charge_paisa: int = Field(default=0, ge=0)
    discount_paisa: int = Field(default=0, ge=0)
    mechanic_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_empty_ids(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for k in ("service_id", "mechanic_id"):
                if data.get(k) == "":
                    data[k] = None
        return data


class JobPartIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    unit_price_paisa: int = Field(default=0, ge=0)


class JobCreateIn(BaseModel):
    customer_id: int
    vehicle_id: int
    reported_issue: str | None = None
    complaint: str | None = None
    inspection: str | None = None
    vehicle_condition: str | None = None
    existing_damage: str | None = None
    fuel_level: str | None = Field(default=None, max_length=20)
    mechanic_id: int | None = None
    odometer: int | None = Field(default=None, ge=0)
    est_labor_paisa: int = Field(default=0, ge=0)
    est_parts_paisa: int = Field(default=0, ge=0)
    est_completion_date: date | None = None
    priority: str = "normal"
    internal_notes: str | None = None
    customer_notes: str | None = None
    warranty_days: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def coerce_empty(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for k in ("mechanic_id", "odometer", "est_completion_date", "fuel_level"):
                if data.get(k) == "":
                    data[k] = None
            for k in ("est_labor_paisa", "est_parts_paisa", "warranty_days"):
                if data.get(k) in ("", None):
                    data[k] = 0
            if isinstance(data.get("est_completion_date"), str) and len(data["est_completion_date"]) > 10:
                data["est_completion_date"] = data["est_completion_date"][:10]
        return data

    @field_validator("priority")
    @classmethod
    def pr_ok(cls, v):
        if v not in JOB_PRIORITIES:
            raise ValueError("Invalid priority")
        return v


class JobUpdateIn(BaseModel):
    customer_id: int | None = None
    vehicle_id: int | None = None
    reported_issue: str | None = None
    complaint: str | None = None
    inspection: str | None = None
    vehicle_condition: str | None = None
    existing_damage: str | None = None
    fuel_level: str | None = Field(default=None, max_length=20)
    mechanic_id: int | None = None
    odometer: int | None = Field(default=None, ge=0)
    est_labor_paisa: int | None = Field(default=None, ge=0)
    est_parts_paisa: int | None = Field(default=None, ge=0)
    est_completion_date: date | None = None
    priority: str | None = None
    internal_notes: str | None = None
    customer_notes: str | None = None
    warranty_days: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def coerce_empty(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for k in ("customer_id", "vehicle_id", "mechanic_id", "odometer", "est_completion_date", "fuel_level"):
                if data.get(k) == "":
                    data[k] = None
            if isinstance(data.get("est_completion_date"), str) and len(data["est_completion_date"]) > 10:
                data["est_completion_date"] = data["est_completion_date"][:10]
        return data

    @field_validator("priority")
    @classmethod
    def pr_ok(cls, v):
        if v is not None and v not in JOB_PRIORITIES:
            raise ValueError("Invalid priority")
        return v


class JobStatusIn(BaseModel):
    status: str
    notes: str | None = None


class JobApprovalIn(BaseModel):
    approval_status: str = Field(pattern="^(not_required|pending|approved|rejected)$")
    notes: str | None = None


class JobEstimateIn(BaseModel):
    est_labor_paisa: int = Field(ge=0)
    est_parts_paisa: int = Field(ge=0)
    est_completion_date: date | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_empty(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            if data.get("est_completion_date") == "":
                data["est_completion_date"] = None
        return data

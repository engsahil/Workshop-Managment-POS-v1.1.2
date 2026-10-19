from datetime import date
from pydantic import BaseModel, Field, field_validator

from ..core.constants import VEHICLE_TYPES


class ServiceIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    code: str | None = Field(default=None, max_length=48)
    description: str | None = None
    default_charge_paisa: int = Field(default=0, ge=0)
    estimated_minutes: int = Field(default=0, ge=0)
    vehicle_types: str = "motorcycle,car"
    is_active: bool = True

    @field_validator("vehicle_types")
    @classmethod
    def vt_ok(cls, v):
        allowed = set(VEHICLE_TYPES)
        parts = [p.strip() for p in (v or "").split(",") if p.strip()]
        bad = [p for p in parts if p not in allowed]
        if bad:
            raise ValueError(f"Vehicle types must be one of: {', '.join(sorted(allowed))}")
        return ",".join(parts) if parts else "motorcycle,car"


class ServiceUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    code: str | None = Field(default=None, max_length=48)
    description: str | None = None
    default_charge_paisa: int | None = Field(default=None, ge=0)
    estimated_minutes: int | None = Field(default=None, ge=0)
    vehicle_types: str | None = None
    is_active: bool | None = None

    @field_validator("vehicle_types")
    @classmethod
    def vt_ok(cls, v):
        if v is None:
            return v
        allowed = set(VEHICLE_TYPES)
        parts = [p.strip() for p in v.split(",") if p.strip()]
        bad = [p for p in parts if p not in allowed]
        if bad:
            raise ValueError(f"Vehicle types must be one of: {', '.join(sorted(allowed))}")
        return ",".join(parts) if parts else "motorcycle,car"


class MechanicIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    skill: str | None = Field(default=None, max_length=120)
    commission_type: str = "none"      # none | percent_per_job | fixed_per_job
    commission_value: int = Field(default=0, ge=0)
    is_active: bool = True
    hire_date: date | None = None
    notes: str | None = None
    user_id: int | None = None


class MechanicUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    skill: str | None = Field(default=None, max_length=120)
    commission_type: str | None = None
    commission_value: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    hire_date: date | None = None
    notes: str | None = None

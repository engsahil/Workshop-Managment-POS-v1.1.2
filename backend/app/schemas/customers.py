import re
from pydantic import BaseModel, Field, field_validator, model_validator

from ..core.constants import VEHICLE_TYPES

_PHONE_RE = re.compile(r"^[+]?[0-9][0-9\s\-().]{5,24}$")


def _clean_opt_str(v):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s if s else None
    return v


def _validate_phone(v: str | None) -> str | None:
    s = _clean_opt_str(v)
    if s is None:
        return None
    digits = re.sub(r"\D", "", s)
    if len(digits) < 7 or len(digits) > 15 or not _PHONE_RE.match(s):
        raise ValueError("Invalid phone number format (e.g. 0300-1234567 or +923001234567)")
    return s


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    alt_phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=300)
    cnic: str | None = Field(default=None, max_length=30)
    notes: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("phone", "alt_phone", mode="before")
    @classmethod
    def clean_phones(cls, v):
        return _validate_phone(v)

    @field_validator("address", "cnic", "notes", mode="before")
    @classmethod
    def clean_strings(cls, v):
        return _clean_opt_str(v)


class CustomerUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    alt_phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=300)
    cnic: str | None = Field(default=None, max_length=30)
    notes: str | None = None
    is_active: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, v):
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v

    @field_validator("phone", "alt_phone", mode="before")
    @classmethod
    def clean_phones(cls, v):
        return _validate_phone(v)

    @field_validator("address", "cnic", "notes", mode="before")
    @classmethod
    def clean_strings(cls, v):
        return _clean_opt_str(v)


class CustomerOut(BaseModel):
    id: int
    code: str
    name: str
    phone: str | None
    alt_phone: str | None
    address: str | None
    cnic: str | None
    notes: str | None
    is_active: bool
    balance_paisa: int = 0
    advance_paisa: int = 0
    vehicle_count: int = 0
    created_at: object


class VehicleIn(BaseModel):
    customer_id: int
    vehicle_type: str = "motorcycle"
    registration_no: str | None = Field(default=None, max_length=40)
    make: str | None = Field(default=None, max_length=60)
    model: str | None = Field(default=None, max_length=80)
    year: int | None = None
    color: str | None = Field(default=None, max_length=40)
    engine_no: str | None = Field(default=None, max_length=60)
    chassis_no: str | None = Field(default=None, max_length=60)
    odometer: int | None = None
    fuel_type: str | None = Field(default=None, max_length=24)
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_fields(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            if not data.get("registration_no"):
                alias = data.get("registration_number") or data.get("plate_number")
                if alias:
                    data["registration_no"] = alias
            for k in ("year", "odometer", "registration_no", "make", "model", "color", "engine_no", "chassis_no", "fuel_type", "notes"):
                if isinstance(data.get(k), str):
                    s = data[k].strip()
                    data[k] = None if s == "" else (s.upper() if k == "registration_no" else s)
        return data

    @field_validator("vehicle_type")
    @classmethod
    def vt_ok(cls, v):
        if v not in VEHICLE_TYPES:
            raise ValueError(f"Vehicle type must be one of: {', '.join(VEHICLE_TYPES)}")
        return v


class VehicleUpdateIn(BaseModel):
    customer_id: int | None = None
    vehicle_type: str | None = None
    registration_no: str | None = Field(default=None, max_length=40)
    make: str | None = Field(default=None, max_length=60)
    model: str | None = Field(default=None, max_length=80)
    year: int | None = None
    color: str | None = Field(default=None, max_length=40)
    engine_no: str | None = Field(default=None, max_length=60)
    chassis_no: str | None = Field(default=None, max_length=60)
    odometer: int | None = None
    fuel_type: str | None = Field(default=None, max_length=24)
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_fields(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            if not data.get("registration_no"):
                alias = data.get("registration_number") or data.get("plate_number")
                if alias:
                    data["registration_no"] = alias
            for k in ("customer_id", "year", "odometer", "registration_no", "make", "model", "color", "engine_no", "chassis_no", "fuel_type", "notes"):
                if data.get(k) == "":
                    data[k] = None
        return data

    @field_validator("vehicle_type")
    @classmethod
    def vt_ok(cls, v):
        if v is not None and v not in VEHICLE_TYPES:
            raise ValueError(f"Vehicle type must be one of: {', '.join(VEHICLE_TYPES)}")
        return v


class VehicleOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str | None = None
    vehicle_type: str
    registration_no: str | None
    make: str | None
    model: str | None
    year: int | None
    color: str | None
    engine_no: str | None
    chassis_no: str | None
    odometer: int | None
    fuel_type: str | None
    notes: str | None
    created_at: object
    updated_at: object

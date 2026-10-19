from pydantic import BaseModel, Field, field_validator

from ..core.constants import ROLES


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class SetupAdminIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    password_confirm: str | None = Field(default=None, min_length=6, max_length=128)

    @field_validator("password_confirm")
    @classmethod
    def match(cls, v, info):
        if v is not None and v != info.data.get("password"):
            raise ValueError("Passwords do not match")
        return v


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    email: str | None
    phone: str | None
    role: str
    is_active: bool
    must_change_password: bool
    last_login_at: object | None
    created_at: object


class UserCreateIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    role: str
    email: str | None = None
    phone: str | None = None

    @field_validator("role")
    @classmethod
    def role_ok(cls, v):
        if v not in ROLES:
            raise ValueError("Invalid role")
        return v


class UserUpdateIn(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    role: str | None = None
    is_active: bool | None = None
    must_change_password: bool | None = None

    @field_validator("role")
    @classmethod
    def role_ok(cls, v):
        if v is not None and v not in ROLES:
            raise ValueError("Invalid role")
        return v


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)


class ResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

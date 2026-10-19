"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status

from ..core.constants import ROLE_ADMIN
from ..core.deps import get_current_user, get_db, require_admin
from ..models import User
from ..schemas.auth import (ChangePasswordIn, LoginIn, ResetPasswordIn,
                            SetupAdminIn, TokenOut, UserOut, UserCreateIn, UserUpdateIn)
from ..services import auth_service, audit_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(u: User) -> dict:
    return {
        "id": u.id, "username": u.username, "full_name": u.full_name,
        "email": u.email, "phone": u.phone, "role": u.role,
        "is_active": u.is_active, "must_change_password": u.must_change_password,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


@router.get("/setup-status")
def setup_status(db=Depends(get_db)):
    return {"needs_setup": auth_service.user_count(db) == 0}


@router.post("/setup", response_model=TokenOut)
def setup_admin(payload: SetupAdminIn, db=Depends(get_db)):
    """First-run administrator creation. Only works when no users exist."""
    if auth_service.user_count(db) > 0:
        raise HTTPException(status_code=403, detail="Administrator already exists")
    user = auth_service.create_user(db, username=payload.username,
                                    full_name=payload.full_name,
                                    password=payload.password, role=ROLE_ADMIN)
    token = auth_service.issue_token(user)
    audit_service.log(db, user_id=user.id, username=user.username,
                      action="auth.setup_admin", entity_type="user", entity_id=user.id)
    return {"access_token": token, "token_type": "bearer",
            "user": _user_out(user)}


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db=Depends(get_db)):
    user = auth_service.authenticate(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid username or password")
    auth_service.record_login(db, user)
    token = auth_service.issue_token(user)
    audit_service.log(db, user_id=user.id, username=user.username,
                      action="auth.login")
    return {"access_token": token, "token_type": "bearer",
            "user": _user_out(user)}


@router.get("/me", response_model=dict)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)


@router.post("/change-password")
def change_password(payload: ChangePasswordIn,
                    user: User = Depends(get_current_user), db=Depends(get_db)):
    auth_service.change_password(db, user, payload.current_password,
                                 payload.new_password)
    return {"ok": True, "message": "Password changed"}


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, payload: ResetPasswordIn,
                   admin: User = Depends(require_admin), db=Depends(get_db)):
    target = auth_service.get_user(db, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    auth_service.reset_password(db, target, payload.new_password, admin)
    return {"ok": True, "message": f"Password reset for {target.username}"}


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    # JWTs are stateless; client discards the token. Expiry bounds sessions.
    return {"ok": True, "message": "Logged out"}

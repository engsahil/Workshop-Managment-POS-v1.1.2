"""User management (admin only)."""
from fastapi import APIRouter, Depends, HTTPException

from ..core.deps import get_current_user, get_db, require_admin
from ..models import User
from ..schemas.auth import UserCreateIn, UserUpdateIn
from ..services import auth_service

router = APIRouter(prefix="/api/users", tags=["users"])


def _out(u: User) -> dict:
    return {"id": u.id, "username": u.username, "full_name": u.full_name,
            "email": u.email, "phone": u.phone, "role": u.role,
            "is_active": u.is_active, "must_change_password": u.must_change_password,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "created_at": u.created_at.isoformat() if u.created_at else None}


@router.get("")
def list_users(db=Depends(get_db), _: User = Depends(require_admin)):
    return [_out(u) for u in db.query(User).order_by(User.id).all()]


@router.post("")
def create_user(payload: UserCreateIn, db=Depends(get_db),
                admin: User = Depends(require_admin)):
    try:
        user = auth_service.create_user(db, username=payload.username,
                                        full_name=payload.full_name,
                                        password=payload.password,
                                        role=payload.role, email=payload.email,
                                        phone=payload.phone, created_by=admin.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _out(user)


@router.put("/{user_id}")
def update_user(user_id: int, payload: UserUpdateIn, db=Depends(get_db),
                admin: User = Depends(require_admin)):
    user = auth_service.get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and payload.is_active is False:
        raise HTTPException(status_code=400,
                            detail="You cannot deactivate your own account")
    data = payload.model_dump(exclude_unset=True)
    auth_service.update_user(db, user, changed_by=admin.id, **data)
    return _out(user)


@router.get("/roles")
def roles():
    from ..core.constants import ROLES
    return {"roles": list(ROLES)}

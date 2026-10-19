"""FastAPI dependencies: DB session, current user, role gates."""
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from .security import decode_token, token_expired
from ..models import User
from ..core.constants import ROLE_ADMIN, ROLE_MANAGER, ROLE_CASHIER, ROLE_MECHANIC


def get_current_user(db: Session = Depends(get_db),
                     authorization: str | None = Header(default=None)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if token_expired(payload):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account disabled")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return user


def require_financial(user: User = Depends(get_current_user)) -> User:
    """Void invoices, returns/refunds, credit sales, expenses, purchases."""
    if user.role not in (ROLE_ADMIN, ROLE_MANAGER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Manager or administrator approval is required for this action")
    return user


def require_pos(user: User = Depends(get_current_user)) -> User:
    if user.role not in (ROLE_ADMIN, ROLE_MANAGER, ROLE_CASHIER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cashier access required")
    return user


def require_workshop(user: User = Depends(get_current_user)) -> User:
    if user.role not in (ROLE_ADMIN, ROLE_MANAGER, ROLE_CASHIER, ROLE_MECHANIC):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workshop access required")
    return user


def require_report(user: User = Depends(get_current_user)) -> User:
    if user.role not in (ROLE_ADMIN, ROLE_MANAGER, ROLE_CASHIER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access required")
    return user

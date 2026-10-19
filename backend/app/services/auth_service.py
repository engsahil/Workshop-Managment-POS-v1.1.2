"""Authentication & user management business logic."""
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..core.security import hash_password, verify_password, create_token
from ..models import User
from ..services import audit_service


def user_count(db: Session) -> int:
    return db.query(func.count(User.id)).scalar() or 0


def get_user(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def find_user(db: Session, username: str) -> User | None:
    return db.query(User).filter(func.lower(User.username) == func.lower(username.strip())).first()


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = find_user(db, username)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def issue_token(user: User) -> str:
    return create_token(user.id, user.username, user.role)


def create_user(db: Session, *, username: str, full_name: str, password: str,
                role: str, email: str | None = None, phone: str | None = None,
                created_by: int | None = None) -> User:
    if find_user(db, username):
        raise ValueError("A user with this username already exists.")
    user = User(
        username=username.strip(),
        full_name=full_name.strip(),
        email=(email or None), phone=(phone or None),
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    audit_service.log(db, user_id=created_by, username=None, action="user.create",
                      entity_type="user", entity_id=user.id,
                      new_values={"username": user.username, "role": role})
    return user


def update_user(db: Session, user: User, *, full_name=None, email=None, phone=None,
                role=None, is_active=None, must_change_password=None, changed_by=None) -> User:
    old = {"full_name": user.full_name, "role": user.role, "is_active": user.is_active}
    if full_name is not None:
        user.full_name = full_name.strip()
    if email is not None:
        user.email = email.strip() or None
    if phone is not None:
        user.phone = phone.strip() or None
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = bool(is_active)
    if must_change_password is not None:
        user.must_change_password = bool(must_change_password)
    db.commit()
    audit_service.log(db, user_id=changed_by, username=None, action="user.update",
                      entity_type="user", entity_id=user.id,
                      old_values=old, new_values={"full_name": user.full_name,
                                                   "role": user.role, "is_active": user.is_active})
    return user


def change_password(db: Session, user: User, current: str, new_password: str) -> None:
    if not verify_password(current, user.password_hash):
        raise ValueError("Current password is incorrect.")
    if len(new_password) < 6:
        raise ValueError("New password must be at least 6 characters.")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    db.commit()
    audit_service.log(db, user_id=user.id, username=user.username,
                      action="user.change_password", entity_type="user", entity_id=user.id)


def reset_password(db: Session, target: User, new_password: str, admin_user: User) -> None:
    if len(new_password) < 6:
        raise ValueError("New password must be at least 6 characters.")
    target.password_hash = hash_password(new_password)
    target.must_change_password = True
    db.commit()
    audit_service.log(db, user_id=admin_user.id, username=admin_user.username,
                      action="user.reset_password", entity_type="user", entity_id=target.id,
                      new_values={"username": target.username})


def record_login(db: Session, user: User) -> None:
    from ..core.security import utcnow
    user.last_login_at = utcnow()
    db.commit()

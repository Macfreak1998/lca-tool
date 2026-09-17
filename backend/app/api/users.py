from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.constants import ROLE_ADMIN, ROLE_USER
from app.deps import AdminUser, DbDep
from app.models import User
from app.schemas import PromoteIn, UserOut
from app.serialize import user_out

router = APIRouter()


@router.get("", response_model=list[UserOut])
def list_users(_admin: AdminUser, db: DbDep) -> list[UserOut]:
    return [user_out(item) for item in db.query(User).order_by(User.email).all()]


@router.patch("/{user_id}", response_model=UserOut)
def promote(user_id: int, payload: PromoteIn, admin: AdminUser, db: DbDep) -> UserOut:
    if payload.role not in {ROLE_ADMIN, ROLE_USER}:
        raise HTTPException(status_code=400, detail="Ungültige Rolle.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Nutzer nicht gefunden.")
    if user.id == admin.id and payload.role != ROLE_ADMIN:
        raise HTTPException(status_code=400, detail="Sie können sich nicht selbst die Admin-Rolle entziehen.")
    user.role = payload.role
    db.commit()
    return user_out(user)

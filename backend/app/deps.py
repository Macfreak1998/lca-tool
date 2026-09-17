from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.constants import ROLE_ADMIN
from app.db import get_db
from app.models import User

DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DbDep) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Bitte anmelden.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Bitte anmelden.")
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Bitte zuerst die E-Mail-Adresse bestätigen.")
    return user


def get_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Nur für Administratorinnen.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(get_admin)]

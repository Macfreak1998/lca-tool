from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.constants import ROLE_USER
from app.deps import CurrentUser, DbDep
from app.models import Configuration, Dataset, DatasetProposal, User
from pydantic import BaseModel

from app.schemas import LoginIn, PasswordResetIn, PasswordResetRequestIn, RegisterIn, UserOut
from app.serialize import user_out
from app.services.auth import consume_token, create_token, hash_password, mark_verified, verify_password
from app.services.mail import send_mail
from app.constants import SOURCE_USER

router = APIRouter()


@router.post("/login", response_model=UserOut)
def login(payload: LoginIn, request: Request, db: DbDep) -> UserOut:
    if "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Bitte eine gültige E-Mail eingeben.")
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="E-Mail oder Passwort ist falsch.")
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Bitte zuerst die E-Mail-Adresse bestätigen.")
    request.session["user_id"] = user.id
    return user_out(user)


@router.post("/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return user_out(user)


@router.post("/register", response_model=UserOut)
def register(payload: RegisterIn, db: DbDep) -> UserOut:
    if not settings.public_signup:
        raise HTTPException(status_code=403, detail="Registrierung ist derzeit geschlossen.")
    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Bitte eine gültige E-Mail eingeben.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Diese E-Mail ist bereits registriert.")
    user = User(email=email, password_hash=hash_password(payload.password), role=ROLE_USER)
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(db, user, "verify")
    send_mail(
        email,
        "LCA-Tool: E-Mail bestätigen",
        f"Bitte bestätigen Sie Ihre Adresse:\n{settings.app_base_url}/confirm?token={token}\n",
    )
    return user_out(user)


class TokenIn(BaseModel):
    token: str


@router.post("/confirm")
def confirm(payload: TokenIn, db: DbDep) -> dict:
    user = consume_token(db, payload.token, "verify")
    if user is None:
        raise HTTPException(status_code=400, detail="Der Bestätigungslink ist ungültig.")
    mark_verified(db, user)
    return {"ok": True}


@router.post("/password-reset/request")
def password_reset_request(payload: PasswordResetRequestIn, db: DbDep) -> dict:
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if user:
        token = create_token(db, user, "reset")
        send_mail(
            user.email,
            "LCA-Tool: Passwort zurücksetzen",
            f"Neues Passwort setzen:\n{settings.app_base_url}/reset-password?token={token}\n",
        )
    return {"ok": True}


@router.post("/password-reset")
def password_reset(payload: PasswordResetIn, db: DbDep) -> dict:
    user = consume_token(db, payload.token, "reset")
    if user is None:
        raise HTTPException(status_code=400, detail="Der Link ist ungültig oder abgelaufen.")
    user.password_hash = hash_password(payload.password)
    db.commit()
    return {"ok": True}


@router.delete("/me")
def delete_me(user: CurrentUser, request: Request, db: DbDep) -> dict:
    db.query(DatasetProposal).filter(
        DatasetProposal.user_dataset_id.in_(
            db.query(Dataset.id).filter(Dataset.owner_user_id == user.id, Dataset.source_kind == SOURCE_USER)
        )
    ).delete(synchronize_session=False)
    db.query(Configuration).filter(Configuration.user_id == user.id).delete(synchronize_session=False)
    db.query(Dataset).filter(Dataset.owner_user_id == user.id, Dataset.source_kind == SOURCE_USER).delete(
        synchronize_session=False
    )
    db.delete(user)
    db.commit()
    request.session.clear()
    return {"ok": True}

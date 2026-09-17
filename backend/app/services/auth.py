from __future__ import annotations

import secrets
from datetime import datetime

import bcrypt
from sqlalchemy.orm import Session

from app.models import EmailToken, User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(db: Session, user: User, purpose: str) -> str:
    token = secrets.token_urlsafe(32)
    db.add(EmailToken(user_id=user.id, token=token, purpose=purpose))
    db.commit()
    return token


def consume_token(db: Session, token: str, purpose: str) -> User | None:
    row = (
        db.query(EmailToken)
        .filter(EmailToken.token == token, EmailToken.purpose == purpose)
        .first()
    )
    if row is None:
        return None
    user = db.get(User, row.user_id)
    db.delete(row)
    db.commit()
    return user


def mark_verified(db: Session, user: User) -> None:
    user.email_verified_at = datetime.utcnow()
    db.commit()

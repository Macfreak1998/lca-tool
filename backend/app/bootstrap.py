from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.constants import ROLE_ADMIN, SETTING_ARCHIVE_PATH
from app.models import Setting, User
from app.services.auth import hash_password
from app.services.demo import seed_demo


def bootstrap(db: Session) -> None:
    email = settings.admin_email.strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing is None:
        db.add(
            User(
                email=email,
                password_hash=hash_password(settings.admin_password),
                role=ROLE_ADMIN,
                email_verified_at=datetime.utcnow(),
            )
        )
    elif existing.role != ROLE_ADMIN:
        existing.role = ROLE_ADMIN
        if existing.email_verified_at is None:
            existing.email_verified_at = datetime.utcnow()
    if settings.archive_path and db.get(Setting, SETTING_ARCHIVE_PATH) is None:
        db.add(Setting(key=SETTING_ARCHIVE_PATH, value=settings.archive_path))
    db.commit()
    seed_demo(db)

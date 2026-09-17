from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, HTTPException

from app.deps import AdminUser, CurrentUser, DbDep
from app.models import Role
from app.schemas import RoleIn, RoleOut

router = APIRouter()


def slugify(label: str) -> str:
    normalized = unicodedata.normalize("NFKD", label)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "kategorie"


@router.get("", response_model=list[RoleOut])
def list_roles(_user: CurrentUser, db: DbDep) -> list[Role]:
    return db.query(Role).order_by(Role.label).all()


@router.post("", response_model=RoleOut)
def create_role(payload: RoleIn, _admin: AdminUser, db: DbDep) -> Role:
    slug = (payload.slug or slugify(payload.label)).strip()
    if db.query(Role).filter(Role.slug == slug).first():
        raise HTTPException(status_code=400, detail="Diese Kategorie gibt es schon.")
    role = Role(slug=slug, label=payload.label.strip())
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

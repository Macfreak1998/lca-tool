from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, HTTPException
from sqlalchemy import func

from app.deps import AdminUser, CurrentUser, DbDep
from app.models import ChainNode, DatasetRole, Role
from app.schemas import RoleIn, RoleOut, RoleUpdateIn
from app.serialize import role_out

router = APIRouter()


def slugify(label: str) -> str:
    normalized = unicodedata.normalize("NFKD", label)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "kategorie"


def _counts(db) -> dict[int, int]:
    rows = db.query(DatasetRole.role_id, func.count()).group_by(DatasetRole.role_id).all()
    return {role_id: count for role_id, count in rows}


@router.get("", response_model=list[RoleOut])
def list_roles(_user: CurrentUser, db: DbDep) -> list[RoleOut]:
    counts = _counts(db)
    return [role_out(row, counts.get(row.id, 0)) for row in db.query(Role).order_by(Role.label).all()]


@router.post("", response_model=RoleOut)
def create_role(payload: RoleIn, _admin: AdminUser, db: DbDep) -> RoleOut:
    slug = (payload.slug or slugify(payload.label)).strip()
    if db.query(Role).filter(Role.slug == slug).first():
        raise HTTPException(status_code=400, detail="Diese Kategorie gibt es schon.")
    role = Role(slug=slug, label=payload.label.strip())
    db.add(role)
    db.commit()
    db.refresh(role)
    return role_out(role, 0)


@router.patch("/{role_id}", response_model=RoleOut)
def update_role(role_id: int, payload: RoleUpdateIn, _admin: AdminUser, db: DbDep) -> RoleOut:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden.")
    role.label = payload.label.strip()
    db.commit()
    db.refresh(role)
    return role_out(role, _counts(db).get(role.id, 0))


@router.delete("/{role_id}")
def delete_role(role_id: int, _admin: AdminUser, db: DbDep) -> dict:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden.")
    if db.query(DatasetRole).filter(DatasetRole.role_id == role_id).first():
        raise HTTPException(status_code=409, detail="Kategorie ist Datensätzen zugeordnet.")
    if db.query(ChainNode).filter(ChainNode.role_id == role_id).first():
        raise HTTPException(status_code=409, detail="Kategorie wird in einer Kette verwendet.")
    db.delete(role)
    db.commit()
    return {"ok": True}

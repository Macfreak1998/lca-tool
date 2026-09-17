from __future__ import annotations

from fastapi import APIRouter

from app.deps import AdminUser, CurrentUser, DbDep
from app.models import EndProduct
from app.schemas import EndProductIn, EndProductOut

router = APIRouter()


@router.get("", response_model=list[EndProductOut])
def list_end_products(_user: CurrentUser, db: DbDep) -> list[EndProduct]:
    return db.query(EndProduct).order_by(EndProduct.name).all()


@router.post("", response_model=EndProductOut)
def create_end_product(payload: EndProductIn, _admin: AdminUser, db: DbDep) -> EndProduct:
    item = EndProduct(name=payload.name.strip(), unit=payload.unit.strip())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

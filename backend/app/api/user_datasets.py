from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import selectinload

from app.constants import CLIMATE_CHANGE, SOURCE_USER
from app.deps import CurrentUser, DbDep
from app.models import (
    Configuration,
    ConfigurationExtraSlot,
    ConfigurationReplacedStage,
    ConfigurationSelection,
    Dataset,
    DatasetProposal,
    DatasetRole,
    Role,
)
from app.schemas import DatasetOut, UserDatasetIn, UserDatasetUpdateIn
from app.serialize import dataset_out, replace_factors

router = APIRouter()


def _owned(db, user_id: int, dataset_id: int) -> Dataset:
    row = (
        db.query(Dataset)
        .options(selectinload(Dataset.roles), selectinload(Dataset.factors))
        .filter(
            Dataset.id == dataset_id,
            Dataset.owner_user_id == user_id,
            Dataset.source_kind == SOURCE_USER,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Eigener Datensatz nicht gefunden.")
    return row


def _invalidate_using(db, dataset_id: int, reason: str) -> None:
    ids: set[int] = set()
    for item in db.query(ConfigurationSelection.configuration_id).filter(
        ConfigurationSelection.dataset_id == dataset_id
    ):
        ids.add(item[0])
    for item in db.query(ConfigurationExtraSlot.configuration_id).filter(
        ConfigurationExtraSlot.dataset_id == dataset_id
    ):
        ids.add(item[0])
    for item in db.query(ConfigurationReplacedStage.configuration_id).filter(
        ConfigurationReplacedStage.dataset_id == dataset_id
    ):
        ids.add(item[0])
    if ids:
        db.query(Configuration).filter(Configuration.id.in_(ids)).update(
            {"invalid": True, "invalid_reason": reason},
            synchronize_session=False,
        )


@router.get("", response_model=list[DatasetOut])
def list_mine(user: CurrentUser, db: DbDep) -> list[DatasetOut]:
    rows = (
        db.query(Dataset)
        .options(selectinload(Dataset.roles), selectinload(Dataset.factors))
        .filter(Dataset.owner_user_id == user.id, Dataset.source_kind == SOURCE_USER)
        .order_by(Dataset.name)
        .all()
    )
    return [dataset_out(row, include_factors=True) for row in rows]


@router.post("", response_model=DatasetOut)
def create_mine(payload: UserDatasetIn, user: CurrentUser, db: DbDep) -> DatasetOut:
    if db.get(Role, payload.role_id) is None:
        raise HTTPException(status_code=400, detail="Kategorie nicht gefunden.")
    dataset = Dataset(
        name=payload.name.strip(),
        location="",
        unit=payload.unit.strip(),
        source_kind=SOURCE_USER,
        source_id=f"user:{user.id}",
        source_note=payload.source_note,
        inputs_doc=payload.inputs_doc,
        owner_user_id=user.id,
    )
    db.add(dataset)
    dataset.roles.append(DatasetRole(role_id=payload.role_id))
    values = dict(payload.factors)
    values[CLIMATE_CHANGE] = payload.climate_change
    replace_factors(dataset, values)
    db.commit()
    db.refresh(dataset)
    return dataset_out(dataset, include_factors=True)


@router.put("/{dataset_id}", response_model=DatasetOut)
def update_mine(
    dataset_id: int, payload: UserDatasetUpdateIn, user: CurrentUser, db: DbDep
) -> DatasetOut:
    dataset = _owned(db, user.id, dataset_id)
    if payload.name is not None:
        dataset.name = payload.name.strip()
    if payload.unit is not None:
        dataset.unit = payload.unit.strip()
    if payload.source_note is not None:
        dataset.source_note = payload.source_note
    if payload.inputs_doc is not None:
        dataset.inputs_doc = payload.inputs_doc
    if payload.role_id is not None:
        dataset.roles.clear()
        dataset.roles.append(DatasetRole(role_id=payload.role_id))
    values = {row.indicator_id: row.value for row in dataset.factors}
    if payload.factors is not None:
        values.update(payload.factors)
    if payload.climate_change is not None:
        values[CLIMATE_CHANGE] = payload.climate_change
    replace_factors(dataset, values)
    db.commit()
    return dataset_out(_owned(db, user.id, dataset_id), include_factors=True)


@router.delete("/{dataset_id}")
def delete_mine(dataset_id: int, user: CurrentUser, db: DbDep) -> dict:
    dataset = _owned(db, user.id, dataset_id)
    _invalidate_using(db, dataset.id, "Ein eigener Datensatz wurde gelöscht.")
    db.delete(dataset)
    db.commit()
    return {"ok": True}


@router.post("/{dataset_id}/propose")
def propose(dataset_id: int, user: CurrentUser, db: DbDep) -> dict:
    dataset = _owned(db, user.id, dataset_id)
    existing = (
        db.query(DatasetProposal)
        .filter(DatasetProposal.user_dataset_id == dataset.id, DatasetProposal.status == "open")
        .first()
    )
    if existing:
        return {"id": existing.id, "status": existing.status}
    proposal = DatasetProposal(user_dataset_id=dataset.id, status="open")
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return {"id": proposal.id, "status": proposal.status}

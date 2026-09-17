from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbDep
from app.models import (
    Chain,
    Configuration,
    ConfigurationExtraSlot,
    ConfigurationOptional,
    ConfigurationReplacedStage,
    ConfigurationSelection,
    ConfigurationShare,
)
from app.schemas import ConfigurationIn, ConfigurationOut
from app.serialize import configuration_out


router = APIRouter()


def _load(db, user_id: int, config_id: int) -> Configuration:
    row = (
        db.query(Configuration)
        .options(
            selectinload(Configuration.chain).selectinload(Chain.end_product),
            selectinload(Configuration.selections),
            selectinload(Configuration.shares),
            selectinload(Configuration.optional_on),
            selectinload(Configuration.extra_slots),
            selectinload(Configuration.replaced_stages),
        )
        .filter(Configuration.id == config_id, Configuration.user_id == user_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Konfiguration nicht gefunden.")
    return row


def _apply(db, row: Configuration, payload: ConfigurationIn) -> None:
    row.name = payload.name.strip() or "Konfiguration"
    row.chain_id = payload.chain_id
    row.end_amount = payload.end_amount
    row.invalid = False
    row.invalid_reason = ""
    row.selections.clear()
    row.shares.clear()
    row.optional_on.clear()
    row.extra_slots.clear()
    row.replaced_stages.clear()
    db.flush()
    for slot_id, dataset_id in payload.selections.items():
        row.selections.append(
            ConfigurationSelection(slot_id=int(slot_id), dataset_id=dataset_id)
        )
    for key, percent in payload.shares.items():
        row.shares.append(ConfigurationShare(slot_key=str(key), percent=percent))
    for slot_id in payload.optional_on:
        row.optional_on.append(ConfigurationOptional(slot_id=slot_id))
    for extra in payload.extra_slots:
        if extra.dataset_id is None:
            continue
        row.extra_slots.append(
            ConfigurationExtraSlot(
                stage_id=extra.stage_id,
                role_id=extra.role_id,
                dataset_id=extra.dataset_id,
                share=extra.share,
            )
        )
    for stage_id, dataset_id in payload.replaced_stages.items():
        row.replaced_stages.append(
            ConfigurationReplacedStage(stage_id=int(stage_id), dataset_id=dataset_id)
        )


@router.get("", response_model=list[ConfigurationOut])
def list_configurations(user: CurrentUser, db: DbDep) -> list[ConfigurationOut]:
    rows = (
        db.query(Configuration)
        .options(
            selectinload(Configuration.chain).selectinload(Chain.end_product),
            selectinload(Configuration.selections),
            selectinload(Configuration.shares),
            selectinload(Configuration.optional_on),
            selectinload(Configuration.extra_slots),
            selectinload(Configuration.replaced_stages),
        )
        .filter(Configuration.user_id == user.id)
        .order_by(Configuration.updated_at.desc())
        .all()
    )
    return [configuration_out(row) for row in rows]


@router.post("", response_model=ConfigurationOut)
def create_configuration(payload: ConfigurationIn, user: CurrentUser, db: DbDep) -> ConfigurationOut:
    if db.get(Chain, payload.chain_id) is None:
        raise HTTPException(status_code=400, detail="Kette nicht gefunden.")
    row = Configuration(user_id=user.id, chain_id=payload.chain_id, end_amount=payload.end_amount)
    db.add(row)
    db.flush()
    _apply(db, row, payload)
    db.commit()
    return configuration_out(_load(db, user.id, row.id))


@router.get("/{config_id}", response_model=ConfigurationOut)
def get_configuration(config_id: int, user: CurrentUser, db: DbDep) -> ConfigurationOut:
    return configuration_out(_load(db, user.id, config_id))


@router.put("/{config_id}", response_model=ConfigurationOut)
def update_configuration(
    config_id: int, payload: ConfigurationIn, user: CurrentUser, db: DbDep
) -> ConfigurationOut:
    row = _load(db, user.id, config_id)
    _apply(db, row, payload)
    db.commit()
    return configuration_out(_load(db, user.id, config_id))


@router.delete("/{config_id}")
def delete_configuration(config_id: int, user: CurrentUser, db: DbDep) -> dict:
    row = _load(db, user.id, config_id)
    db.delete(row)
    db.commit()
    return {"ok": True}

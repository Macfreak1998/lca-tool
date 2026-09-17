from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import selectinload

from app.constants import CHAIN_DRAFT, CHAIN_PUBLISHED
from app.deps import AdminUser, CurrentUser, DbDep
from app.models import Chain, EndProduct, Slot, Stage
from app.schemas import ChainCreateIn, ChainOut, ChainUpdateIn
from app.serialize import chain_out
from app.services.publish import invalidate_configurations, probe_and_publish, validate_structure

router = APIRouter()


def _load_chain(db, chain_id: int) -> Chain:
    chain = (
        db.query(Chain)
        .options(
            selectinload(Chain.end_product),
            selectinload(Chain.stages).selectinload(Stage.slots),
        )
        .filter(Chain.id == chain_id)
        .first()
    )
    if chain is None:
        raise HTTPException(status_code=404, detail="Kette nicht gefunden.")
    return chain


def _apply_stages(db, chain: Chain, stages_in) -> None:
    existing_stages = {stage.id: stage for stage in chain.stages}
    keep_stage_ids: set[int] = set()
    created: list[Stage] = []
    for index, stage_in in enumerate(sorted(stages_in, key=lambda item: item.sort_order)):
        stage = existing_stages.get(stage_in.id) if stage_in.id else None
        if stage is None:
            stage = Stage(chain=chain)
            db.add(stage)
        stage.name = stage_in.name.strip()
        stage.sort_order = index
        stage.upstream_amount = stage_in.upstream_amount
        existing_slots = {slot.id: slot for slot in stage.slots}
        keep_slot_ids: set[int] = set()
        for slot_in in stage_in.slots:
            slot = existing_slots.get(slot_in.id) if slot_in.id else None
            if slot is None:
                slot = Slot(stage=stage)
                db.add(slot)
            slot.role_id = slot_in.role_id
            slot.required = slot_in.required
            slot.optional_default_off = slot_in.optional_default_off
            slot.min_count = slot_in.min_count
            slot.specific_amount = slot_in.specific_amount
            slot.unit = slot_in.unit
            slot.default_dataset_id = slot_in.default_dataset_id
            slot.default_share = slot_in.default_share
            db.flush()
            keep_slot_ids.add(slot.id)
        for slot in list(stage.slots):
            if slot.id and slot.id not in keep_slot_ids:
                db.delete(slot)
        db.flush()
        created.append(stage)
        keep_stage_ids.add(stage.id)
    for stage in list(chain.stages):
        if stage.id and stage.id not in keep_stage_ids:
            db.delete(stage)
    db.flush()
    for index, stage in enumerate(created):
        stage.outgoing_stage_id = created[index + 1].id if index + 1 < len(created) else None


@router.get("", response_model=list[ChainOut])
def list_chains(user: CurrentUser, db: DbDep) -> list[ChainOut]:
    query = db.query(Chain).options(
        selectinload(Chain.end_product),
        selectinload(Chain.stages).selectinload(Stage.slots),
    )
    if user.role != "admin":
        query = query.filter(Chain.status == CHAIN_PUBLISHED)
    return [chain_out(item) for item in query.order_by(Chain.name).all()]


@router.post("", response_model=ChainOut)
def create_chain(payload: ChainCreateIn, _admin: AdminUser, db: DbDep) -> ChainOut:
    end_product = db.get(EndProduct, payload.end_product_id)
    if end_product is None:
        raise HTTPException(status_code=400, detail="Endprodukt nicht gefunden.")
    chain = Chain(
        name=payload.name.strip(),
        status=CHAIN_DRAFT,
        end_product_id=end_product.id,
        end_unit=end_product.unit,
    )
    db.add(chain)
    db.commit()
    return chain_out(_load_chain(db, chain.id))


@router.get("/{chain_id}", response_model=ChainOut)
def get_chain(chain_id: int, user: CurrentUser, db: DbDep) -> ChainOut:
    chain = _load_chain(db, chain_id)
    if user.role != "admin" and chain.status != CHAIN_PUBLISHED:
        raise HTTPException(status_code=404, detail="Kette nicht gefunden.")
    return chain_out(chain)


@router.patch("/{chain_id}", response_model=ChainOut)
def update_chain(chain_id: int, payload: ChainUpdateIn, _admin: AdminUser, db: DbDep) -> ChainOut:
    chain = _load_chain(db, chain_id)
    if payload.name is not None:
        chain.name = payload.name.strip()
    if payload.status == CHAIN_DRAFT and chain.status == CHAIN_PUBLISHED:
        chain.status = CHAIN_DRAFT
        invalidate_configurations(db, chain.id, "Die Kette wurde zurückgezogen.")
    if payload.stages is not None:
        _apply_stages(db, chain, payload.stages)
        if chain.status == CHAIN_PUBLISHED:
            chain.status = CHAIN_DRAFT
            invalidate_configurations(db, chain.id, "Die Kettenstruktur hat sich geändert.")
    db.commit()
    return chain_out(_load_chain(db, chain.id))


@router.post("/{chain_id}/publish", response_model=ChainOut)
def publish_chain(chain_id: int, _admin: AdminUser, db: DbDep) -> ChainOut:
    chain = _load_chain(db, chain_id)
    ok, errors = probe_and_publish(db, chain)
    if not ok:
        raise HTTPException(status_code=400, detail=errors)
    return chain_out(_load_chain(db, chain.id))


@router.post("/{chain_id}/unpublish", response_model=ChainOut)
def unpublish_chain(chain_id: int, _admin: AdminUser, db: DbDep) -> ChainOut:
    chain = _load_chain(db, chain_id)
    chain.status = CHAIN_DRAFT
    invalidate_configurations(db, chain.id, "Die Kette wurde zurückgezogen.")
    db.commit()
    return chain_out(_load_chain(db, chain.id))


@router.get("/{chain_id}/validate")
def validate_chain(chain_id: int, _admin: AdminUser, db: DbDep) -> dict:
    chain = _load_chain(db, chain_id)
    return {"errors": validate_structure(chain)}

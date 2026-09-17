from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session, selectinload

from app.models import Chain, Configuration, Dataset, Role
from app.services.calculate import CalcInput, calculate, ordered_stages


def invalidate_configurations(db: Session, chain_id: int, reason: str) -> None:
    rows = db.query(Configuration).filter(Configuration.chain_id == chain_id).all()
    for row in rows:
        row.invalid = True
        row.invalid_reason = reason
    db.commit()


def validate_structure(chain: Chain) -> list[str]:
    errors: list[str] = []
    stages = ordered_stages(chain)
    if not stages:
        errors.append("Mindestens eine Stufe ist nötig.")
        return errors
    seen_outgoing: set[int] = set()
    for stage in stages:
        if stage.outgoing_stage_id:
            if stage.outgoing_stage_id in seen_outgoing:
                errors.append("Eine Stufe darf nur eine eingehende Vorgängerstufe haben.")
            seen_outgoing.add(stage.outgoing_stage_id)
        grouped: dict[int, list] = defaultdict(list)
        for slot in stage.slots:
            grouped[slot.role_id].append(slot)
            if slot.specific_amount < 0:
                errors.append(f"Menge in Stufe „{stage.name}“ darf nicht negativ sein.")
        for slots in grouped.values():
            required = [slot for slot in slots if slot.required and not slot.optional_default_off]
            for slot in required:
                if slot.default_dataset_id is None:
                    errors.append(
                        f"Default-Datensatz fehlt für einen Pflicht-Slot in „{stage.name}“."
                    )
            if len(slots) > 1:
                share_sum = sum(slot.default_share for slot in slots)
                if abs(share_sum - 1.0) > 1e-6 and abs(share_sum - 100.0) > 1e-6:
                    errors.append(
                        f"Default-Anteile in „{stage.name}“ müssen 100 % ergeben."
                    )
    return errors


def probe_and_publish(db: Session, chain: Chain) -> tuple[bool, list[str]]:
    errors = validate_structure(chain)
    if errors:
        return False, errors
    datasets = {
        item.id: item
        for item in db.query(Dataset).options(
            selectinload(Dataset.factors),
            selectinload(Dataset.roles),
            selectinload(Dataset.exchanges),
        ).all()
    }
    roles = {item.id: item for item in db.query(Role).all()}
    selections: dict[str, int] = {}
    shares: dict[str, float] = {}
    optional_on: list[int] = []
    for stage in chain.stages:
        for slot in stage.slots:
            if slot.default_dataset_id:
                selections[str(slot.id)] = slot.default_dataset_id
            shares[str(slot.id)] = slot.default_share
    result = calculate(
        chain,
        CalcInput(end_amount=1.0, selections=selections, shares=shares, optional_on=optional_on),
        datasets,
        roles,
        require_published=False,
    )
    if result.blockers:
        return False, result.blockers
    chain.status = "published"
    db.commit()
    return True, []

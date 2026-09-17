from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import selectinload

from app.constants import SOURCE_CATALOG_MANUAL, SOURCE_ECOINVENT
from app.deps import AdminUser, CurrentUser, DbDep
from app.models import Dataset, DatasetExchange, DatasetFactor, DatasetProposal, DatasetRole, Role
from app.schemas import CatalogFromProposalIn, CatalogImportIn, DatasetOut
from app.serialize import dataset_out
from app.services.archive import dataset_file, get_archive_path
from app.services.characterize import parse_spold

router = APIRouter()


@router.get("/datasets", response_model=list[DatasetOut])
def list_datasets(
    user: CurrentUser,
    db: DbDep,
    role: int | None = None,
    source: str | None = None,
    include_factors: bool = False,
) -> list[DatasetOut]:
    query = db.query(Dataset).options(
        selectinload(Dataset.roles),
        selectinload(Dataset.factors),
        selectinload(Dataset.exchanges),
    )
    if source:
        query = query.filter(Dataset.source_kind == source)
    else:
        query = query.filter(Dataset.source_kind.in_([SOURCE_ECOINVENT, SOURCE_CATALOG_MANUAL]))
    if role:
        query = query.join(DatasetRole).filter(DatasetRole.role_id == role)
    rows = query.order_by(Dataset.name).all()
    show_factors = include_factors and user.role == "admin"
    return [dataset_out(row, include_factors=show_factors) for row in rows]


@router.post("/import", response_model=DatasetOut)
def import_dataset(payload: CatalogImportIn, _admin: AdminUser, db: DbDep) -> DatasetOut:
    if db.get(Role, payload.role_id) is None:
        raise HTTPException(status_code=400, detail="Kategorie nicht gefunden.")
    archive = get_archive_path(db)
    if archive is None or not archive.exists():
        raise HTTPException(status_code=400, detail="Archiv-Pfad ist nicht gesetzt.")
    path = dataset_file(archive, payload.filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Datei nicht gefunden: {payload.filename}")
    existing = (
        db.query(Dataset)
        .filter(Dataset.filename == path.name, Dataset.source_kind == SOURCE_ECOINVENT)
        .first()
    )
    try:
        meta, flows = parse_spold(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Datei konnte nicht gelesen werden: {exc}") from exc
    if existing:
        dataset = existing
        dataset.name = meta["name"]
        dataset.location = meta["location"]
        dataset.unit = meta["unit"]
        dataset.activity_name = meta["activity_name"]
        dataset.activity_uuid = meta["activity_uuid"]
        dataset.product_uuid = meta["product_uuid"]
        dataset.factors.clear()
        dataset.exchanges.clear()
        dataset.roles.clear()
    else:
        dataset = Dataset(
            name=meta["name"],
            location=meta["location"],
            unit=meta["unit"],
            source_kind=SOURCE_ECOINVENT,
            source_id="ecoinvent-3.10.1-cutoff-lci",
            activity_name=meta["activity_name"],
            activity_uuid=meta["activity_uuid"],
            product_uuid=meta["product_uuid"],
            filename=meta["filename"],
        )
        db.add(dataset)
    dataset.roles.append(DatasetRole(role_id=payload.role_id))
    for flow in flows:
        dataset.exchanges.append(
            DatasetExchange(
                flow_id=flow.flow_id,
                name=flow.name,
                compartment=flow.compartment,
                subcompartment=flow.subcompartment,
                unit=flow.unit,
                amount=flow.amount,
            )
        )
    db.commit()
    db.refresh(dataset)
    return dataset_out(dataset)


@router.post("/from-proposal", response_model=DatasetOut)
def catalog_from_proposal(payload: CatalogFromProposalIn, _admin: AdminUser, db: DbDep) -> DatasetOut:
    proposal = db.get(DatasetProposal, payload.proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Vorschlag nicht gefunden.")
    source = db.get(Dataset, proposal.user_dataset_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Der Nutzerdatensatz fehlt.")
    role_id = payload.role_id or (source.roles[0].role_id if source.roles else None)
    if role_id is None:
        raise HTTPException(status_code=400, detail="Bitte eine Kategorie zuweisen.")
    clone = Dataset(
        name=payload.name or source.name,
        location=source.location,
        unit=source.unit,
        source_kind=SOURCE_CATALOG_MANUAL,
        source_id=f"proposal:{proposal.id}",
        source_note=source.source_note,
        inputs_doc=source.inputs_doc,
    )
    db.add(clone)
    clone.roles.append(DatasetRole(role_id=role_id))
    for factor in source.factors:
        clone.factors.append(
            DatasetFactor(method_id=factor.method_id, indicator_id=factor.indicator_id, value=factor.value)
        )
    proposal.status = "accepted"
    db.commit()
    db.refresh(clone)
    return dataset_out(clone, include_factors=True)


@router.get("/proposals")
def list_proposals(_admin: AdminUser, db: DbDep, status: str = Query(default="open")) -> list[dict]:
    rows = (
        db.query(DatasetProposal)
        .options(selectinload(DatasetProposal.user_dataset).selectinload(Dataset.factors))
        .filter(DatasetProposal.status == status)
        .all()
    )
    return [
        {
            "id": row.id,
            "status": row.status,
            "note": row.note,
            "dataset": dataset_out(row.user_dataset, include_factors=True),
        }
        for row in rows
        if row.user_dataset
    ]

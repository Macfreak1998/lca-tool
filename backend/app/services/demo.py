from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.constants import CHAIN_DRAFT, SOURCE_ECOINVENT
from app.models import Chain, Dataset, DatasetExchange, DatasetRole, EndProduct, Role, Slot, Stage
from app.services.archive import dataset_file
from app.services.characterize import parse_spold
from app.services.publish import probe_and_publish


def seed_demo(db: Session) -> None:
    if not settings.demo_seed:
        return
    if db.query(Chain).first() is not None:
        return

    starch = Role(slug="staerke", label="Stärke")
    db.add(starch)
    db.flush()

    product = EndProduct(name="Folie", unit="kg")
    db.add(product)
    db.flush()

    archive = Path(settings.archive_path) if settings.archive_path else None
    if archive is None or not archive.exists():
        db.commit()
        return

    path = dataset_file(archive, "aaa-111_bbb-222.spold")
    if not path.exists():
        db.commit()
        return

    meta, flows = parse_spold(path)
    dataset = Dataset(
        name=meta["name"],
        location=meta["location"],
        unit=meta["unit"],
        source_kind=SOURCE_ECOINVENT,
        source_id="demo",
        activity_name=meta["activity_name"],
        activity_uuid=meta["activity_uuid"],
        product_uuid=meta["product_uuid"],
        filename=meta["filename"],
    )
    dataset.roles.append(DatasetRole(role_id=starch.id))
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
    db.add(dataset)
    db.flush()

    chain = Chain(
        name="Demo: Maisstärke → Folie",
        status=CHAIN_DRAFT,
        end_product_id=product.id,
        end_unit=product.unit,
    )
    db.add(chain)
    db.flush()
    stage = Stage(chain=chain, name="Folie", sort_order=0, upstream_amount=1.0)
    db.add(stage)
    db.flush()
    db.add(
        Slot(
            stage=stage,
            role_id=starch.id,
            required=True,
            specific_amount=1.0,
            unit="kg",
            default_dataset_id=dataset.id,
            default_share=1.0,
        )
    )
    db.flush()
    probe_and_publish(db, chain)
    db.commit()

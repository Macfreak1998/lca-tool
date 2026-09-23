from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.constants import CHAIN_DRAFT, SOURCE_ECOINVENT
from app.models import (
    Chain,
    ChainEdge,
    ChainNode,
    ChainCombination,
    ChainCombinationAmount,
    ChainCombinationAxis,
    ChainDatasetShare,
    Dataset,
    DatasetExchange,
    DatasetRole,
    EndProduct,
    Role,
)
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
    folie = ChainNode(
        chain=chain,
        type="product",
        name="Folie",
        unit="kg",
        is_functional=True,
        position_x=480,
        position_y=180,
    )
    category = ChainNode(
        chain=chain,
        type="category",
        name="Stärke",
        role_id=starch.id,
        unit="kg",
        datasets_differ=True,
        position_x=40,
        position_y=180,
    )
    process = ChainNode(
        chain=chain,
        type="process",
        name="Herstellung",
        unit="kg",
        position_x=260,
        position_y=180,
    )
    db.add_all([folie, category, process])
    db.flush()
    db.add_all(
        [
            ChainEdge(
                chain=chain,
                source_id=category.id,
                target_id=process.id,
                kind="material",
                input_amount=1.0,
                efficiency=1.0,
            ),
            ChainEdge(
                chain=chain,
                source_id=process.id,
                target_id=folie.id,
                kind="material",
                input_amount=1.0,
                efficiency=1.0,
            ),
        ]
    )
    combo = ChainCombination(chain=chain, process_node_id=process.id)
    db.add(combo)
    db.flush()
    db.add(ChainCombinationAxis(combination=combo, category_node_id=category.id, dataset_id=dataset.id))
    db.add(
        ChainCombinationAmount(
            combination=combo,
            category_node_id=category.id,
            input_amount=1.0,
        )
    )
    db.add(
        ChainDatasetShare(
            chain=chain,
            category_node_id=category.id,
            dataset_id=dataset.id,
            default_share=1.0,
        )
    )
    db.flush()
    probe_and_publish(db, chain)
    db.commit()

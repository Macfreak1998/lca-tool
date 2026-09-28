from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.constants import CHAIN_DRAFT, METHOD_ID, SOURCE_CATALOG_MANUAL, SOURCE_ECOINVENT
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
    DatasetFactor,
    DatasetRole,
    EndProduct,
    Role,
)
from app.services.archive import dataset_file
from app.services.characterize import parse_spold
from app.services.publish import probe_and_publish


EXAMPLE_CHAIN_NAME = "Beispiel: Stärkecompound → Spritzgussteil"
_EXAMPLE_NOTE = (
    "Illustrative Prüfwerte für alle 16 PEF-Kategorien der Beispielkette. "
    "Keine ecoinvent- oder EF-3.1-Charakterisierung."
)
_EXAMPLE_PROFILES: dict[str, tuple[str, dict[str, float]]] = {
    "Kartoffelstärke": (
        "kg",
        {
            "climate_change": 0.80,
            "ozone_depletion": 2.0e-8,
            "human_toxicity_cancer": 1.0e-9,
            "human_toxicity_non_cancer": 2.0e-8,
            "particulate_matter": 1.5e-7,
            "ionising_radiation": 0.02,
            "photochemical_ozone": 0.0015,
            "acidification": 0.006,
            "eutrophication_terrestrial": 0.025,
            "eutrophication_freshwater": 0.0004,
            "eutrophication_marine": 0.003,
            "ecotoxicity_freshwater": 12.0,
            "land_use": 8.0,
            "water_use": 3.0,
            "resource_use_minerals": 1.0e-5,
            "resource_use_fossils": 6.0,
        },
    ),
    "Additiv": (
        "kg",
        {
            "climate_change": 2.50,
            "ozone_depletion": 1.0e-7,
            "human_toxicity_cancer": 4.0e-8,
            "human_toxicity_non_cancer": 1.2e-7,
            "particulate_matter": 3.0e-7,
            "ionising_radiation": 0.08,
            "photochemical_ozone": 0.006,
            "acidification": 0.012,
            "eutrophication_terrestrial": 0.018,
            "eutrophication_freshwater": 0.0003,
            "eutrophication_marine": 0.002,
            "ecotoxicity_freshwater": 50.0,
            "land_use": 0.8,
            "water_use": 1.2,
            "resource_use_minerals": 8.0e-5,
            "resource_use_fossils": 45.0,
        },
    ),
    "Strom": (
        "kWh",
        {
            "climate_change": 0.40,
            "ozone_depletion": 3.0e-8,
            "human_toxicity_cancer": 2.0e-9,
            "human_toxicity_non_cancer": 4.0e-8,
            "particulate_matter": 2.0e-8,
            "ionising_radiation": 0.25,
            "photochemical_ozone": 0.0004,
            "acidification": 0.0008,
            "eutrophication_terrestrial": 0.0015,
            "eutrophication_freshwater": 4.0e-5,
            "eutrophication_marine": 0.00015,
            "ecotoxicity_freshwater": 4.0,
            "land_use": 0.03,
            "water_use": 0.08,
            "resource_use_minerals": 4.0e-6,
            "resource_use_fossils": 7.0,
        },
    ),
    "Lkw": (
        "kg·km",
        {
            "climate_change": 0.0001,
            "ozone_depletion": 2.0e-11,
            "human_toxicity_cancer": 1.0e-13,
            "human_toxicity_non_cancer": 2.0e-12,
            "particulate_matter": 8.0e-12,
            "ionising_radiation": 2.0e-5,
            "photochemical_ozone": 4.0e-7,
            "acidification": 2.0e-7,
            "eutrophication_terrestrial": 8.0e-7,
            "eutrophication_freshwater": 2.0e-8,
            "eutrophication_marine": 8.0e-8,
            "ecotoxicity_freshwater": 0.002,
            "land_use": 1.0e-5,
            "water_use": 2.0e-5,
            "resource_use_minerals": 2.0e-9,
            "resource_use_fossils": 0.0014,
        },
    ),
    "Verwertung": (
        "kg",
        {
            "climate_change": 1.20,
            "ozone_depletion": 4.0e-8,
            "human_toxicity_cancer": 8.0e-9,
            "human_toxicity_non_cancer": 6.0e-8,
            "particulate_matter": 1.2e-7,
            "ionising_radiation": 0.03,
            "photochemical_ozone": 0.001,
            "acidification": 0.003,
            "eutrophication_terrestrial": 0.005,
            "eutrophication_freshwater": 0.0001,
            "eutrophication_marine": 0.0005,
            "ecotoxicity_freshwater": 15.0,
            "land_use": 0.05,
            "water_use": 0.2,
            "resource_use_minerals": 1.5e-5,
            "resource_use_fossils": 0.8,
        },
    ),
}


def seed_demo(db: Session) -> None:
    if not settings.demo_seed:
        return
    _seed_maize_demo(db)
    seed_example_chain(db)


def _seed_maize_demo(db: Session) -> None:
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


def seed_example_chain(db: Session) -> None:
    if db.query(Chain).filter(Chain.name == EXAMPLE_CHAIN_NAME).first() is not None:
        return
    starch = _role(db, "starke", "Stärke")
    additive = _role(db, "additiv", "Additiv")
    power = _role(db, "strommix", "Strommix")
    product = db.query(EndProduct).filter(EndProduct.name == "Kunststoffteil").first()
    if product is None:
        product = EndProduct(name="Kunststoffteil", unit="kg")
        db.add(product)
        db.flush()
    starch_ds = _example_dataset(db, "Kartoffelstärke")
    additive_ds = _example_dataset(db, "Additiv")
    power_ds = _example_dataset(db, "Strom")
    truck_ds = _example_dataset(db, "Lkw")
    recovery_ds = _example_dataset(db, "Verwertung")
    for dataset, role in (
        (starch_ds, starch),
        (additive_ds, additive),
        (power_ds, power),
    ):
        if not any(link.role_id == role.id for link in dataset.roles):
            dataset.roles.append(DatasetRole(role_id=role.id))
    chain = Chain(
        name=EXAMPLE_CHAIN_NAME,
        status=CHAIN_DRAFT,
        end_product_id=product.id,
        end_unit="kg",
    )
    db.add(chain)
    db.flush()
    part = _node(chain, "product", "Kunststoffteil", x=920, y=180, unit="kg", is_functional=True)
    granulate = _node(chain, "product", "Granulat", x=460, y=180, unit="kg")
    compound = _node(chain, "process", "Granulieren", x=250, y=180, unit="kg")
    mould = _node(chain, "process", "Spritzguss", x=700, y=180, unit="kg")
    starch_node = _node(chain, "category", "Kartoffelstärke", x=20, y=40, unit="kg", role_id=starch.id)
    additive_node = _node(chain, "category", "Additiv", x=20, y=180, unit="kg", role_id=additive.id)
    power_compound = _node(chain, "category", "Strom Granulieren", x=20, y=320, unit="kWh", role_id=power.id)
    power_mould = _node(chain, "category", "Strom Spritzguss", x=520, y=40, unit="kWh", role_id=power.id)
    haul_starch = _node(
        chain, "transport", "Transport Stärke", x=140, y=40, unit="kg·km", dataset_id=truck_ds.id, distance_km=100
    )
    haul_granulate = _node(
        chain, "transport", "Transport Granulat", x=580, y=180, unit="kg·km", dataset_id=truck_ds.id, distance_km=100
    )
    recover_compound = _node(
        chain, "recovery", "Verwertung Granulieren", x=250, y=360, unit="kg", dataset_id=recovery_ds.id
    )
    recover_mould = _node(
        chain, "recovery", "Verwertung Spritzguss", x=700, y=360, unit="kg", dataset_id=recovery_ds.id
    )
    db.add_all(
        [
            part,
            granulate,
            compound,
            mould,
            starch_node,
            additive_node,
            power_compound,
            power_mould,
            haul_starch,
            haul_granulate,
            recover_compound,
            recover_mould,
        ]
    )
    db.flush()
    db.add_all(
        [
            ChainEdge(chain=chain, source_id=starch_node.id, target_id=haul_starch.id, kind="material"),
            ChainEdge(chain=chain, source_id=haul_starch.id, target_id=compound.id, kind="material"),
            ChainEdge(chain=chain, source_id=additive_node.id, target_id=compound.id, kind="material"),
            ChainEdge(chain=chain, source_id=power_compound.id, target_id=compound.id, kind="energy"),
            ChainEdge(chain=chain, source_id=compound.id, target_id=granulate.id, kind="material"),
            ChainEdge(chain=chain, source_id=compound.id, target_id=recover_compound.id, kind="waste"),
            ChainEdge(chain=chain, source_id=granulate.id, target_id=haul_granulate.id, kind="material"),
            ChainEdge(
                chain=chain,
                source_id=haul_granulate.id,
                target_id=mould.id,
                kind="material",
                input_amount=1.0,
                efficiency=0.95,
            ),
            ChainEdge(chain=chain, source_id=power_mould.id, target_id=mould.id, kind="energy"),
            ChainEdge(chain=chain, source_id=mould.id, target_id=part.id, kind="material"),
            ChainEdge(chain=chain, source_id=mould.id, target_id=recover_mould.id, kind="waste"),
        ]
    )
    compound_combo = ChainCombination(chain=chain, process_node_id=compound.id)
    mould_combo = ChainCombination(chain=chain, process_node_id=mould.id)
    db.add_all([compound_combo, mould_combo])
    db.flush()
    db.add_all(
        [
            ChainCombinationAmount(
                combination=compound_combo,
                category_node_id=starch_node.id,
                input_amount=0.95,
                efficiency=0.90,
                recovery_node_id=recover_compound.id,
            ),
            ChainCombinationAmount(
                combination=compound_combo,
                category_node_id=additive_node.id,
                input_amount=0.05,
                efficiency=0.85,
                recovery_node_id=recover_compound.id,
            ),
            ChainCombinationAmount(
                combination=compound_combo,
                category_node_id=power_compound.id,
                input_amount=0.80,
                efficiency=1.0,
            ),
            ChainCombinationAmount(
                combination=mould_combo,
                category_node_id=power_mould.id,
                input_amount=1.50,
                efficiency=1.0,
            ),
        ]
    )
    for category, dataset in (
        (starch_node, starch_ds),
        (additive_node, additive_ds),
        (power_compound, power_ds),
        (power_mould, power_ds),
    ):
        db.add(
            ChainDatasetShare(
                chain=chain,
                category_node_id=category.id,
                dataset_id=dataset.id,
                default_share=1.0,
            )
        )
    db.flush()
    ok, errors = probe_and_publish(db, chain)
    if not ok:
        raise RuntimeError("Beispielkette lässt sich nicht veröffentlichen: " + "; ".join(errors))
    db.commit()


def _role(db: Session, slug: str, label: str) -> Role:
    role = db.query(Role).filter(Role.slug == slug).one_or_none()
    if role is None:
        role = Role(slug=slug, label=label)
        db.add(role)
        db.flush()
    return role


def _example_dataset(db: Session, name: str) -> Dataset:
    dataset = (
        db.query(Dataset)
        .filter(Dataset.name == name, Dataset.location == "Prüfwert", Dataset.source_kind == SOURCE_CATALOG_MANUAL)
        .one_or_none()
    )
    unit, factors = _EXAMPLE_PROFILES[name]
    if dataset is None:
        dataset = Dataset(
            name=name,
            location="Prüfwert",
            unit=unit,
            source_kind=SOURCE_CATALOG_MANUAL,
            source_note=_EXAMPLE_NOTE,
        )
        db.add(dataset)
        db.flush()
    else:
        dataset.source_note = _EXAMPLE_NOTE
    present = {row.indicator_id for row in dataset.factors}
    for indicator_id, value in factors.items():
        if indicator_id not in present:
            dataset.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=indicator_id, value=value))
    return dataset


def _node(chain: Chain, node_type: str, name: str, *, x: float, y: float, unit: str, **extra) -> ChainNode:
    return ChainNode(chain=chain, type=node_type, name=name, position_x=x, position_y=y, unit=unit, **extra)

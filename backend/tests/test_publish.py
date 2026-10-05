from __future__ import annotations

from app.constants import CLIMATE_CHANGE, METHOD_ID, SOURCE_ECOINVENT
from app.models import (
    Chain,
    ChainCombination,
    ChainCombinationAmount,
    ChainCombinationAxis,
    ChainDatasetShare,
    ChainEdge,
    ChainNode,
    Dataset,
    DatasetExchange,
    DatasetFactor,
    DatasetRole,
    EndProduct,
    Role,
)
from app.services.publish import probe_and_publish, validate_structure


def _base(db):
    end = EndProduct(name="Folie", unit="kg")
    role = Role(slug="energie", label="Energie")
    db.add_all([end, role])
    db.flush()
    chain = Chain(name="Test", status="draft", end_product_id=end.id, end_unit="kg")
    db.add(chain)
    db.flush()
    folie = ChainNode(chain=chain, type="product", name="Folie", unit="kg", is_functional=True)
    process = ChainNode(chain=chain, type="process", name="Herstellung", unit="kg")
    db.add_all([folie, process])
    db.flush()
    db.add(ChainEdge(chain=chain, source_id=process.id, target_id=folie.id, kind="material"))
    db.flush()
    return chain, role, folie, process


def _energy(db, chain, role, process, ds, *, amount=1.0):
    energy = ChainNode(chain=chain, type="category", name="Energie", role_id=role.id, unit="kWh")
    db.add(energy)
    db.flush()
    db.add(ChainEdge(chain=chain, source_id=energy.id, target_id=process.id, kind="energy"))
    combo = ChainCombination(chain=chain, process_node_id=process.id)
    db.add(combo)
    db.flush()
    db.add(ChainCombinationAmount(combination=combo, category_node_id=energy.id, input_amount=amount))
    ds.roles.append(DatasetRole(role_id=role.id))
    db.add(
        ChainDatasetShare(
            chain=chain, category_node_id=energy.id, dataset_id=ds.id, default_share=1.0
        )
    )
    db.flush()
    return energy


def test_publish_requires_defaults_and_probe(db):
    chain, role, _folie, process = _base(db)
    ds = Dataset(name="Strom", location="DE", unit="kWh", source_kind=SOURCE_ECOINVENT)
    ds.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=0.4))
    db.add(ds)
    db.flush()
    errors = validate_structure(chain)
    assert errors == []
    energy = ChainNode(
        chain=chain, type="category", name="Energie", role_id=role.id, unit="kWh", datasets_differ=True
    )
    db.add(energy)
    db.flush()
    db.add(ChainEdge(chain=chain, source_id=energy.id, target_id=process.id, kind="energy"))
    db.flush()
    errors = validate_structure(chain)
    assert any("Datensätze fehlen" in msg for msg in errors)
    combo = ChainCombination(chain=chain, process_node_id=process.id)
    db.add(combo)
    db.flush()
    db.add(ChainCombinationAxis(combination=combo, category_node_id=energy.id, dataset_id=ds.id))
    db.add(ChainCombinationAmount(combination=combo, category_node_id=energy.id, input_amount=1.0))
    db.add(ChainDatasetShare(chain=chain, category_node_id=energy.id, dataset_id=ds.id, default_share=1.0))
    db.flush()
    ok, errs = probe_and_publish(db, chain)
    assert ok, errs
    assert chain.status == "published"


def test_publish_blocks_on_unit_mismatch(db):
    chain, role, _folie, process = _base(db)
    ds = Dataset(name="Strom DE", location="DE", unit="kWh", source_kind=SOURCE_ECOINVENT)
    ds.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=0.4))
    db.add(ds)
    db.flush()
    _energy(db, chain, role, process, ds)
    energy = next(node for node in chain.nodes if node.name == "Energie")
    energy.unit = "kg"
    db.flush()
    errors = validate_structure(chain)
    assert "Einheit von „Strom DE“ (kWh) passt nicht zu „Energie“ (kg)." in errors
    ok, errs = probe_and_publish(db, chain)
    assert not ok
    assert chain.status == "draft"


def test_publish_accepts_unit_synonym(db):
    chain, role, _folie, process = _base(db)
    ds = Dataset(name="Strom", location="DE", unit="kWh", source_kind=SOURCE_ECOINVENT)
    ds.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=0.4))
    db.add(ds)
    db.flush()
    energy = _energy(db, chain, role, process, ds)
    energy.unit = "kilowatt hour"
    db.flush()
    ok, errs = probe_and_publish(db, chain)
    assert ok, errs


def test_publish_blocks_on_bad_shares(db):
    end = EndProduct(name="Folie", unit="kg")
    role = Role(slug="staerke", label="Stärke")
    db.add_all([end, role])
    db.flush()
    first = Dataset(name="A", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    second = Dataset(name="B", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    first.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=1.0))
    second.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=1.0))
    db.add_all([first, second])
    db.flush()
    chain = Chain(name="Test", status="draft", end_product_id=end.id, end_unit="kg")
    db.add(chain)
    db.flush()
    folie = ChainNode(chain=chain, type="product", name="Mix", unit="kg", is_functional=True)
    process = ChainNode(chain=chain, type="process", name="Mischen", unit="kg")
    category = ChainNode(
        chain=chain, type="category", name="Stärke", role_id=role.id, unit="kg", datasets_differ=True
    )
    db.add_all([folie, process, category])
    db.flush()
    db.add_all(
        [
            ChainEdge(chain=chain, source_id=category.id, target_id=process.id, kind="material"),
            ChainEdge(chain=chain, source_id=process.id, target_id=folie.id, kind="material"),
        ]
    )
    for dataset, share in ((first, 0.5), (second, 0.2)):
        combo = ChainCombination(chain=chain, process_node_id=process.id)
        db.add(combo)
        db.flush()
        db.add(ChainCombinationAxis(combination=combo, category_node_id=category.id, dataset_id=dataset.id))
        db.add(ChainCombinationAmount(combination=combo, category_node_id=category.id, input_amount=1.0))
        db.add(
            ChainDatasetShare(
                chain=chain, category_node_id=category.id, dataset_id=dataset.id, default_share=share
            )
        )
    db.flush()
    errors = validate_structure(chain)
    assert not any("100" in msg or "Anteile" in msg for msg in errors)


def test_publish_blocks_transport_on_energy(db):
    chain, role, _folie, process = _base(db)
    transport = ChainNode(chain=chain, type="transport", name="Stromweg", optional=True, unit="kg·km")
    energy = ChainNode(chain=chain, type="category", name="Energie", role_id=role.id, unit="kWh")
    db.add_all([transport, energy])
    db.flush()
    db.add_all(
        [
            ChainEdge(chain=chain, source_id=energy.id, target_id=transport.id, kind="energy"),
            ChainEdge(chain=chain, source_id=transport.id, target_id=process.id, kind="energy"),
        ]
    )
    db.flush()
    errors = validate_structure(chain)
    assert any("Transport" in msg for msg in errors)


def test_publish_accepts_transport_between_product_and_process(db):
    chain, role, folie, process = _base(db)
    ds = Dataset(name="Strom", location="DE", unit="kWh", source_kind=SOURCE_ECOINVENT)
    ds.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=0.4))
    db.add(ds)
    db.flush()
    _energy(db, chain, role, process, ds)
    granulat = ChainNode(chain=chain, type="product", name="Granulat", unit="kg")
    transport = ChainNode(
        chain=chain, type="transport", name="Lkw", dataset_id=ds.id, unit="kg·km", distance_km=10
    )
    db.add_all([granulat, transport])
    db.flush()
    db.add_all(
        [
            ChainEdge(chain=chain, source_id=granulat.id, target_id=transport.id, kind="material"),
            ChainEdge(chain=chain, source_id=transport.id, target_id=process.id, kind="material"),
        ]
    )
    db.flush()
    errors = validate_structure(chain)
    assert not any("Transport" in msg for msg in errors)
    assert folie.id


def test_publish_blocks_recovery_without_inventory(db):
    chain, _role, _folie, process = _base(db)
    starch = Role(slug="staerke", label="Stärke")
    db.add(starch)
    db.flush()
    starch_ds = Dataset(name="Stärke", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    starch_ds.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=1.0))
    empty = Dataset(name="Leer", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    db.add_all([starch_ds, empty])
    db.flush()
    category = ChainNode(chain=chain, type="category", name="Stärke", role_id=starch.id, unit="kg")
    recovery = ChainNode(chain=chain, type="recovery", name="Verwertung", dataset_id=empty.id, unit="kg")
    db.add_all([category, recovery])
    db.flush()
    db.add(ChainEdge(chain=chain, source_id=category.id, target_id=process.id, kind="material"))
    combo = ChainCombination(chain=chain, process_node_id=process.id)
    db.add(combo)
    db.flush()
    db.add(
        ChainCombinationAmount(
            combination=combo,
            category_node_id=category.id,
            input_amount=1.0,
            efficiency=0.8,
            recovery_node_id=recovery.id,
        )
    )
    db.add(
        ChainDatasetShare(
            chain=chain, category_node_id=category.id, dataset_id=starch_ds.id, default_share=1.0
        )
    )
    db.flush()
    errors = validate_structure(chain)
    assert any("kein Inventar" in msg for msg in errors)


def test_publish_blocks_two_recoveries(db):
    chain, _role, _folie, process = _base(db)
    starch = Role(slug="staerke-zwei", label="Stärke")
    db.add(starch)
    db.flush()
    starch_ds = Dataset(name="Stärke", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    starch_ds.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=1.0))
    first_ds = Dataset(name="Verbrennung A", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    second_ds = Dataset(name="Verbrennung B", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    first_ds.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=1.0))
    second_ds.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=1.0))
    db.add_all([starch_ds, first_ds, second_ds])
    db.flush()
    category = ChainNode(chain=chain, type="category", name="Stärke", role_id=starch.id, unit="kg")
    other = ChainNode(chain=chain, type="category", name="Additiv", role_id=starch.id, unit="kg")
    first = ChainNode(chain=chain, type="recovery", name="Verwertung A", dataset_id=first_ds.id, unit="kg")
    second = ChainNode(chain=chain, type="recovery", name="Verwertung B", dataset_id=second_ds.id, unit="kg")
    db.add_all([category, other, first, second])
    db.flush()
    db.add_all(
        [
            ChainEdge(chain=chain, source_id=category.id, target_id=process.id, kind="material"),
            ChainEdge(chain=chain, source_id=other.id, target_id=process.id, kind="material"),
        ]
    )
    combo = ChainCombination(chain=chain, process_node_id=process.id)
    db.add(combo)
    db.flush()
    db.add_all(
        [
            ChainCombinationAmount(
                combination=combo, category_node_id=category.id, input_amount=0.6, efficiency=0.9, recovery_node_id=first.id
            ),
            ChainCombinationAmount(
                combination=combo, category_node_id=other.id, input_amount=0.4, efficiency=0.8, recovery_node_id=second.id
            ),
        ]
    )
    db.add_all(
        [
            ChainDatasetShare(chain=chain, category_node_id=category.id, dataset_id=starch_ds.id, default_share=1.0),
            ChainDatasetShare(chain=chain, category_node_id=other.id, dataset_id=starch_ds.id, default_share=1.0),
        ]
    )
    db.flush()
    errors = validate_structure(chain)
    assert any("nur eine Verwertung" in message for message in errors)


def _kg_dataset(db, name: str) -> Dataset:
    dataset = Dataset(name=name, location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    dataset.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=1.0))
    db.add(dataset)
    db.flush()
    return dataset


def _recipe(db, chain, process, parts: list[tuple[ChainNode, float]]) -> ChainCombination:
    combo = ChainCombination(chain=chain, process_node_id=process.id)
    db.add(combo)
    db.flush()
    for category, amount in parts:
        db.add(
            ChainCombinationAmount(
                combination=combo, category_node_id=category.id, input_amount=amount, efficiency=1.0
            )
        )
    db.flush()
    return combo


def test_publish_accepts_closed_mass(db):
    chain, _role, _folie, process = _base(db)
    starch_role = Role(slug="staerke", label="Stärke")
    additive_role = Role(slug="additiv", label="Additiv")
    db.add_all([starch_role, additive_role])
    db.flush()
    starch_ds = _kg_dataset(db, "Kartoffelstärke")
    additive_ds = _kg_dataset(db, "Additiv")
    starch_ds.roles.append(DatasetRole(role_id=starch_role.id))
    additive_ds.roles.append(DatasetRole(role_id=additive_role.id))
    starch = ChainNode(chain=chain, type="category", name="Stärke", role_id=starch_role.id, unit="kg")
    additive = ChainNode(chain=chain, type="category", name="Additiv", role_id=additive_role.id, unit="kg")
    db.add_all([starch, additive])
    db.flush()
    db.add_all(
        [
            ChainEdge(chain=chain, source_id=starch.id, target_id=process.id, kind="material"),
            ChainEdge(chain=chain, source_id=additive.id, target_id=process.id, kind="material"),
        ]
    )
    _recipe(db, chain, process, [(starch, 0.95), (additive, 0.05)])
    db.add_all(
        [
            ChainDatasetShare(chain=chain, category_node_id=starch.id, dataset_id=starch_ds.id, default_share=1.0),
            ChainDatasetShare(chain=chain, category_node_id=additive.id, dataset_id=additive_ds.id, default_share=1.0),
        ]
    )
    db.flush()
    ok, errs = probe_and_publish(db, chain)
    assert ok, errs
    assert chain.status == "published"


def test_publish_blocks_open_mass(db):
    chain, _role, _folie, process = _base(db)
    starch_role = Role(slug="staerke", label="Stärke")
    additive_role = Role(slug="additiv", label="Additiv")
    db.add_all([starch_role, additive_role])
    db.flush()
    starch_ds = _kg_dataset(db, "Kartoffelstärke")
    additive_ds = _kg_dataset(db, "Additiv")
    starch = ChainNode(chain=chain, type="category", name="Stärke", role_id=starch_role.id, unit="kg")
    additive = ChainNode(chain=chain, type="category", name="Additiv", role_id=additive_role.id, unit="kg")
    db.add_all([starch, additive])
    db.flush()
    db.add_all(
        [
            ChainEdge(chain=chain, source_id=starch.id, target_id=process.id, kind="material"),
            ChainEdge(chain=chain, source_id=additive.id, target_id=process.id, kind="material"),
        ]
    )
    _recipe(db, chain, process, [(starch, 0.0), (additive, 0.05)])
    db.add_all(
        [
            ChainDatasetShare(chain=chain, category_node_id=starch.id, dataset_id=starch_ds.id, default_share=1.0),
            ChainDatasetShare(chain=chain, category_node_id=additive.id, dataset_id=additive_ds.id, default_share=1.0),
        ]
    )
    db.flush()
    errors = validate_structure(chain)
    assert "Masse an „Herstellung“ ist 0,05 kg je 1 kg, erwartet 1 kg." in errors
    ok, errs = probe_and_publish(db, chain)
    assert not ok
    assert chain.status == "draft"


def test_publish_skips_mass_check_for_energy_only(db):
    chain, role, _folie, process = _base(db)
    ds = Dataset(name="Strom", location="DE", unit="kWh", source_kind=SOURCE_ECOINVENT)
    ds.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=0.4))
    db.add(ds)
    db.flush()
    _energy(db, chain, role, process, ds)
    errors = validate_structure(chain)
    assert errors == []
    assert not any(msg.startswith("Masse") for msg in errors)


def test_publish_accepts_product_edge_mass(db):
    chain, role, _folie, process = _base(db)
    ds = Dataset(name="Strom", location="DE", unit="kWh", source_kind=SOURCE_ECOINVENT)
    ds.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=0.4))
    db.add(ds)
    db.flush()
    _energy(db, chain, role, process, ds)
    granulat = ChainNode(chain=chain, type="product", name="Granulat", unit="kg")
    db.add(granulat)
    db.flush()
    link = ChainEdge(
        chain=chain, source_id=granulat.id, target_id=process.id, kind="material", input_amount=1.0
    )
    db.add(link)
    db.flush()
    errors = validate_structure(chain)
    assert not any(msg.startswith("Masse") for msg in errors)
    link.input_amount = 0.5
    db.flush()
    errors = validate_structure(chain)
    assert "Masse an „Herstellung“ ist 0,5 kg je 1 kg, erwartet 1 kg." in errors


def test_publish_counts_category_mass_once_through_transport(db):
    chain, _role, _folie, process = _base(db)
    starch_role = Role(slug="staerke", label="Stärke")
    db.add(starch_role)
    db.flush()
    starch_ds = _kg_dataset(db, "Kartoffelstärke")
    starch_ds.roles.append(DatasetRole(role_id=starch_role.id))
    truck = Dataset(name="Lkw", location="DE", unit="kg·km", source_kind=SOURCE_ECOINVENT)
    db.add(truck)
    db.flush()
    starch = ChainNode(chain=chain, type="category", name="Stärke", role_id=starch_role.id, unit="kg")
    haul = ChainNode(
        chain=chain, type="transport", name="Transport Stärke", dataset_id=truck.id, unit="kg·km", distance_km=10
    )
    db.add_all([starch, haul])
    db.flush()
    db.add_all(
        [
            ChainEdge(chain=chain, source_id=starch.id, target_id=haul.id, kind="material"),
            ChainEdge(chain=chain, source_id=haul.id, target_id=process.id, kind="material", input_amount=1.0),
        ]
    )
    combo = _recipe(db, chain, process, [(starch, 1.0)])
    db.add(
        ChainDatasetShare(chain=chain, category_node_id=starch.id, dataset_id=starch_ds.id, default_share=1.0)
    )
    db.flush()
    errors = validate_structure(chain)
    assert not any(msg.startswith("Masse") for msg in errors)
    amount = next(row for row in combo.amounts if row.category_node_id == starch.id)
    amount.input_amount = 0.4
    db.flush()
    errors = validate_structure(chain)
    assert "Masse an „Herstellung“ ist 0,4 kg je 1 kg, erwartet 1 kg." in errors


def test_publish_without_lcia_uses_inventory(db, monkeypatch):
    monkeypatch.setattr("app.services.calculate.try_load_method", lambda: None)
    chain, role, _folie, process = _base(db)
    ds = Dataset(name="Strom", location="DE", unit="kWh", source_kind=SOURCE_ECOINVENT)
    ds.exchanges.append(DatasetExchange(flow_id="flow-co2", name="CO2", unit="kg", amount=0.4))
    db.add(ds)
    db.flush()
    _energy(db, chain, role, process, ds)
    ok, errs = probe_and_publish(db, chain)
    assert ok, errs
    assert chain.status == "published"

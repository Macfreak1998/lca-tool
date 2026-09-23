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
    assert any("100" in msg for msg in errors)


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

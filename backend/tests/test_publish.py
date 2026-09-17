from __future__ import annotations

from app.constants import CLIMATE_CHANGE, METHOD_ID, SOURCE_ECOINVENT
from app.models import Chain, Dataset, DatasetExchange, DatasetFactor, EndProduct, Role, Slot, Stage
from app.services.publish import probe_and_publish, validate_structure


def test_publish_requires_defaults_and_probe(db):
    end = EndProduct(name="Folie", unit="kg")
    role = Role(slug="energie", label="Energie")
    db.add_all([end, role])
    db.flush()
    ds = Dataset(name="Strom", location="DE", unit="kWh", source_kind=SOURCE_ECOINVENT)
    ds.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=0.4))
    db.add(ds)
    db.flush()
    chain = Chain(name="Test", status="draft", end_product_id=end.id, end_unit="kg")
    db.add(chain)
    db.flush()
    stage = Stage(chain=chain, name="Folie", sort_order=0, upstream_amount=1.0)
    db.add(stage)
    db.flush()
    db.add(
        Slot(
            stage=stage,
            role_id=role.id,
            required=True,
            specific_amount=1.0,
            unit="kWh",
            default_dataset_id=None,
        )
    )
    db.flush()
    errors = validate_structure(chain)
    assert errors
    stage.slots[0].default_dataset_id = ds.id
    db.flush()
    ok, errs = probe_and_publish(db, chain)
    assert ok, errs
    assert chain.status == "published"


def test_publish_blocks_on_bad_shares(db):
    end = EndProduct(name="Folie", unit="kg")
    role = Role(slug="staerke", label="Stärke")
    db.add_all([end, role])
    db.flush()
    ds = Dataset(name="A", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    ds.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=1.0))
    db.add(ds)
    db.flush()
    chain = Chain(name="Test", status="draft", end_product_id=end.id, end_unit="kg")
    stage = Stage(chain=chain, name="Mix", sort_order=0)
    db.add_all([chain, stage])
    db.flush()
    db.add_all(
        [
            Slot(
                stage=stage,
                role_id=role.id,
                required=True,
                specific_amount=1.0,
                unit="kg",
                default_dataset_id=ds.id,
                default_share=0.5,
            ),
            Slot(
                stage=stage,
                role_id=role.id,
                required=True,
                specific_amount=1.0,
                unit="kg",
                default_dataset_id=ds.id,
                default_share=0.2,
            ),
        ]
    )
    db.flush()
    errors = validate_structure(chain)
    assert any("100" in msg for msg in errors)


def test_publish_without_lcia_uses_inventory(db, monkeypatch):
    monkeypatch.setattr("app.services.calculate.try_load_method", lambda: None)
    end = EndProduct(name="Folie", unit="kg")
    role = Role(slug="energie", label="Energie")
    db.add_all([end, role])
    db.flush()
    ds = Dataset(name="Strom", location="DE", unit="kWh", source_kind=SOURCE_ECOINVENT)
    ds.exchanges.append(DatasetExchange(flow_id="flow-co2", name="CO2", unit="kg", amount=0.4))
    db.add(ds)
    db.flush()
    chain = Chain(name="Test", status="draft", end_product_id=end.id, end_unit="kg")
    db.add(chain)
    db.flush()
    stage = Stage(chain=chain, name="Folie", sort_order=0, upstream_amount=1.0)
    db.add(stage)
    db.flush()
    db.add(
        Slot(
            stage=stage,
            role_id=role.id,
            required=True,
            specific_amount=1.0,
            unit="kWh",
            default_dataset_id=ds.id,
        )
    )
    db.flush()
    ok, errs = probe_and_publish(db, chain)
    assert ok, errs
    assert chain.status == "published"

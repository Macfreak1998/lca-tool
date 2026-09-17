from __future__ import annotations

from pathlib import Path

from app.constants import SOURCE_ECOINVENT
from app.models import Dataset, DatasetExchange, Role
from app.services.characterize import characterize_spold, parse_spold


def test_parse_and_characterize(fixtures_dir: Path):
    spold = fixtures_dir / "sample.spold"
    method = fixtures_dir / "ef31_method.json"
    meta, flows = parse_spold(spold)
    assert meta["activity_name"] == "market for maize starch"
    assert meta["unit"] == "kg"
    assert len(flows) == 2
    assert flows[0].name == "Carbon dioxide, fossil"
    assert flows[1].name == "Sulfur dioxide"
    result = characterize_spold(spold, method)
    assert result.factors["climate_change"] == 0.5
    assert result.factors["acidification"] == 0.131
    assert result.factors["water_use"] == 0.0


def test_import_without_method_stores_exchanges(db, fixtures_dir: Path):
    meta, flows = parse_spold(fixtures_dir / "sample.spold")
    role = Role(slug="staerke", label="Stärke")
    db.add(role)
    db.flush()
    dataset = Dataset(
        name=meta["name"],
        location=meta["location"],
        unit=meta["unit"],
        source_kind=SOURCE_ECOINVENT,
        activity_name=meta["activity_name"],
        filename=meta["filename"],
    )
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
    assert len(dataset.factors) == 0
    assert len(dataset.exchanges) == 2
    assert dataset.exchanges[0].flow_id == "flow-co2"
    assert dataset.exchanges[0].amount == 0.5

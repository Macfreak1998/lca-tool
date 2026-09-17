from __future__ import annotations

import pytest

from app.constants import CLIMATE_CHANGE, METHOD_ID, SOURCE_ECOINVENT, SOURCE_USER
from app.models import Chain, Dataset, DatasetExchange, DatasetFactor, DatasetRole, EndProduct, Role, Slot, Stage
from app.services.calculate import MODE_INVENTORY, MODE_LCIA, CalcInput, ExtraSlot, calculate


def _factor(dataset: Dataset, indicator: str, value: float) -> None:
    dataset.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=indicator, value=value))


def _chain(db, *, optional: bool = False, two_starch: bool = False):
    end = EndProduct(name="Folie", unit="kg")
    energy = Role(slug="energie", label="Energie")
    starch = Role(slug="staerke", label="Stärke")
    db.add_all([end, energy, starch])
    db.flush()
    starch_ds = Dataset(name="Maisstärke", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    starch_ds2 = Dataset(name="Kartoffelstärke", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    elec = Dataset(name="Strom DE", location="DE", unit="kWh", source_kind=SOURCE_ECOINVENT)
    _factor(starch_ds, CLIMATE_CHANGE, 1.0)
    _factor(starch_ds2, CLIMATE_CHANGE, 2.0)
    _factor(elec, CLIMATE_CHANGE, 0.4)
    starch_ds.roles.append(DatasetRole(role_id=starch.id))
    starch_ds2.roles.append(DatasetRole(role_id=starch.id))
    elec.roles.append(DatasetRole(role_id=energy.id))
    db.add_all([starch_ds, starch_ds2, elec])
    db.flush()
    chain = Chain(name="HOF", status="published", end_product_id=end.id, end_unit="kg")
    db.add(chain)
    db.flush()
    granulat = Stage(chain=chain, name="Granulat", sort_order=0, upstream_amount=1.0)
    folie = Stage(chain=chain, name="Folie", sort_order=1, upstream_amount=1.1)
    db.add_all([granulat, folie])
    db.flush()
    granulat.outgoing_stage_id = folie.id
    s1 = Slot(
        stage=granulat,
        role_id=starch.id,
        required=True,
        specific_amount=0.8,
        unit="kg",
        default_dataset_id=starch_ds.id,
        default_share=0.6 if two_starch else 1.0,
    )
    slots = [s1]
    if two_starch:
        slots.append(
            Slot(
                stage=granulat,
                role_id=starch.id,
                required=True,
                specific_amount=0.8,
                unit="kg",
                default_dataset_id=starch_ds2.id,
                default_share=0.4,
            )
        )
    slots.append(
        Slot(
            stage=folie,
            role_id=energy.id,
            required=not optional,
            optional_default_off=optional,
            specific_amount=0.5,
            unit="kWh",
            default_dataset_id=elec.id,
            default_share=1.0,
        )
    )
    db.add_all(slots)
    db.flush()
    datasets = {starch_ds.id: starch_ds, starch_ds2.id: starch_ds2, elec.id: elec}
    roles = {energy.id: energy, starch.id: starch}
    return chain, datasets, roles, starch_ds, starch_ds2, elec, granulat, folie, slots


def test_two_stages_with_upstream(db):
    chain, datasets, roles, starch, _s2, elec, granulat, folie, slots = _chain(db)
    starch_slot = granulat.slots[0]
    energy_slot = folie.slots[0]
    result = calculate(
        chain,
        CalcInput(
            end_amount=1.0,
            selections={str(starch_slot.id): starch.id, str(energy_slot.id): elec.id},
        ),
        datasets,
        roles,
    )
    assert result.blockers == []
    # film energy: 1 * 0.5 * 0.4 = 0.2
    # granulate output = 1 * 1.1 = 1.1; starch 1.1 * 0.8 * 1.0 * 1.0 = 0.88
    assert result.totals[CLIMATE_CHANGE] == pytest_approx(0.88 + 0.2)


def pytest_approx(value: float, rel: float = 1e-9):
    return pytest.approx(value, rel=rel)


def test_shares_must_sum_to_one(db):
    chain, datasets, roles, starch, starch2, _elec, granulat, _folie, _slots = _chain(
        db, two_starch=True
    )
    a, b = granulat.slots[0], granulat.slots[1]
    result = calculate(
        chain,
        CalcInput(
            end_amount=1.0,
            selections={str(a.id): starch.id, str(b.id): starch2.id},
            shares={str(a.id): 0.5, str(b.id): 0.2},
        ),
        datasets,
        roles,
    )
    assert any("100" in msg for msg in result.blockers)


def test_shares_split_amount(db):
    chain, datasets, roles, starch, starch2, elec, granulat, folie, _slots = _chain(
        db, two_starch=True
    )
    a, b = granulat.slots[0], granulat.slots[1]
    energy = folie.slots[0]
    result = calculate(
        chain,
        CalcInput(
            end_amount=1.0,
            selections={str(a.id): starch.id, str(b.id): starch2.id, str(energy.id): elec.id},
            shares={str(a.id): 0.6, str(b.id): 0.4},
        ),
        datasets,
        roles,
    )
    assert result.blockers == []
    # granulate 1.1 kg; starch total 0.88: 0.528 * 1 + 0.352 * 2 = 1.232; energy 0.2
    assert result.totals[CLIMATE_CHANGE] == pytest_approx(1.232 + 0.2)


def test_optional_slot_off_by_default(db):
    chain, datasets, roles, starch, _s2, elec, granulat, folie, _slots = _chain(db, optional=True)
    starch_slot = granulat.slots[0]
    energy_slot = folie.slots[0]
    result = calculate(
        chain,
        CalcInput(end_amount=1.0, selections={str(starch_slot.id): starch.id}),
        datasets,
        roles,
    )
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest_approx(0.88)
    on = calculate(
        chain,
        CalcInput(
            end_amount=1.0,
            selections={str(starch_slot.id): starch.id, str(energy_slot.id): elec.id},
            optional_on=[energy_slot.id],
        ),
        datasets,
        roles,
    )
    assert on.totals[CLIMATE_CHANGE] == pytest_approx(0.88 + 0.2)


def test_missing_end_amount_blocks(db):
    chain, datasets, roles, *_ = _chain(db)
    result = calculate(chain, CalcInput(end_amount=None), datasets, roles)
    assert result.blockers


def test_replaced_stage_skips_upstream(db):
    chain, datasets, roles, starch, _s2, elec, granulat, folie, _slots = _chain(db)
    own = Dataset(name="Eigenes Granulat", unit="kg", source_kind=SOURCE_USER, location="")
    own.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=CLIMATE_CHANGE, value=3.0))
    db.add(own)
    db.flush()
    datasets[own.id] = own
    energy = folie.slots[0]
    result = calculate(
        chain,
        CalcInput(
            end_amount=1.0,
            selections={str(energy.id): elec.id},
            replaced_stages={granulat.id: own.id},
        ),
        datasets,
        roles,
    )
    assert result.blockers == []
    # replaced granulate: amount = 1 * 1.1 * 3.0 = 3.3; film energy 0.2
    assert result.totals[CLIMATE_CHANGE] == pytest_approx(3.3 + 0.2)
    assert all(row.dataset_id != starch.id for row in result.contributions)


def test_user_dataset_without_co2_blocks(db):
    chain, datasets, roles, _s, _s2, elec, granulat, folie, _slots = _chain(db)
    own = Dataset(name="Ohne CO2", unit="kg", source_kind=SOURCE_USER)
    db.add(own)
    db.flush()
    datasets[own.id] = own
    starch_slot = granulat.slots[0]
    energy = folie.slots[0]
    result = calculate(
        chain,
        CalcInput(
            end_amount=1.0,
            selections={str(starch_slot.id): own.id, str(energy.id): elec.id},
        ),
        datasets,
        roles,
    )
    assert any("CO₂e" in msg or "CO2" in msg for msg in result.blockers)


def test_unpublished_chain_blocks(db):
    chain, datasets, roles, *_ = _chain(db)
    chain.status = "draft"
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert any("veröffentlicht" in msg for msg in result.blockers)


def test_missing_indicator_omitted_not_zero(db):
    chain, datasets, roles, starch, _s2, elec, granulat, folie, _slots = _chain(db)
    starch_slot = granulat.slots[0]
    energy = folie.slots[0]
    result = calculate(
        chain,
        CalcInput(
            end_amount=1.0,
            selections={str(starch_slot.id): starch.id, str(energy.id): elec.id},
        ),
        datasets,
        roles,
    )
    assert "acidification" not in result.totals
    assert all(row.indicator_id != "acidification" for row in result.contributions)


def test_extra_slot_shares(db):
    chain, datasets, roles, starch, starch2, elec, granulat, folie, _slots = _chain(db)
    starch_slot = granulat.slots[0]
    energy = folie.slots[0]
    result = calculate(
        chain,
        CalcInput(
            end_amount=1.0,
            selections={str(starch_slot.id): starch.id, str(energy.id): elec.id},
            shares={str(starch_slot.id): 0.5},
            extra_slots=[
                ExtraSlot(
                    key="extra:1",
                    stage_id=granulat.id,
                    role_id=starch_slot.role_id,
                    dataset_id=starch2.id,
                    share=0.5,
                )
            ],
        ),
        datasets,
        roles,
    )
    assert result.blockers == []
    # 1.1 * 0.8 * 0.5 * 1 + 1.1 * 0.8 * 0.5 * 2 + 0.2 = 0.44 + 0.88 + 0.2
    assert result.totals[CLIMATE_CHANGE] == pytest_approx(1.52)


def test_inventory_mode_without_lcia(db, monkeypatch):
    monkeypatch.setattr("app.services.calculate.try_load_method", lambda: None)
    chain, datasets, roles, starch, _s2, elec, granulat, folie, _slots = _chain(db)
    starch.factors.clear()
    elec.factors.clear()
    starch.exchanges.append(DatasetExchange(flow_id="flow-co2", name="CO2", unit="kg", amount=1.0))
    elec.exchanges.append(DatasetExchange(flow_id="flow-co2", name="CO2", unit="kg", amount=0.4))
    db.flush()
    starch_slot = granulat.slots[0]
    energy = folie.slots[0]
    result = calculate(
        chain,
        CalcInput(
            end_amount=1.0,
            selections={str(starch_slot.id): starch.id, str(energy.id): elec.id},
        ),
        datasets,
        roles,
    )
    assert result.blockers == []
    assert result.mode == MODE_INVENTORY
    assert result.totals == {}
    assert result.inventory_summary.flow_count == 1
    assert result.inventory_summary.catalog_dataset_count == 2
    # 1.1 * 0.8 * 1.0 + 1 * 0.5 * 0.4 = 0.88 + 0.2
    assert sum(line.value for line in result.inventory_lines) == pytest_approx(1.08)


def test_lcia_applied_as_final_step(db, monkeypatch):
    monkeypatch.setattr(
        "app.services.calculate.try_load_method",
        lambda: {"flow-co2": {CLIMATE_CHANGE: 2.0}},
    )
    chain, datasets, roles, starch, _s2, elec, granulat, folie, _slots = _chain(db)
    starch.factors.clear()
    elec.factors.clear()
    starch.exchanges.append(DatasetExchange(flow_id="flow-co2", name="CO2", unit="kg", amount=1.0))
    elec.exchanges.append(DatasetExchange(flow_id="flow-co2", name="CO2", unit="kg", amount=0.4))
    db.flush()
    starch_slot = granulat.slots[0]
    energy = folie.slots[0]
    result = calculate(
        chain,
        CalcInput(
            end_amount=1.0,
            selections={str(starch_slot.id): starch.id, str(energy.id): elec.id},
        ),
        datasets,
        roles,
    )
    assert result.blockers == []
    assert result.mode == MODE_LCIA
    assert result.totals[CLIMATE_CHANGE] == pytest_approx(2.16)


def test_export_inventory_lists_all_flows(db, monkeypatch):
    from app.services.export import to_csv

    monkeypatch.setattr("app.services.calculate.try_load_method", lambda: None)
    chain, datasets, roles, starch, _s2, elec, granulat, folie, _slots = _chain(db)
    starch.factors.clear()
    elec.factors.clear()
    starch.exchanges.append(
        DatasetExchange(flow_id="flow-co2", name="Carbon dioxide, fossil", unit="kg", amount=1.0)
    )
    elec.exchanges.append(
        DatasetExchange(flow_id="flow-so2", name="Sulfur dioxide", unit="kg", amount=0.1)
    )
    db.flush()
    result = calculate(
        chain,
        CalcInput(
            end_amount=1.0,
            selections={str(granulat.slots[0].id): starch.id, str(folie.slots[0].id): elec.id},
        ),
        datasets,
        roles,
    )
    text = to_csv([(chain.name, result)]).decode("utf-8-sig")
    assert "Carbon dioxide, fossil" in text
    assert "Sulfur dioxide" in text
    assert "Fluss" in text

from __future__ import annotations

import pytest

from app.constants import CLIMATE_CHANGE, METHOD_ID, SOURCE_ECOINVENT, SOURCE_USER
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
from app.services.calculate import MODE_INVENTORY, MODE_LCIA, CalcInput, calculate, share_key


def _factor(dataset: Dataset, indicator: str, value: float) -> None:
    dataset.factors.append(DatasetFactor(method_id=METHOD_ID, indicator_id=indicator, value=value))


def _combo(db, chain, process, axes, amounts):
    combo = ChainCombination(chain=chain, process_node_id=process.id)
    db.add(combo)
    db.flush()
    for category, dataset in axes:
        db.add(
            ChainCombinationAxis(
                combination=combo, category_node_id=category.id, dataset_id=dataset.id
            )
        )
    for category, amount, recovery in amounts:
        db.add(
            ChainCombinationAmount(
                combination=combo,
                category_node_id=category.id,
                input_amount=amount,
                recovery_node_id=recovery.id if recovery is not None else None,
            )
        )
    return combo


def _share(db, chain, category, dataset, value):
    db.add(
        ChainDatasetShare(
            chain=chain,
            category_node_id=category.id,
            dataset_id=dataset.id,
            default_share=value,
        )
    )


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
    granulat = ChainNode(chain=chain, type="product", name="Granulat", unit="kg")
    folie = ChainNode(chain=chain, type="product", name="Folie", unit="kg", is_functional=True)
    make = ChainNode(chain=chain, type="process", name="Granulieren", unit="kg")
    form = ChainNode(chain=chain, type="process", name="Folieren", unit="kg")
    starch_node = ChainNode(
        chain=chain, type="category", name="Stärke", role_id=starch.id, unit="kg", datasets_differ=True
    )
    energy_node = ChainNode(
        chain=chain,
        type="category",
        name="Energie",
        role_id=energy.id,
        unit="kWh",
        optional=optional,
        datasets_differ=False,
    )
    db.add_all([granulat, folie, make, form, starch_node, energy_node])
    db.flush()
    db.add_all(
        [
            ChainEdge(chain=chain, source_id=starch_node.id, target_id=make.id, kind="material"),
            ChainEdge(chain=chain, source_id=make.id, target_id=granulat.id, kind="material"),
            ChainEdge(chain=chain, source_id=granulat.id, target_id=form.id, kind="material", input_amount=1.0),
            ChainEdge(chain=chain, source_id=form.id, target_id=folie.id, kind="material"),
            ChainEdge(chain=chain, source_id=energy_node.id, target_id=form.id, kind="energy"),
        ]
    )
    _combo(db, chain, make, [(starch_node, starch_ds)], [(starch_node, 0.8, None)])
    if two_starch:
        _combo(db, chain, make, [(starch_node, starch_ds2)], [(starch_node, 0.8, None)])
        _share(db, chain, starch_node, starch_ds, 0.6)
        _share(db, chain, starch_node, starch_ds2, 0.4)
    else:
        _share(db, chain, starch_node, starch_ds, 1.0)
    _combo(db, chain, form, [], [(energy_node, 0.5, None)])
    _share(db, chain, energy_node, elec, 1.0)
    db.flush()
    datasets = {starch_ds.id: starch_ds, starch_ds2.id: starch_ds2, elec.id: elec}
    roles = {energy.id: energy, starch.id: starch}
    return chain, datasets, roles, starch_ds, starch_ds2, elec, granulat, folie, energy_node, make, form


def test_two_stages_with_upstream(db):
    chain, datasets, roles, starch, *_rest = _chain(db)
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(0.8 + 0.2)


def test_shares_must_sum_to_one(db):
    chain, datasets, roles, starch, starch2, *_rest = _chain(db, two_starch=True)
    starch_node = next(node for node in chain.nodes if node.name == "Stärke")
    result = calculate(
        chain,
        CalcInput(
            end_amount=1.0,
            shares={
                share_key(starch_node.id, starch.id): 0.5,
                share_key(starch_node.id, starch2.id): 0.2,
            },
        ),
        datasets,
        roles,
    )
    assert any("100" in msg for msg in result.blockers)


def test_shares_split_amount(db):
    chain, datasets, roles, *_rest = _chain(db, two_starch=True)
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(1.12 + 0.2)


def test_optional_energy_off_by_default(db):
    chain, datasets, roles, _s, _s2, elec, _g, _f, energy_node, *_rest = _chain(db, optional=True)
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(0.8)
    on = calculate(
        chain,
        CalcInput(end_amount=1.0, optional_on=[energy_node.id]),
        datasets,
        roles,
    )
    assert on.totals[CLIMATE_CHANGE] == pytest.approx(0.8 + 0.2)


def test_missing_end_amount_blocks(db):
    chain, datasets, roles, *_ = _chain(db)
    result = calculate(chain, CalcInput(end_amount=None), datasets, roles)
    assert result.blockers


def test_replaced_product_skips_upstream(db):
    chain, datasets, roles, starch, _s2, elec, granulat, *_rest = _chain(db)
    own = Dataset(name="Eigenes Granulat", unit="kg", source_kind=SOURCE_USER, location="")
    _factor(own, CLIMATE_CHANGE, 3.0)
    db.add(own)
    db.flush()
    datasets[own.id] = own
    result = calculate(
        chain,
        CalcInput(end_amount=1.0, replaced_nodes={granulat.id: own.id}),
        datasets,
        roles,
    )
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(3.0 + 0.2)
    assert all(row.dataset_id != starch.id for row in result.contributions)


def test_user_dataset_without_co2_blocks(db):
    chain, datasets, roles, _s, _s2, elec, *_rest = _chain(db)
    own = Dataset(name="Ohne CO2", unit="kg", source_kind=SOURCE_USER)
    db.add(own)
    db.flush()
    datasets[own.id] = own
    axis = next(axis for combo in chain.combinations for axis in combo.axes)
    axis.dataset_id = own.id
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert any("CO₂e" in msg or "CO2" in msg for msg in result.blockers)


def test_unpublished_chain_blocks(db):
    chain, datasets, roles, *_ = _chain(db)
    chain.status = "draft"
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert any("veröffentlicht" in msg for msg in result.blockers)


def test_cycle_blocks(db):
    chain, datasets, roles, *_rest = _chain(db)
    folie = next(node for node in chain.nodes if node.is_functional)
    make = next(node for node in chain.nodes if node.name == "Granulieren")
    db.add(ChainEdge(chain=chain, source_id=folie.id, target_id=make.id, kind="material"))
    db.flush()
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert any("Zyklus" in msg for msg in result.blockers)


def test_combination_weight_is_product_of_shares(db):
    end = EndProduct(name="Folie", unit="kg")
    starch = Role(slug="staerke", label="Stärke")
    additive = Role(slug="additiv", label="Additiv")
    db.add_all([end, starch, additive])
    db.flush()
    bio = Dataset(name="Bio", unit="kg", source_kind=SOURCE_ECOINVENT)
    fossil = Dataset(name="Fossil", unit="kg", source_kind=SOURCE_ECOINVENT)
    add_a = Dataset(name="Additiv A", unit="kg", source_kind=SOURCE_ECOINVENT)
    add_b = Dataset(name="Additiv B", unit="kg", source_kind=SOURCE_ECOINVENT)
    _factor(bio, CLIMATE_CHANGE, 1.0)
    _factor(fossil, CLIMATE_CHANGE, 2.0)
    _factor(add_a, CLIMATE_CHANGE, 3.0)
    _factor(add_b, CLIMATE_CHANGE, 4.0)
    bio.roles.append(DatasetRole(role_id=starch.id))
    fossil.roles.append(DatasetRole(role_id=starch.id))
    add_a.roles.append(DatasetRole(role_id=additive.id))
    add_b.roles.append(DatasetRole(role_id=additive.id))
    db.add_all([bio, fossil, add_a, add_b])
    db.flush()
    chain = Chain(name="Mix", status="published", end_product_id=end.id, end_unit="kg")
    db.add(chain)
    db.flush()
    folie = ChainNode(chain=chain, type="product", name="Folie", unit="kg", is_functional=True)
    process = ChainNode(chain=chain, type="process", name="Mischen", unit="kg")
    starch_node = ChainNode(chain=chain, type="category", name="Stärke", role_id=starch.id, unit="kg", datasets_differ=True)
    add_node = ChainNode(chain=chain, type="category", name="Additiv", role_id=additive.id, unit="kg", datasets_differ=True)
    db.add_all([folie, process, starch_node, add_node])
    db.flush()
    db.add_all(
        [
            ChainEdge(chain=chain, source_id=starch_node.id, target_id=process.id, kind="material"),
            ChainEdge(chain=chain, source_id=add_node.id, target_id=process.id, kind="material"),
            ChainEdge(chain=chain, source_id=process.id, target_id=folie.id, kind="material"),
        ]
    )
    for starch_ds, starch_amount in ((bio, 1.0), (fossil, 0.9)):
        for add_ds in (add_a, add_b):
            _combo(
                db,
                chain,
                process,
                [(starch_node, starch_ds), (add_node, add_ds)],
                [(starch_node, starch_amount, None), (add_node, 1.0, None)],
            )
    _share(db, chain, starch_node, bio, 0.6)
    _share(db, chain, starch_node, fossil, 0.4)
    _share(db, chain, add_node, add_a, 0.5)
    _share(db, chain, add_node, add_b, 0.5)
    db.flush()
    datasets = {item.id: item for item in (bio, fossil, add_a, add_b)}
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, {starch.id: starch, additive.id: additive})
    assert result.blockers == []
    starch_total = 0.6 * 0.5 * 1.0 * 1 + 0.6 * 0.5 * 1.0 * 1 + 0.4 * 0.5 * 0.9 * 2 + 0.4 * 0.5 * 0.9 * 2
    additive_total = 0.6 * 0.5 * 1 * 3 + 0.6 * 0.5 * 1 * 4 + 0.4 * 0.5 * 1 * 3 + 0.4 * 0.5 * 1 * 4
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(starch_total + additive_total)
    assert len(chain.combinations) == 4


def test_uniform_energy_does_not_multiply_rows(db):
    chain, datasets, roles, starch, _starch2, elec, *_rest = _chain(db, two_starch=True)
    other = Dataset(name="Strom EU", location="EU", unit="kWh", source_kind=SOURCE_ECOINVENT)
    _factor(other, CLIMATE_CHANGE, 0.8)
    energy_node = next(node for node in chain.nodes if node.name == "Energie")
    other.roles.append(DatasetRole(role_id=energy_node.role_id))
    db.add(other)
    db.flush()
    datasets[other.id] = other
    make = next(node for node in chain.nodes if node.name == "Granulieren")
    form = next(node for node in chain.nodes if node.name == "Folieren")
    next(edge for edge in chain.edges if edge.kind == "energy").target_id = make.id
    for combo in list(chain.combinations):
        if combo.process_node_id == form.id:
            db.delete(combo)
    db.flush()
    db.expire(chain, ["combinations"])
    for combo in chain.combinations:
        kwh = 2.0 if combo.axes[0].dataset_id == starch.id else 3.5
        db.add(ChainCombinationAmount(combination=combo, category_node_id=energy_node.id, input_amount=kwh))
    next(share for share in chain.dataset_shares if share.dataset_id == elec.id).default_share = 0.5
    _share(db, chain, energy_node, other, 0.5)
    db.flush()
    assert len(chain.combinations) == 2
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert result.blockers == []
    starch_total = 0.6 * 0.8 * 1 + 0.4 * 0.8 * 2
    energy_total = (0.6 * 2.0 + 0.4 * 3.5) * (0.5 * 0.4 + 0.5 * 0.8)
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(starch_total + energy_total)


def test_category_unit_must_match_dataset(db):
    chain, datasets, roles, *_rest = _chain(db)
    energy_node = next(node for node in chain.nodes if node.name == "Energie")
    energy_node.unit = "kg"
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert "Einheit von „Strom DE“ (kWh) passt nicht zu „Energie“ (kg)." in result.blockers
    assert result.totals == {}


def test_category_unit_synonym_is_accepted(db):
    chain, datasets, roles, _s, _s2, elec, *_rest = _chain(db)
    energy_node = next(node for node in chain.nodes if node.name == "Energie")
    energy_node.unit = "kilowatt hour"
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(0.8 + 0.2)
    assert elec.unit == "kWh"


def test_user_dataset_unit_must_match_category(db):
    chain, datasets, roles, *_rest = _chain(db)
    energy_node = next(node for node in chain.nodes if node.name == "Energie")
    elec = next(item for item in datasets.values() if item.name == "Strom DE")
    own = Dataset(name="Eigenstrom", unit="kg", source_kind=SOURCE_USER, location="")
    _factor(own, CLIMATE_CHANGE, 0.2)
    own.roles.append(DatasetRole(role_id=energy_node.role_id))
    db.add(own)
    db.flush()
    datasets[own.id] = own
    result = calculate(
        chain,
        CalcInput(
            end_amount=1.0,
            shares={
                share_key(energy_node.id, elec.id): 0.5,
                share_key(energy_node.id, own.id): 0.5,
            },
        ),
        datasets,
        roles,
    )
    assert "Einheit von „Eigenstrom“ (kg) passt nicht zu „Energie“ (kWh)." in result.blockers


def test_energy_above_one_has_no_waste(db):
    chain, datasets, roles, *_rest = _chain(db)
    form = next(node for node in chain.nodes if node.name == "Folieren")
    amount = next(
        row
        for combo in chain.combinations
        if combo.process_node_id == form.id
        for row in combo.amounts
    )
    amount.input_amount = 1.5
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(0.8 + 0.6)
    assert all("Verwertung" not in row.role_label for row in result.contributions)


def test_waste_is_amount_minus_one(db):
    chain, datasets, roles, *_rest = _chain(db)
    recovery_ds = Dataset(name="Verbrennung", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    _factor(recovery_ds, CLIMATE_CHANGE, 10.0)
    db.add(recovery_ds)
    db.flush()
    datasets[recovery_ds.id] = recovery_ds
    recovery = ChainNode(chain=chain, type="recovery", name="Verwertung", dataset_id=recovery_ds.id, unit="kg")
    db.add(recovery)
    db.flush()
    make = next(node for node in chain.nodes if node.name == "Granulieren")
    amount = next(
        row
        for combo in chain.combinations
        if combo.process_node_id == make.id
        for row in combo.amounts
    )
    amount.input_amount = 1.0
    amount.efficiency = 1 / 1.2
    amount.recovery_node_id = recovery.id
    db.flush()
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(1.2 + 0.2 + 0.2 * 10)


def test_upstream_product_edge_waste(db):
    chain, datasets, roles, *_rest = _chain(db)
    recovery_ds = Dataset(name="Verbrennung", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    _factor(recovery_ds, CLIMATE_CHANGE, 10.0)
    db.add(recovery_ds)
    db.flush()
    datasets[recovery_ds.id] = recovery_ds
    recovery = ChainNode(chain=chain, type="recovery", name="Verwertung", dataset_id=recovery_ds.id, unit="kg")
    db.add(recovery)
    db.flush()
    form = next(node for node in chain.nodes if node.name == "Folieren")
    link = next(edge for edge in chain.edges if edge.target_id == form.id and edge.kind == "material")
    link.input_amount = 1.0
    link.efficiency = 1 / 1.1
    db.add(ChainEdge(chain=chain, source_id=form.id, target_id=recovery.id, kind="waste"))
    db.flush()
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(0.8 * 1.1 + 0.2 + 0.1 * 10)


def test_inventory_mode_without_lcia(db, monkeypatch):
    monkeypatch.setattr("app.services.calculate.try_load_method", lambda: None)
    chain, datasets, roles, starch, _s2, elec, *_rest = _chain(db)
    starch.factors.clear()
    elec.factors.clear()
    starch.exchanges.append(DatasetExchange(flow_id="flow-co2", name="CO2", unit="kg", amount=1.0))
    elec.exchanges.append(DatasetExchange(flow_id="flow-co2", name="CO2", unit="kg", amount=0.4))
    db.flush()
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert result.blockers == []
    assert result.mode == MODE_INVENTORY
    assert result.totals == {}
    assert result.inventory_summary.flow_count == 1
    assert result.inventory_summary.catalog_dataset_count == 2
    assert sum(line.value for line in result.inventory_lines) == pytest.approx(1.0)


def test_lcia_applied_as_final_step(db, monkeypatch):
    monkeypatch.setattr(
        "app.services.calculate.try_load_method",
        lambda: {"flow-co2": {CLIMATE_CHANGE: 2.0}},
    )
    chain, datasets, roles, starch, _s2, elec, *_rest = _chain(db)
    starch.factors.clear()
    elec.factors.clear()
    starch.exchanges.append(DatasetExchange(flow_id="flow-co2", name="CO2", unit="kg", amount=1.0))
    elec.exchanges.append(DatasetExchange(flow_id="flow-co2", name="CO2", unit="kg", amount=0.4))
    db.flush()
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert result.blockers == []
    assert result.mode == MODE_LCIA
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(2.0)


def test_additive_efficiency_creates_waste_below_one(db):
    chain, datasets, roles, *_rest = _chain(db)
    recovery_ds = Dataset(name="Verbrennung", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    _factor(recovery_ds, CLIMATE_CHANGE, 10.0)
    db.add(recovery_ds)
    db.flush()
    datasets[recovery_ds.id] = recovery_ds
    recovery = ChainNode(chain=chain, type="recovery", name="Verwertung", dataset_id=recovery_ds.id, unit="kg")
    db.add(recovery)
    db.flush()
    make = next(node for node in chain.nodes if node.name == "Granulieren")
    amount = next(
        row for combo in chain.combinations if combo.process_node_id == make.id for row in combo.amounts
    )
    amount.input_amount = 0.05
    amount.efficiency = 0.85
    amount.recovery_node_id = recovery.id
    db.flush()
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    einsatz = 0.05 / 0.85
    waste = 0.05 * (1 / 0.85 - 1)
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(einsatz + waste * 10 + 0.2)


def test_energy_efficiency_is_ignored(db):
    chain, datasets, roles, *_rest = _chain(db)
    form = next(node for node in chain.nodes if node.name == "Folieren")
    amount = next(row for combo in chain.combinations if combo.process_node_id == form.id for row in combo.amounts)
    amount.input_amount = 0.5
    amount.efficiency = 0.95
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(0.8 + 0.5 * 0.4)
    assert all("Verwertung" not in row.role_label for row in result.contributions)


def test_material_wastes_share_one_recovery(db):
    chain, datasets, roles, *_rest = _chain(db)
    recovery_ds = Dataset(name="Verbrennung", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    _factor(recovery_ds, CLIMATE_CHANGE, 10.0)
    db.add(recovery_ds)
    db.flush()
    datasets[recovery_ds.id] = recovery_ds
    recovery = ChainNode(chain=chain, type="recovery", name="Verwertung", dataset_id=recovery_ds.id, unit="kg")
    other = ChainNode(chain=chain, type="category", name="Additiv", unit="kg")
    db.add_all([recovery, other])
    db.flush()
    make = next(node for node in chain.nodes if node.name == "Granulieren")
    db.add(ChainEdge(chain=chain, source_id=other.id, target_id=make.id, kind="material"))
    db.add(ChainEdge(chain=chain, source_id=make.id, target_id=recovery.id, kind="waste"))
    starch_amount = next(
        row for combo in chain.combinations if combo.process_node_id == make.id for row in combo.amounts
    )
    starch_amount.input_amount = 0.6
    starch_amount.efficiency = 0.9
    starch_amount.recovery_node_id = recovery.id
    db.add(
        ChainCombinationAmount(
            combination=starch_amount.combination,
            category_node_id=other.id,
            input_amount=0.4,
            efficiency=0.8,
            recovery_node_id=recovery.id,
        )
    )
    other_ds = Dataset(name="Additiv", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    _factor(other_ds, CLIMATE_CHANGE, 1.0)
    db.add(other_ds)
    db.flush()
    datasets[other_ds.id] = other_ds
    _share(db, chain, other, other_ds, 1.0)
    db.flush()
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    starch_waste = 0.6 * (1 / 0.9 - 1)
    other_waste = 0.4 * (1 / 0.8 - 1)
    assert result.blockers == []
    recovery_rows = [row for row in result.contributions if row.node_name == "Verwertung"]
    assert len(recovery_rows) == 1
    assert recovery_rows[0].amount == pytest.approx(starch_waste + other_waste)
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(
        0.6 / 0.9 + 0.4 / 0.8 + (starch_waste + other_waste) * 10 + 0.2
    )


def test_two_recoveries_on_one_process_block(db):
    chain, datasets, roles, *_rest = _chain(db)
    first = ChainNode(chain=chain, type="recovery", name="Verwertung A", unit="kg")
    second = ChainNode(chain=chain, type="recovery", name="Verwertung B", unit="kg")
    other = ChainNode(chain=chain, type="category", name="Additiv", unit="kg")
    db.add_all([first, second, other])
    db.flush()
    make = next(node for node in chain.nodes if node.name == "Granulieren")
    db.add(ChainEdge(chain=chain, source_id=other.id, target_id=make.id, kind="material"))
    starch_amount = next(
        row for combo in chain.combinations if combo.process_node_id == make.id for row in combo.amounts
    )
    starch_amount.efficiency = 0.9
    starch_amount.recovery_node_id = first.id
    db.add(
        ChainCombinationAmount(
            combination=starch_amount.combination,
            category_node_id=other.id,
            input_amount=0.4,
            efficiency=0.8,
            recovery_node_id=second.id,
        )
    )
    db.flush()
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert any("nur eine Verwertung" in message for message in result.blockers)


def test_category_through_transport_keeps_mass_and_impact(db):
    chain, datasets, roles, starch, *_rest = _chain(db)
    truck = Dataset(name="Lkw", location="DE", unit="kg·km", source_kind=SOURCE_ECOINVENT)
    _factor(truck, CLIMATE_CHANGE, 0.01)
    db.add(truck)
    db.flush()
    datasets[truck.id] = truck
    starch_node = next(node for node in chain.nodes if node.name == "Stärke")
    make = next(node for node in chain.nodes if node.name == "Granulieren")
    direct = next(edge for edge in chain.edges if edge.source_id == starch_node.id and edge.target_id == make.id)
    chain.edges.remove(direct)
    db.delete(direct)
    haul = ChainNode(
        chain=chain, type="transport", name="Transport", dataset_id=truck.id, unit="kg·km", distance_km=10
    )
    db.add(haul)
    db.flush()
    db.add_all(
        [
            ChainEdge(chain=chain, source_id=starch_node.id, target_id=haul.id, kind="material"),
            ChainEdge(chain=chain, source_id=haul.id, target_id=make.id, kind="material"),
        ]
    )
    db.flush()
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(0.8 + 0.8 * 10 * 0.01 + 0.2)


def test_byproduct_share_includes_recovery_and_credit(db):
    end = EndProduct(name="Teil", unit="kg")
    starch = Role(slug="staerke", label="Stärke")
    energy = Role(slug="energie", label="Energie")
    db.add_all([end, starch, energy])
    db.flush()
    starch_ds = Dataset(name="Stärke", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    elec = Dataset(name="Strom", location="DE", unit="kWh", source_kind=SOURCE_ECOINVENT)
    recovery_ds = Dataset(name="Verbrennung", location="DE", unit="kg", source_kind=SOURCE_ECOINVENT)
    _factor(starch_ds, CLIMATE_CHANGE, 1.0)
    _factor(elec, CLIMATE_CHANGE, 0.4)
    _factor(recovery_ds, CLIMATE_CHANGE, 10.0)
    db.add_all([starch_ds, elec, recovery_ds])
    db.flush()
    chain = Chain(name="Anteil", status="published", end_product_id=end.id, end_unit="kg")
    db.add(chain)
    db.flush()
    part = ChainNode(chain=chain, type="product", name="Teil", unit="kg", is_functional=True)
    side = ChainNode(chain=chain, type="product", name="Nebenprodukt", unit="kg")
    process = ChainNode(chain=chain, type="process", name="Granulieren", unit="kg")
    starch_node = ChainNode(chain=chain, type="category", name="Stärke", role_id=starch.id, unit="kg")
    credit = ChainNode(chain=chain, type="category", name="Stromabgabe", role_id=energy.id, unit="kWh")
    recovery = ChainNode(chain=chain, type="recovery", name="Verwertung", dataset_id=recovery_ds.id, unit="kg")
    db.add_all([part, side, process, starch_node, credit, recovery])
    db.flush()
    db.add_all(
        [
            ChainEdge(chain=chain, source_id=starch_node.id, target_id=process.id, kind="material"),
            ChainEdge(chain=chain, source_id=process.id, target_id=part.id, kind="material"),
            ChainEdge(chain=chain, source_id=process.id, target_id=side.id, kind="material", input_amount=0.25),
            ChainEdge(chain=chain, source_id=process.id, target_id=credit.id, kind="energy"),
        ]
    )
    combo = _combo(
        db,
        chain,
        process,
        [],
        [(starch_node, 1.0, recovery), (credit, 0.5, None)],
    )
    next(row for row in combo.amounts if row.category_node_id == starch_node.id).efficiency = 0.8
    _share(db, chain, starch_node, starch_ds, 1.0)
    _share(db, chain, credit, elec, 1.0)
    db.flush()
    datasets = {starch_ds.id: starch_ds, elec.id: elec, recovery_ds.id: recovery_ds}
    roles = {starch.id: starch, energy.id: energy}
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    einsatz = 1 / 0.8
    waste = 1 * (1 / 0.8 - 1)
    share = 1 / 1.25
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest.approx((einsatz + waste * 10 - 0.5 * 0.4) * share)


def test_export_inventory_lists_all_flows(db, monkeypatch):
    from app.services.export import to_csv

    monkeypatch.setattr("app.services.calculate.try_load_method", lambda: None)
    chain, datasets, roles, starch, _s2, elec, *_rest = _chain(db)
    starch.factors.clear()
    elec.factors.clear()
    starch.exchanges.append(
        DatasetExchange(flow_id="flow-co2", name="Carbon dioxide, fossil", unit="kg", amount=1.0)
    )
    elec.exchanges.append(
        DatasetExchange(flow_id="flow-so2", name="Sulfur dioxide", unit="kg", amount=0.1)
    )
    db.flush()
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    text = to_csv([(chain.name, result)]).decode("utf-8-sig")
    assert "Carbon dioxide, fossil" in text
    assert "Sulfur dioxide" in text
    assert "Fluss" in text
    assert "Knoten" in text

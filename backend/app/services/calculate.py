from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from app.constants import CLIMATE_CHANGE, INDICATOR_IDS, SOURCE_USER
from app.models import Chain, Dataset, Role, Stage
from app.services.characterize import apply_lcia, try_load_method

MODE_LCIA = "lcia"
MODE_INVENTORY = "inventory"


@dataclass
class ExtraSlot:
    key: str
    stage_id: int
    role_id: int
    dataset_id: int | None
    share: float = 0.0


@dataclass
class CalcInput:
    end_amount: float | None
    selections: dict[str, int] = field(default_factory=dict)
    shares: dict[str, float] = field(default_factory=dict)
    optional_on: list[int] = field(default_factory=list)
    extra_slots: list[ExtraSlot] = field(default_factory=list)
    replaced_stages: dict[int, int] = field(default_factory=dict)


@dataclass
class Contribution:
    stage_id: int
    stage_name: str
    role_id: int
    role_label: str
    slot_key: str
    dataset_id: int
    dataset_name: str
    amount: float
    unit: str
    indicator_id: str
    value: float


@dataclass
class InventorySummary:
    flow_count: int = 0
    catalog_dataset_count: int = 0
    user_dataset_count: int = 0
    slot_count: int = 0


@dataclass
class InventoryLine:
    flow_id: str
    name: str
    compartment: str
    subcompartment: str
    unit: str
    stage_name: str
    role_label: str
    dataset_name: str
    value: float


@dataclass
class CalcResult:
    totals: dict[str, float]
    contributions: list[Contribution]
    blockers: list[str]
    mode: str = MODE_LCIA
    inventory_summary: InventorySummary = field(default_factory=InventorySummary)
    inventory_lines: list[InventoryLine] = field(default_factory=list)


@dataclass
class _SlotUse:
    stage: Stage
    role_id: int
    slot_key: str
    dataset: Dataset
    amount: float
    unit: str


def ordered_stages(chain: Chain) -> list[Stage]:
    stages = list(chain.stages)
    stages.sort(key=lambda item: item.sort_order)
    return stages


def terminal_stage(stages: list[Stage]) -> Stage | None:
    if not stages:
        return None
    terminals = [stage for stage in stages if stage.outgoing_stage_id is None]
    for stage in reversed(stages):
        if stage.outgoing_stage_id is None:
            return stage
    return terminals[-1] if terminals else stages[-1]


def walk_backward(stages: list[Stage]) -> list[Stage]:
    if not stages:
        return []
    incoming: dict[int | None, list[Stage]] = defaultdict(list)
    for stage in stages:
        incoming[stage.outgoing_stage_id].append(stage)
    start = terminal_stage(stages)
    if start is None:
        return []
    order: list[Stage] = []
    seen: set[int] = set()

    def visit(stage: Stage) -> None:
        if stage.id in seen:
            return
        seen.add(stage.id)
        order.append(stage)
        for prev in incoming.get(stage.id, []):
            visit(prev)

    visit(start)
    for stage in stages:
        if stage.id not in seen:
            order.append(stage)
    return order


def _slot_key(slot_id: int) -> str:
    return str(slot_id)


def _is_optional(slot) -> bool:  # type: ignore[no-untyped-def]
    return (not slot.required) or slot.optional_default_off


def _slot_active(slot, optional_on: set[int]) -> bool:  # type: ignore[no-untyped-def]
    if _is_optional(slot):
        return slot.id in optional_on
    return True


def _dataset_factors(dataset: Dataset) -> dict[str, float | None]:
    return {row.indicator_id: row.value for row in dataset.factors}


def _role_label(role: Role | None, role_id: int) -> str:
    return role.label if role else f"Kategorie {role_id}"


def _empty_result(blockers: list[str]) -> CalcResult:
    return CalcResult({}, [], blockers)


def calculate(
    chain: Chain,
    payload: CalcInput,
    datasets: dict[int, Dataset],
    roles: dict[int, Role],
    *,
    require_published: bool = True,
) -> CalcResult:
    blockers: list[str] = []
    if require_published and chain.status != "published":
        blockers.append("Die Kette ist nicht veröffentlicht.")
    if payload.end_amount is None or payload.end_amount <= 0:
        blockers.append("Bitte eine Endmenge größer als 0 eingeben.")

    stages = ordered_stages(chain)
    if not stages:
        blockers.append("Die Kette hat keine Stufen.")
        return _empty_result(blockers)

    skipped_stage_ids = _skipped_upstream(stages, payload.replaced_stages)

    extras_by_stage_role: dict[tuple[int, int], list[ExtraSlot]] = defaultdict(list)
    for extra in payload.extra_slots:
        extras_by_stage_role[(extra.stage_id, extra.role_id)].append(extra)

    optional_on = set(payload.optional_on)
    uses: list[_SlotUse] = []

    amounts: dict[int, float] = {}
    if payload.end_amount and payload.end_amount > 0:
        term = terminal_stage(stages)
        if term:
            amounts[term.id] = payload.end_amount
        for stage in walk_backward(stages):
            if stage.id in skipped_stage_ids:
                continue
            ausgang = amounts.get(stage.id)
            if ausgang is None:
                continue
            replaced_id = payload.replaced_stages.get(stage.id)
            if replaced_id:
                _collect_blackbox(uses, blockers, stage, ausgang, replaced_id, datasets)
                continue
            predecessors = [item for item in stages if item.outgoing_stage_id == stage.id]
            if predecessors:
                pred = predecessors[0]
                if pred.id not in skipped_stage_ids:
                    amounts[pred.id] = ausgang * (stage.upstream_amount or 1.0)

            grouped: dict[int, list] = defaultdict(list)
            for slot in stage.slots:
                grouped[slot.role_id].append(slot)

            for role_id, slots in grouped.items():
                extras = extras_by_stage_role.get((stage.id, role_id), [])
                active_slots = [slot for slot in slots if _slot_active(slot, optional_on)]
                if not active_slots and not extras:
                    if any(not _is_optional(slot) for slot in slots):
                        blockers.append(
                            f"Pflichtfeld fehlt: {_role_label(roles.get(role_id), role_id)} in {stage.name}."
                        )
                    continue

                specific = active_slots[0].specific_amount if active_slots else slots[0].specific_amount
                unit = active_slots[0].unit if active_slots else slots[0].unit
                members: list[tuple[str, int | None, float]] = []
                for slot in active_slots:
                    dataset_id = payload.selections.get(_slot_key(slot.id))
                    if dataset_id is None and slot.default_dataset_id:
                        dataset_id = slot.default_dataset_id
                    share = payload.shares.get(_slot_key(slot.id), slot.default_share)
                    members.append((_slot_key(slot.id), dataset_id, share))
                for extra in extras:
                    members.append((extra.key, extra.dataset_id, extra.share))

                if len(members) > 1:
                    share_sum = sum(item[2] for item in members)
                    if abs(share_sum - 1.0) > 1e-6 and abs(share_sum - 100.0) > 1e-6:
                        blockers.append(
                            f"Anteile für {_role_label(roles.get(role_id), role_id)} in {stage.name} müssen 100 % ergeben."
                        )
                    share_factor = 100.0 if share_sum > 2 else 1.0
                else:
                    share_factor = 1.0
                    members = [(members[0][0], members[0][1], 1.0)] if members else members

                for slot_key, dataset_id, share in members:
                    if dataset_id is None:
                        blockers.append(
                            f"Bitte einen Datensatz wählen ({_role_label(roles.get(role_id), role_id)}, {stage.name})."
                        )
                        continue
                    dataset = datasets.get(dataset_id)
                    if dataset is None:
                        blockers.append("Ein gewählter Datensatz ist nicht mehr verfügbar.")
                        continue
                    if dataset.source_kind == SOURCE_USER:
                        factors = _dataset_factors(dataset)
                        if factors.get(CLIMATE_CHANGE) is None:
                            blockers.append(f"Eigener Datensatz „{dataset.name}“ braucht mindestens CO₂e.")
                            continue
                    raw_share = share / share_factor if share_factor == 100.0 else share
                    if len(members) == 1:
                        raw_share = 1.0
                    menge = ausgang * specific * raw_share
                    uses.append(
                        _SlotUse(
                            stage=stage,
                            role_id=role_id,
                            slot_key=slot_key,
                            dataset=dataset,
                            amount=menge,
                            unit=unit,
                        )
                    )

    if blockers:
        return _empty_result(blockers)
    return _finish(uses, roles)


def _skipped_upstream(stages: list[Stage], replaced: dict[int, int]) -> set[int]:
    skipped: set[int] = set()
    by_outgoing: dict[int, list[Stage]] = defaultdict(list)
    for stage in stages:
        if stage.outgoing_stage_id:
            by_outgoing[stage.outgoing_stage_id].append(stage)

    def walk_prev(stage_id: int) -> None:
        for prev in by_outgoing.get(stage_id, []):
            skipped.add(prev.id)
            walk_prev(prev.id)

    for stage_id in replaced:
        walk_prev(stage_id)
    return skipped


def _collect_blackbox(
    uses: list[_SlotUse],
    blockers: list[str],
    stage: Stage,
    amount: float,
    dataset_id: int,
    datasets: dict[int, Dataset],
) -> None:
    dataset = datasets.get(dataset_id)
    if dataset is None:
        blockers.append(f"Ersatzdatensatz für Stufe „{stage.name}“ fehlt.")
        return
    if dataset.source_kind != SOURCE_USER:
        blockers.append("Eine Zwischenstufe darf nur durch einen eigenen Datensatz ersetzt werden.")
        return
    factors = _dataset_factors(dataset)
    if factors.get(CLIMATE_CHANGE) is None:
        blockers.append(f"Eigener Datensatz „{dataset.name}“ braucht mindestens CO₂e.")
        return
    role_id = dataset.roles[0].role_id if dataset.roles else 0
    uses.append(
        _SlotUse(
            stage=stage,
            role_id=role_id,
            slot_key=f"stage:{stage.id}",
            dataset=dataset,
            amount=amount,
            unit=dataset.unit,
        )
    )


def _finish(uses: list[_SlotUse], roles: dict[int, Role]) -> CalcResult:
    inventory_lines: list[InventoryLine] = []
    factor_uses: list[_SlotUse] = []
    catalog_ids: set[int] = set()
    user_ids: set[int] = set()

    for use in uses:
        if use.dataset.source_kind == SOURCE_USER:
            user_ids.add(use.dataset.id)
            factor_uses.append(use)
            continue
        catalog_ids.add(use.dataset.id)
        exchanges = list(use.dataset.exchanges)
        if exchanges:
            role_label = _role_label(roles.get(use.role_id), use.role_id)
            for exchange in exchanges:
                inventory_lines.append(
                    InventoryLine(
                        flow_id=exchange.flow_id,
                        name=exchange.name,
                        compartment=exchange.compartment,
                        subcompartment=exchange.subcompartment,
                        unit=exchange.unit,
                        stage_name=use.stage.name,
                        role_label=role_label,
                        dataset_name=use.dataset.name,
                        value=use.amount * exchange.amount,
                    )
                )
        elif any(row.value is not None for row in use.dataset.factors):
            factor_uses.append(use)
        else:
            return _empty_result(
                [f"Datensatz „{use.dataset.name}“ hat kein Inventar. Bitte neu importieren."]
            )

    inventory_totals: dict[str, float] = {}
    for line in inventory_lines:
        inventory_totals[line.flow_id] = inventory_totals.get(line.flow_id, 0.0) + line.value

    mapping = try_load_method()
    lcia_totals, matched = apply_lcia(inventory_totals, mapping) if mapping else ({}, False)

    factor_totals: dict[str, float] = {}
    factor_contributions: list[Contribution] = []
    for use in factor_uses:
        _add_factor_contributions(factor_contributions, factor_totals, use, roles)

    summary = InventorySummary(
        flow_count=len(inventory_totals),
        catalog_dataset_count=len(catalog_ids),
        user_dataset_count=len(user_ids),
        slot_count=len(uses),
    )

    if matched:
        totals = dict(lcia_totals)
        for indicator_id, value in factor_totals.items():
            totals[indicator_id] = totals.get(indicator_id, 0.0) + value
        contributions = _inventory_lcia_contributions(uses, roles, mapping or {}) + factor_contributions
        return CalcResult(
            totals=totals,
            contributions=contributions,
            blockers=[],
            mode=MODE_LCIA,
            inventory_summary=summary,
            inventory_lines=inventory_lines,
        )

    if inventory_lines:
        return CalcResult(
            totals={},
            contributions=_slot_quantity_contributions(uses, roles),
            blockers=[],
            mode=MODE_INVENTORY,
            inventory_summary=summary,
            inventory_lines=inventory_lines,
        )

    return CalcResult(
        totals=factor_totals,
        contributions=factor_contributions,
        blockers=[],
        mode=MODE_LCIA,
        inventory_summary=summary,
        inventory_lines=[],
    )


def _slot_quantity_contributions(uses: list[_SlotUse], roles: dict[int, Role]) -> list[Contribution]:
    rows: list[Contribution] = []
    for use in uses:
        rows.append(
            Contribution(
                stage_id=use.stage.id,
                stage_name=use.stage.name,
                role_id=use.role_id,
                role_label=_role_label(roles.get(use.role_id), use.role_id),
                slot_key=use.slot_key,
                dataset_id=use.dataset.id,
                dataset_name=use.dataset.name,
                amount=use.amount,
                unit=use.unit,
                indicator_id="",
                value=use.amount,
            )
        )
    return rows


def _inventory_lcia_contributions(
    uses: list[_SlotUse],
    roles: dict[int, Role],
    mapping: dict[str, dict[str, float]],
) -> list[Contribution]:
    rows: list[Contribution] = []
    for use in uses:
        if use.dataset.source_kind == SOURCE_USER or not use.dataset.exchanges:
            continue
        slot_totals: dict[str, float] = {}
        for exchange in use.dataset.exchanges:
            factors = mapping.get(exchange.flow_id)
            if not factors:
                continue
            scaled = use.amount * exchange.amount
            for indicator, factor in factors.items():
                slot_totals[indicator] = slot_totals.get(indicator, 0.0) + scaled * factor
        for indicator_id in INDICATOR_IDS:
            raw = slot_totals.get(indicator_id)
            if raw is None:
                continue
            rows.append(
                Contribution(
                    stage_id=use.stage.id,
                    stage_name=use.stage.name,
                    role_id=use.role_id,
                    role_label=_role_label(roles.get(use.role_id), use.role_id),
                    slot_key=use.slot_key,
                    dataset_id=use.dataset.id,
                    dataset_name=use.dataset.name,
                    amount=use.amount,
                    unit=use.unit,
                    indicator_id=indicator_id,
                    value=raw,
                )
            )
    return rows


def _add_factor_contributions(
    contributions: list[Contribution],
    totals: dict[str, float],
    use: _SlotUse,
    roles: dict[int, Role],
) -> None:
    factors = _dataset_factors(use.dataset)
    for indicator_id in INDICATOR_IDS:
        raw = factors.get(indicator_id)
        if raw is None:
            continue
        value = use.amount * raw
        totals[indicator_id] = totals.get(indicator_id, 0.0) + value
        contributions.append(
            Contribution(
                stage_id=use.stage.id,
                stage_name=use.stage.name,
                role_id=use.role_id,
                role_label=_role_label(roles.get(use.role_id), use.role_id),
                slot_key=use.slot_key,
                dataset_id=use.dataset.id,
                dataset_name=use.dataset.name,
                amount=use.amount,
                unit=use.unit,
                indicator_id=indicator_id,
                value=value,
            )
        )

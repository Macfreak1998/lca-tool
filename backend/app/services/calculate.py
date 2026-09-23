from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from app.constants import CLIMATE_CHANGE, INDICATOR_IDS, SOURCE_USER
from app.models import Chain, ChainEdge, ChainNode, Dataset, Role
from app.services.characterize import apply_lcia, try_load_method
from app.services.units import same_unit, unit_mismatch_message

MODE_LCIA = "lcia"
MODE_INVENTORY = "inventory"


@dataclass
class CalcInput:
    end_amount: float | None
    selections: dict[str, int] = field(default_factory=dict)
    shares: dict[str, float] = field(default_factory=dict)
    optional_on: list[int] = field(default_factory=list)
    replaced_nodes: dict[int, int] = field(default_factory=dict)


@dataclass
class Contribution:
    node_id: int
    node_name: str
    role_id: int
    role_label: str
    use_key: str
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
    node_name: str
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
class _Use:
    node_id: int
    node_name: str
    role_id: int
    role_label: str
    use_key: str
    dataset: Dataset
    amount: float
    unit: str


@dataclass
class _ProductLink:
    upstream_id: int
    downstream_id: int
    input_amount: float


def _role_label(role: Role | None, role_id: int, fallback: str = "") -> str:
    if role:
        return role.label
    if fallback:
        return fallback
    if role_id:
        return f"Kategorie {role_id}"
    return "Knoten"


def _empty_result(blockers: list[str]) -> CalcResult:
    return CalcResult({}, [], blockers)


def _dataset_factors(dataset: Dataset) -> dict[str, float | None]:
    return {row.indicator_id: row.value for row in dataset.factors}


def has_cycle(nodes: list[ChainNode], edges: list[ChainEdge]) -> bool:
    adjacency: dict[int, list[int]] = defaultdict(list)
    for edge in edges:
        adjacency[edge.source_id].append(edge.target_id)
    color = {node.id: 0 for node in nodes}

    def visit(node_id: int) -> bool:
        color[node_id] = 1
        for nxt in adjacency.get(node_id, []):
            state = color.get(nxt, 0)
            if state == 1 or (state == 0 and visit(nxt)):
                return True
        color[node_id] = 2
        return False

    return any(state == 0 and visit(node_id) for node_id, state in color.items())


def functional_node(nodes: list[ChainNode]) -> ChainNode | None:
    found = [node for node in nodes if node.is_functional]
    return found[0] if len(found) == 1 else None


def _flow_source(
    nodes: dict[int, ChainNode], incoming: dict[int, list[ChainEdge]], node_id: int
) -> ChainNode | None:
    node = nodes.get(node_id)
    if node is None or node.type != "transport":
        return node
    for hop in incoming.get(node_id, []):
        upstream = nodes.get(hop.source_id)
        if upstream and upstream.type in {"product", "process"}:
            return upstream
    return None


def product_links(nodes: dict[int, ChainNode], edges: list[ChainEdge]) -> list[_ProductLink]:
    incoming: dict[int, list[ChainEdge]] = defaultdict(list)
    for edge in edges:
        if edge.kind == "material":
            incoming[edge.target_id].append(edge)
    links: list[_ProductLink] = []
    for edge in edges:
        if edge.kind != "material":
            continue
        target = nodes.get(edge.target_id)
        if target is None or target.type not in {"product", "process"}:
            continue
        source = _flow_source(nodes, incoming, edge.source_id)
        if source is None or source.type not in {"product", "process"}:
            continue
        if source.type == "process" and target.type == "product":
            amount = 1.0
        elif source.type == "product" and target.type == "process":
            amount = edge.input_amount or 0.0
        elif source.type == "product" and target.type == "product":
            amount = edge.input_amount or 0.0
        else:
            continue
        links.append(_ProductLink(source.id, target.id, amount))
    return links


def _ancestors(edges: list[ChainEdge], start_id: int) -> set[int]:
    incoming: dict[int, list[int]] = defaultdict(list)
    for edge in edges:
        incoming[edge.target_id].append(edge.source_id)
    seen: set[int] = set()
    stack = list(incoming.get(start_id, []))
    while stack:
        node_id = stack.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        stack.extend(incoming.get(node_id, []))
    return seen


def waste_per_unit(amount: float) -> float:
    """Rest oberhalb einer Einheit Ziel. Einsatz 1,1 ergibt 0,1 Abfall."""
    return max(0.0, amount - 1.0)


def _waste_target(edges: list[ChainEdge], product_id: int) -> int | None:
    for edge in edges:
        if edge.kind == "waste" and edge.source_id == product_id:
            return edge.target_id
    return None


def share_key(category_id: int, dataset_id: int) -> str:
    return f"{category_id}:{dataset_id}"


def _normalize_share_map(pairs: list[tuple[int, float]]) -> tuple[dict[int, float], str | None]:
    if not pairs:
        return {}, "leer"
    if len(pairs) == 1:
        return {pairs[0][0]: 1.0}, None
    share_sum = sum(share for _dataset_id, share in pairs)
    if abs(share_sum - 1.0) > 1e-6 and abs(share_sum - 100.0) > 1e-6:
        return {}, "100 %"
    factor = 100.0 if share_sum > 2 else 1.0
    return {dataset_id: share / factor for dataset_id, share in pairs}, None


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

    nodes = list(chain.nodes)
    edges = list(chain.edges)
    combinations = list(chain.combinations)
    defaults = {
        (row.category_node_id, row.dataset_id): row.default_share for row in chain.dataset_shares
    }
    if not nodes:
        blockers.append("Die Kette hat keine Knoten.")
        return _empty_result(blockers)
    if has_cycle(nodes, edges):
        blockers.append("Die Kette enthält einen Zyklus.")
        return _empty_result(blockers)

    by_id = {node.id: node for node in nodes}
    end = functional_node(nodes)
    if end is None:
        blockers.append("Die Kette braucht genau ein Endprodukt.")
        return _empty_result(blockers)
    if payload.end_amount is None or payload.end_amount <= 0:
        return _empty_result(blockers)

    replaced = {
        node_id: dataset_id
        for node_id, dataset_id in payload.replaced_nodes.items()
        if node_id != end.id and node_id in by_id
    }
    skipped: set[int] = set()
    for node_id in replaced:
        skipped |= _ancestors(edges, node_id)

    amounts: dict[int, float] = {end.id: payload.end_amount}
    links = product_links(by_id, edges)
    upstreams: dict[int, list[_ProductLink]] = defaultdict(list)
    sched_in: dict[int, int] = defaultdict(int)
    sched_out: dict[int, list[int]] = defaultdict(list)
    involved: set[int] = {end.id}
    for link in links:
        upstreams[link.downstream_id].append(link)
        sched_out[link.downstream_id].append(link.upstream_id)
        sched_in[link.upstream_id] += 1
        involved.add(link.upstream_id)
        involved.add(link.downstream_id)

    queue = [node_id for node_id in involved if sched_in[node_id] == 0]
    while queue:
        node_id = queue.pop()
        if node_id not in skipped:
            demand = amounts.get(node_id)
            if demand is not None:
                for link in upstreams.get(node_id, []):
                    if link.upstream_id in skipped and link.upstream_id not in replaced:
                        continue
                    amounts[link.upstream_id] = (
                        amounts.get(link.upstream_id, 0.0) + demand * link.input_amount
                    )
        for nxt in sched_out.get(node_id, []):
            sched_in[nxt] -= 1
            if sched_in[nxt] == 0:
                queue.append(nxt)

    optional_on = set(payload.optional_on)
    uses: list[_Use] = []
    recovery_amounts: dict[int, float] = defaultdict(float)

    def add_use(
        node: ChainNode,
        dataset_id: int | None,
        amount: float,
        unit: str,
        use_key: str,
        role_id: int = 0,
        role_fallback: str = "",
    ) -> None:
        if amount <= 0:
            return
        if dataset_id is None:
            blockers.append(f"Bitte einen Datensatz wählen ({node.name}).")
            return
        dataset = datasets.get(dataset_id)
        if dataset is None:
            blockers.append("Ein gewählter Datensatz ist nicht mehr verfügbar.")
            return
        if dataset.source_kind == SOURCE_USER:
            factors = _dataset_factors(dataset)
            if factors.get(CLIMATE_CHANGE) is None:
                blockers.append(f"Eigener Datensatz „{dataset.name}“ braucht mindestens CO₂e.")
                return
        if node.type == "category" and not same_unit(dataset.unit, unit):
            message = unit_mismatch_message(dataset.name, dataset.unit, node.name, unit)
            if message not in blockers:
                blockers.append(message)
            return
        label = role_fallback or _role_label(roles.get(role_id), role_id)
        uses.append(
            _Use(
                node_id=node.id,
                node_name=node.name,
                role_id=role_id,
                role_label=label,
                use_key=use_key,
                dataset=dataset,
                amount=amount,
                unit=unit,
            )
        )

    for node_id, dataset_id in replaced.items():
        node = by_id[node_id]
        add_use(
            node,
            dataset_id,
            amounts.get(node_id, 0.0),
            node.unit or "kg",
            f"replace:{node_id}",
            role_fallback="Ersatz",
        )

    category_kind: dict[tuple[int, int], str] = {}
    incoming_categories: dict[int, list[ChainNode]] = defaultdict(list)
    for edge in edges:
        source = by_id.get(edge.source_id)
        target = by_id.get(edge.target_id)
        if source is None or target is None or edge.kind == "waste":
            continue
        if source.type == "category" and target.type == "process":
            category_kind[(target.id, source.id)] = edge.kind
            incoming_categories[target.id].append(source)

    def share_of(category_id: int, dataset_id: int) -> float:
        key = share_key(category_id, dataset_id)
        if key in payload.shares:
            return payload.shares[key]
        return defaults.get((category_id, dataset_id), 0.0)

    combos_by_process: dict[int, list] = defaultdict(list)
    for combo in combinations:
        combos_by_process[combo.process_node_id].append(combo)

    for process in nodes:
        if process.type != "process" or process.id in skipped:
            continue
        demand = amounts.get(process.id)
        if demand is None:
            continue
        categories = incoming_categories.get(process.id, [])
        active_categories = []
        for category in categories:
            if category.datasets_differ:
                active_categories.append(category)
                continue
            if category.optional and category.id not in optional_on:
                continue
            active_categories.append(category)
        process_combos = combos_by_process.get(process.id, [])
        if not process_combos and active_categories:
            blockers.append(f"Kombination fehlt für {process.name}.")
            continue
        share_maps: dict[int, dict[int, float]] = {}
        share_failed = False
        for category in active_categories:
            if category.datasets_differ:
                dataset_ids = sorted(
                    {
                        axis.dataset_id
                        for combo in process_combos
                        for axis in combo.axes
                        if axis.category_node_id == category.id and axis.dataset_id is not None
                    }
                )
            else:
                dataset_ids = sorted(
                    {
                        dataset_id
                        for (category_id, dataset_id) in defaults
                        if category_id == category.id
                    }
                    | {
                        int(key.split(":", 1)[1])
                        for key in payload.shares
                        if key.startswith(f"{category.id}:") and key.split(":", 1)[1].isdigit()
                    }
                )
            if not dataset_ids:
                if not category.optional:
                    blockers.append(f"Datensatz fehlt für {category.name}.")
                    share_failed = True
                continue
            scaled, share_error = _normalize_share_map(
                [(dataset_id, share_of(category.id, dataset_id)) for dataset_id in dataset_ids]
            )
            if share_error:
                blockers.append(f"Anteile für {category.name} müssen 100 % ergeben.")
                share_failed = True
                continue
            share_maps[category.id] = scaled
        if share_failed:
            continue
        for combo in process_combos:
            axis = {
                item.category_node_id: item.dataset_id
                for item in combo.axes
                if item.dataset_id is not None
            }
            weight = 1.0
            for category_id, dataset_id in axis.items():
                weight *= share_maps.get(category_id, {}).get(dataset_id, 0.0)
            if weight <= 1e-12:
                continue
            for amount in combo.amounts:
                category = by_id.get(amount.category_node_id)
                if category is None or category.id not in share_maps:
                    continue
                kind = category_kind.get((process.id, category.id), "material")
                unit = category.unit
                if category.datasets_differ:
                    portions = [(axis.get(category.id), 1.0)]
                else:
                    portions = list(share_maps[category.id].items())
                for dataset_id, portion in portions:
                    qty = demand * amount.input_amount * weight * portion
                    add_use(
                        category,
                        dataset_id,
                        qty,
                        unit,
                        f"combo:{combo.id}:{category.id}:{dataset_id}",
                        role_id=category.role_id or 0,
                    )
                if kind != "material":
                    continue
                waste_qty = demand * waste_per_unit(amount.input_amount) * weight
                if waste_qty <= 1e-12:
                    continue
                if amount.recovery_node_id is None:
                    blockers.append(f"Verwertung fehlt für Abfall an {process.name}.")
                else:
                    recovery_amounts[amount.recovery_node_id] += waste_qty

    for link in links:
        downstream = by_id.get(link.downstream_id)
        if downstream is None or downstream.id in replaced or downstream.id in skipped:
            continue
        demand = amounts.get(downstream.id)
        if demand is None:
            continue
        waste_qty = demand * waste_per_unit(link.input_amount)
        if waste_qty <= 1e-12:
            continue
        recovery_id = _waste_target(edges, downstream.id)
        if recovery_id is None:
            blockers.append(f"Verwertung fehlt für Abfall an {downstream.name}.")
        else:
            recovery_amounts[recovery_id] += waste_qty

    for node_id, qty in recovery_amounts.items():
        node = by_id.get(node_id)
        if node is None:
            continue
        add_use(
            node,
            node.dataset_id,
            qty,
            node.unit or "kg",
            f"recovery:{node.id}",
            role_fallback="Verwertung",
        )

    transport_mass: dict[int, float] = defaultdict(float)
    for edge in edges:
        if edge.kind != "material":
            continue
        source = by_id.get(edge.source_id)
        target = by_id.get(edge.target_id)
        if source is None or target is None:
            continue
        if source.type == "transport" and target.type in {"product", "process"} and target.id not in skipped:
            if source.optional and source.id not in optional_on:
                continue
            demand = amounts.get(target.id)
            if demand is None:
                continue
            transport_mass[source.id] += demand * (edge.input_amount or 0.0)

    for node_id, mass in transport_mass.items():
        node = by_id[node_id]
        distance = node.distance_km or 0.0
        add_use(
            node,
            node.dataset_id,
            mass * distance,
            node.unit or "kg·km",
            f"transport:{node.id}",
            role_fallback="Transport",
        )

    if blockers:
        return _empty_result(blockers)
    return _finish(uses, roles)


def _finish(uses: list[_Use], roles: dict[int, Role]) -> CalcResult:
    inventory_lines: list[InventoryLine] = []
    factor_uses: list[_Use] = []
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
            for exchange in exchanges:
                inventory_lines.append(
                    InventoryLine(
                        flow_id=exchange.flow_id,
                        name=exchange.name,
                        compartment=exchange.compartment,
                        subcompartment=exchange.subcompartment,
                        unit=exchange.unit,
                        node_name=use.node_name,
                        role_label=use.role_label or _role_label(roles.get(use.role_id), use.role_id),
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
            contributions=_quantity_contributions(uses, roles),
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


def _contribution(use: _Use, roles: dict[int, Role], indicator_id: str, value: float) -> Contribution:
    return Contribution(
        node_id=use.node_id,
        node_name=use.node_name,
        role_id=use.role_id,
        role_label=use.role_label or _role_label(roles.get(use.role_id), use.role_id),
        use_key=use.use_key,
        dataset_id=use.dataset.id,
        dataset_name=use.dataset.name,
        amount=use.amount,
        unit=use.unit,
        indicator_id=indicator_id,
        value=value,
    )


def _quantity_contributions(uses: list[_Use], roles: dict[int, Role]) -> list[Contribution]:
    return [_contribution(use, roles, "", use.amount) for use in uses]


def _inventory_lcia_contributions(
    uses: list[_Use],
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
            rows.append(_contribution(use, roles, indicator_id, raw))
    return rows


def _add_factor_contributions(
    contributions: list[Contribution],
    totals: dict[str, float],
    use: _Use,
    roles: dict[int, Role],
) -> None:
    factors = _dataset_factors(use.dataset)
    for indicator_id in INDICATOR_IDS:
        raw = factors.get(indicator_id)
        if raw is None:
            continue
        value = use.amount * raw
        totals[indicator_id] = totals.get(indicator_id, 0.0) + value
        contributions.append(_contribution(use, roles, indicator_id, value))

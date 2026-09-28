from __future__ import annotations

from collections import defaultdict
from itertools import product as cartesian

from sqlalchemy.orm import Session, selectinload

from app.models import Chain, Configuration, Dataset, Role
from app.services.calculate import (
    CalcInput,
    allocation_factor,
    calculate,
    has_cycle,
    material_waste,
    process_recovery_ids,
    share_key,
)
from app.services.units import same_unit, unit_mismatch_message


def invalidate_configurations(db: Session, chain_id: int, reason: str) -> None:
    rows = db.query(Configuration).filter(Configuration.chain_id == chain_id).all()
    for row in rows:
        row.invalid = True
        row.invalid_reason = reason
    db.commit()


def _shares_ok(values: list[float]) -> bool:
    if len(values) < 2:
        return True
    share_sum = sum(values)
    return abs(share_sum - 1.0) <= 1e-6 or abs(share_sum - 100.0) <= 1e-6


def validate_structure(chain: Chain) -> list[str]:
    errors: list[str] = []
    nodes = list(chain.nodes)
    edges = list(chain.edges)
    combinations = list(chain.combinations)
    if not nodes:
        errors.append("Mindestens ein Knoten ist nötig.")
        return errors
    functional = [node for node in nodes if node.is_functional]
    if len(functional) != 1:
        errors.append("Die Kette braucht genau ein Endprodukt.")
    if has_cycle(nodes, edges):
        errors.append("Die Kette enthält einen Zyklus.")

    by_id = {node.id: node for node in nodes}
    kind_of: dict[tuple[int, int], str] = {}
    incoming: dict[int, list] = defaultdict(list)
    produced_by: dict[int, list] = defaultdict(list)

    for edge in edges:
        source = by_id.get(edge.source_id)
        target = by_id.get(edge.target_id)
        if source is None or target is None:
            errors.append("Eine Kante verweist auf einen fehlenden Knoten.")
            continue
        if edge.input_amount < 0:
            errors.append(f"Menge der Kante nach „{target.name}“ darf nicht negativ sein.")
        if edge.efficiency <= 0:
            errors.append(f"Effizienz der Kante nach „{target.name}“ muss größer als 0 sein.")
        if edge.kind == "waste":
            continue
        if source.type == "category" and target.type == "process":
            kind_of[(target.id, source.id)] = edge.kind
            incoming[target.id].append(source)
        if source.type == "process" and target.type == "category" and edge.kind == "energy":
            kind_of[(source.id, target.id)] = "credit"
            incoming[source.id].append(target)
        if source.type == "transport" and target.type == "process" and edge.kind == "material":
            origin = _transport_origin(by_id, edges, source.id)
            if origin is not None and origin.type == "category":
                kind_of[(target.id, origin.id)] = "material"
                incoming[target.id].append(origin)
        if edge.kind == "material" and source.type == "process" and target.type == "product":
            produced_by[target.id].append(source)

    for process in nodes:
        if process.type != "process":
            continue
        outs = [
            edge
            for edge in edges
            if edge.source_id == process.id
            and edge.kind == "material"
            and by_id.get(edge.target_id) is not None
            and by_id[edge.target_id].type == "product"
        ]
        if not outs:
            errors.append(f"Prozess „{process.name}“ braucht ein Folgeprodukt.")
        elif functional:
            _factor, share_error = allocation_factor(process.id, by_id, edges, functional[0].id)
            if share_error:
                errors.append(share_error)

    for product_id, producers in produced_by.items():
        if len(producers) > 1:
            errors.append(f"„{by_id[product_id].name}“ darf nur einen Prozess haben.")

    shares_by_category: dict[int, list] = defaultdict(list)
    for share in chain.dataset_shares:
        shares_by_category[share.category_node_id].append(share)

    for process in nodes:
        if process.type != "process":
            continue
        categories = incoming.get(process.id, [])
        differing = [node for node in categories if node.datasets_differ]
        combos = [item for item in combinations if item.process_node_id == process.id]
        axis_sets: list[list[tuple[int, int]]] = []
        missing_axis = False
        for category in differing:
            dataset_ids = sorted(
                {
                    axis.dataset_id
                    for combo in combos
                    for axis in combo.axes
                    if axis.category_node_id == category.id and axis.dataset_id is not None
                }
            )
            if not dataset_ids:
                errors.append(f"Datensätze fehlen für „{category.name}“.")
                missing_axis = True
                continue
            axis_sets.append([(category.id, dataset_id) for dataset_id in dataset_ids])
            if len(dataset_ids) > 1:
                rows = [
                    share
                    for share in shares_by_category[category.id]
                    if share.dataset_id in dataset_ids
                ]
                if len(rows) != len(dataset_ids) or not _shares_ok([share.default_share for share in rows]):
                    errors.append(f"Default-Anteile für „{category.name}“ müssen 100 % ergeben.")
        if not missing_axis and differing:
            expected = {frozenset(choice) for choice in cartesian(*axis_sets)}
            stored = [
                frozenset(
                    (axis.category_node_id, axis.dataset_id)
                    for axis in combo.axes
                    if axis.dataset_id is not None
                )
                for combo in combos
            ]
            if set(stored) != expected or len(stored) != len(expected):
                errors.append(f"Kombination fehlt für „{process.name}“.")
        elif not differing and categories and not any(not combo.axes for combo in combos):
            errors.append(f"Kombination fehlt für „{process.name}“.")

        required = [node for node in categories if node.datasets_differ or not node.optional]
        for combo in combos:
            present = {amount.category_node_id for amount in combo.amounts}
            for category in required:
                if category.id not in present:
                    errors.append(f"Menge fehlt für „{category.name}“ an „{process.name}“.")
            for amount in combo.amounts:
                if amount.input_amount < 0:
                    errors.append(f"Mengen an „{process.name}“ dürfen nicht negativ sein.")
                kind = kind_of.get((process.id, amount.category_node_id), "material")
                if kind == "material" and amount.efficiency <= 0:
                    errors.append(f"Effizienz an „{process.name}“ muss größer als 0 sein.")
        has_waste = any(
            kind_of.get((process.id, amount.category_node_id), "material") == "material"
            and material_waste(amount.input_amount, amount.efficiency) > 1e-12
            for combo in combos
            for amount in combo.amounts
        ) or any(
            edge.kind == "material"
            and edge.target_id == process.id
            and by_id.get(edge.source_id) is not None
            and by_id[edge.source_id].type in {"product", "transport"}
            and material_waste(edge.input_amount, edge.efficiency) > 1e-12
            for edge in edges
        )
        recovery_ids = process_recovery_ids(process.id, by_id, edges, combinations)
        if len(recovery_ids) > 1:
            errors.append(f"Prozess „{process.name}“ hat nur eine Verwertung.")
        elif has_waste and not recovery_ids:
            errors.append(f"Verwertung fehlt für Abfall an „{process.name}“.")

        for category in categories:
            if category.datasets_differ or category.optional:
                continue
            rows = shares_by_category[category.id]
            if not rows:
                errors.append(f"Anteile fehlen für „{category.name}“.")
            elif not _shares_ok([share.default_share for share in rows]):
                errors.append(f"Default-Anteile für „{category.name}“ müssen 100 % ergeben.")

    for node in nodes:
        if node.type == "transport":
            errors.extend(_transport_errors(node, edges, by_id))
        if node.type == "transport" and not node.optional:
            if node.dataset_id is None:
                errors.append(f"Datensatz fehlt für Transport „{node.name}“.")
            if not node.distance_km or node.distance_km <= 0:
                errors.append(f"Distanz fehlt für Transport „{node.name}“.")
        if node.type == "recovery" and any(
            edge.kind == "energy" and node.id in {edge.source_id, edge.target_id} for edge in edges
        ):
            errors.append(f"Verwertung „{node.name}“ hat keine Energiekante.")
        if node.type == "recovery" and node.dataset_id is None:
            referenced = any(
                amount.recovery_node_id == node.id
                for combo in combinations
                for amount in combo.amounts
            ) or any(edge.kind == "waste" and edge.target_id == node.id for edge in edges)
            if referenced:
                errors.append(f"Datensatz fehlt für Verwertung „{node.name}“.")
        elif node.type == "recovery" and node.dataset is not None:
            referenced = any(
                amount.recovery_node_id == node.id
                for combo in combinations
                for amount in combo.amounts
            ) or any(edge.kind == "waste" and edge.target_id == node.id for edge in edges)
            dataset = node.dataset
            has_inventory = bool(dataset.exchanges) or any(row.value is not None for row in dataset.factors)
            if referenced and not has_inventory:
                errors.append(f"Datensatz der Verwertung „{node.name}“ hat kein Inventar.")
        if node.type == "category" and node.role_id is None:
            errors.append(f"Kategorie fehlt am Knoten „{node.name}“.")
        if node.type == "category" and node.datasets_differ and node.optional:
            errors.append(f"„{node.name}“ ist ungleich und darf nicht optional sein.")

    errors.extend(_category_unit_errors(chain))
    return errors


def _transport_origin(nodes: dict[int, object], edges: list, transport_id: int):
    for edge in edges:
        if edge.kind == "material" and edge.target_id == transport_id:
            return nodes.get(edge.source_id)
    return None


def _transport_errors(node, edges: list, nodes: dict[int, object]) -> list[str]:
    incoming = [edge for edge in edges if edge.target_id == node.id]
    outgoing = [edge for edge in edges if edge.source_id == node.id]
    if len(incoming) != 1 or len(outgoing) != 1:
        return [f"Transport „{node.name}“ braucht genau eine Kante hinein und hinaus."]
    arrived = incoming[0]
    left = outgoing[0]
    if arrived.kind == "energy" or left.kind == "energy" or arrived.kind != left.kind:
        return [f"Energie läuft nicht über Transport „{node.name}“."]
    source = nodes.get(arrived.source_id)
    target = nodes.get(left.target_id)
    if source is None or target is None:
        return [f"Transport „{node.name}“ steht an einer ungültigen Stelle."]
    material_forward = (
        arrived.kind == "material"
        and target.type == "process"
        and (source.type == "product" or source.type == "category")
    )
    waste_forward = (
        arrived.kind == "waste" and source.type == "process" and target.type == "recovery"
    )
    if material_forward or waste_forward:
        return []
    return [f"Transport „{node.name}“ steht an einer ungültigen Stelle."]


def _category_unit_errors(chain: Chain) -> list[str]:
    by_id = {node.id: node for node in chain.nodes}
    seen: set[tuple[int, int]] = set()
    errors: list[str] = []
    pairs: list[tuple[int, Dataset | None]] = []
    for share in chain.dataset_shares:
        pairs.append((share.category_node_id, share.dataset))
    for combo in chain.combinations:
        for axis in combo.axes:
            if axis.dataset_id is None:
                continue
            pairs.append((axis.category_node_id, axis.dataset))
    for category_id, dataset in pairs:
        if dataset is None:
            continue
        key = (category_id, dataset.id)
        if key in seen:
            continue
        seen.add(key)
        category = by_id.get(category_id)
        if category is None or category.type != "category":
            continue
        if same_unit(dataset.unit, category.unit):
            continue
        errors.append(unit_mismatch_message(dataset.name, dataset.unit, category.name, category.unit))
    return errors


def probe_and_publish(db: Session, chain: Chain) -> tuple[bool, list[str]]:
    errors = validate_structure(chain)
    if errors:
        return False, errors
    datasets = {
        item.id: item
        for item in db.query(Dataset)
        .options(
            selectinload(Dataset.factors),
            selectinload(Dataset.roles),
            selectinload(Dataset.exchanges),
        )
        .all()
    }
    roles = {item.id: item for item in db.query(Role).all()}
    selections: dict[str, int] = {}
    shares: dict[str, float] = {}
    for node in chain.nodes:
        if node.dataset_id:
            selections[str(node.id)] = node.dataset_id
    for share in chain.dataset_shares:
        shares[share_key(share.category_node_id, share.dataset_id)] = share.default_share
    result = calculate(
        chain,
        CalcInput(end_amount=1.0, selections=selections, shares=shares, optional_on=[]),
        datasets,
        roles,
        require_published=False,
    )
    if result.blockers:
        return False, result.blockers
    chain.status = "published"
    db.commit()
    return True, []

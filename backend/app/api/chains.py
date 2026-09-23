from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import selectinload

from app.constants import CHAIN_DRAFT, CHAIN_PUBLISHED
from app.deps import AdminUser, CurrentUser, DbDep
from app.models import (
    Chain,
    ChainCombination,
    ChainCombinationAmount,
    ChainCombinationAxis,
    ChainDatasetShare,
    ChainEdge,
    ChainNode,
    Dataset,
    EndProduct,
)
from app.schemas import ChainCreateIn, ChainOut, ChainUpdateIn
from app.serialize import chain_out
from app.services.publish import invalidate_configurations, probe_and_publish, validate_structure
from app.services.units import resolve_category_unit

router = APIRouter()

_NODE_TYPES = {"category", "product", "process", "transport", "recovery"}
_EDGE_KINDS = {"material", "energy", "waste"}

_LOAD = (
    selectinload(Chain.end_product),
    selectinload(Chain.nodes),
    selectinload(Chain.edges),
    selectinload(Chain.combinations).selectinload(ChainCombination.axes),
    selectinload(Chain.combinations).selectinload(ChainCombination.amounts),
    selectinload(Chain.dataset_shares),
)


def _load_chain(db, chain_id: int) -> Chain:
    chain = db.query(Chain).options(*_LOAD).filter(Chain.id == chain_id).first()
    if chain is None:
        raise HTTPException(status_code=404, detail="Kette nicht gefunden.")
    return chain


def _apply_graph(db, chain: Chain, payload: ChainUpdateIn) -> None:
    if payload.nodes is None:
        return
    existing = {node.id: node for node in chain.nodes}
    original_functional_id = next((node.id for node in chain.nodes if node.is_functional), None)
    key_to_node: dict[str, ChainNode] = {}
    keep: set[int] = set()
    functional_ids: list[int] = []
    for item in payload.nodes:
        if item.type not in _NODE_TYPES:
            raise HTTPException(status_code=400, detail=f"Unbekannter Knotentyp „{item.type}“.")
        node = existing.get(item.id) if item.id else None
        if node is None:
            node = ChainNode(chain=chain)
            db.add(node)
        node.type = item.type
        node.name = item.name.strip() or "Knoten"
        node.position_x = item.position_x
        node.position_y = item.position_y
        node.role_id = item.role_id
        node.dataset_id = item.dataset_id
        node.unit = item.unit
        node.distance_km = item.distance_km
        node.optional = item.optional and not item.datasets_differ
        node.is_functional = item.is_functional
        node.datasets_differ = item.datasets_differ if item.type == "category" else False
        db.flush()
        key_to_node[item.client_key] = node
        keep.add(node.id)
        if item.is_functional:
            functional_ids.append(node.id)
    if len(functional_ids) != 1:
        raise HTTPException(status_code=400, detail="Die Kette braucht genau ein Endprodukt.")
    if original_functional_id is not None and original_functional_id not in functional_ids:
        raise HTTPException(status_code=400, detail="Das Endprodukt darf nicht entfernt werden.")
    for edge in list(chain.edges):
        db.delete(edge)
    for combo in list(chain.combinations):
        db.delete(combo)
    for share in list(chain.dataset_shares):
        db.delete(share)
    db.flush()
    for node in list(chain.nodes):
        if node.id not in keep:
            if node.is_functional:
                raise HTTPException(status_code=400, detail="Das Endprodukt darf nicht entfernt werden.")
            db.delete(node)
    db.flush()

    edges = payload.edges or []
    for item in edges:
        if item.kind not in _EDGE_KINDS:
            raise HTTPException(status_code=400, detail=f"Unbekannte Kantenart „{item.kind}“.")
        source = key_to_node.get(item.source_key)
        target = key_to_node.get(item.target_key)
        if source is None or target is None:
            raise HTTPException(status_code=400, detail="Eine Kante verweist auf einen fehlenden Knoten.")
        db.add(
            ChainEdge(
                chain=chain,
                source_id=source.id,
                target_id=target.id,
                kind=item.kind,
                input_amount=item.input_amount,
                efficiency=item.efficiency,
            )
        )
    for item in payload.combinations or []:
        process = key_to_node.get(item.process_key)
        if process is None or process.type != "process":
            raise HTTPException(status_code=400, detail="Eine Kombination verweist auf einen fehlenden Prozess.")
        combo = ChainCombination(chain=chain, process_node_id=process.id)
        db.add(combo)
        db.flush()
        for axis in item.axes:
            category = key_to_node.get(axis.category_key)
            if category is None:
                raise HTTPException(status_code=400, detail="Eine Kombination verweist auf eine fehlende Kategorie.")
            db.add(
                ChainCombinationAxis(
                    combination=combo,
                    category_node_id=category.id,
                    dataset_id=axis.dataset_id,
                )
            )
        for amount in item.amounts:
            category = key_to_node.get(amount.category_key)
            if category is None:
                raise HTTPException(status_code=400, detail="Eine Menge verweist auf eine fehlende Kategorie.")
            recovery = key_to_node.get(amount.recovery_key) if amount.recovery_key else None
            db.add(
                ChainCombinationAmount(
                    combination=combo,
                    category_node_id=category.id,
                    input_amount=amount.input_amount,
                    recovery_node_id=recovery.id if recovery else None,
                )
            )
    for item in payload.dataset_shares or []:
        category = key_to_node.get(item.category_key)
        if category is None:
            raise HTTPException(status_code=400, detail="Ein Anteil verweist auf eine fehlende Kategorie.")
        db.add(
            ChainDatasetShare(
                chain=chain,
                category_node_id=category.id,
                dataset_id=item.dataset_id,
                default_share=item.default_share,
            )
        )
    _assign_category_units(db, key_to_node, payload)
    db.flush()


def _assign_category_units(db, key_to_node: dict[str, ChainNode], payload: ChainUpdateIn) -> None:
    ordered: dict[str, list[int]] = defaultdict(list)
    seen: dict[str, set[int]] = defaultdict(set)

    def add(category_key: str, dataset_id: int | None) -> None:
        if dataset_id is None or dataset_id in seen[category_key]:
            return
        seen[category_key].add(dataset_id)
        ordered[category_key].append(dataset_id)

    for item in payload.dataset_shares or []:
        add(item.category_key, item.dataset_id)
    for combo in payload.combinations or []:
        for axis in combo.axes:
            add(axis.category_key, axis.dataset_id)

    energy_keys: set[str] = set()
    for edge in payload.edges or []:
        if edge.kind != "energy":
            continue
        source = key_to_node.get(edge.source_key)
        if source is not None and source.type == "category":
            energy_keys.add(edge.source_key)

    ids = {dataset_id for values in ordered.values() for dataset_id in values}
    by_id = {row.id: row for row in db.query(Dataset).filter(Dataset.id.in_(ids)).all()} if ids else {}
    for key, node in key_to_node.items():
        if node.type != "category":
            continue
        units = [by_id[dataset_id].unit for dataset_id in ordered.get(key, []) if dataset_id in by_id]
        node.unit = resolve_category_unit(node.unit, units, energy=key in energy_keys)


@router.get("", response_model=list[ChainOut])
def list_chains(user: CurrentUser, db: DbDep) -> list[ChainOut]:
    query = db.query(Chain).options(*_LOAD)
    if user.role != "admin":
        query = query.filter(Chain.status == CHAIN_PUBLISHED)
    return [chain_out(item) for item in query.order_by(Chain.name).all()]


@router.post("", response_model=ChainOut)
def create_chain(payload: ChainCreateIn, _admin: AdminUser, db: DbDep) -> ChainOut:
    end_product = db.get(EndProduct, payload.end_product_id)
    if end_product is None:
        raise HTTPException(status_code=400, detail="Endprodukt nicht gefunden.")
    chain = Chain(
        name=payload.name.strip(),
        status=CHAIN_DRAFT,
        end_product_id=end_product.id,
        end_unit=end_product.unit,
    )
    db.add(chain)
    db.flush()
    db.add(
        ChainNode(
            chain=chain,
            type="product",
            name=end_product.name,
            unit=end_product.unit,
            is_functional=True,
            position_x=480,
            position_y=180,
        )
    )
    db.commit()
    return chain_out(_load_chain(db, chain.id))


@router.get("/{chain_id}", response_model=ChainOut)
def get_chain(chain_id: int, user: CurrentUser, db: DbDep) -> ChainOut:
    chain = _load_chain(db, chain_id)
    if user.role != "admin" and chain.status != CHAIN_PUBLISHED:
        raise HTTPException(status_code=404, detail="Kette nicht gefunden.")
    return chain_out(chain)


@router.patch("/{chain_id}", response_model=ChainOut)
def update_chain(chain_id: int, payload: ChainUpdateIn, _admin: AdminUser, db: DbDep) -> ChainOut:
    chain = _load_chain(db, chain_id)
    if payload.name is not None:
        chain.name = payload.name.strip()
    if payload.status == CHAIN_DRAFT and chain.status == CHAIN_PUBLISHED:
        chain.status = CHAIN_DRAFT
        invalidate_configurations(db, chain.id, "Die Kette wurde zurückgezogen.")
    if payload.nodes is not None:
        _apply_graph(db, chain, payload)
        if chain.status == CHAIN_PUBLISHED:
            chain.status = CHAIN_DRAFT
            invalidate_configurations(db, chain.id, "Die Kettenstruktur hat sich geändert.")
    db.commit()
    return chain_out(_load_chain(db, chain.id))


@router.post("/{chain_id}/publish", response_model=ChainOut)
def publish_chain(chain_id: int, _admin: AdminUser, db: DbDep) -> ChainOut:
    chain = _load_chain(db, chain_id)
    ok, errors = probe_and_publish(db, chain)
    if not ok:
        raise HTTPException(status_code=400, detail=errors)
    return chain_out(_load_chain(db, chain.id))


@router.post("/{chain_id}/unpublish", response_model=ChainOut)
def unpublish_chain(chain_id: int, _admin: AdminUser, db: DbDep) -> ChainOut:
    chain = _load_chain(db, chain_id)
    chain.status = CHAIN_DRAFT
    invalidate_configurations(db, chain.id, "Die Kette wurde zurückgezogen.")
    db.commit()
    return chain_out(_load_chain(db, chain.id))


@router.get("/{chain_id}/validate")
def validate_chain(chain_id: int, _admin: AdminUser, db: DbDep) -> dict:
    chain = _load_chain(db, chain_id)
    return {"errors": validate_structure(chain)}

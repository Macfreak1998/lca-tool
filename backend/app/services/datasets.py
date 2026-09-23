from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    ChainCombination,
    ChainCombinationAxis,
    ChainDatasetShare,
    ChainNode,
    Configuration,
    ConfigurationReplacedNode,
    ConfigurationSelection,
)


def invalidate_using(db: Session, dataset_id: int, reason: str) -> None:
    ids: set[int] = set()
    for item in db.query(ConfigurationSelection.configuration_id).filter(
        ConfigurationSelection.dataset_id == dataset_id
    ):
        ids.add(item[0])
    for item in db.query(ConfigurationReplacedNode.configuration_id).filter(
        ConfigurationReplacedNode.dataset_id == dataset_id
    ):
        ids.add(item[0])
    chain_ids: set[int] = set()
    for item in (
        db.query(ChainDatasetShare.chain_id).filter(ChainDatasetShare.dataset_id == dataset_id)
    ):
        chain_ids.add(item[0])
    for item in (
        db.query(ChainCombination.chain_id)
        .join(ChainCombinationAxis, ChainCombinationAxis.combination_id == ChainCombination.id)
        .filter(ChainCombinationAxis.dataset_id == dataset_id)
    ):
        chain_ids.add(item[0])
    for item in db.query(ChainNode.chain_id).filter(ChainNode.dataset_id == dataset_id):
        chain_ids.add(item[0])
    if chain_ids:
        for item in db.query(Configuration.id).filter(Configuration.chain_id.in_(chain_ids)):
            ids.add(item[0])
    if ids:
        db.query(Configuration).filter(Configuration.id.in_(ids)).update(
            {"invalid": True, "invalid_reason": reason},
            synchronize_session=False,
        )


def detach_dataset_references(db: Session, dataset_id: int) -> None:
    db.query(ChainNode).filter(ChainNode.dataset_id == dataset_id).update(
        {"dataset_id": None},
        synchronize_session=False,
    )
    db.query(ChainCombinationAxis).filter(ChainCombinationAxis.dataset_id == dataset_id).update(
        {"dataset_id": None},
        synchronize_session=False,
    )
    db.query(ChainDatasetShare).filter(ChainDatasetShare.dataset_id == dataset_id).delete(
        synchronize_session=False
    )
    db.query(ConfigurationSelection).filter(ConfigurationSelection.dataset_id == dataset_id).delete(
        synchronize_session=False
    )
    db.query(ConfigurationReplacedNode).filter(
        ConfigurationReplacedNode.dataset_id == dataset_id
    ).delete(synchronize_session=False)


def prepare_dataset_delete(db: Session, dataset_id: int, reason: str) -> None:
    invalidate_using(db, dataset_id, reason)
    detach_dataset_references(db, dataset_id)

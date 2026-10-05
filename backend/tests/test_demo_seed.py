from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
from app.constants import CLIMATE_CHANGE
from app.models import Chain, Dataset, Role
from app.services.calculate import CalcInput, calculate, category_dataset_options
from app.services.demo import EXAMPLE_CHAIN_NAME, seed_demo


def test_seed_demo_creates_published_chain(db, fixtures_dir: Path, tmp_path: Path, monkeypatch):
    archive = tmp_path / "demo-archive"
    (archive / "datasets").mkdir(parents=True)
    (archive / "FilenameToActivityLookup.csv").write_text(
        "Filename,ActivityName,Location,ReferenceProduct\n"
        "aaa-111_bbb-222.spold,market for maize starch,DE,maize starch\n",
        encoding="utf-8",
    )
    (archive / "datasets" / "aaa-111_bbb-222.spold").write_text(
        (fixtures_dir / "sample.spold").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "demo_seed", True)
    monkeypatch.setattr(settings, "archive_path", str(archive))
    seed_demo(db)
    maize = db.query(Chain).filter(Chain.name == "Demo: Maisstärke → Folie").one()
    example = db.query(Chain).filter(Chain.name == EXAMPLE_CHAIN_NAME).one()
    assert maize.status == "published"
    assert example.status == "published"
    assert db.query(Dataset).count() == 12
    seed_demo(db)
    assert db.query(Chain).count() == 2
    assert db.query(Dataset).count() == 12


def test_example_chain_seeds_without_archive(db, monkeypatch):
    monkeypatch.setattr(settings, "demo_seed", True)
    monkeypatch.setattr(settings, "archive_path", "")
    seed_demo(db)
    chain = db.query(Chain).filter(Chain.name == EXAMPLE_CHAIN_NAME).one()
    assert chain.status == "published"
    datasets = {item.id: item for item in db.query(Dataset).all()}
    roles = {item.id: item for item in db.query(Role).all()}
    result = calculate(chain, CalcInput(end_amount=1.0), datasets, roles)
    assert result.blockers == []
    assert result.totals[CLIMATE_CHANGE] == pytest.approx(2.209803921568627)

    def option_names(node_name: str) -> list[str]:
        node = next(item for item in chain.nodes if item.name == node_name)
        return [item.name for item in category_dataset_options(node, datasets, list(chain.combinations))]

    assert option_names("Kartoffelstärke") == ["Kartoffelstärke", "Maisstärke", "Weizenstärke"]
    assert option_names("Additiv") == ["Additiv", "Füllstoff", "Weichmacher"]
    assert option_names("Strom Spritzguss") == ["Strom", "Strommix EU", "Ökostrom"]
    assert option_names("Strom Granulieren") == ["Strom", "Strommix EU", "Ökostrom"]
    seed_demo(db)
    assert db.query(Chain).filter(Chain.name == EXAMPLE_CHAIN_NAME).count() == 1
    assert db.query(Dataset).count() == 11


def test_seed_demo_off_by_default(db, monkeypatch):
    monkeypatch.setattr(settings, "demo_seed", False)
    seed_demo(db)
    assert db.query(Chain).count() == 0
